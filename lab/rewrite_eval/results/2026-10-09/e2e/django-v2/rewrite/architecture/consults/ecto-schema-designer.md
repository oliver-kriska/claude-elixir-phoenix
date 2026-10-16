# Consult: ecto-schema-designer (Conduit, legacy Django schema on ecto_sqlite3)

Scope: answers Q1-Q5 under ADR-000 (ASSUMED): Replacement cutover, schema kept as-is, SQLite, separate ledger, no destructive DDL.
No Ash detected. Evidence: SOURCE `conduit/apps/*/models.py` and `*/migrations/0*.py`; contracts C-01..C-09, C-42, Data Schema Notes, Q2, Q8;
mechanisms M-01, M-12, M-20, M-21, M-24, M-40; kb/data-compat.md; kb/sqlite-on-beam.md; kb/stacks/django.md.
ecto_sqlite3 behaviour checked against the adapter source (local copy 0.22.0: `codec.ex`, `connection.ex`). Re-check it on the pinned version (KB cites 0.25.0).

---

## Q1. Schema mapping: keep a `Profile` schema. Do not fold it into User.

**Recommendation.** Use one Ecto schema per legacy table, with the exact `schema "<table>"` name and integer autoincrement PKs (the Ecto default `:id`). Keep `Profiles.Profile` as a real schema. `articles_article.author_id` and `articles_comment.author_id` are profile ids, so `belongs_to :author, Profile`.

**Why not fold it (Q8).** Folding means one of two things. Either DDL moves `author_id` to user ids, which is destructive and breaks rollback to legacy. Or every query has to translate profile to user through a join. Neither is worth it, because profile ids never reach clients (only comment `id` is exposed). To hide the mismatch, resolve the auth scope once per request: verify the JWT `id` (a user id, C-11), then load the user with its profile using one join. Contexts take `scope.profile_id` for authoring, following and favoriting. Controllers never see the two id spaces.

| Schema | `schema` source | Fields / notes |
|---|---|---|
| `Accounts.User` | `authentication_user` | `username`, `email`, `field :password_hash, :string, source: :password`, `last_login` (nullable, legacy datetime type), `is_superuser`, `is_staff`, `is_active` (all `:boolean`, stored 0/1), timestamps. `has_one :profile, Profile`. Do not map the Django `authentication_user_groups` and `_user_permissions` tables (C-53). |
| `Profiles.Profile` | `profiles_profile` | `belongs_to :user, User`, `bio` default `""`, `image` default `""` (both NOT NULL in the DDL: never write nil), timestamps. `many_to_many :following, Profile, join_through: Follow, join_keys: [from_profile_id: :id, to_profile_id: :id]`. `many_to_many :followers, Profile, join_through: Follow, join_keys: [to_profile_id: :id, from_profile_id: :id]`. `many_to_many :favorites, Article, join_through: Favorite, join_keys: [profile_id: :id, article_id: :id]`. |
| `Profiles.Follow` | `profiles_profile_follows` | `id` (the legacy surrogate PK), `from_profile_id` (follower), `to_profile_id` (followee). No timestamps. Direction: from follows to (M-40, `symmetrical=False`). |
| `Profiles.Favorite` | `profiles_profile_favorites` | `id`, `profile_id`, `article_id`. No timestamps. |
| `Articles.Article` | `articles_article` | `slug`, `title`, `description`, `body`, `belongs_to :author, Profile` (column `author_id` matches the default), timestamps. `has_many :comments`. `many_to_many :tags, Tag, join_through: ArticleTag`. |
| `Articles.Comment` | `articles_comment` | `body`, `belongs_to :article`, `belongs_to :author, Profile`, timestamps. |
| `Articles.Tag` | `articles_tag` | `tag` (display text, case kept), `slug` (= lowercase of `tag`), timestamps. |
| `Articles.ArticleTag` | `articles_article_tags` | `id`, `article_id`, `tag_id`. No timestamps. |

Rules:
- **Join tables get small schema modules**, not string `join_through`. Each join table has its own `id INTEGER PRIMARY KEY AUTOINCREMENT`, and a module gives typed `insert_all` / `delete_all` plus the `on_conflict` writes in Q3. Read through `many_to_many`. Write through the join schema. Never use `put_assoc` / `on_replace` for tags, follows or favorites.
- **Timestamps.** Use `@timestamps_opts [type: Conduit.Ecto.LegacyDateTime, inserted_at: :created_at, autogenerate: {Conduit.Ecto.LegacyDateTime, :utc_now, []}]` on the six timestamped schemas, User included (it inherits `TimestampedModel`). `insert_all` and `update_all` skip autogenerate, so set `created_at`/`updated_at` by hand in those paths. Django `auto_now` updated `updated_at` on every save, and `Repo.update` reproduces that only when the changeset has changes.
- **Ordering (M-12)** is not a schema concern. Put `order_by: [desc: :created_at, desc: :updated_at]` in every list query, and add `desc: :id` as a deterministic tiebreak (an incidental widening).
- **`on_delete`.** The legacy FKs are plain `REFERENCES` with no `ON DELETE CASCADE`, because Django cascaded in Python. ecto_sqlite3 turns `PRAGMA foreign_keys` ON by default, so deleting a parent that still has children now **fails** where legacy silently cascaded. Any delete of an article, profile or user must remove the children explicitly in one transaction: comments, article_tags and favorites, then the article. Today only comment delete exists (C-36 article DELETE is a gap), so the risk is small. Write these paths explicitly when they appear, and set `on_delete: :nothing` explicitly on the `has_many` declarations so nobody expects schema-level cascades. Before relying on this, confirm the real FK clause (and any `DEFERRABLE`) from `sqlite3 .schema` on a legacy-built copy.

## Q2. SQLite datetimes: use a project-owned custom Ecto type, and leave `datetime_type` alone.

**Facts.**
- Django 1.10 on SQLite with `USE_TZ=True` writes `str(naive_utc_datetime)`. Python's `isoformat(' ')` **omits the fraction when microsecond == 0**, so legacy rows mix two widths: `2016-08-28 16:56:40` and `2016-08-28 16:56:40.500000`. This is inferred from Django/Python behaviour. Confirm it with the format scan in Q5.
- Loading already works with the stock types. ecto_sqlite3 decodes through `NaiveDateTime.from_iso8601/1`, which accepts the space separator and an optional fraction. `utc_datetime_decode` then wraps the result as Etc/UTC.
- Writing is the problem. The default `:iso8601` writes `2016-08-28T16:56:41.000000Z`. Under text ordering, `T` (0x54) sorts after ` ` (0x20), so on the same date every port row sorts after every legacy row whatever the real time. `:text_datetime` writes `%Y-%m-%d %H:%M:%S` and drops microseconds, so a port row written at `:41.2` gets the same timestamp as a legacy row at `:41.7` and sorts as older. That is exactly the C-03 witness failure. Both options are global app env, so neither can be scoped to legacy columns.

**Recommendation.** Add `Conduit.Ecto.LegacyDateTime` (`use Ecto.Type`, `type: :string`). It is used on every legacy datetime column: the timestamps, plus `last_login`.
- `load/1`: `NaiveDateTime.from_iso8601/1`, then `DateTime.from_naive!(…, "Etc/UTC")`, then normalise to `microsecond: {us, 6}`. This step matters because a row without a fraction parses with precision 0.
- `dump/1`: always `Calendar.strftime(dt, "%Y-%m-%d %H:%M:%S.%f")`, which gives 6 digits, a space, and no zone.
- `cast/1`: delegate to `Ecto.Type.cast(:utc_datetime_usec, v)`. `utc_now/0`: `DateTime.utc_now()` (already microsecond precision).

**Why it sorts correctly.** Mixed widths still sort correctly as text. A legacy `…:40` is a prefix of a port `…:40.000000` and sorts first, which matches the instants being equal. A legacy `…:40.5` sorts before a port `…:41.000000`. Django can read the always-6-digit form, so a rollback is unaffected. Query parameters such as `where: a.created_at < ^cursor` dump through the field type automatically, so comparisons stay text-consistent. Never compare a legacy column against an untyped `fragment`.

**Risks.**
- Any row in a third format (`T`, `+00:00`, written by other tooling) breaks ordering silently. The Q5 format scan covers this.
- Leave the global `datetime_type` at its default for Ecto-only tables, such as a future Oban or token table. Those values are never compared with legacy columns.
- JSON output format (DRF `…Z` rendering) belongs to the view layer, not this type.

## Q3. Transactions and idempotent writes

Set `default_transaction_mode: :immediate` on the Repo (kb/sqlite-on-beam.md). That takes the write lock at `BEGIN` and avoids SQLITE_BUSY on lock upgrade. Use `Repo.transact/2` with a `with` chain. `Ecto.Multi` is optional. Every row below is a recorded strengthening (M-21: legacy ran in autocommit).

| Operation | Transaction? | Shape |
|---|---|---|
| Register (M-01, C-05) | **Yes** | Insert user (`unique_constraint` on username and email), then insert profile with `bio: ""`, `image: ""`. Both or neither. |
| Update user + profile (PUT /api/user) | **Yes** | User changeset (and password rehash if allowed, C-37), then profile changeset (bio/image). |
| Create article + tags (M-20, C-08, C-09) | **Yes** | (1) Insert the article. On a unique error on `slug`, regenerate the 6-char suffix and retry up to N times. On SQLite a failed statement does not abort the surrounding transaction, so retrying inside `transact` is fine. Return a 4xx after N attempts, never a 5xx. (2) `insert_all(Tag, rows, on_conflict: :nothing)` with `slug: String.downcase(tag)` and explicit timestamps. (3) `from t in Tag, where t.slug in ^slugs`: reuse the existing tag whatever its display casing, which fixes C-08. (4) `insert_all(ArticleTag, pairs, on_conflict: :nothing)`. |
| Update article with tagList (if supported) | **Yes** | Update the article, then `delete_all` the ArticleTag rows for the article, then the same tag upsert. |
| Follow / favorite (M-24) | No (single statement) | `Repo.insert_all(Follow, [%{from_profile_id: me, to_profile_id: them}], on_conflict: :nothing)`. Repeating it is a no-op, and the endpoint still returns its legacy status. Reject a self-follow in the context before the insert (C-38). |
| Unfollow / unfavorite | No | `Repo.delete_all(from f in Follow, where: …)`. Zero rows deleted is fine. |
| Add / delete comment | No | Single insert or delete. Check the article exists in the context (see below). |

Notes:
- **Prefer `on_conflict: :nothing` without `conflict_target` on SQLite.** It emits `ON CONFLICT DO NOTHING`, which applies to any unique constraint. A `conflict_target` must exactly match an existing UNIQUE index or constraint, or SQLite rejects the statement. Django 1.10's M2M uniqueness DDL (inline `UNIQUE(...)` or a named index) has not been verified, and the `.schema` dump would settle it.
- **`returning` returns nothing for skipped rows.** Re-select whatever you need, as step (3) above does.
- **`foreign_key_constraint/3` cannot match on SQLite.** The adapter maps FK errors to `foreign_key: nil`. Check that the parent exists (article by slug, profile by username) in the context and return 404. Also handle `Ecto.ConstraintError` as a backstop.

## Q4. Separate ledger and baseline migration

**Config.** Set `config :conduit, Conduit.Repo, migration_source: "ecto_schema_migrations"`. Never read or write `django_migrations` (C-42). A rollback boots Django against it unchanged.

**Baseline: one idempotent migration that replays the legacy DDL verbatim with `IF NOT EXISTS`.** Do not use Ecto `create table`.
- Source the DDL: `sqlite3 legacy.db .schema` for the 8 tables and their indexes, from a DB built by the 10 legacy migrations on an isolated copy (needs the user's permission, contracts Q7). Paste it into `execute/1` statements with `CREATE TABLE IF NOT EXISTS` and `CREATE [UNIQUE] INDEX IF NOT EXISTS`, keeping **Django's index names** (the hash-suffixed ones).
- On a fresh dev or test DB this creates a schema byte-identical to legacy: the same non-cascading FKs, the same unique indexes. Tests then exercise production DDL, not an Ecto approximation.
- On an imported legacy DB every statement is a no-op, so no DDL runs. The baseline version is recorded in `ecto_schema_migrations` on its own, with no manual ledger insert.
- `down/0`: raise `Ecto.MigrationError` (irreversible). Never drop legacy tables.

**Why not Ecto's `create_if_not_exists table/index`.** Ecto produces different DDL (types, FK clauses), so dev would drift from production. Its index names differ from Django's, so `create_if_not_exists index` on a legacy DB creates **duplicate indexes**: DDL against live data, which breaks the "no DDL at cutover" intent.

**Why not the KB's "record as applied without executing".** It needs a manual ledger insert on the production file. Fresh DBs would then need a separate code path. `IF NOT EXISTS` gives one path for both.

**Risk: `IF NOT EXISTS` hides drift.** A legacy table that differs, from a hand edit or an unapplied migration, is accepted silently. Mitigate with a preflight in the release `migrate` task. If `django_migrations` exists, assert that it contains the 10 expected app migrations, and compare the `sqlite_master.sql` text for the 8 tables against the baseline. Refuse to start on a mismatch. Later migrations are additive only until the rollback window closes (ADR-000). SQLite `ALTER TABLE` limits mean rehearsing them on a copy.

## Q5. Pre-cutover data scans and constraints the changesets must mirror

Run these read-only scans on a copy of `db.sqlite3`. Each must return 0 rows, or have a recorded decision.

| Scan | SQL sketch | Why |
|---|---|---|
| Orphans (all FKs) | `PRAGMA foreign_key_check;` plus explicit LEFT JOINs: article→profile, comment→article/profile, follows→profile (both columns), favorites→profile/article, article_tags→article/tag, profile→user | FKs were never enforced (Django < 2.2) and CASCADE ran in Python. Orphans become `nil` preloads, which crash the views. Also, once FKs are ON, deleting a parent with orphan-adjacent children fails. |
| Users without a profile (C-05) | `user LEFT JOIN profile … WHERE p.id IS NULL` | The scope loader assumes exactly one. Backfill (additive insert, `bio=''`, `image=''`) or fail fast. |
| Self-follows (C-38) | `WHERE from_profile_id = to_profile_id` | The port rejects new ones. Decide whether existing rows stay (harmless) or are deleted (destructive, so it needs an ADR). |
| Case-variant emails / usernames (C-04) | `GROUP BY lower(email) HAVING count(*) > 1` (same for username) | Only blocks a move to case-insensitive matching. Under the kept exact-match policy it is informational. |
| Oversize values (C-07) | `length(slug) > 50 OR length(tag) > 255` (tag); `length(slug) > 255` (article); username > 255, email > 254, image > 200 | SQLite never enforced varchar. The port must load and serve these values, so **do not** apply `validate_length(:slug, max: 50)` to tags (new tags only, if ever). |
| Tag slug drift | `WHERE slug <> lower(tag)` | The port's reuse-by-slug lookup assumes `slug = lower(tag)`. Python `.lower()` and `String.downcase/1` differ on a few Unicode cases, so list the non-ASCII tags. |
| Datetime format (C-03) | `WHERE created_at NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]*' OR created_at GLOB '*[TZ+]*'` (all datetime columns) | Confirms the two widths, which the custom type relies on. |
| Password hashes (C-02) | `WHERE password NOT LIKE 'pbkdf2_sha256$%'` | Unusable (`!`) hashes or other algorithms need an explicit path. |
| Empty / malformed article slugs (C-06) | `WHERE slug = '' OR slug IS NULL` | Must stay routable, or be documented. |

**Constraints the changesets must mirror.** These are checked against the ecto_sqlite3 source. On SQLite the adapter **derives** the constraint name from the error text `UNIQUE constraint failed: table.col[, table.col]` as `<table>_<col>[_<col>]_index`. Django's real (hash-suffixed) index names therefore never reach Ecto, and Ecto's default names already match. This is the opposite of the Postgres advice in kb/stacks/django.md. Still pass `name:` explicitly so the dependency is visible and greppable:
- User: `unique_constraint(:username, name: "authentication_user_username_index")`, `unique_constraint(:email, name: "authentication_user_email_index")`.
- Profile: `unique_constraint(:user_id, name: "profiles_profile_user_id_index")`.
- Article: `unique_constraint(:slug, name: "articles_article_slug_index")`. Drive the slug retry (C-09) off this error.
- Tag: `unique_constraint(:slug, name: "articles_tag_slug_index")`, only if tags are ever inserted through a changeset. The `insert_all` path relies on `on_conflict`.
- Pair uniques (follows, favorites, article_tags) are handled by `on_conflict: :nothing`, not changesets.
- Validations that mirror legacy: username and email required; email lowercased only in the domain part (`normalize_email`, C-04), with exact-case equality kept; username max 255, email max 254, title max 255, generated slug max 255; `bio`/`image` cast `nil` to `""`. Do not add URL validation to `image` (legacy did not validate on the API path).
- No `foreign_key_constraint/3`: check parent existence in the context (Q3).

## Open items to confirm on a legacy-built DB (needs Q7 permission)

1. The exact `.schema` text: FK clauses (`ON DELETE`, `DEFERRABLE`), and whether M2M pair uniqueness is an inline `UNIQUE(...)` or a named index.
2. Mixed-width datetime text in real rows.
3. The ecto_sqlite3 version pin: re-verify `constraint_name_hack`, `datetime_type` and the decode path (0.22.0 was read; the KB cites 0.25.0).
