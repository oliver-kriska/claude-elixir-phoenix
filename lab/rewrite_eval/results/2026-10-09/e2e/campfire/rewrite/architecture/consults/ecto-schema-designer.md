# Consult: Ecto Schema Designer — Campfire data layer under ADR-000

**Scope**: answers only (no plan, no implementation). **Bar**: ADR-000 (ASSUMED) — schema as-is, in-place SQLite,
pinned Rails image must boot on a port-written DB, additive-only DDL.
**Evidence read**: ADR-000, contracts.md (C-01..C-17, C-55, Data Schema Notes, Questions), mechanisms.md (M-01..M-03,
M-13, M-14, M-28, M-54, Q10), features.md (F-07, F-09, F-16, T-08, T-10), kb/data-compat.md, kb/sqlite-on-beam.md,
kb/stacks/rails.md; SOURCE `db/schema.rb`, all 15 `db/migrate/*`, `config/database.yml`, `app/models/**`.
**Library source checked** (hex cache, not run): ecto_sqlite3 0.25.0 (`codec.ex`, `sqlite3.ex`, `connection.ex`),
ecto_sql 3.14.0 (`migration/schema_migration.ex`), oban 2.24.1 (`engines/lite.ex`).
**Ash**: not applicable (no Ash in the rewrite workspace).

`lib/rails_ext/active_record_has_json.rb` is gone: commit `42c411b "Use upstream version of has_json"` moved to
Rails 8.2.0.alpha's built-in `has_json` (Gemfile.lock pins rails main @ `1a02651a`). `account.rb:9` still declares
`has_json :settings, restrict_room_creation_to_administrators: false`.

---

## Answers

### Q1. Ecto type mapping

#### Timestamps — the headline finding: no built-in ecto_sqlite3 option reproduces the Rails format

Verified in ecto_sqlite3 0.25.0 `codec.ex:117-143`:

| `config :ecto_sqlite3, datetime_type:` | What `:utc_datetime_usec` writes | Compatible with Rails text ordering? |
|---|---|---|
| `:iso8601` (default) | `2025-12-12T15:43:40.123456Z` | **No.** `T` (0x54) sorts after ` ` (0x20), so every port row on a given date sorts after every Rails row on that date. The trailing `Z` also breaks equality |
| `:text_datetime` | `Calendar.strftime(v, "%Y-%m-%d %H:%M:%S")` → `2025-12-12 15:43:40` | **No.** It **drops the microseconds**. Ordering within a second breaks: 40 messages in one second all tie, so `created_at < ?` pagination skips rows (this makes T-08 worse) |

`kb/data-compat.md` and `kb/sqlite-on-beam.md` both recommend `datetime_type: :text_datetime`. **That advice is wrong for
C-02 and needs correcting**: it loses precision and does not match Rails.

What Rails writes: Rails' `quoted_date` gives `YYYY-MM-DD HH:MM:SS` and appends `.%06d` **only when `usec > 0`**
(this is from my memory of ActiveRecord `Quoting#quoted_date`; confirm it on the pinned image). So C-02 as written
("always `.ffffff`") is probably slightly off: a row with a whole-second time has no fractional part. Mixed forms
still order correctly as text, because a string that is a prefix of another sorts before it.

**Mapping: a custom Ecto type**, `Campfire.Types.RailsTime`, used for every datetime column in legacy tables:

```elixir
defmodule Campfire.Types.RailsTime do
  use Ecto.Type
  def type, do: :string                      # adapter passes strings through untouched
  def cast(%DateTime{} = dt), do: {:ok, DateTime.truncate(DateTime.shift_zone!(dt, "Etc/UTC"), :microsecond)}
  def cast(%NaiveDateTime{} = n), do: {:ok, DateTime.from_naive!(n, "Etc/UTC") |> DateTime.truncate(:microsecond)}
  def cast(s) when is_binary(s), do: load(s)
  def cast(_), do: :error
  # Accepts Rails "YYYY-MM-DD HH:MM:SS[.ffffff]" and, defensively, ISO8601 "T"/"Z" forms
  def load(nil), do: {:ok, nil}
  def load(s) when is_binary(s) do
    with {:ok, n} <- NaiveDateTime.from_iso8601(s), do: {:ok, DateTime.from_naive!(n, "Etc/UTC")}
  end
  def dump(nil), do: {:ok, nil}
  def dump(%DateTime{} = dt) do
    dt = DateTime.shift_zone!(dt, "Etc/UTC")
    base = Calendar.strftime(dt, "%Y-%m-%d %H:%M:%S")
    {usec, _} = dt.microsecond
    {:ok, if(usec > 0, do: base <> "." <> String.pad_leading("#{usec}", 6, "0"), else: base)}
  end
  def dump(_), do: :error
  def utc_now, do: DateTime.utc_now() |> DateTime.truncate(:microsecond)
end
```

- Schema header: `@timestamps_opts [type: Campfire.Types.RailsTime, inserted_at: :created_at, autogenerate: {Campfire.Types.RailsTime, :utc_now, []}]`.
- Other datetime fields (`unread_at`, `connected_at`, `last_active_at`) use `field :x, Campfire.Types.RailsTime`.
- **Leave the global `datetime_type` at the default `:iso8601`.** It is global app env, so it also applies to
  `oban_jobs`, and Oban Lite compares through `datetime(?)` (`lite.ex:372`), which works with either form. Legacy
  tables never use the built-in datetime types, so the global setting does not affect them.
- **Query rule:** never use `ago/2`, `from_now/2` or `datetime_add/3` against legacy columns. ecto_sqlite3 renders
  these as `strftime('%Y-%m-%d %H:%M:%f000Z')` (`connection.ex:1276`), which adds `000Z` and breaks text
  comparison. Compute the cutoff in Elixir and pin it as `^cutoff` against a typed field, or use
  `type(^cutoff, Campfire.Types.RailsTime)`. This applies to `Membership` connected/disconnected with a 60 s TTL,
  `page_created_since` and `page_updated_since`.
- `insert_all` and `update_all` bypass autogenerate. Always pass `created_at`/`updated_at` explicitly. Rails 7+
  `insert_all` fills both (`Room#grant_to`, `User#grant_membership_to_open_rooms`), and `update_all` call sites set
  `updated_at: Time.current` explicitly.
- Use one `now` per transaction, so `messages.created_at`, the room touch and `unread_at` stay coherent.

#### Enums

| Column | Ecto | Note |
|---|---|---|
| `users.role` (int) | `field :role, Ecto.Enum, values: [member: 0, administrator: 1, bot: 2], default: :member` | Explicit integers only (C-03). An unknown integer raises on load, so the auto-migrator must run `20240115124901` (role 2 → 1) before any port code loads users |
| `users.status` (int) | `Ecto.Enum, values: [active: 0, deactivated: 1, banned: 2], default: :active` | Added by `20251126115722`, which backfills `active=0 → status=1` |
| `memberships.involvement` (string, nullable, DB default `mentions`) | `Ecto.Enum, values: [:invisible, :nothing, :mentions, :everything]` (atom names = stored strings) | The column is nullable. A NULL loads as `nil`; treat `nil` as `:mentions` in queries (Rails' `visible` scope is `involvement != 'invisible'`, which **excludes NULL** in SQL; reproduce that three-valued logic exactly, do not "fix" it silently). Set involvement explicitly on insert: `"everything"` for direct rooms, `"mentions"` otherwise |

#### STI `rooms.type`

One schema, `Campfire.Rooms.Room`, with `field :type, Ecto.Enum, values: [open: "Rooms::Open", closed: "Rooms::Closed", direct: "Rooms::Direct"]`.
Do not create a module per subclass. Subclass behavior becomes pattern-matched functions:
`default_involvement(%Room{type: :direct}) -> "everything"`, and open-grant runs on a transition to `:open`.

- `type_changeset/2` rejects a change when `data.type == :direct`, or when the new type is `:direct` (C-05, M-13).
- `creator_id` has no DB FK. Use `belongs_to :creator, User` with `define_field: true`, and handle `nil` on preload
  (orphans are possible).

#### Polymorphic Action Text / Active Storage

Ecto has no polymorphic `belongs_to`. Keep `record_type` + `record_id` as plain fields. Iron Law 3 forbids creating
**new** polymorphic tables, not mapping existing ones, so it does not apply here.

- `ActionText.RichText` (`action_text_rich_texts`):
  - `record_type` is `Ecto.Enum, values: [message: "Message"]`.
  - `name` is `:string` (`"body"`), `body` is `:string` (HTML), and `record_id` is `:id`.
- On `Message`: `has_one :rich_body, RichText, foreign_key: :record_id, where: [record_type: :message, name: "body"]`.
  Preload works. Write it explicitly in the Multi, and do not rely on `cast_assoc` to set `record_type`.
- `ActiveStorage.Attachment`:
  - `record_type` is `Ecto.Enum` over the full C-06 set: `"Message"`, `"User"`, `"Account"`,
    `"ActiveStorage::VariantRecord"`, `"ActiveStorage::Blob"`.
  - `name` is `:string`. `belongs_to :blob` is a real FK.
  - The table has no `updated_at`, so use `timestamps(updated_at: false)`.
- Before shipping, run the C-06 probe `SELECT DISTINCT record_type, name` on production-shaped copies. An unknown
  `record_type` makes `Ecto.Enum` raise on load. If a real install shows any unexpected value, switch that column to
  `:string` with module constants instead.
- Rails side effects to reproduce:
  - `ActionText::RichText belongs_to :record, touch: true`: editing a body bumps `messages.updated_at`, which then
    cascades to `rooms.updated_at`.
  - Active Storage attachments also touch their record by default.
  - Both feed `page_updated_since`, the refresh endpoint (M-03).
- `ActiveStorage.Blob.metadata` is a TEXT JSON column. Map it as `field :metadata, :map`: the ecto_sqlite3 `:map`
  loader decodes text JSON, and the dumper writes text JSON with the default `map_type: :string`. **Do not set
  `map_type: :binary` (JSONB)**, because Rails could not read it.

#### `accounts.settings` (Rails 8.2 `has_json`, column declared `json` → SQLite NUMERIC affinity, stored as TEXT)

- Map it as `field :settings, :map` plus a small accessor module, `Campfire.Accounts.Settings`. **Do not use
  `embeds_one`**: it drops unknown keys on write, and Rails or a future setting may add keys that a rollback would
  lose.
- Read: `Map.merge(%{"restrict_room_creation_to_administrators" => false}, settings || %{})`, then cast the boolean
  leniently (`true`/`"true"`/`"1"`/`1`).
- Write: merge into the existing map and write JSON booleans.
- Verify how `has_json` serializes booleans by writing one from the pinned image (C-12 witness). This is the one
  JSON detail I could not confirm from source.
- `singleton_guard` is `field :singleton_guard, :integer, default: 0`, read-only to app code. Map the unique index
  with `unique_constraint(:singleton_guard)`.

#### Constraint names on SQLite

ecto_sqlite3 (`connection.ex:144`) derives unique-constraint names from the **columns** in the SQLite error
(`users_email_address_index`), not from Rails' index names (`index_users_on_email_address`). Use the default
`unique_constraint(:email_address)` and `unique_constraint([:room_id, :user_id])` names, not the Rails names.

`FOREIGN KEY constraint failed` maps to `[foreign_key: nil]`, so `foreign_key_constraint/3` never matches. Check
existence in the context instead.

### Q2. Migration authority

**Recommendation: two ledgers, two runners, one boot sequence.** Do not port the 15 Rails migrations as ordinary
Ecto migrations recorded in Ecto's ledger.

Why Ecto cannot own Rails' `schema_migrations`:

- ecto_sql 3.14 `SchemaMigration.up/4` inserts a struct with `version` **and** `inserted_at`
  (`schema_migration.ex:26-60`). Rails' table is `schema_migrations(version varchar PRIMARY KEY)` with no
  `inserted_at`, so every insert would fail.
- `migration_cast_version_column` only fixes reads, not writes.
- Pointing Ecto at the Rails table also risks `create_if_not_exists` reshaping assumptions.

**Boot sequence (`Campfire.Release.migrate/0`, run before the endpoint starts — C-55):**

1. Open the writer Repo only.
2. Log `SELECT sqlite_version()`. Take an online backup (`VACUUM INTO` or the backup API) if there is anything
   pending.
3. **Fresh install** (no `schema_migrations` table):
   - Execute a frozen baseline `priv/repo/rails_baseline.sql`: the `sqlite3 .schema` output of a DB freshly
     created by the pinned image at `20251212154340`, which includes the FTS5 virtual table.
   - Insert all 15 Rails versions into `schema_migrations`.
   - Insert `ar_internal_metadata` (`environment = 'production'`) with Rails' row shape, so a later Rails boot
     sees nothing pending.
4. **Existing install**: a hand-written `Campfire.Release.RailsMigrator`, with a fixed ordered list of
   `{version_string, step_fun}` for the 15 versions. For each version **missing** from
   Rails' `schema_migrations`, run one `BEGIN IMMEDIATE` transaction that executes the step's SQL and runs
   `INSERT INTO schema_migrations(version) VALUES (?)`. SQLite DDL is transactional, so a crash leaves no
   half-applied step. Port each step from Rails' observed effect, not from the DSL:

   | Version | Port step | Note |
   |---|---|---|
   | `20231215043540` initial | baseline-at-that-version DDL + FTS5 | Only reached if an install predates it; practically never |
   | `20231220143106` bio | `ALTER TABLE users ADD COLUMN bio text` | |
   | `20240110071740` sessions | `CREATE TABLE` + FK + 2 indexes | Copy the DDL text from the pinned image's `.schema` (Rails emits `integer PRIMARY KEY AUTOINCREMENT NOT NULL`, which needs confirming) |
   | `20240115124901` owner→admin | `UPDATE users SET role = 1 WHERE role = 2` | **Critical**: it must run before `bot_token`/role 2 exists (C-03) |
   | `20240130003150` webhooks | `CREATE TABLE` + FK + index | |
   | `20240130213001` custom_styles | `ADD COLUMN custom_styles text` | |
   | `20240131105830` digest NOT NULL | `UPDATE users SET password_digest = '' WHERE password_digest IS NULL` + a table rebuild to NOT NULL | Paired with the next step. The net schema effect is "nullable", but the `NULL → ''` data change must still happen for parity |
   | `20240209110503` bot_token | `ADD COLUMN bot_token`, unique index, rebuild back to nullable digest | The port may collapse 0131+0209 into "data UPDATE only, schema unchanged" **only if both are pending together**; record both versions |
   | `20250825100957/58/59` Active Storage | no-ops for Campfire (`service_name`, the variant table and nullable `checksum` already exist in the initial schema) | Still insert the versions. Keep the `column_exists?` guards as `PRAGMA table_info` checks |
   | `20251126092013` bans | `CREATE TABLE` + FK + 2 indexes | |
   | `20251126115722` status | `ADD COLUMN status integer NOT NULL DEFAULT 0`; `UPDATE ... SET status = 1 WHERE active = 0`; `ALTER TABLE users DROP COLUMN active` | Native DROP COLUMN works on SQLite ≥ 3.35 because `active` has no index. This is the only destructive step, and it is Rails' own history |
   | `20251126130131` settings | `ADD COLUMN settings json` | |
   | `20251212154340` singleton | `ADD COLUMN singleton_guard integer NOT NULL DEFAULT 0` + unique index | Preflight: abort with a clear message if `count(accounts) > 1`, because Rails would fail too |

5. **Port's own additive migrations**: `Ecto.Migrator.run(Repo, :up, all: true)` with
   `migration_source: "ecto_schema_migrations"`, for example Oban's `Oban.Migration.up/1` and any optional index.
   - Use version numbers greater than `20251212154340`.
   - The ADR says to also mirror these versions into Rails' `schema_migrations`. That is **harmless**: Rails ignores
     unknown versions, which show as `NO FILE`, and only runs versions it has files for that are missing. But it adds
     nothing.
   - I recommend amending ADR-000's Data line to: "Rails `schema_migrations` holds exactly the Rails versions, written
     by the RailsMigrator; port DDL is ledgered in `ecto_schema_migrations`."
   - If mirroring is kept, the port's Ecto migration does it with `execute "INSERT OR IGNORE INTO schema_migrations ..."`,
     so it lands in the same transaction.
6. Start the reader pool. A read-only connection cannot create the DB or switch it to WAL.

**Answer to "identical version numbers?"**: yes for the **ledger value**. The RailsMigrator writes exactly Rails'
version strings into Rails' table. That table is what lets the pinned Rails image boot without re-running a step
(for example, re-adding `status` would crash Rails' `db:prepare`). No for the **mechanism**: do not express them as
`Ecto.Migration` files in Ecto's ledger, because that creates a second record of the same fact, which can disagree
with the first.

**C-55 witness**: run the boot against DB snapshots made by each released image tag (contracts Q4: oldest
supported version), then boot the pinned Rails image on the result. It must report no pending migrations.

### Q3. FTS5 `message_search_index` inside the message transaction

Keep the virtual table, the `porter` tokenizer, `rowid = messages.id`, app maintenance and no triggers (C-09). Move
the writes **inside** the transaction. That closes Rails' after-commit gap (M-02) and does not change the stored
form.

```elixir
# Campfire.Search.Index — the only module that touches the FTS table
def put(repo, id, body) do
  # delete+insert = idempotent upsert; repairs rows Rails lost after a crash
  repo.query!("DELETE FROM message_search_index WHERE rowid = ?1", [id])
  repo.query!("INSERT INTO message_search_index(rowid, body) VALUES (?1, ?2)", [id, body])
end
def delete(repo, id), do: repo.query!("DELETE FROM message_search_index WHERE rowid = ?1", [id])
def delete_for_room(repo, room_id),
  do: repo.query!("DELETE FROM message_search_index WHERE rowid IN (SELECT id FROM messages WHERE room_id = ?1)", [room_id])

# In Chat.create_message/3 (Ecto.Multi on the writer Repo)
Multi.new()
|> Multi.insert(:message, Message.create_changeset(...))
|> Multi.insert(:rich_text, fn %{message: m} -> RichText.body_changeset(m, html, now) end)
|> Multi.run(:fts, fn repo, %{message: m} -> {:ok, Index.put(repo, m.id, PlainText.from(html, attachment))} end)
|> ...
```

- **Create and update** both use `put/3`. Rails used `UPDATE ... WHERE rowid = ?`, which silently no-ops when the
  row is missing; delete+insert also repairs those rows.
- **Destroy**: delete the FTS row in the same Multi as the message. On room delete (M-14), `delete_for_room/2` runs
  **before** the messages are deleted, because the subquery needs them.
- **Plain text parity** is the real risk, not the SQL. The body must equal Rails `body.to_plain_text.presence ||
  attachment.filename || ""`. Pin it with fixtures from the pinned image: Trix, Lexxy, mentions (`@Name`),
  attachments.
- **Query**: `join: i in fragment("message_search_index"), on: i.rowid == m.id`, with
  `where: fragment("message_search_index MATCH ?", ^scrubbed)`. Keep the `gsub(/[^[:word:]]/, " ")` scrub (Unicode
  word class: `~r/[^\p{L}\p{N}_]/u`), restrict to rooms the user can reach, order by `created_at`, last 100.
- **Reads**: search goes through `Repo.reader()`. FTS writes always go through the writer inside the transaction.
- **Release task** `Campfire.Release.rebuild_search_index/0`: delete all FTS rows, then insert in batches from
  messages + rich text. It reconciles Rails-era drift and is safe for rollback (same table, same contents).

### Q4. Derived state (C-13): where it lives

**Rule: one context function per write intent owns every derived write in one `Repo.transact`/`Ecto.Multi` on the
writer. Schemas hold changesets only, with no Repo calls.** The web controller, the bot API controller, webhook-reply
handling, Oban workers and the admin scripts (`script/admin/reset-password` → a release `eval`) all call the same
context function. The compat layer never writes tables directly.

| Intent (context fn) | Derived writes in the same transaction | After commit |
|---|---|---|
| `Chat.create_message(scope, room, attrs, opts)` | message (`client_message_id` defaults to a UUID); rich text; attachment + blob rows; FTS put; `rooms.updated_at = now`; `memberships` `update_all(unread_at: m.created_at, updated_at: now)` where `room_id`, visible, disconnected (`connected_at IS NULL OR < ^(now-60s)`, or the Presence snapshot per M-28), `user_id != creator`; `Oban.insert` push job; webhook jobs **unless** `opts[:webhook_reply]` (M-01 loop guard) | PubSub broadcasts (append, unread notices) |
| `Chat.update_message/3` | rich text; `messages.updated_at` (the Action Text touch); `rooms.updated_at` (cascade); FTS put | broadcast replace |
| `Chat.delete_message/2` | FTS delete; boosts; rich text; attachment rows; message; room touch | Oban blob purge, broadcast remove |
| `Chat.boost/3`, `Chat.unboost/2` | boost row; `messages.updated_at`; `rooms.updated_at` | broadcast |
| `Accounts.create_user/2` (signup, first run, bots) | user; `insert_all` memberships for every `Rooms::Open` with **explicit** `created_at`/`updated_at` and `involvement: "mentions"`, `on_conflict: :nothing, conflict_target: [:room_id, :user_id]` | — |
| `Rooms.create_room/3` | room + memberships with type-based default involvement | broadcast sidebar |
| `Rooms.change_type/3` (→ open) | type; grant all `status = active` users (`on_conflict: :nothing`, matching Rails `insert_all` skip-duplicates) | — |
| `Rooms.revise_memberships/3`, `Rooms.delete_room/2` | per M-14, children first (`foreign_keys` is ON) | disconnect revoked sockets, purge job |
| `Accounts.deactivate/1`, `ban/1`, `unban/1` | per `user.rb` / `bannable.rb`, including the email rewrite `-deactivated-<uuid>@` and bans from session IPs | socket close, banned-content job |
| `Searches.record/2` | find-or-insert + touch + trim to 10 | — |
| `Sessions.resume/3` | update only if `last_active_at` < now−1 h | — |
| Boot | `Membership.disconnect_all` (`connected_at = NULL`, `connections = 0`, `updated_at`) if presence stays in the DB | — |

Enforcement:

- (a) A Credo or Boundary check: `Repo.insert*/update*/delete*` and `Repo.query` are allowed only under
  `lib/campfire/<context>/` and `Campfire.Release`.
- (b) A shared property test: for every public write function, assert the C-13 invariants (room `updated_at` ≥
  child `updated_at`, unread set for non-present members, FTS row count = message count for touched ids).
- (c) The bidirectional rollback test from data-compat.md.

Keep each transaction short (sqlite-on-beam rule 9). No HTTP, no rendering and no broadcast inside the transaction.

### Q5. Additive improvements: rollback safety

**T-08 `(created_at, id)` keyset — safe, recommended.**

- It is mostly a query change: `where: m.created_at < ^c or (m.created_at == ^c and m.id < ^id)`,
  `order_by: [asc: :created_at, asc: :id]`. The client still sends a message id, so the wire contract is unchanged.
- It only works with the consistent text format from Q1. The tie-break is only meaningful if both apps write the
  same format.
- Optional additive index: `messages(room_id, created_at)`. SQLite index entries carry the rowid, so `id`
  tie-breaking is covered.
  - Today only `index_messages_on_room_id` exists, so this is a performance win for room load. Measure it against
    the slice-0 baseline.
  - Rails ignores extra indexes, so rollback is safe; the only cost is one extra index write per message.
  - Create it from an Ecto migration with a port-specific name (`port_messages_room_id_created_at_index`), so it can
    never collide with a Rails index name.
  - On large DBs, index creation holds the writer lock for its duration. Run it at boot before serving, and log the
    duration.

**T-10 DM canonical key — prefer the no-DDL variant.**

- **Preferred (zero schema change):**
  - A SQL lookup over memberships, scoped to the first user's DMs:
    `SELECT m.room_id FROM memberships m JOIN rooms r ON r.id = m.room_id AND r.type = 'Rooms::Direct' WHERE m.room_id IN (SELECT room_id FROM memberships WHERE user_id = ?) GROUP BY m.room_id HAVING count(*) = ?n AND sum(m.user_id IN (...)) = ?n ORDER BY m.room_id LIMIT 1`.
    It uses the existing `memberships(user_id)` and `(room_id, user_id)` indexes, and costs O(that user's DMs)
    instead of O(all DMs).
  - The "races" in T-10 are closed by running find-or-create inside one `BEGIN IMMEDIATE` transaction on the
    single-writer Repo. There is no Rails coexistence (replacement mode), so the transaction serializes every
    creator.
  - Rollback risk is nil. `ORDER BY room_id` matches Rails' `detect`, which in practice returns the first row by
    rowid, if legacy duplicates exist.
- **Only if measurements demand it — the key column:**
  - `ALTER TABLE rooms ADD COLUMN direct_member_key text` (nullable; no rebuild) plus a **partial** unique index
    `ON rooms(direct_member_key) WHERE type = 'Rooms::Direct' AND direct_member_key IS NOT NULL`.
  - Rollback-safe: Rails inserts NULL (with `partial_inserts` off it writes every column, here NULL), and NULLs never
    conflict. Rails' scan still works.
  - Roll-forward cost: the port must backfill keys that Rails left NULL, and Rails races may have created duplicate
    DMs. The backfill keys the lowest id and leaves the duplicates NULL. It must never fail the boot.
  - It is a second source of truth that only the port maintains: treat it as a cache.

### Q6. SQLite repo configuration (ecto_sqlite3 0.25.0)

Match Rails' `database.yml` on purpose: `timeout: 5000`, `default_transaction_mode: immediate`, pool 10.
ActiveRecord ≥ 7.1 SQLite defaults are WAL, `synchronous=NORMAL`, `foreign_keys=ON`,
`journal_size_limit=64MB` and `mmap_size=128MB`; that list is from memory, so confirm it with `PRAGMA` reads on the
pinned image.

```elixir
config :campfire, Campfire.Repo,                 # writer
  database: "/rails/storage/db/production.sqlite3",   # C-52: same path
  pool_size: 1,                                  # one writer (rule 1-2); replaces Rails' 10
  default_transaction_mode: :immediate,          # = Rails
  journal_mode: :wal, synchronous: :normal,      # = Rails 8; record the durability choice
  foreign_keys: :on,                             # = Rails; delete children first (M-14)
  busy_timeout: 5_000,                           # = Rails timeout; adapter option, never PRAGMA
  temp_store: :memory, cache_size: -64_000,
  timeout: 15_000, queue_target: 500, queue_interval: 2_000,   # tune vs slice-0 baseline
  migration_source: "ecto_schema_migrations"

config :campfire, Campfire.Repo.Read,
  database: same_path, mode: :readonly, read_only: true,
  pool_size: min(System.schedulers_online(), 8), busy_timeout: 5_000

config :ecto_sqlite3, map_type: :string, binary_id_type: :string   # keep defaults; datetime_type left :iso8601 (see Q1)
```

- **`journal_size_limit` and `mmap_size`** are not adapter options in 0.25.0. If parity matters, issue
  `PRAGMA journal_size_limit = 67108864` from an `after_connect` callback on the writer. These PRAGMAs are safe to
  set; `busy_timeout` is not.
- **FTS5 in the bundled SQLite**: Exqlite's bundled SQLite (3.53.x) is compiled with FTS5. Assert it at boot with
  `SELECT count(*) FROM message_search_index LIMIT 0`.
- **Backups (C-53)**: `/hooks/pre-backup` uses `VACUUM INTO` or the backup API and never copies files. The
  post-restore hook deleting `-wal`/`-shm` is legal only while the app is stopped.
- **Oban Lite** runs on the writer Repo, in the same file (atomic enqueue). `oban_jobs` is an extra table that Rails
  ignores on rollback (rollback loses queued jobs, so state it in the ADR).

---

## Schema mapping table

All modules use `@timestamps_opts [type: Campfire.Types.RailsTime, inserted_at: :created_at, autogenerate: {Campfire.Types.RailsTime, :utc_now, []}]`
and the default integer `:id` PK (SQLite `INTEGER PRIMARY KEY`, Rails AUTOINCREMENT). FK fields are `:id`.

| Table | Schema module | Notable fields / mapping | Associations (DB FK?) |
|---|---|---|---|
| `accounts` | `Campfire.Accounts.Account` | `settings :map` + accessor (default `restrict_room_creation_to_administrators: false`); `join_code :string` (`XXXX-XXXX-XXXX`); `custom_styles :string`; `singleton_guard :integer` (unique) | logo via `ActiveStorage.Attachment` (`record_type: "Account"`, `name: "logo"`) |
| `users` | `Campfire.Accounts.User` | `role Ecto.Enum [member: 0, administrator: 1, bot: 2]`; `status Ecto.Enum [active: 0, deactivated: 1, banned: 2]`; `password_digest :string` nullable (bcrypt `$2a$`; NULL never verifies); `email_address` nullable, unique, **case-sensitive**; `bot_token` unique; `bio` | has_many memberships (no FK), sessions/bans/searches/push_subscriptions/webhooks (FK), messages via `creator_id` (FK) |
| `sessions` | `Campfire.Accounts.Session` | `token` unique (has_secure_token, 24 chars); `last_active_at RailsTime` | belongs_to user (FK) |
| `bans` | `Campfire.Accounts.Ban` | `ip_address :string` (public IPs only, validated with `:inet`) | belongs_to user (FK) |
| `rooms` | `Campfire.Rooms.Room` | `type Ecto.Enum [open: "Rooms::Open", closed: "Rooms::Closed", direct: "Rooms::Direct"]`; `name` nullable (directs); `creator_id` (no FK) | has_many memberships, messages |
| `memberships` | `Campfire.Rooms.Membership` | `involvement Ecto.Enum [:invisible, :nothing, :mentions, :everything]` (nullable, DB default `mentions`); `unread_at`, `connected_at RailsTime`; `connections :integer` | belongs_to room, user (**no DB FK**, orphans possible); unique `(room_id, user_id)` |
| `messages` | `Campfire.Chat.Message` | `client_message_id :string` NOT NULL (UUID default); **no body column** | belongs_to room (FK), creator (FK); has_one rich_body (`where:` polymorphic); has_many boosts (FK) |
| `boosts` | `Campfire.Chat.Boost` | `content :string` — **do not** `validate_length(max: 16)` on load or update of legacy rows (C-16) | belongs_to message (FK), booster (no FK) |
| `action_text_rich_texts` | `Campfire.Compat.ActionText.RichText` | `record_type Ecto.Enum [message: "Message"]`; `name :string`; `body :string` (HTML, sgid mentions C-10); `record_id :id` | none (polymorphic); unique `(record_type, record_id, name)` |
| `active_storage_blobs` | `Campfire.Compat.ActiveStorage.Blob` | `key` unique; `metadata :map` (text JSON); `checksum` nullable base64 MD5; `service_name` `"local"`; `byte_size :integer`; `timestamps(updated_at: false)` | has_many attachments, variant_records (FK) |
| `active_storage_attachments` | `Campfire.Compat.ActiveStorage.Attachment` | `record_type Ecto.Enum` (5 values, C-06); `name :string`; `timestamps(updated_at: false)` | belongs_to blob (FK) |
| `active_storage_variant_records` | `Campfire.Compat.ActiveStorage.VariantRecord` | `variation_digest :string` (Marshal-derived digest, computed by the SHIM); no timestamps | belongs_to blob (FK) |
| `push_subscriptions` | `Campfire.Push.Subscription` | `endpoint`, `p256dh_key`, `auth_key`, `user_agent` (non-unique composite index) | belongs_to user (FK) |
| `searches` | `Campfire.Search.RecentSearch` | `query :string`; no unique index (benign race) | belongs_to user (FK) |
| `webhooks` | `Campfire.Bots.Webhook` | `url :string` (may embed credentials: filter in logs) | belongs_to user (FK) |
| `message_search_index` (FTS5) | none; `Campfire.Search.Index` raw SQL | `rowid` = `messages.id`, `body` | — |
| `schema_migrations`, `ar_internal_metadata` | none; `Campfire.Release.RailsMigrator` only | Rails ledger, never written by Ecto's migrator | — |
| `ecto_schema_migrations`, `oban_jobs` | Ecto / Oban internal | port-only, additive | — |

---

## Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | The KB-recommended `datetime_type: :text_datetime` **truncates microseconds**, and the default writes `T…Z`. Either one silently breaks C-02 ordering and pagination for mixed rows | **High** | Custom `RailsTime` type (Q1); fix kb/data-compat.md and kb/sqlite-on-beam.md; byte-compare probe against a pinned-image row |
| R2 | `ago/2` / `datetime_add` in queries emit `%f000Z` text, which compares wrongly against Rails text | High | Lint rule: no `ago`/`from_now`/`datetime_add` on legacy tables; pin cutoffs computed in Elixir |
| R3 | `insert_all`/`update_all` skip autogenerated timestamps, giving NULLs in NOT NULL `created_at` (insert error) or a stale `updated_at` that breaks refresh-since | High | Context helpers always pass `created_at`/`updated_at`; property test |
| R4 | Ecto's migrator pointed at Rails' `schema_migrations` fails (no `inserted_at`). Running a ported Rails step without recording its version makes the pinned Rails image re-run it and crash on rollback | High | RailsMigrator writes Rails' ledger in the same transaction; C-55 snapshot matrix |
| R5 | `Ecto.Enum` raises on unknown stored values: role 2 (owner) on unmigrated installs, an unexpected polymorphic `record_type` | Med | Run `20240115124901` first; C-06 distinct-value probe; `:string` fallback for attachments if needed |
| R6 | FTS plain-text drift (Trix/Lexxy/mentions/attachment filename) makes port-written rows search differently, and rollback inherits that | Med | Fixture parity tests against the pinned image; the `rebuild_search_index` release task |
| R7 | `has_json` boolean serialization unknown; a wrong write form flips `restrict_room_creation_to_administrators` for Rails after rollback | Med | Write-from-Rails probe; lenient read, JSON-boolean write, preserve unknown keys |
| R8 | `involvement IS NULL` rows: SQL `!= 'invisible'` excludes them in Rails; an Elixir-side filter would include them | Low-Med | Express "visible" in SQL exactly as Rails does; probe for NULL counts on real data |
| R9 | `foreign_key_constraint/3` cannot match on SQLite (name is nil), so FK violations surface as raises | Low | Validate existence in contexts; delete children first (M-14) |
| R10 | Adding the optional `messages(room_id, created_at)` index on a large DB blocks the single writer during boot | Low | Time it on a production-shaped copy; log progress |
| R11 | The Rails `.ffffff` assumption in C-02 is likely imprecise (whole-second times have no fraction) | Low | Mirror Rails' `quoted_date` exactly; fix the C-02 wording after the probe |

## Recommendations

1. **Adopt `Campfire.Types.RailsTime`** for every legacy datetime column. Leave the global `datetime_type` at
   `:iso8601` (Oban). Correct the two KB files that recommend `:text_datetime`.
2. **Boot migrator = baseline SQL (fresh) + `RailsMigrator` (15 steps, Rails ledger) + `Ecto.Migrator`
   (`ecto_schema_migrations`, port-only).** Amend ADR-000's "recorded in Rails' `schema_migrations`" line: leave
   Rails' table holding only Rails versions. Mirroring is harmless if the ADR keeps it.
3. **FTS maintenance as `Multi.run` steps** in the same writer transaction, with delete+insert upsert, plus a
   `rebuild_search_index` release task and plain-text parity fixtures.
4. **One context function per write intent** owns all C-13 derived writes. Enforce it with a Repo-call boundary
   check and a derived-state property test. Admin scripts and the bot API call the same functions.
5. **T-08**: ship the `(created_at, id)` keyset now (query-only). Add the `messages(room_id, created_at)` index only
   if the slice-0 baseline shows room-load benefit.
6. **T-10**: implement the membership-group SQL lookup inside an immediate transaction (no DDL). Defer the
   `direct_member_key` column unless measurements require it, and if added, make it nullable with a partial unique
   index and a non-failing backfill.
7. **Repo config**: writer `pool_size: 1`, `:immediate`, WAL, `synchronous: :normal`, `foreign_keys: :on`,
   `busy_timeout: 5_000`, `migration_source: "ecto_schema_migrations"`; read-only reader pool. Add
   `journal_size_limit` via `after_connect` if parity with Rails 8 defaults is wanted.
8. **Probes to run on the pinned image before the data slice**, using production-shaped copies and never SOURCE:
   - timestamp text for `usec == 0` and `usec > 0`;
   - `PRAGMA` values (`journal_mode`, `synchronous`, `foreign_keys`, `journal_size_limit`, `mmap_size`);
   - `.schema` DDL (AUTOINCREMENT) for the baseline;
   - `has_json` boolean form;
   - `SELECT DISTINCT record_type, name` for attachments and rich texts;
   - `SELECT count(*) FROM memberships WHERE involvement IS NULL`;
   - `max(length(boosts.content))`.
