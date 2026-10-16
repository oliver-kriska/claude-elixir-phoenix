# Consult: Ecto schema designer: mapping the Prisma schema unchanged

**Scope:** answers Q1-Q5 under ADR-000: Replacement cutover, schema kept as-is, no DDL during the observation window, rollback to Node must keep working. This consult does not plan or implement anything. Snippets show shapes only.
**Ash check:** not applicable. The target is greenfield Ecto, and the legacy app uses Prisma 4.16.1 (`package.json:17,53`).
**SOURCE root:** `testbeds/node-express-realworld/src`. `S:` = that root.

---

## Q1. Mapping tables, columns, timestamps and ids unchanged

### Tables and columns (C-01, M-17), confidence: high

- `schema "User"`, `"Article"`, `"Comment"`, `"Tag"`. Ecto/Postgrex always quote identifiers, so the reserved word `User` and mixed case both work. Do not set `@schema_prefix` (everything lives in `public`).
- Use snake_case field names with `source:`. Then the code stays idiomatic and the DB stays camelCase:
  `field :author_id ... source: :authorId` (via `belongs_to :author, User, source: :authorId`), and the same for
  `articleId`. Every column is `TEXT`, so map them all as `:string`. Add no length validations the legacy app does not have.
- `belongs_to` accepts `source:`. For example `belongs_to :author, App.Accounts.User, source: :authorId` makes the field
  `author_id` with the column `"authorId"`.

### SERIAL int4 ids (C-06), confidence: high

- Keep the default `@primary_key {:id, :id, autogenerate: true}`. Ecto omits `id` on insert, `nextval('"Article_id_seq"')` fires, and Ecto reads the id back via `RETURNING`. Both runtimes share the sequence, so a rollback causes no collision.
- `:id` and `belongs_to` foreign keys are `:id`, which is compatible with int4 (the values fit). Never compute ids yourself.
- Do **not** use `:binary_id`. Future Elixir-only tables that point at legacy tables need `:integer` / `:id` FKs.

### TIMESTAMP(3) without time zone (C-04), confidence: high

Source: `S:prisma/migrations/20210924225358_initial/migration.sql`, where `"createdAt"`/`"updatedAt"` are `TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP`. Prisma 4 writes UTC wall-clock values into these columns.

**Use `:utc_datetime_usec`, not `:naive_datetime_usec`.**
- Postgrex returns a `NaiveDateTime` for `timestamp`. Ecto's `:utc_datetime*` load treats it as UTC, and dump writes the UTC wall clock. That matches what Prisma reads and writes. This is the same pairing Phoenix generators use (`timestamp without time zone` + `:utc_datetime`).
- `:naive_datetime_usec` matches the column type literally, but it invites timezone bugs at every call site and gives no benefit here.
- Use `_usec` rather than `:utc_datetime`, because `:utc_datetime` truncates to whole seconds and would discard the legacy milliseconds on read.

**Millisecond fidelity, write side.** Postgres **rounds** (it does not truncate) usec to the `(3)` precision. If Ecto writes `.123500`, the DB stores `.124`, while the struct in memory and the response still say `.123500`. So:
- Generate timestamps already at ms granularity, but still at precision 6. `:utc_datetime_usec` dump raises on precision != 6, so a plain `DateTime.truncate(:millisecond)` result cannot be stored directly. Shape: `App.Compat.Time.now_ms/0` returns `%{dt | microsecond: {div(us, 1000) * 1000, 6}}`. Wire it in with
  `timestamps(... autogenerate: {App.Compat.Time, :now_ms, []})`, and use the same function for the forced `updated_at`.
  The alternative is a tiny custom `Ecto.Type` over `:utc_datetime_usec` that floors to ms on `dump/1`. Either works. The custom type also protects against hand-built values.

**Millisecond fidelity, JSON side (M-19, C-20).** The legacy app emits `JSON.stringify(Date)`, which always gives 3 fractional digits plus `Z` (`2021-09-24T22:53:58.000Z`). Elixir: `dt |> DateTime.truncate(:millisecond) |> DateTime.to_iso8601()`. Loaded values have precision 6, and `truncate` sets precision 3, so `.000` still prints and the suffix is `Z`. Put this in the JSON view helper. Do not rely on `Jason.Encoder` for `DateTime`, which would print 6 digits.

**DB-default trap.** For a `timestamp` column, `CURRENT_TIMESTAMP` is evaluated in the **session** `TimeZone`. If the server or DB default timezone is not UTC, any row created by the DB default stores local time. Mitigations, all cheap and none of them DDL:
- Set `parameters: [timezone: "UTC"]` in the Repo config, so Ecto sessions are UTC.
- Have Ecto always send `createdAt`/`updatedAt` explicitly (via autogenerate) instead of relying on the DB default.
- Rehearsal check: `SHOW timezone;` on the prod snapshot, then compare `createdAt` of a fresh legacy-created row against wall-clock UTC.

### `updatedAt` (runtime Q4, M-33), confidence: high

- Prisma declares `updatedAt DateTime @default(now())` with **no `@updatedAt`** (`S:prisma/schema.prisma:18,28`). No DB trigger exists.
- The legacy code sets it in exactly one place: `updateArticle` → `updatedAt: new Date()` (`S:app/routes/article/article.service.ts:354`). That call happens on **every** successful PUT, even one that only sends `tagList` or sends no truthy field.
- Comments are never updated (no update path). `User` has no timestamp columns. Favorite and follow writes touch only join tables, so `Article.updatedAt` does not change.
- **Ecto mapping:** `timestamps(inserted_at: :created_at, inserted_at_source: :createdAt, updated_at: :updated_at, updated_at_source: :updatedAt, type: :utc_datetime_usec, autogenerate: {App.Compat.Time, :now_ms, []})` on `Article` and `Comment`. On insert, both get the same value. That matches legacy closely enough: Prisma's `now()` default fills both within the same statement.
- **Trap:** Ecto updates `updated_at` automatically only when the changeset has changes. A PUT with `{tagList: [...]}` only, or with all-falsy fields, would leave `updatedAt` untouched, while the legacy app bumps it. So the article update changeset must call `force_change(:updated_at, App.Compat.Time.now_ms())` unconditionally. Golden test: `PUT {article:{}}` changes `updatedAt` and keeps `createdAt`.
- **`User.image`:** declare `field :image, :string, read_after_writes: true`, and do not give it an Ecto default. On insert, Ecto does not send nil struct fields, so the DB default (`https://api.realworld.io/...`, migration `20211105153605_api_url`) applies, and `RETURNING` brings the value back for the response (C-07). `field :demo, :boolean, default: false`, and the register changeset never casts `demo` (C-08). Do not cast it from params.

---

## Q2. Implicit m2m join tables `_ArticleToTag`, `_UserFavorites`, `_UserFollows`

### Facts from SOURCE (C-03, M-16)

| Table | A → | B → | Indexes | Source |
|---|---|---|---|---|
| `_ArticleToTag` | `Article.id` | `Tag.id` | `_ArticleToTag_AB_unique` (A,B), `_ArticleToTag_B_index` | `migrations/20211001143221_implicit_tags` |
| `_UserFavorites` | `Article.id` | `User.id` | `_UserFavorites_AB_unique`, `_UserFavorites_B_index` | `migrations/20210924225358_initial` |
| `_UserFollows` | `User.id` | `User.id` | `_UserFollows_AB_unique`, `_UserFollows_B_index` | `migrations/20210924225358_initial` |

There is no PK and no timestamps, and every FK is `ON DELETE CASCADE ON UPDATE CASCADE`. For two distinct models, Prisma assigns A to the model that sorts first (`Article` < `Tag`, `Article` < `User`), and the FKs above confirm that.

### Ecto mapping, confidence: high (except the `_UserFollows` direction)

`join_keys` is `[{join_col_for_owner, owner_pk}, {join_col_for_related, related_pk}]`. Write the keys as atoms `:A` / `:B`; Ecto quotes them as `"A"` / `"B"`.

```elixir
# Article
many_to_many :tags, Tag, join_through: "_ArticleToTag", join_keys: [{:A, :id}, {:B, :id}], on_replace: :delete
many_to_many :favorited_by, User, join_through: "_UserFavorites", join_keys: [{:A, :id}, {:B, :id}]
# Tag
many_to_many :articles, Article, join_through: "_ArticleToTag", join_keys: [{:B, :id}, {:A, :id}]
# User
many_to_many :favorites, Article, join_through: "_UserFavorites", join_keys: [{:B, :id}, {:A, :id}]
many_to_many :followers, User, join_through: "_UserFollows", join_keys: [{:A, :id}, {:B, :id}]  # = Prisma followedBy (see below)
many_to_many :following, User, join_through: "_UserFollows", join_keys: [{:B, :id}, {:A, :id}]  # = Prisma following
```

Writes:
- For follow, unfollow, favorite and unfavorite, prefer schemaless `Repo.insert_all("_UserFollows", [%{A: a, B: b}], on_conflict: :nothing, conflict_target: [:A, :B])` and `Repo.delete_all` over `put_assoc`. This reproduces Prisma's idempotent `connect`/`disconnect` (calling twice is a no-op), avoids preloading whole lists, and needs no join schema.
- Reads (`following`, `favorited`, `favoritesCount`, feed) should use `EXISTS` / `count` subqueries on the join table instead of preloading lists (M-19).
- An optional join schema module (`@primary_key false`, `schema "_UserFollows"`, `field :A, :id` ...) is fine if the team wants typed `insert_all`. It is not required.

### Which `_UserFollows` column is the follower?

**The schema.** `S:prisma/schema.prisma`, `model User`:
```
followedBy User[] @relation("UserFollows")
following  User[] @relation("UserFollows")
```
Both fields belong to the same relation `"UserFollows"` on the same model, so the model-name rule ties.

**Prisma's rule for implicit m-n.** The two relation fields are ordered by (model name, then relation-field name). The first one is field "A", and the ids of the model owning field A are stored in column `A`. You can see this in the two-model case: `Article.tagList` is field A, and column A holds Article ids. For the self-relation the tie-break is the field name: `"followedBy"` vs `"following"`. The common prefix is `"follow"`, then `'e'` (0x65) < `'i'` (0x69), so **`followedBy` is field A**.

**What it means.**
- `X.followedBy` reads `SELECT "B" FROM "_UserFollows" WHERE "A" = X`.
- The legacy follow path is `prisma.user.update({where:{username: target}, data:{followedBy:{connect:{id: currentUser}}}})` (`S:app/routes/profile/profile.service.ts:22-36`). It inserts `(A = target, B = currentUser)`.
- Therefore **A = the followed user, B = the follower**.
- Consistent reads: `following` flag = `followedBy.some(id === viewer)` (`S:app/routes/profile/profile.utils.ts:8-9`) → `EXISTS(... WHERE "A" = profile.id AND "B" = viewer.id)`. Feed = `author.followedBy some {id: viewer}` (`S:app/routes/article/article.service.ts:117,125`) → articles whose `authorId` is in `SELECT "A" FROM "_UserFollows" WHERE "B" = viewer`.
- The legacy code never uses the `following` field; only `followedBy` appears. A wrong direction would therefore invert every `following` flag and every feed (C-03 failure mode).

**Confidence: medium (~70-75%).** The reasoning follows Prisma's documented ordering convention, but I have not checked the tie-break direction against Prisma 4.16.1 engine source. The seed (`S:prisma/seed.ts`) creates no follows, so the data cannot confirm it either. Treat this as a blocking verification before porting the profile and feed slices.

**Scratch-DB check (decisive, about 5 minutes, never against prod):**
1. Start Postgres and run the pinned legacy image (`30b68e1`, Prisma 4.16.1) with `prisma migrate deploy` against a scratch DB. Set `DEBUG=prisma:query` or Prisma `log: ['query']`.
2. Register users X and Y through the API. With X's token, call `POST /api/profiles/Y/follow`.
3. Run `SELECT "A","B" FROM "_UserFollows";`. Expected: `A = Y.id`, `B = X.id`. The query log should show `INSERT INTO "public"."_UserFollows" ("A","B") VALUES (Y, X) ON CONFLICT DO NOTHING`.
4. Cross-check: `GET /api/profiles/Y` as X → `following: true`. `GET /api/articles/feed` as X lists Y's articles.
5. Freeze it as a golden fixture: the port test inserts `(A=Y, B=X)` and asserts the same two responses. Run the same check in the reverse (port-writes, Node-reads) rollback test.

If step 3 shows the opposite, swap the `join_keys` of `followers` and `following`. Nothing else changes.

---

## Q3. Constraint names and FK cascade expectations

### Unique constraints (C-05, M-25, R-12), confidence: high

The initial migration created `"Article.slug_unique"`, `"User.email_unique"`, `"User.username_unique"` and (in migration 2) `"Tag.name_unique"`. **Migration `20211221184529_deprecated_preview` renamed them** to:

| Constraint/index | Changeset |
|---|---|
| `User_email_key` | `unique_constraint(:email, name: "User_email_key", message: "has already been taken")` (use the C-18 legacy wording) |
| `User_username_key` | `unique_constraint(:username, name: "User_username_key", ...)` |
| `Article_slug_key` | `unique_constraint(:slug, name: "Article_slug_key")`, with the error placed on `:title` / `"must be unique"` to match `article.service.ts:190,330` |
| `Tag_name_key` | not used in a changeset. Tags are upserted with `on_conflict: :nothing, conflict_target: :name` (Q4) |
| `_ArticleToTag_AB_unique`, `_UserFavorites_AB_unique`, `_UserFollows_AB_unique` | not in changesets. Writes use `on_conflict: :nothing` |

- Ecto's default name would be `User_email_index`, which would not match. Always pass `name:`.
- These are UNIQUE INDEXes, not table constraints. Postgres still reports the index name as the `constraint` in the error, so `unique_constraint` matches it.
- Uniqueness is case-sensitive (plain TEXT, no citext, no lower() index). Do not downcase in changesets.
- Behaviour note for the C-19 owner: the legacy app pre-checks with SELECTs (`auth.service.ts:9-30`, `article.service.ts:180-191`), so the **race loser gets a Prisma 500**. Mapping the constraint to 422 changes only that race-loser response. I recommend keeping the pre-check (same messages on the happy path) plus `unique_constraint` as the safety net, and recording the 500→422 race delta as an accepted improvement.

### Foreign keys and cascades (C-09), confidence: high

- The FKs were created unnamed in the initial migration, so Postgres auto-named them `<table>_<column>_fkey`. Migration 2 confirms the convention: it drops `"ArticleTags_articleId_fkey"`. Expected names: `Article_authorId_fkey`, `Comment_articleId_fkey`, `Comment_authorId_fkey`, `_ArticleToTag_A_fkey`, `_ArticleToTag_B_fkey`, `_UserFavorites_A_fkey`, `_UserFavorites_B_fkey`, `_UserFollows_A_fkey`, `_UserFollows_B_fkey`. Verify them with `\d "Comment"` on the snapshot.
- Changesets: `foreign_key_constraint(:article_id, name: "Comment_articleId_fkey")` on comment create. That covers the "article deleted between lookup and insert" race. Legacy returns 500 there, so map it to the legacy 404 or leave it as 500 per C-19, explicitly. Pass `name:`, because Ecto's default name derivation from the field and source should not be trusted with camelCase sources.
- `has_many :comments, Comment, on_delete: :nothing` and `has_many :articles ... on_delete: :nothing`, each with a comment saying "DB cascades (C-09)". Do **not** use `:delete_all`. Ecto would issue its own redundant DELETEs, which duplicates the DB rule (C-09 says the port must not duplicate or contradict it). `ON UPDATE CASCADE` does not matter because ids never change.
- Article delete = one `Repo.delete`. The DB removes comments, `_ArticleToTag` rows and `_UserFavorites` rows. `"Tag"` rows stay as orphans, which is legacy behaviour; do not clean them up.

---

## Q4. Atomic article update that keeps C-27 bug-for-bug

**Legacy behaviour** (`S:app/routes/article/article.service.ts:276-383`, M-14):
1. Look up the article by slug → 404 `{}`. Not the author → 403.
2. If `title` is truthy: `newSlug = slugify(title)-userId`. If it differs and is taken → 422 `title: must be unique`.
3. `tagList` = the list if it is a non-empty array, else `[]`.
4. **Statement 1:** `tagList: {set: []}`, which wipes every tag link.
5. **Statement 2:** update the truthy `title`/`body`/`description`, `slug` if a new one exists, `updatedAt = now`, and `connectOrCreate` each tag.

No transaction wraps steps 4 and 5. Prisma wraps only each nested write.

**Recommended shape:** one `Ecto.Multi`, so the SQL footprint stays explicit and reviewable.

```elixir
names = if is_list(attrs["tagList"]) and attrs["tagList"] != [], do: Enum.uniq(attrs["tagList"]), else: []

Ecto.Multi.new()
|> Multi.run(:article, fn repo, _ ->            # lock + 404/403 checks
     ArticleQuery.by_slug(slug) |> lock("FOR UPDATE") |> repo.one() |> check_owner(user_id) end)
|> Multi.run(:slug, fn repo, %{article: a} -> new_slug_or_422(repo, a, attrs, user_id) end)   # pre-check, legacy message
|> Multi.delete_all(:clear_tags, fn %{article: a} ->               # C-27: ALWAYS wipe
     from(j in "_ArticleToTag", where: field(j, :A) == ^a.id) end)
|> Multi.run(:tags, fn repo, _ -> upsert_tags(repo, names) end)  # insert_all(Tag, ..., on_conflict: :nothing,
                                                                  #   conflict_target: :name) + select ids by name
|> Multi.insert_all(:link_tags, "_ArticleToTag",
     fn %{article: a, tags: tags} -> for t <- tags, do: %{A: a.id, B: t.id} end,
     on_conflict: :nothing)
|> Multi.update(:updated, fn %{article: a, slug: s} ->
     a |> Article.update_changeset(attrs, s)          # cast only truthy title/body/description (C-27)
       |> force_change(:updated_at, App.Compat.Time.now_ms())   # Q1 trap
       |> unique_constraint(:slug, name: "Article_slug_key") end)  # race loser → error on :title
|> Repo.transaction()
```

After this, reload with tags / author / flags for the mapper, preferably in the same transaction or right after.

**Properties:**
- **Bug-for-bug:** with no `tagList`, `[]`, or a non-array value, the result is zero tags. A non-empty list replaces the set. Falsy fields are not changed. `updatedAt` is always bumped. 404/403/422 come out in the legacy order.
- **Atomic:** if the slug race or any DB error occurs after the wipe, everything rolls back and the tags survive. The legacy app would lose them. This deviation is invisible on every successful path. Record it as an accepted improvement under the M-14 REPLACE disposition; it is not a contract change.
- `Enum.uniq` + `on_conflict: :nothing` reproduce Prisma's idempotent `connectOrCreate` for duplicate names in one request. The upsert-then-select also fixes the M-15 concurrent new-tag 500 (`Tag_name_key`).
- `FOR UPDATE` serialises concurrent PUTs to the same article. Legacy has no lock, and nothing observable on the success path depends on its absence.
- Tag names are stored raw: no trim, no downcase (contracts.md Data Schema Notes). Non-string entries made Prisma raise a 500 in legacy. Decide explicitly whether to keep that 500 or reject with 422. That is the C-19 owner's call.

**Acceptable alternative:** `put_assoc(:tags, upserted_tags)` with `on_replace: :delete` on the preloaded article. It wipes only the removed links (a diff), not all of them, but the end state is identical, including `[]` → wipes all. Tags must be upserted first, so it still needs `Repo.transact/2` around upsert + update. Prefer the Multi: it mirrors the legacy two-step clearly and does not need the preload.

**Create (`createArticle`, lines 162-239):** use the same Multi without the clear step: insert article → upsert tags → `insert_all` links. A missing or non-array `tagList` gives no tags.

---

## Q5. Ecto migration authority while `_prisma_migrations` stays untouched

### During the observation window: Ecto runs zero DDL (C-10, M-25, ADR-000), confidence: high

- Keep `priv/repo/migrations/` **empty** and put no `Ecto.Migrator` child in the supervision tree. The release `App.Release.migrate/0` must not be wired into the start command or overlay. Even a migration-less `Ecto.Migrator.run` **creates `schema_migrations`**, which is DDL.
- Belt and braces: `App.Release.migrate/0` refuses to run unless `ECTO_DDL_OWNER=true` (an env var flipped only at the baseline milestone), and logs why.
- Set `migration_source: "ecto_schema_migrations"` in the Repo config now. It does not collide with `_prisma_migrations` and makes ownership obvious later. `prisma migrate deploy` ignores unknown tables, so the table would not break a rollback even if it appeared. ADR-000 still forbids creating it during the window.
- Never point `mix ecto.create/drop/reset` at shared environments.
- **Test/dev DB without Ecto DDL:** generate `priv/repo/structure.sql` once. Apply the 4 Prisma SQL migrations (or `prisma migrate deploy` from the pinned image) to a scratch DB, then run `pg_dump --schema-only`, including `_prisma_migrations` and its rows (dump that table's data too). Test alias: `["ecto.create --quiet", "ecto.load --skip-if-loaded --quiet", "test"]`. Run a CI drift check: `pg_dump --schema-only` of the scratch DB vs the committed `structure.sql`.
- Rollback rehearsal must show `prisma migrate status` = "Database schema is up to date" on the DB Elixir has been writing to (C-10 witness).

### Baseline migration (after rollback retires), conceptual, confidence: high

- One migration, e.g. `priv/repo/migrations/<ts>_baseline_prisma_schema.exs`, with `@disable_ddl_transaction false`.
- `up/0`:
  1. If `to_regclass('public."User"')` is NULL (fresh environment): `execute(File.read!(priv/repo/baseline.sql))`. That file is the frozen `structure.sql` minus `_prisma_migrations`. It has the same table, index and FK names as listed in Q3, and the `User.image` default is the api.realworld.io URL.
  2. Otherwise (existing prod/staging DB): **assert, don't create**. Check that the four tables and three join tables exist and that the constraint and index names (`User_email_key`, ..., `_UserFollows_AB_unique`, the `*_fkey` names) exist via `pg_indexes` / `pg_constraint`. Raise with a diff on any mismatch. This blocks owning a drifted schema.
- `down/0`: `raise Ecto.MigrationError, "baseline is irreversible"`.
- Running it records its version in `ecto_schema_migrations`. That is the one DDL-free "record as applied" step on existing DBs. Creating the table itself happens here, after the window.
- **Leave `_prisma_migrations` in place.** Dropping it is a later contract step, after Node and the Prisma CLI are retired for good. From the baseline on, the Prisma CLI must never run against this DB. Remove `npx prisma migrate deploy` from every deploy path at the same milestone (C-38).
- Later migrations keep the quoted legacy names (`alter table("Article")`, `add :someCol ...`). New FKs into legacy tables use `references("User", type: :integer, on_delete: ...)`. A snake_case rename is a separate expand→contract decision (ADR-000 Data).

---

## Open verifications (blocking or rehearsal)

1. `_UserFollows` A/B direction: scratch-DB check in Q2. Blocks the profile and feed slices.
2. `SHOW timezone` on the prod snapshot, plus a check of a legacy-created `createdAt` against UTC (Q1).
3. Actual FK constraint names via `\d` on the snapshot (Q3). Expected `<table>_<col>_fkey`.
4. A golden test that `PUT {article:{}}` returns `tagList: []` and bumps `updatedAt` (Q1 + Q4).
5. The C-19 owner decides on race-loser and non-string-tag responses (500 vs 422).
