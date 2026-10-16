# Data Compatibility

The legacy database, files, cookies and signed links are **contracts**. The core stays idiomatic Ecto. Legacy
formats get one-way readers at the edge (`lib/app/compat/`), each with a SHIM row and a retirement condition.
Decide the cutover mode and the data decision in ADR-000 first. Keeping the legacy schema with a rollback path
needs most of this file; a new schema plus ETL needs only the readers.

Versions: Ecto 3.14.2, ecto_sql 3.14.0, ecto_sqlite3 0.25.0, joken 2.7.0, joken_jwks 1.8.0, bcrypt_elixir 3.3.2,
argon2_elixir 4.1.3, cloak_ecto 1.3.0, ex_aws 2.7.0, ex_aws_s3 2.5.9.

## Ecto Over an Existing Schema

Map the schema as it is. Never let Ecto defaults create new columns next to the legacy ones.

```elixir
defmodule App.Chat.Message do
  use Ecto.Schema
  @timestamps_opts [type: :utc_datetime_usec, inserted_at: :created_at]   # Rails names, precision 6
  schema "messages" do
    field :body_plain, :string, source: :content                  # legacy column name
    field :status, Ecto.Enum, values: [pending: 0, sent: 1]       # Rails integer enum
    field :record_type, Ecto.Enum, values: [room: "Room", user: "User"]  # polymorphic *_type
    field :record_id, :id                                         # no FK: Ecto has no polymorphic belongs_to
    field :deleted_at, :utc_datetime_usec                         # soft delete
    belongs_to :room, App.Chat.Room
    belongs_to :creator, App.Accounts.User, foreign_key: :creator_id
    timestamps()
  end
end
```

| Concern | Legacy forms | Ecto mapping | Trap |
|---------|--------------|--------------|------|
| Table and column names | Rails plural, Django `<app>_<model>`, Laravel plural, Hibernate `@Table` | `schema "blog_comment"`, `field :x, :t, source: :legacy_col` | Renaming in the DB breaks the legacy reader during coexistence |
| Primary keys | Rails/Laravel bigint (Laravel unsigned), Django `AutoField`, UUID, Prisma `cuid()` strings, Django multi-table `<parent>_ptr_id` | Default `:id`; `@primary_key {:id, :binary_id, autogenerate: true}` + `@foreign_key_type :binary_id`; `{:id, :string, autogenerate: false}`; `{:post_ptr_id, :id, autogenerate: false}` | UUIDs on SQLite are text by default (`config :ecto_sqlite3, binary_id_type: :string`), which matches Rails on SQLite |
| Timestamps | Rails `created_at`/`updated_at` `timestamp(6)` UTC in `timestamp without time zone`; Laravel seconds in the app timezone; Django `USE_TZ` → `timestamptz`, varied names | `@timestamps_opts` with `inserted_at: :created_at`; `:utc_datetime_usec` vs `:naive_datetime`; `timestamps(type: ...)` per schema | Laravel `config('app.timezone')` other than UTC means naive local time: convert at the edge |
| SQLite datetimes | Rails writes `2025-12-12 15:43:40.123456` (space, no zone, microseconds) | A project-owned custom Ecto type on legacy columns that dumps and loads exactly `YYYY-MM-DD HH:MM:SS.ffffff` (UTC, no zone). No built-in `datetime_type` matches: in 0.25.0 `:text_datetime` formats `%Y-%m-%d %H:%M:%S` and drops microseconds even for `_usec` fields, and `:iso8601` writes `T` (and `Z` for UTC). `datetime_type` is global app env, not a per-Repo option | A mismatched format sorts new rows wrongly against legacy rows within one second (pagination, unread markers). Probe test: compare a port-written row with a Rails-written row as text |
| Migration table | Rails `schema_migrations(version varchar)`, Laravel `migrations`, Django `django_migrations` | Repo config `migration_source: "ecto_schema_migrations"` | Ecto's default `schema_migrations` collides with Rails' table of the same name |
| STI | Rails `type` column with class names (`Rooms::Direct`) | One schema + `field :type, Ecto.Enum, values: [direct: "Rooms::Direct", open: "Rooms::Open"]` + pattern-matched functions | A schema module per subclass reproduces inheritance; renaming persisted values breaks the legacy app |
| Polymorphic | Rails `*_type` = class name (or `polymorphic_name`); Laravel FQCN `App\Models\Post` unless `morphMap`; Django `content_type_id` → `django_content_type(app_label, model)` | `Ecto.Enum` over the stored strings; query by type + id; for Django resolve content-type ids once at boot | There is no FK, so orphans exist: handle `nil` on load |
| Enums | Rails integer or string `enum`; Django `choices` strings; Laravel backed enums; Postgres enum types | `Ecto.Enum` with explicit `values:` (integers or strings), never positional | Adding a value on one side only crashes the other side's cast |
| Soft delete | `deleted_at` (paranoia, Laravel `SoftDeletes`), `discarded_at`, `is_deleted` | Context query helpers filter `is_nil(m.deleted_at)`; or `Repo.prepare_query/3` with an explicit opt-out | Unique indexes are often partial (`WHERE deleted_at IS NULL`): mirror them in `unique_constraint` names |
| Counter caches | `comments_count` maintained by Rails callbacks | Update in the same Multi: `Ecto.Multi.update_all(multi, :bump, where(Post, id: ^id), inc: [comments_count: 1])`, or a DB trigger both apps share | Ecto writes skip legacy callbacks, so counts drift silently |
| JSON and serialized columns | Postgres `jsonb`; SQLite/MySQL JSON text; Rails `serialize` YAML; PHP `serialize()`; paper_trail YAML `object` | `:map`/`{:array, _}` for JSON (SQLite text by default, `config :ecto_sqlite3, map_type:`); read YAML with yaml_elixir only for history | Never write YAML, Marshal or PHP-serialized data. Backfill to JSON with an Oban job, then switch the readers |
| Encrypted columns | Rails `encrypts` (Active Record Encryption), Laravel `encrypted` casts, attr_encrypted | cloak_ecto 1.3.0 for new data; a one-way compat decryptor for old ciphertext | Ciphertext rarely interoperates: re-encrypt in a backfill, keep the legacy key until it is done |
| Collations and encodings | MySQL `utf8` (3-byte) vs `utf8mb4`; `*_ci` collations; Postgres `citext`; SQLite `NOCASE` (ASCII only) | MyXQL charset `utf8mb4`; normalize case in the changeset where the DB compares case-insensitively | The DB treats `A@x.com` and `a@x.com` as equal while Elixir `==` does not, so dedupe before `cast_assoc` (Iron Law 17) |
| Booleans and money | MySQL `tinyint(1)`; SQLite 0/1 (Rails < 6 wrote `'t'`/`'f'`); money as float | `:boolean`; `:decimal` or integer cents (Iron Law 4) | Check real rows on old SQLite data before trusting the type |

Ecto writes run none of the legacy callbacks: FTS updates, `touch` cascades, cache busting, broadcasts, audit
rows, counter caches. List every callback in the ledger, and make each one an explicit Multi step, an Oban job,
or a DB trigger both apps share.

## Migration Ownership During Coexistence

- **One DDL owner at a time.** While the legacy app owns the schema, its migrations run and Ecto has none for
  those tables.
- **Baseline once.** Dump the structure (`pg_dump --schema-only`, `structure.sql`, `sqlite3 .schema`) into a
  single Ecto baseline migration. Record it as applied (insert its version into `ecto_schema_migrations`)
  without executing it against the live DB.
- **Elixir-only tables** go through Ecto migrations recorded in `ecto_schema_migrations`. Keep Rails'
  `schema_migrations` rows intact, because rollback boots the legacy app against them.
- **A schema gate that must stop boot** is a supervision-tree child whose `start` function runs the check and
  returns `:ignore` on success or `{:error, reason}` on failure, placed before the Repo users and the Endpoint.
  A `restart: :temporary` Task cannot fence: its `start_link` has already returned `{:ok, pid}`, so a later
  crash leaves the app running.
- **Flip ownership at a ledger milestone.** After the flip, freeze the legacy migrations. Until the rollback
  window closes, changes are additive only: no renames, no drops, no `NOT NULL` without a default.
- **SQLite `ALTER TABLE`** often means a table rebuild. Rehearse it on a copy and run it inside the
  maintenance window.
- Campfire's rule: preserve the Rails migration metadata and never run two migration authorities
  independently over the same live schema.

## Password Hashes

Verify the legacy hash, then rehash on a successful login. Never force a mass reset when verification is possible.

| Source | Stored form | Verify in Elixir |
|--------|-------------|------------------|
| Devise, `has_secure_password` | `$2a$`/`$2b$` bcrypt | `Bcrypt.verify_pass(password <> pepper, hash)`; the Devise `pepper` is empty unless configured |
| Laravel, PHP `password_hash` | `$2y$` bcrypt | bcrypt_elixir rejects `$2y$`: replace the prefix with `$2b$` and verify (the same algorithm, as the library advises) |
| Laravel/PHP argon2, Node argon2 | PHC `$argon2id$v=19$m=...` | `Argon2.verify_pass/2` |
| Django default | `pbkdf2_sha256$<iter>$<salt>$<hash>` | `:crypto.pbkdf2_hmac(:sha256, password, salt, iter, 32)`, base64, then `Plug.Crypto.secure_compare/2`; the salt is the raw string. Not `pbkdf2_elixir`: its Elixir loop runs 1,000,000 rounds on the normal schedulers and starves the VM under concurrent logins |
| Django `bcrypt_sha256` | `bcrypt_sha256$$2b$...` | Strip `bcrypt_sha256$`; the password is SHA256-hex prehashed: `Bcrypt.verify_pass(sha256_hex(password), bcrypt_part)` |
| Django argon2 | `argon2$argon2id$...` | Strip the `argon2` prefix, then `Argon2.verify_pass/2` |
| Spring `DelegatingPasswordEncoder` | `{bcrypt}$2a$...`, `{pbkdf2}...`, `{argon2}...` | Strip `{id}` and dispatch on it; reject `{noop}` |
| ASP.NET Identity V3 | base64: `0x01`, PRF, iterations, salt length (UInt32 BE each), salt, subkey | The custom verifier below; V2 (`0x00`) is HMAC-SHA1, 1000 iterations, 16-byte salt, 32-byte subkey |

```elixir
def verify_aspnet_v3(password, encoded) do
  with {:ok, <<1, prf::32, iterations::32, salt_len::32, rest::binary>>} <- Base.decode64(encoded),
       <<salt::binary-size(salt_len), subkey::binary>> when subkey != "" <- rest,
       {:ok, digest} <- Map.fetch(%{0 => :sha, 1 => :sha256, 2 => :sha512}, prf) do
    derived = :crypto.pbkdf2_hmac(digest, password, salt, iterations, byte_size(subkey))
    Plug.Crypto.secure_compare(derived, subkey)
  else
    _ -> false
  end
end
```

Rehash rules: dispatch on the prefix inside one `Accounts.verify_legacy/2`. On success, write the new hash. While
rollback is possible, **the legacy app must still verify the user**. Either rehash into a format it accepts, or
write the new hash to a new column and leave the legacy column untouched until the rollback window closes.
Keep a `hash_algorithm` marker until no legacy hashes remain.

## Sessions

Rank the options, cheapest first:

1. **Forced re-login at cutover.** It is a user-visible decision, so record it in ADR-000.
2. **Handoff endpoint (preferred).** The legacy app mints a one-time token for the logged-in user and redirects
   to Phoenix. Phoenix verifies it once and creates its own phx.gen.auth session. No crypto port is needed.
3. **One-way cookie reader.** A plug decrypts the legacy cookie, extracts the user id, mints a Phoenix session
   and **never writes the legacy format**. Use it only when a redirect hop is impossible.
4. **Shared bidirectional session store.** Never. That is how Campfire ended up with a Marshal codec.

```elixir
# Phoenix side of the handoff: HS256 with a secret shared with the legacy app, 60 s TTL, single use
defmodule App.Compat.Handoff do
  use Joken.Config
  def token_config, do: default_claims(default_exp: 60, iss: "legacy", aud: "app")
end
# {:ok, %{"sub" => user_id, "jti" => jti}} = App.Compat.Handoff.verify_and_validate(token, signer)
# Reject a jti that was already used (unique index on handoff_jtis), then log_in_user/2.
```

One-way readers, when option 3 is unavoidable:

- **Rails 5.2+ encrypted cookie.**
  - Key: `Plug.Crypto.KeyGenerator.generate(secret_key_base, "authenticated encrypted cookie", iterations: 1000,
    length: 32, digest: :sha256)`. SHA256 applies under `load_defaults 7.0`; SHA1 before that.
  - Wire value (after URL-decoding): `b64(ciphertext)--b64(iv)--b64(tag)`. Decrypt with
    `:crypto.crypto_one_time_aead(:aes_256_gcm, key, iv, ct, "", tag, false)`.
  - Envelope: `{"_rails": {"message": b64(json), "pur": "cookie.<name>"}}` on 6.0–7.0, `"data"` on 7.1+. Check
    `pur` and `exp`.
  - Devise keeps `"warden.user.user.key" => [[id], salt]`. The Rails 8 auth generator keeps a signed `session_id`
    plus a `sessions` table.
- **Marshal.** If `cookies_serializer` is nil or `:marshal`, switch it to `:hybrid` weeks before cutover so
  active cookies get rewritten as JSON. Treat leftover Marshal cookies as logged out. **Never parse Marshal**:
  deserializing it is code execution on untrusted input.
- **Django.** The DB backend stores the key in the cookie and the data in `django_session`. `session_data` is
  `signing.dumps(..., compress=True)` with salt `django.contrib.sessions.SessionStore`. Its form is
  `payload:timestamp:signature`, where a leading `.` on the payload means zlib. HMAC-SHA256; try
  `SECRET_KEY_FALLBACKS` too. Read `_auth_user_id` and check `expire_date`. Pre-3.1 encodings count as logged out.
- **Laravel.** `APP_KEY` is `base64:<32 bytes>`. The cookie is base64 JSON `{iv, value, mac, tag}`. The plaintext
  has the prefix `hash_hmac('sha1', name . 'v2', key) . '|'`. Switch session `serialization` to `json` before
  cutover instead of writing a PHP-unserialize parser.
- **express-session, ASP.NET Data Protection, Spring Session.** Decoding them is impractical. Use option 1 or 2.

Generate known-answer vectors in the pinned legacy version. Test valid, expired, wrong-purpose, tampered and
rotated-key cases. `plug_rails_cookie_session_store` 2.0.0 implements only the legacy AES-CBC jar, not 5.2+ GCM.

## CSRF Continuity

- **Stale tabs.** Forms open across the cutover carry legacy tokens that Phoenix rejects. Treat that as an
  expected 403 with a reload prompt, not as an attack.
- **Kept Rails frontend.** If the Rails JS stays (rails-ujs, Turbo), render `<meta name="csrf-token"
  content={get_csrf_token()}>` and `<meta name="csrf-param" content="_csrf_token">`. Turbo sends the
  `X-CSRF-Token` header and rails-ujs uses the param name from `csrf-param`. `Plug.CSRFProtection` accepts both.
- **Fetch Metadata.** `Sec-Fetch-Site` checks in place of tokens are a policy change: they need an ADR. Campfire's
  main branch adopted them (`66b1d4d`) across all ports as a documented known difference.
- **Cross-verification.** Never cross-verify Rails masked tokens in Elixir. The formats differ, and the shim would
  have to read the Rails session.

## JWT, Signed URLs and Signed IDs

- **Bearer JWTs.** Validate the same `iss`, `aud` and `kid` against the same JWKS with joken_jwks 1.8.0. Match
  the legacy clock-skew leeway and map claim names (ASP.NET `ClaimTypes` URIs, Spring `scope`/`scp`). Let
  legacy tokens expire naturally instead of revoking them all.
- **Long-lived signed links already in the wild.** These include Rails signed global ids, Active Storage
  `signed_id` blob URLs, Django `signing` tokens, Laravel signed routes (HMAC-SHA256 over the URL with
  `APP_KEY`), and password-reset or invite links. Give each one a narrow verifier in compat that checks purpose
  and expiry. Mint new capabilities with `Phoenix.Token` or a signed or database-backed token scheme that keeps
  purpose, expiry and any required revocation. Verified routes may build the URL that carries the token; they
  neither sign nor authorize it.
- **Re-signing.** Re-signing new links does not repair old links stored in messages, emails or bookmarks
  (Campfire: avatars, transfer links, blob URLs). Inventory where old links persist before deciding when the
  verifier can retire.

## Files: Active Storage and S3 Key Layout

- **Keep the bucket and the keys.** The S3 object key is `active_storage_blobs.key`, with no prefix unless the
  service config adds one. The Disk service stores `<root>/<key[0..1]>/<key[2..3]>/<key>`, and Campfire's root is
  `storage/files`.
- **Tables to map read-only first:**
  - `active_storage_blobs`: key, filename, content_type, metadata JSON text, service_name, byte_size, checksum
    (base64 MD5 by default).
  - `active_storage_attachments`: name, record_type, record_id, blob_id.
  - `active_storage_variant_records`: blob_id, variation_digest.
- **Variants.** Regenerate them lazily on a miss, and only if URL, integrity and rollback requirements permit it.
  Keep old variant URLs resolvable (redirect or regenerate).
- **Django and Laravel.** Django `FileField` stores a relative name under the storage's location prefix
  (`AWS_LOCATION`). Laravel stores a path per disk. Map the column, never re-key the objects.
- **Elixir side.** An owned `Media` context over ex_aws_s3 2.5.9, and LiveView `allow_upload` with `external:`
  for direct uploads. Do not re-implement Active Storage's polymorphic tables as a framework.

## ID Strategy While Both Apps Insert

- **Generate IDs in the database** (identity, `bigserial`, SQLite `INTEGER PRIMARY KEY`). Never compute `max(id) + 1`.
- **UUID keys** can be generated on either side. Match the stored form: native `uuid` on Postgres, text on
  SQLite, `char(36)` or `binary(16)` on MySQL (a custom type under MyXQL).
- **Hibernate sequences.** `pooled`/`pooled-lo` optimizers tolerate external `nextval` writers. Legacy `hilo`
  does not, so verify it per app.
- **Public identifiers.** Keep friendly_id slugs and hashids if URLs expose them. They are wire contracts.
- **Elixir-only tables** may choose freely, but foreign keys into legacy tables must use the legacy PK type.

## The Bidirectional Rollback Test

"Rollback" means the legacy app reads what Elixir wrote. Booting the old image proves nothing.

1. Restore a production-shaped snapshot. Run every Elixir write path through its public API: create, update,
   delete, upload, login, rehash, enqueue.
2. Boot the **pinned** legacy app on the same database and files. Replay its characterization requests: pages,
   API responses, search, attachments, sessions.
3. Assert that the legacy app renders every Elixir-written row. Check timestamp text and precision, enum values,
   STI and polymorphic type strings, counter caches, FTS rows, rich-text bodies, blob metadata and variants, and
   password hashes it can still verify.
4. Run the reverse direction: legacy writes, Elixir reads.
5. Record what rollback loses: sessions minted by Phoenix, Oban jobs the legacy app ignores, Elixir-only tables.
   Make each loss an explicit ADR line with a time boundary. A restored snapshot discards later writes unless
   a replay plan exists.

Run it in CI against a pinned legacy container on every schema-touching change. A failure blocks the
compatibility claim, so it is never an accepted risk by default.
