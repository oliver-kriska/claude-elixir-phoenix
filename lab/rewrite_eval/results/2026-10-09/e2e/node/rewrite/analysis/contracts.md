# Contracts — node-express-realworld (Conduit API)

Source: `testbeds/node-express-realworld` @ `30b68e1` · Contracts: data 11 / wire 25 / operational 4 (40 total)

Pinned library versions (package-lock.json): express 4.18.2, express-jwt 8.4.1, jsonwebtoken 9.0.2,
bcryptjs 2.4.3, slugify 1.6.6, cors 2.8.5, @prisma/client 4.16.2. Contract behaviour below follows from
these versions. Re-check if the lockfile changes.

Paths are relative to SOURCE. `S:` = `src/app/routes/`.

Legacy test strength: the unit tests in `src/tests/services/*` mock Prisma, and most error assertions
compare against `String({...})`, which is `"[object Object]"`. So they pin only that an error is thrown,
never its body or status. The single e2e test (`e2e/src/server/server.spec.ts`) expects
`{message:'Hello API'}` from `GET /`, but the app returns something else, so the test is stale and fails.
**No HTTP-level behaviour is pinned by a passing legacy test.** Every witness below has to be built as a
characterization test against a pinned legacy build.

## Contract Register

### Data

| ID | Surface | Assertion | Consumers | Break cost | Witness (probe) | Legacy test | Anchor |
|----|---------|-----------|-----------|------------|-----------------|-------------|--------|
| C-01 | data | The port reads and writes the existing tables. Names are quoted PascalCase (`"User"`, `"Article"`, `"Comment"`, `"Tag"`) and columns are camelCase (`"createdAt"`, `"authorId"`, `"articleId"`). Every legacy row loads in the port, and the legacy app loads every row the port writes | existing Postgres data, rollback path | data migration or downtime. Rollback impossible if renamed | load a prod-shaped snapshot. Port reads every row of each table with no cast errors. Legacy app (pinned) serves rows the port inserted (bidirectional rollback test) | none | src/prisma/schema.prisma, migrations/20210924225358_initial |
| C-02 | data | Existing password hashes keep verifying. Format: bcryptjs `$2a$10$...` (cost 10). The plaintext is `.trim()`med before hashing on register and before compare on login | every user | password reset for all users | fixture: hash made by bcryptjs 2.4.3 of `" pw "` trimmed → port login with `"pw"` and with `" pw "` both succeed. Wrong password fails. Hash created by port verifies in legacy `bcrypt.compare` | auth.service.test.ts:173 (mocked, weak) | S:auth/auth.service.ts:64,102,121 |
| C-03 | data | Implicit many-to-many tables keep Prisma semantics. `_ArticleToTag` (A→Article.id, B→Tag.id), `_UserFavorites` (A→Article.id, B→User.id), `_UserFollows` (A,B both →User.id). Unique index on (A,B), no PK. **Which `_UserFollows` column is the follower must be confirmed from data** | follow graph, favorites, tags of every article | follow direction inverted = every feed and `following` flag wrong | legacy: user X follows Y via API, then read the `_UserFollows` row. Port: `GET /profiles/Y` as X → `following:true`, X's feed holds Y's articles. Port-written follow → legacy sees the same | none | migrations/20211001143221_implicit_tags, initial (lines for `_UserFavorites`/`_UserFollows`) |
| C-04 | data | Timestamps are `TIMESTAMP(3)` without time zone and hold UTC (Prisma convention), with millisecond precision. `updatedAt` has no `@updatedAt`: only article update sets it (`new Date()`). Comment `updatedAt` never changes | all API clients (dates shown), rollback | wrong times (timezone shift), or microsecond values that legacy truncates differently | port insert, then legacy read: same instant to the ms. Port JSON prints ms precision with `Z` (see C-20). Updating an article changes `updatedAt` and keeps `createdAt` | none | migrations/initial `TIMESTAMP(3)`. S:article/article.service.ts:354 |
| C-05 | data | Unique constraints are case-sensitive and enforced by the DB: `User_email_key`, `User_username_key`, `Article_slug_key`, `Tag_name_key`. The port maps violations to the legacy 422 bodies (C-18) using these constraint names | registration, article create, tag create | duplicate accounts, or 500s instead of 422 | register `a@x` then `A@x` → both succeed (case-sensitive). Duplicate exact email → 422 `has already been taken`. Ecto `unique_constraint(..., name: "User_email_key")` maps | auth.service.test.ts:77 (weak) | migrations/20211221184529_deprecated_preview |
| C-06 | data | PKs are `SERIAL` int4 from DB sequences (`"Article_id_seq"`, etc.). During coexistence both apps insert through the sequence. Comment ids show up in URLs (C-26) and user ids show up in slugs (C-11) | coexistence writers, comment delete URLs | PK collisions if the port computes ids | interleave inserts from legacy and port → no duplicate-key errors. Ids increase monotonically | none | migrations/initial |
| C-07 | data | `User.image` DB default is `https://api.realworld.io/images/smiley-cyrus.jpeg` (Prisma default the same). Rows created before migration `20211105153605` may hold `https://realworld-temp-api.herokuapp.com/images/smiley-cyrus.jpeg`. `bio` is nullable, so `null` is emitted as JSON `null` | front-ends rendering avatars | broken avatars, or a changed default for new users | register without image → `image` equals the legacy default string exactly. `bio` → `null`. Count snapshot rows still on the herokuapp URL | profile.utils.test.ts:5 (mapper only) | schema.prisma `image @default`. migrations/20211105153605_api_url |
| C-08 | data | `User.demo` boolean (default false) is set true only by the seed script. Register forces `demo:false`. The flag drives content visibility (C-23) | visibility rule, seeded demo content | all non-demo content becomes public, or demo content disappears | register via API → `demo=false` even if the body sends `demo:true`. Seeded users `demo=true` | none | S:auth/auth.controller.ts:15. src/prisma/seed.ts:22 |
| C-09 | data | FK actions are `ON DELETE CASCADE ON UPDATE CASCADE`. Deleting an article removes its comments, favorites and tag links. Tags stay behind as orphans. No API deletes users, but a manual user delete cascades to articles, comments, follows and favorites | operators, article delete | orphan rows or FK errors on delete | delete an article with comments, favorites and tags → those rows are gone and the `"Tag"` rows remain. Port-side `on_delete` must not duplicate or contradict the DB | none | migrations/initial `AddForeignKey` |
| C-10 | data | `_prisma_migrations` is the schema history table. While legacy owns DDL, `npx prisma migrate deploy` must keep working. Ecto must not create or drop tables Prisma tracks, and must not run a second migration authority on the same tables | operators, rollback path | broken `migrate deploy`, drift, failed rollback | after the Ecto baseline is recorded (not executed), `prisma migrate status` on the same DB reports "up to date". Ecto uses its own `schema_migrations`-style table | none | src/prisma/migrations/migration_lock.toml |
| C-11 | data | Slugs are stored as `slugify(title) + "-" + authorId`, using slugify 1.6.6 defaults: case is **preserved** (not lowercased), spaces become `-`, its charMap applies (e.g. `&`→`and`, `$`→`dollar`, accented letters transliterated), and `$*_+~.()'"!:@` are kept (non-strict). Existing slugs stay byte-for-byte. New slugs from the port must equal what legacy would produce for the same title and author | bookmarked/shared article URLs, uniqueness check | slugs from the two apps diverge. Duplicates slip past the "must be unique" check | golden table of about 30 titles (ASCII, mixed case, punctuation, `&`, emoji, accented letters, CJK) run through slugify 1.6.6 offline vs the port's slug function → identical | none | S:article/article.service.ts:178,317 |

### Wire

| ID | Surface | Assertion | Consumers | Break cost | Witness (probe) | Legacy test | Anchor |
|----|---------|-----------|-----------|------------|-----------------|-------------|--------|
| C-12 | wire | A JWT minted by the legacy app authenticates the same user in the port. HS256, secret `JWT_SECRET` (env), payload `{"user":{"id":<int>},"iat","exp"}`, `exp = iat + 60d` (5,184,000 s), no `iss`/`aud`/`sub`/`kid`, zero clock leeway. The reverse also holds for rollback: port-minted tokens verify in legacy | every logged-in SPA or mobile client (token in localStorage) | forced logout of every user, and of port-issued users after rollback | mint with jsonwebtoken 9.0.2 and test secret → `GET /api/user` on port returns that user. Tampered signature, `alg:none`, HS512, or expired token → 401 (C-14). Port token → legacy `GET /api/user` 200 | auth.service.test.ts:32,131 (only "has token") | S:auth/token.utils.ts:3-6. S:auth/auth.ts:16-28 |
| C-13 | wire | Token is read from `Authorization: Token <jwt>` **or** `Authorization: Bearer <jwt>`. The scheme is case-sensitive and the header is split on a single space (`split(' ')[1]`). Any other scheme counts as "no token" | RealWorld front-ends (use `Token`), generic clients (`Bearer`) | clients on one scheme lose auth | both schemes → 200. `token x` (lowercase) → treated as anonymous (optional routes 200, required routes 401). `Token  x` (two spaces) → empty token → anonymous | none | S:auth/auth.ts:4-12 |
| C-14 | wire | Every JWT failure returns `401 {"status":"error","message":"missing authorization credentials"}`. That covers a missing token on required routes, plus a bad, expired or wrong-alg token on **any** route, optional ones included (`GET /articles` with an expired token → 401, not anonymous) | front-ends that clear the token on 401 | clients stuck logged in, or anonymous reads that start failing | optional route plus expired token → 401 with the exact body. Optional route with no header → 200 | none | src/main.ts:33-38 |
| C-15 | wire | There is no server-side revocation. A token stays valid until `exp` after a password change or email change. A token for a deleted user id passes auth, and then most handlers return 500 (e.g. `GET /user` → TypeError) | all clients | (guarantee: none) adding revocation would log users out, which is a behaviour change | change password → old token still 200 on `GET /user`. Delete the user row → old token gives 500 on legacy. Record what the port does | none | S:auth/auth.service.ts:136-157 |
| C-16 | wire | Register, login, `GET /user` and `PUT /user` each return a **freshly minted** token (sliding renewal). Clients that store the latest token extend their session past 60 days | SPA session longevity | sessions start expiring 60 days after login instead of being renewed | `GET /user` twice with a 1 s gap → different `token` values, each with a new `exp` | auth.service.test.ts:222,251 | S:auth/auth.service.ts:151,186 |
| C-17 | wire | User envelope `{"user":{...}}`. Register (201), `GET /user` and `PUT /user` (200) return `id,email,username,bio,image,token`. Login (200) returns `email,username,bio,image,token` **without `id`** | front-ends, mobile | client parse errors or missing id | JSON key-set comparison per endpoint against legacy golden responses | none | S:auth/auth.service.ts:66-81,113-120. registered-user.model.ts |
| C-18 | wire | Validation errors are `422 {"errors":{"<field>":["<msg>"]}}` with these exact messages: `can't be blank` (email, username, password, title, description, body), `has already been taken` (email and/or username, both keys when both clash), `must be unique` (title). Values are checked after trim on register and login. Bad login → **403** `{"errors":{"email or password":["is invalid"]}}` | front-ends showing field errors (RealWorld spec shape) | error messages vanish in the UI | table-driven: each blank field, duplicate email, duplicate username, both duplicates, duplicate title, wrong password, unknown email → exact status and body | auth.service.test.ts:35-198 (weak, see header) | S:auth/auth.service.ts:9-56,124-128. S:article/article.service.ts:166-191 |
| C-19 | wire | Other error bodies: `404 {}` for unknown profile, article on update/delete, and comment on delete. `GET /articles/:slug` → `404 {"errors":{"article":["not found"]}}`. Non-author update/delete article → `403 {"message":"You are not authorized to ... this article"}`. Unhandled errors (Prisma P2025/P2002, TypeErrors) → `500` with the error message as a JSON string | front-ends (mostly 404 handling) | low: clients mostly branch on status | probes: missing slug GET, PUT, DELETE. Other user's article PUT, DELETE. Follow unknown user (legacy: 500). Favorite unknown slug (legacy: 500) | article.service.test.ts:10,72 (weak) | src/main.ts:39-44. S:article/article.service.ts:270,307,311,401,405,546 |
| C-20 | wire | Article object: `slug,title,description,body,tagList:[string],createdAt,updatedAt,favorited,favoritesCount,author:{username,bio,image,following}`. Timestamps are ISO-8601 UTC with exactly 3 fractional digits and `Z` (`JSON.stringify(Date)`). `favorited` and `following` are false for anonymous callers. Envelope is `{"article":{...}}` | all front-ends | parse errors, dates shown wrong | golden comparison of `GET /articles/:slug` anonymous and authed. Regex `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$` on dates | none | S:article/article.mapper.ts. S:article/author.mapper.ts |
| C-21 | wire | **Favorite and unfavorite responses leak extra fields.** `POST/DELETE /articles/:slug/favorite` spreads the raw Prisma row, so `article` also carries `id`, `authorId`, and `favoritedBy: [full User rows including password hash, email, demo]` | (nobody legitimate) | keeping it keeps a credential leak. Removing it breaks only clients that read `id`/`authorId` from this response | legacy: favorite → response body contains `favoritedBy[].password` starting `$2a$`. Port: key set equals C-20 exactly (if `change` is approved) | article.service.test.ts:67 (only `favoritesCount`) | S:article/article.service.ts:597-603,643-649 |
| C-22 | wire | `GET /api/articles?tag&author&favorited&limit&offset` → `{"articles":[...],"articlesCount":N}`. Ordered by `createdAt desc`. Defaults `limit=10` and `offset=0`. `limit=0` or a non-number falls back to 10 (falsy). No maximum limit. `articlesCount` counts all matches. Filters combine with AND, match exactly and case-sensitively. A negative `offset` gives a 500 | list and pagination UIs | pagination drift, wrong totals | matrix: each filter alone and combined. `limit=0`, `limit=abc`, `limit=1000`, `offset=-1` → compare status and body with legacy | none | S:article/article.service.ts:8-111. S:article/article.controller.ts:30 |
| C-23 | wire | **Visibility rule.** `GET /articles`, `GET /articles/:slug/comments` and `GET /tags` only return content whose author has `demo=true` **or** is the requesting user. `GET /articles/feed` and `GET /articles/:slug` skip this filter. Tag ranking counts all articles but only lists tags that have a visible article | the hosted demo (api.realworld.io) and its front-ends | real users' content suddenly public, or demo content hidden | user A (non-demo) posts and comments. User B and anonymous: A's article missing from `/articles`, A's comment missing, A's tag missing from `/tags`. A sees their own. B fetches the slug directly → 200 | tag.service.test.ts (todo only) | S:article/article.service.ts:13-25,419-431. S:tag/tag.service.ts:5-14 |
| C-24 | wire | `GET /api/articles/feed?limit&offset` (auth required) returns articles by authors the user follows, `createdAt desc`, same envelope and defaults as C-22 | logged-in front-ends | empty or incorrect feed | follow a user and compare feed with legacy. A non-number limit gives 10 | none | S:article/article.service.ts:113-160 |
| C-25 | wire | Article URLs are slug-based (`/api/articles/:slug`). Changing the title changes the slug (C-11). The old slug then returns 404, with no redirect and no history. Slugs reveal the author's numeric id | shared and bookmarked links in front-ends | (legacy already breaks links on rename) adding redirects would be a behaviour change | PUT a new title → response has a new slug. Old slug GET → 404 | none | S:article/article.service.ts:316-353 |
| C-26 | wire | Comments: `GET /articles/:slug/comments` → `{"comments":[{id,createdAt,updatedAt,body,author}]}` with order unspecified (DB order) and the C-23 filter. For an unknown slug it returns **200 `{}`** (no `comments` key). `POST` returns **200** (not 201) `{"comment":{...}}`. A missing `comment` envelope → 500. An unknown slug → 500. `DELETE /articles/:slug/comments/:id` → **200 `{}`**. The slug is ignored, and a non-author gets 404 (not 403) | front-ends | client status checks fail (201/204 expected by some) | probe each case and compare status and body. Delete a comment through the wrong article's slug → legacy 200 | article.service.test.ts:10 (weak) | S:article/article.controller.ts:149-201. S:article/article.service.ts:416-560 |
| C-27 | wire | `POST /articles` → 201 `{"article"}`. `PUT /articles/:slug` → 200. `DELETE /articles/:slug` → **204 empty**. A missing `tagList` on create gives no tags. On update, **tags are always cleared first**: omitting `tagList` or sending `[]` removes every tag. A non-empty list replaces the set. Title, description and body change only when truthy. Clear-then-update is two statements with no transaction | editor UIs | tags vanish on edit, a behaviour change in either direction | PUT `{article:{body:"x"}}` with no tagList → legacy response has `tagList:[]`. Port must match, or the change must be approved | none | S:article/article.service.ts:162-239,289-383 |
| C-28 | wire | Profiles: `GET /profiles/:username` (optional auth) and `POST/DELETE /profiles/:username/follow` (required) → `{"profile":{username,bio,image,following}}`. Unknown user: GET 404 `{}`, follow and unfollow → 500. Self-follow allowed. Follow and unfollow are idempotent (repeating them gives 200) | front-ends | follow buttons break | probes: follow twice, unfollow twice, follow self, unknown user per verb | profile.service.test.ts, profile.utils.test.ts | S:profile/profile.service.ts. S:profile/profile.utils.ts |
| C-29 | wire | `GET /api/tags` → `{"tags":[string]}`. At most 10, ordered by article count desc (ties in DB order), visibility-filtered (C-23) | tag sidebar in front-ends | wrong popular tags | seed controlled counts and compare the list with legacy, including ties | tag.service.test.ts (todo) | S:tag/tag.service.ts |
| C-30 | wire | `PUT /api/user` changes only truthy fields: email, username, image and bio cannot be cleared with `""` or `null`. The new password is **not trimmed**, although login trims (so a password with trailing spaces set here cannot log in). Duplicate email or username → 500 (no 422 check) | settings page | changing these is an approved behaviour change | PUT `bio:""` → bio unchanged. PUT `password:" p "` then login `" p "` → legacy 403. Duplicate email → legacy 500 | auth.service.test.ts:227 (weak) | S:auth/auth.service.ts:160-187 |
| C-31 | wire | CORS via `cors()` defaults: `Access-Control-Allow-Origin: *` on every response, preflight `OPTIONS` → 204 with `Access-Control-Allow-Methods: GET,HEAD,PUT,PATCH,POST,DELETE`, request headers reflected, no credentials | browser SPAs on any origin | every browser client blocked | `OPTIONS /api/articles` with `Origin: https://x.test` and `Access-Control-Request-Headers: authorization,content-type` → same status and headers as legacy | none | src/main.ts:13 |
| C-32 | wire | Request bodies are accepted as `application/json` and `application/x-www-form-urlencoded` (qs extended, e.g. `user[email]=...`), 100 kb default limit. Payloads are wrapped in `user`, `article` or `comment`. A missing envelope: register → 422, login → 500, comment → 500 | front-ends, scripts using form posts | form-encoded clients rejected | POST `/api/users/login` form-encoded with `user[email]` and `user[password]` → 200. Body larger than 100 kb → 413 | none | src/main.ts:14-15 |
| C-33 | wire | `GET /` → 200 `{"status":"API is running on /api"}` (used as a liveness check, inferred). Unknown paths → Express default 404 HTML `Cannot GET /x` | uptime monitors (inferred), e2e test (stale) | monitors alert falsely | GET `/` exact body. GET `/nope` → 404 | e2e/src/server/server.spec.ts (stale: expects a different body) | src/main.ts:20-22 |
| C-34 | wire | Static files served from the web root (outside `/api`): `/images/smiley-cyrus.jpeg` and `/images/demo-avatar.png`. Stored `User.image` values and the DB default point at `https://api.realworld.io/images/...`, so if this deployment is that host, these URLs live in user rows | every avatar render | broken default and demo avatars | GET both paths → 200, same bytes (sha256) and content-type | none | src/main.ts:18. src/assets/images/ |
| C-35 | wire | Express response semantics: `Content-Type: application/json; charset=utf-8`, weak `ETag` on JSON responses with conditional `304` on `If-None-Match`, `X-Powered-By: Express` | browsers (HTTP cache), proxies | low: 304s turning into 200s costs bandwidth only | GET twice with `If-None-Match` → legacy 304. Record what the port does | none | express 4.18.2 defaults (src/main.ts) |
| C-36 | wire | Route table under `/api`: `POST /users`, `POST /users/login`, `GET/PUT /user`, `GET /profiles/:username`, `POST/DELETE /profiles/:username/follow`, `GET /articles`, `GET /articles/feed`, `POST /articles`, `GET/PUT/DELETE /articles/:slug`, `GET/POST /articles/:slug/comments`, `DELETE /articles/:slug/comments/:id`, `POST/DELETE /articles/:slug/favorite`, `GET /tags`. `feed` is matched before `:slug`, so a literal slug `feed` is unreachable | all clients (RealWorld spec) | 404s | route-table diff: every method plus path returns non-404 on both. `GET /api/articles/feed` without auth → 401, not a slug lookup | none | S:routes.ts. S:*/*.controller.ts |

### Operational

| ID | Surface | Assertion | Consumers | Break cost | Witness (probe) | Legacy test | Anchor |
|----|---------|-----------|-----------|------------|-----------------|-------------|--------|
| C-37 | operational | Env vars: `DATABASE_URL` (Postgres URL, read by Prisma), `JWT_SECRET` (HS256 key, read in `auth.ts` and `token.utils.ts`, **with a hardcoded fallback literal used when unset**), `NODE_ENV`, `PORT` (default 3000). The Dockerfile sets `HOST=0.0.0.0`, but the app never reads it (binds all interfaces) | operators, hosting config | boot failure, or every token invalid if the secret name or value changes | port boots with the same env names. Port refuses to boot without `JWT_SECRET` in prod (if `change` is approved), otherwise matches the fallback behaviour | none | S:auth/auth.ts:17,23. S:auth/token.utils.ts:4. src/main.ts:51. README.md env section. Dockerfile |
| C-38 | operational | Operator commands: `npx prisma migrate deploy` (schema), `npx prisma db seed` (12 demo users, each with 12 articles plus comments, random passwords, `demo=true`), `node dist/api/main.js` / docker `node api` on port 3000 as non-root user `api`. Deploy line: `npm ci && npx prisma migrate deploy && node dist/api/main.js` | operators, CI/CD, hosting | broken deploy scripts | port release has equivalents (`bin/migrate`, a seed task) documented in a mapping table. Container listens on 3000 | none | README.md "Deploy". package.json `prisma.seed`. Dockerfile. src/prisma/seed.ts |
| C-39 | operational | The seeded demo dataset is what anonymous and non-demo users see (C-23). Re-seeding through the port must keep `demo=true`, the demo avatar URL, and the `title-authorId` slug format | hosted demo, front-end demos | empty public site | port seed → anonymous `/api/articles` is non-empty and `articlesCount` reflects the seeded total | none | src/prisma/seed.ts:16-57 |
| C-40 | operational | Logging: a single `console.info("server up on port N")` line. No request log, no structured format | (none found) | none | n/a, recorded so nobody hunts for a log consumer | none | src/main.ts:53 |

## Data Schema Notes

- **Tables:** `"User"`, `"Article"`, `"Comment"`, `"Tag"`, plus implicit joins `_ArticleToTag`, `_UserFavorites`
  and `_UserFollows`, and the Prisma history table `_prisma_migrations`. `"User"` is a reserved word: Ecto quotes
  identifiers, so `schema "User"` works. Every column needs a camelCase `source:` mapping (`field :created_at,
  :naive_datetime_usec, source: :createdAt` or keep camelCase field names).
- **Primary keys:** `SERIAL` int4 everywhere. Ecto `:id` is compatible, and FKs from new Elixir tables must be
  `:integer`.
- **Timestamps:** `TIMESTAMP(3)` without tz, values in UTC. Read with `:utc_datetime_usec`, truncate to ms on
  write and on JSON encode. `updatedAt` is app-managed (no DB trigger, no Prisma `@updatedAt`), so Ecto must set
  it explicitly, and only where legacy does (article update).
- **Text columns:** all `TEXT`, with no length limits in the DB or the app.
- **Booleans:** `demo BOOLEAN NOT NULL DEFAULT false`.
- **Defaults:** `User.image` has DB default `https://api.realworld.io/images/smiley-cyrus.jpeg` (changed from the
  herokuapp URL in migration 3, so old rows keep the old string). The port should let the DB default apply
  (omit the field on insert), not re-hardcode it.
- **Join tables:** no primary key, only a unique `(A,B)` index and a `B` index. Prisma derives A and B
  alphabetically by model name: `Article` < `Tag` and `Article` < `User`. For the self-relation `_UserFollows`
  the A/B direction depends on Prisma's relation-field ordering and **must be confirmed from data** (C-03).
- **Index names:** renamed in migration 4 to Prisma 3+ style (`User_email_key`, etc.). Join-table indexes keep
  `_X_AB_unique` and `_X_B_index`.
- **Absent mechanisms:** no enums, JSON columns, soft-delete, STI/polymorphism, triggers, FTS, encrypted columns
  or serialized blobs.
- **Absent constraints:** no `CHECK` constraints. No unique index on `(Comment.articleId, ...)`.
  Tag names are not trimmed or normalized, so `Foo` and `foo` are different tags.
- **Concurrency:** uniqueness of email, username and slug is checked in the app first (a race window) and then
  enforced by the DB. The race loser gets a 500 in legacy.

## Decisions Needed for ADR-000

1. **Cutover mode and token continuity (C-12, C-16).** Do we share `JWT_SECRET` and keep the HS256 `{user:{id}}`
   60d format so existing tokens survive and rollback works? The alternative forces a re-login. Proposed default:
   keep (Joken with the same claims) at least until the last legacy token expires (60 days after cutover).
2. **Schema ownership (C-01, C-10).** Prisma stays the DDL owner during coexistence, and Ecto records a baseline
   without executing it. When does ownership flip? Do we keep the PascalCase/camelCase naming permanently or
   rename after the rollback window?
3. **Visibility rule (C-23, C-08, C-39).** Is the demo-only listing rule a product requirement of this deployment
   (`preserve`) or a hosted-demo artefact (`redesign` or `drop`)? It changes the query layer of three endpoints
   and the seed contract.
4. **Response-leak fix (C-21).** Change favorite and unfavorite to the C-20 shape. Needs explicit approval as a
   `change` because it alters the wire output, though it removes password hashes from responses.
5. **Bug-for-bug vs spec-correct behaviours.** Decide per item, possibly as one policy:
   - login 403 (spec suggests 401/422)
   - comment POST 200, DELETE 200 `{}`
   - unknown-slug comments `200 {}`
   - Prisma 500s for unknown profile, follow and favorite targets
   - duplicate email on `PUT /user` → 500
   - non-cleared fields on update
   - untrimmed password on update
   - tags wiped on article update without `tagList` (C-27)
   - comment delete ignoring the slug
   - invalid token on optional routes → 401 (C-14)

   Each kept quirk becomes a named compat behaviour. Each fix becomes an approved `change`.
6. **Slug generation (C-11).** Write a byte-compatible port of slugify 1.6.6 (golden-tested), or accept a new
   slug format for new articles only (existing slugs untouched)?
7. **Revocation (C-15).** Keep stateless tokens (no revocation, deleted-user tokens still decode) or add a
   check, which changes behaviour for compromised or deleted accounts?
8. **`JWT_SECRET` fallback (C-37).** Keep the hardcoded fallback (tokens minted under it would otherwise break)
   or fail the boot when it is unset? First confirm production actually sets it.
9. **Static avatars (C-34).** Does the Phoenix app keep serving `/images/*` at the web root (required if this
   deployment is `api.realworld.io`)? Should herokuapp-URL rows be rewritten?

## Questions

1. Is this deployment the public `api.realworld.io` host, or a private instance? That decides C-23, C-34 and how
   many unknown third-party front-ends depend on quirks.
2. Which front-ends and mobile clients are known consumers, and which auth scheme do they send (`Token` vs
   `Bearer`)?
3. Is `JWT_SECRET` set in production, or has it ever been unset? If it was unset at any point, live tokens were
   signed with the source fallback literal.
4. Which column of `_UserFollows` is the follower? Confirm with one legacy follow against a scratch DB
   (not production).
5. Do any rows still have `image` on `realworld-temp-api.herokuapp.com`? Is that host dead?
6. Does any monitor or load balancer probe `GET /` and match its body?
7. Are there operator scripts beyond the README (backups, manual user deletion, re-seed jobs)? None are in the
   repo.
8. Does any client read `id`/`authorId` from the favorite response (C-21) or `id` from the register,
   current-user or update responses (C-17)?
9. Is response ordering relied on for comments (DB order) and tag ties? Legacy does not define it.

## Coverage

- **Read:**
  - all 4 controllers, 4 services, 3 mappers, `auth.ts`, `token.utils.ts`, `http-exception.model.ts`, `main.ts`
    and `routes.ts`
  - `schema.prisma`, all 4 migrations and the migration lock
  - `seed.ts`, `prisma-client.ts`
  - Dockerfile, README, package.json, project.json, lockfile versions
  - all unit and e2e tests
- **Absent (grep plus read):** no cookies, sessions, CSRF, websockets, webhooks, email, file uploads, signed
  URLs, background jobs, cron, cache, rate limiting, OAuth or external HTTP calls. `axios` appears only in e2e
  tests, and `@ngneat/falso` only in the seed.
- **Not verified (by rule, legacy never run):**
  - exact cors preflight headers (C-31)
  - Express ETag/304 behaviour (C-35)
  - `_UserFollows` A/B direction (C-03)
  - slugify charMap outputs (C-11)
  - Prisma error message text in 500 bodies (C-19)

  Each needs a characterization run against a pinned legacy build in isolation.
- **Secrets:** no secret values recorded. `JWT_SECRET` is named, and its source fallback literal is referenced
  by location only.
