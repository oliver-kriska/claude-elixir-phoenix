# Features — Conduit (node-express-realworld)

Source: `node-express-realworld` @ `30b68e1e8814` · Stack: Express 4.18 + Prisma 4.16 (PostgreSQL) + express-jwt 8.4.1 / jsonwebtoken 9 · Shape: HTTP JSON API (no UI, no workers, no cron) · Capabilities: 16

All anchors are relative to SOURCE. "Svc" = `src/app/routes/article/article.service.ts`, "Ctl" = `src/app/routes/article/article.controller.ts`.

Legacy test quality warning: the unit tests in `src/tests/**` run against a Prisma mock and mostly assert `toHaveProperty('token')` or `rejects.toThrow(String({...}))`. `String({...})` is `"[object Object]"`, so the error-message assertions match almost any HttpException (for example `src/tests/services/auth.service.test.ts:45`, `:101`). The only e2e test (`e2e/src/server/server.spec.ts:8`) expects `{message:'Hello API'}`, but the app returns `{status:'API is running on /api'}` (`src/main.ts:22`), so that test is stale. Treat the legacy tests as weak evidence. Most invariants below are `observed` from code only.

## Actors

| Actor | How identified | Notes |
|-------|----------------|-------|
| Anonymous client | No `Authorization` header | Sees only content written by **demo** users (see F-06, F-11, F-12) |
| Registered user | JWT in `Authorization: Token <jwt>` or `Bearer <jwt>` (`src/app/routes/auth/auth.ts:4-12`); payload `{user:{id}}`, HS256, 60-day expiry (`src/app/routes/auth/token.utils.ts:3-6`) | Self-registered users always get `demo=false` (`src/app/routes/auth/auth.controller.ts:16`) |
| Demo user | `User.demo = true` (`src/prisma/schema.prisma:55`) | Only created by the seed script (`src/prisma/seed.ts:22`). Their content is public to everyone |
| Article author / comment author | `authorId` equals the token's user id | The only actor allowed to update or delete their own article or comment |
| Front-end client (machine) | CORS `*` (`src/main.ts:13`) | RealWorld SPA consumers rely on the JSON shapes |
| Operator | Shell access | Runs `prisma migrate deploy` and `prisma db seed`, and sets env `DATABASE_URL`, `JWT_SECRET`, `PORT`, `NODE_ENV` (`README.md:27-31`, `src/main.ts:53`) |

No admin role, API keys, webhooks, email, background jobs, sockets or scheduled tasks exist (code-wide grep shows nothing beyond the 4 controllers).

## Capability Map

| ID | Capability (goal) | Actors | Entry anchors | Side effects | Legacy tests | Triage |
|----|-------------------|--------|---------------|--------------|--------------|--------|
| F-01 | A visitor registers with email, username and password and immediately gets a usable token | Anonymous | `src/app/routes/auth/auth.controller.ts:14`, `auth.service.ts:38` | User row, bcrypt hash | `auth.service.test.ts:7-103` | preserve |
| F-02 | A user logs in with email and password and gets a fresh token; wrong credentials are rejected without saying which field was wrong | Anonymous | `auth.controller.ts:30`, `auth.service.ts:84` | none | `auth.service.test.ts:106-199` | preserve (status code question) |
| F-03 | A signed-in user reads and edits their own account (email, username, password, bio, image) and gets a re-issued token | User | `auth.controller.ts:45,61`, `auth.service.ts:131,151` | User row update | `auth.service.test.ts:202-252` | preserve (see triage) |
| F-04 | Anyone views a user's public profile and, if signed in, sees whether they follow that user | Anon, User | `src/app/routes/profile/profile.controller.ts:14`, `profile.service.ts:5` | none | `profile.service.test.ts:5-41`, `profile.utils.test.ts` | preserve |
| F-05 | A signed-in user follows or unfollows another user; repeating the action is harmless | User | `profile.controller.ts:34,54`, `profile.service.ts:22,42` | `_UserFollows` row | `profile.service.test.ts:44-143` | preserve |
| F-06 | Anyone browses the newest articles, filtered by tag, author or favoriter, with offset pagination and a total count; only demo users' and the viewer's own articles are visible | Anon, User | Ctl:30, Svc:8-111 | none | none | **triage** (demo visibility) |
| F-07 | A signed-in user reads a newest-first feed of articles by the users they follow | User | Ctl:45, Svc:113 | none | none | preserve |
| F-08 | Anyone reads a single article by slug, with tags, favorite state and author follow state | Anon, User | Ctl:87, Svc:241 | none | none | preserve |
| F-09 | An author publishes, edits and deletes their own articles; the slug comes from the title and is unique per author | Author | Ctl:71,110,129; Svc:162,289,385 | Article and Tag rows; deletes cascade to comments, favorites and tag links | none | preserve (tag-wipe bug) |
| F-10 | A signed-in user favorites or unfavorites an article and sees the updated count | User | Ctl:210,230; Svc:562,608 | `_UserFavorites` row | `article.service.test.ts:24-142` | **redesign** (data leak) |
| F-11 | Anyone reads an article's comments; a signed-in user adds comments and deletes their own | Anon, User | Ctl:149,170,190; Svc:416,473,527 | Comment rows | `article.service.test.ts:9-21` | **triage** (demo visibility) |
| F-12 | Anyone sees the 10 most-used tags | Anon, User | `src/app/routes/tag/tag.controller.ts:13`, `tag.service.ts:4` | none | `tag.service.test.ts:4` (`test.todo`) | triage |
| F-13 | Clients authenticate every protected call with a long-lived bearer token; missing or bad tokens are refused uniformly | All | `auth.ts:14-26`, `token.utils.ts:3`, `src/main.ts:34-38` | none | none | preserve (secret default) |
| F-14 | Clients get errors in a predictable JSON shape: 422 validation `{errors:{field:[msg]}}`, 401, 403, 404, 500 | All | `src/main.ts:26-47`, `src/app/models/http-exception.model.ts:1` | none | indirect | preserve with fixes |
| F-15 | Monitors and clients can hit `/` for liveness and fetch the bundled default avatar images | Machine | `src/main.ts:19-23`, `src/assets/images/*` | none | `e2e/src/server/server.spec.ts:3` (stale) | preserve |
| F-16 | An operator creates or migrates the schema and seeds demo content (12 demo users × 12 articles, each article commented by every demo user) | Operator | `src/prisma/migrations/*`, `src/prisma/seed.ts:39`, `package.json:11-14`, `README.md:41-74`, `Dockerfile` | DB schema and rows | none | preserve |

## F-01 Register

**Goal**: A visitor registers with email, username and password and immediately gets a usable token.
**Sub-behaviors**: `POST /api/users` with body `{user:{email,username,password,image?,bio?}}` returns `201 {user:{id,email,username,bio,image,token}}`.
**Invariants**:
- email, username and password are trimmed. A blank value after trimming gives 422 `{errors:{<field>:["can't be blank"]}}`, checked in the order email, username, password, so only the first failure is reported (`auth.service.ts:39-54`)
- Duplicates give 422 and can report both fields at once: `{errors:{email:["has already been taken"],username:[...]}}` (`auth.service.ts:9-36`). The check is a separate read before the insert, so two concurrent registrations race. The DB unique index (`User_email_key`, `User_username_key`) then raises an unhandled Prisma error, which becomes a 500
- Uniqueness is case-sensitive: `Foo@x` and `foo@x` are different users (exact `findUnique`)
- `demo` is forced to `false` whatever the client sends (`auth.controller.ts:16`)
- Password is stored as bcrypt with cost 10 (`auth.service.ts:58`)
- `image` defaults at the DB level to `https://api.realworld.io/images/smiley-cyrus.jpeg` (`schema.prisma:48`, migration `20211105153605_api_url`). Older rows may hold the herokuapp URL from the initial migration
- The response includes `id`, which is outside the RealWorld spec (`auth.service.ts:70`). The login response does not (see F-02)
**Acceptance probes**:
- Given no user, when POST valid user, then 201, the body has a `token` that decodes to `{user:{id}}`, and `image` is the default URL
- Given `" alice "` as username, then the stored username is `alice`
- Negative: Given an existing email and username, then 422 with both `email` and `username` keys
- Negative: Given `password:"   "`, then 422 `{errors:{password:["can't be blank"]}}`
- Negative: Given `demo:true` in the body, then the stored `demo` is false
- Negative: Given a missing `user` key, then the legacy returns 500 (TypeError reading `.email` of undefined). The target should return 422 (see triage)
**Side effects**: inserts one User row.

## F-02 Login

**Goal**: A user logs in with email and password and gets a fresh token, and wrong credentials are rejected without saying which field was wrong.
**Sub-behaviors**: `POST /api/users/login` `{user:{email,password}}` returns `200 {user:{email,username,bio,image,token}}`. There is no `id` here, unlike F-01 and F-03.
**Invariants**:
- email and password are trimmed before use (`auth.service.ts:85-86`). A blank value gives 422 `can't be blank` (`:88-94`)
- An unknown email and a wrong password give the **same** error: **403** `{errors:{"email or password":["is invalid"]}}` (`auth.service.ts:124-128`; test `auth.service.test.ts:158-199`)
- Each login issues a new token. Old tokens stay valid until they expire, because there is no revocation (see F-13)
**Acceptance probes**:
- Given a registered user, when they log in with the right password, then 200 with a token
- Given the user registered with password `"pw "`, when they log in with `"pw"`, then success (both sides were trimmed)
- Negative: Given a wrong password, then 403 with the exact `email or password` key; given an unknown email, then an identical body
**Side effects**: none.

## F-03 Current user (read and update)

**Goal**: A signed-in user reads and edits their own account and receives a re-issued token.
**Sub-behaviors**: `GET /api/user` and `PUT /api/user` `{user:{...}}`, both returning `{user:{id,email,username,bio,image,token}}`.
**Invariants**:
- Requires a valid token (`auth.controller.ts:45,61`)
- Update is partial, and only **truthy** fields are applied (`auth.service.ts:164-168`). A user can never clear `bio` or `image` by sending `""` or `null`
- Update does **not** trim, validate or check uniqueness. A duplicate email or username hits the DB unique index, which gives 500 (`auth.service.ts:159`)
- The password on update is hashed **untrimmed** (`:156`), while login trims (`F-02`). A password with surrounding spaces set via update can then never log in
- A token for a deleted user: `getCurrentUser` gets `null` and reads `null.id`, which gives 500 (`auth.service.ts:132-148`). PUT gives 500 through Prisma P2025
**Acceptance probes**:
- Given a signed-in user, when GET `/api/user`, then 200 and the body has a new `token`
- Given PUT `{user:{bio:"hi"}}`, then only bio changes and email and username are unchanged
- Negative: Given no token, then 401 `{status:"error",message:"missing authorization credentials"}`
- Negative: Given PUT `{user:{bio:""}}`, then bio is **unchanged** (legacy behavior, see triage)
- Negative: Given PUT with another user's email, then the legacy returns 500. The target should return 422 `has already been taken`
- Negative: Given a valid token for a deleted user, then the legacy returns 500. The target should return 401 or 404
**Side effects**: User row update.

## F-04 View profile

**Goal**: Anyone views a user's public profile and, if signed in, whether they follow that user.
**Sub-behaviors**: `GET /api/profiles/:username` returns `{profile:{username,bio,image,following}}`.
**Invariants**:
- Optional auth. `following` is false when anonymous (`profile.utils.ts:8-10`; test `profile.utils.test.ts:5-77`)
- Unknown username gives 404 with body `{}` (`profile.service.ts:15-17`)
- Profiles are **not** filtered by `demo`: any user's profile is visible
- Username match is exact and case-sensitive
**Acceptance probes**:
- Given A follows B, when A GETs B's profile, then `following:true`; anonymous gets `following:false`
- Negative: Given an unknown username, then 404 `{}`
- Negative: Given an invalid or expired token on this optional route, then 401 (inferred: express-jwt 8 with `credentialsRequired:false` still rejects malformed tokens). UNKNOWN: confirm against express-jwt 8.4.1 behavior
**Side effects**: none.

## F-05 Follow and unfollow

**Goal**: A signed-in user follows or unfollows another user, and repeating the action is harmless.
**Sub-behaviors**: `POST` and `DELETE /api/profiles/:username/follow` return `{profile}`.
**Invariants**:
- Requires a token. Idempotent: connecting an existing link or disconnecting a missing one is a no-op, with uniqueness enforced by `_UserFollows_AB_unique`
- **Self-follow is allowed** (no check in `profile.service.ts:22`)
- Unknown username gives Prisma P2025, which becomes **500**, not 404 (`profile.service.ts:23`; test `profile.service.test.ts:82-92` asserts only "throws")
- Join table `_UserFollows(A,B)`: A is the followed user (`followedBy`) and B is the follower. Column semantics are part of the kept data contract
**Acceptance probes**:
- Given A not following B, when A POSTs follow twice, then both return `following:true` and one link row exists
- Given A follows B, when A DELETEs follow, then `following:false`; deleting again also gives 200 `following:false`
- Negative: Given an unknown username, then the legacy returns 500. The target should return 404
- Negative: Given no token, then 401
**Side effects**: `_UserFollows` row inserted or deleted. This changes F-07 feed contents.

## F-06 Browse and filter articles

**Goal**: Anyone browses the newest articles, filtered by tag, author or favoriter, with offset pagination and a total count.
**Sub-behaviors**: `GET /api/articles?tag=&author=&favorited=&offset=&limit=` returns `{articles:[...], articlesCount}`.
**Invariants**:
- **Demo visibility filter**: an article is listed only if its author has `demo=true` OR is the viewer (`Svc:13-25, 35-40`). An anonymous client sees only seeded demo content. A registered user sees demo content plus their own, and **never** other real users' articles in the global list. This is a major divergence from the RealWorld spec
- Filters are ANDed. A filter is applied when the key is present, even if empty (`'author' in query`, `Svc:27,44,54`), so `?tag=` matches tags named `""`, which means nothing
- Ordering is `createdAt DESC` with no tie-breaker (`Svc:79-81`). Pages can overlap or skip rows that share a timestamp
- `offset` defaults to 0 and `limit` defaults to 10. Non-numeric values and `0` fall back to the default (`Number(x) || default`, `Svc:82-83`). There is no maximum limit. A negative offset or limit goes to Prisma unchecked, so expect a 500 (inferred)
- `articlesCount` uses the same filter but is a separate query, so it is not snapshot-consistent with the page (`Svc:71-75`)
- Article JSON: `{slug,title,description,body,tagList:[names],createdAt,updatedAt,favorited,favoritesCount,author:{username,bio,image,following}}` (`article.mapper.ts:3-14`). Tag order inside `tagList` is UNKNOWN (no orderBy, so DB order)
- Each article loads the full `favoritedBy` and `author.followedBy` lists to compute flags (`Svc:84-104`). This is an N-size payload per row and a performance hotspot, not a contract
**Acceptance probes**:
- Given 15 demo articles, when anonymous GETs `/api/articles`, then 10 articles newest-first and `articlesCount:15`
- Given `?limit=5&offset=10`, then 5 articles, items 11-15
- Given `?tag=dragons`, then only articles carrying that tag, with the count matching
- Given `?favorited=alice`, then only articles alice favorited (still subject to the demo filter)
- Negative: Given real user R (demo=false) publishes an article, when another user or anonymous lists articles, then R's article is **absent**. R sees it
- Negative: Given `?limit=abc`, then 10 items (fallback)
**Side effects**: none.

## F-07 Personal feed

**Goal**: A signed-in user reads a newest-first feed of articles by the users they follow.
**Sub-behaviors**: `GET /api/articles/feed?offset=&limit=` returns `{articles, articlesCount}`.
**Invariants**:
- Requires a token (`Ctl:47`)
- Includes only articles whose author is followed by the viewer, with **no demo filter** (`Svc:114-126`). This is the only listing where real users see each other's articles
- The route is declared before `/articles/:slug` (`Ctl:45` vs `:87`), so `feed` is never treated as a slug. A slug literally equal to `feed` is unreachable by GET. Route precedence is a wire contract
- Same pagination defaults, ordering and lack of tie-breaker as F-06
**Acceptance probes**:
- Given A follows B (non-demo) and B has 3 articles, when A GETs the feed, then 3 articles and `articlesCount:3`
- Given A follows nobody, then `{articles:[],articlesCount:0}`
- Negative: Given no token, then 401
**Side effects**: none.

## F-08 Read one article

**Goal**: Anyone reads a single article by slug, with tags, favorite state and author follow state.
**Sub-behaviors**: `GET /api/articles/:slug` returns `{article}`.
**Invariants**:
- Optional auth. **No demo filter**: any article is readable by slug (`Svc:241-274`), unlike F-06
- Missing slug gives 404 `{errors:{article:["not found"]}}` (`Svc:269-271`). Note this differs from the update/delete 404 body `{}`
- The slug match is exact and case-sensitive. Slugs keep the title's case (see F-09)
**Acceptance probes**:
- Given a non-demo user's article, when anonymous GETs its slug, then 200 with `favorited:false` and `author.following:false`
- Negative: Given an unknown slug, then 404 with the `errors.article` body
**Side effects**: none.

## F-09 Author articles (create, update, delete)

**Goal**: An author publishes, edits and deletes their own articles, and the slug comes from the title and is unique per author.
**Sub-behaviors**:
- Create: `POST /api/articles` `{article:{title,description,body,tagList?}}` returns **201** `{article}` (`Ctl:71-78`)
- Update: `PUT /api/articles/:slug` returns 200 `{article}` (`Ctl:110`)
- Delete: `DELETE /api/articles/:slug` returns **204** with an empty body (`Ctl:129-140`)
**Invariants**:
- Validation checks title, then description, then body. A falsy value gives 422 `can't be blank` (`Svc:166-176`). There is no trimming and no length limits
- Slug = `slugify(title) + "-" + authorId` (`Svc:178`) using slugify 1.6.6 defaults: **case is preserved**, spaces become `-`, and some symbols are dropped. Including the author id makes the slug unique per author, not globally. A duplicate gives 422 `{errors:{title:["must be unique"]}}` (`Svc:189-191`). The check-then-insert races, and the losing request gets a 500 from the unique index
- Existing slugs are a **wire contract**: client URLs and bookmarks embed them. The target must reproduce slugify output byte-for-byte for new and renamed titles, or keep stored slugs untouched and only generate new ones compatibly
- Tags: `tagList` that is not an array is ignored. Tags are connected-or-created by exact name (`Svc:203-208`). Tag names are not trimmed, lowercased or de-duplicated (duplicates in input: UNKNOWN Prisma behavior). Tags are never deleted when orphaned
- Update: only the author may update. A non-author gets **403** `{message:"You are not authorized to update this article"}`, a missing article gets 404 `{}`, and author mismatch is checked before validation (`Svc:306-314`)
- Update applies only truthy fields. A new title regenerates the slug, so the article URL changes (`Svc:316-333`)
- **Update always wipes tags first** (`disconnectArticlesTags`, `Svc:343`) and then connects only the supplied `tagList`. A PUT without `tagList` therefore **removes all tags**. The wipe and the update are two separate writes with no transaction
- Update sets `updatedAt = now()` explicitly (`Svc:354`). The schema has no `@updatedAt` (`schema.prisma:18`), so favoriting does **not** bump `updatedAt`
- Delete: author only, otherwise 403 `{message:"You are not authorized to delete this article"}`. Missing gives 404 `{}`. The DB cascade removes comments, favorites and tag links (`migration 20210924225358_initial:99,105`, `20211001143221_implicit_tags:33`)
- Deleting a user cascades to their articles and comments (`initial:90,102`), though no API deletes users
**Acceptance probes**:
- Given user 7 creates title "Hello World", then 201 and slug `Hello-World-7`
- Given user 7 creates "Hello World" again, then 422 `title: must be unique`; user 8 creating the same title succeeds with `Hello-World-8`
- Given an article with tags [a,b], when the author PUTs `{article:{body:"x"}}`, then the legacy result has tags **[]** (see triage)
- Given the author PUTs a new title, then the response slug changes, the old slug gives 404 and the new slug gives 200
- Negative: Given user B PUTs or DELETEs A's article, then 403 and the article is unchanged
- Negative: Given DELETE of an article with comments and favorites, then 204 and those comments and favorite links are gone
- Negative: Given a missing `article` key in the POST body, then the legacy returns 500 (destructuring undefined). The target should return 422
**Side effects**: Article insert, update or delete; Tag inserts; cascading deletes.

## F-10 Favorite and unfavorite

**Goal**: A signed-in user favorites or unfavorites an article and sees the updated count.
**Sub-behaviors**: `POST` and `DELETE /api/articles/:slug/favorite` return `{article}`.
**Invariants**:
- Requires a token. Idempotent through connect and disconnect plus `_UserFavorites_AB_unique`
- Unknown slug gives P2025, which becomes **500** (`Svc:563`; test `article.service.test.ts:72-83` asserts only "throws")
- **Response shape differs from every other article response and leaks data**: it spreads the raw Prisma row (`Svc:597-603`), so the body adds `id`, `authorId` and **`favoritedBy`: the full User rows of every favoriter, including `email`, `password` (bcrypt hash) and `demo`**. This is a security defect. RealWorld clients ignore unknown keys, so removing the extra keys is very likely safe (inferred)
- `favoritesCount` comes from `_count` and `favorited` from the favoritedBy list (test `article.service.test.ts:67` asserts `favoritesCount` exists)
- Favorites are visible across the demo boundary: a user can favorite any article whose slug they know
**Acceptance probes**:
- Given an article with 0 favorites, when user A POSTs favorite twice, then `favorited:true` and `favoritesCount:1`
- Given A then DELETEs, then `favorited:false` and `favoritesCount:0`
- Negative: The response body contains no `password`, `email` or `favoritedBy` keys (the target must assert this; the legacy fails it)
- Negative: Given an unknown slug, then the target returns 404 (the legacy returns 500)
**Side effects**: `_UserFavorites` row. This affects F-06 `?favorited=` and F-12 does not depend on it.

## F-11 Comments

**Goal**: Anyone reads an article's comments, and a signed-in user adds comments and deletes their own.
**Sub-behaviors**:
- List: `GET /api/articles/:slug/comments` returns `{comments:[{id,createdAt,updatedAt,body,author:{username,bio,image,following}}]}` (`Svc:416-471`)
- Add: `POST /api/articles/:slug/comments` `{comment:{body}}` returns **200** `{comment}`. The legacy returns 200, not 201 (`Ctl:176`)
- Delete: `DELETE /api/articles/:slug/comments/:id` returns 200 `{}` (`Ctl:196`)
**Invariants**:
- **Demo visibility filter on comments**: only comments whose author is demo or is the viewer are returned (`Svc:417-441`). Real users never see each other's comments, even on their own articles
- Comment order is UNKNOWN: there is no orderBy, so DB order (usually insertion order in practice)
- Unknown slug on list returns 200 `{}` (with `comments` undefined, so the key is omitted by JSON) rather than 404 (`Svc:460`)
- Add: a falsy body gives 422 `can't be blank`. An unknown slug makes the connect target undefined, which gives a 500 (`Svc:478-492`). A missing `comment` key gives 500 (TypeError at `Ctl:175`)
- Delete: lookup is by id AND author = viewer (`Svc:528-534`), so a non-author gets **404** and the 403 branch at `:549` is dead code. The `:slug` path segment is **ignored**: the comment does not have to belong to that article
**Acceptance probes**:
- Given demo user D comments on an article, when anonymous lists, then D's comment is present with `author.following:false`
- Given real user R comments, then R sees it and anonymous and other users do not (legacy)
- Given R deletes their own comment, then 200 `{}` and it is gone
- Negative: Given user B deletes R's comment, then 404 and the comment remains
- Negative: Given POST with `body:""`, then 422 `{errors:{body:["can't be blank"]}}`
- Negative: Given POST to an unknown slug, then the target returns 404 (the legacy returns 500)
**Side effects**: Comment rows.

## F-12 Popular tags

**Goal**: Anyone sees the 10 most-used tags.
**Sub-behaviors**: `GET /api/tags` returns `{tags:[names]}`.
**Invariants**:
- A tag is eligible only if at least one of its articles is by a demo author or by the viewer (`tag.service.ts:4-23`), the same visibility idea as F-06
- Ranked by the **total** article count per tag, including articles the viewer cannot see (`:29-33`). Ties have no tie-breaker, so order among ties is unstable
- Fixed limit of 10 with no pagination
- Legacy test is `test.todo` (`tag.service.test.ts:4`)
**Acceptance probes**:
- Given demo articles tagged a×3, b×2, c×1, then `["a","b","c"]`
- Given 12 eligible tags, then exactly 10 are returned
- Negative: Given a tag used only by non-demo user R, then anonymous does not see it and R does
**Side effects**: none.

## F-13 Token authentication (cross-cutting)

**Goal**: Clients authenticate every protected call with a long-lived bearer token, and missing or bad tokens are refused uniformly.
**Invariants**:
- The header scheme `Token` (RealWorld) **and** `Bearer` are both accepted, split on a single space (`auth.ts:5-10`). Schemes are case-sensitive (`token xyz` is rejected)
- HS256 with secret `JWT_SECRET`, **falling back to the literal `superSecret`** when the env var is unset (`auth.ts:16,21`, `token.utils.ts:4`). Payload `{user:{id}}` plus `iat` and `exp`. Expiry is 60 days
- **Existing tokens must keep validating after cutover** (data/wire contract): same secret, same algorithm, same claim path `user.id`
- No revocation and no check that the user still exists or that the password has not changed since the token was issued
- Every GET or PUT on `/user` and every login or register mints a new token
- Required-auth failure gives 401 `{status:"error",message:"missing authorization credentials"}` (`src/main.ts:34-38`), whether the token is missing, expired or has a bad signature
**Acceptance probes**:
- Given a token minted by the legacy app with the production secret, when it calls `GET /api/user` on the target, then 200
- Given `Authorization: Bearer <valid>`, then 200
- Negative: Given an expired token, then 401 with the exact legacy body
- Negative: Given a token signed with a different secret or with `alg:none`, then 401
**Side effects**: none.

## F-14 Error envelope (cross-cutting)

**Goal**: Clients get errors in a predictable JSON shape.
**Invariants**:
- `HttpException(status, payload)` sends `res.status(status).json(payload)` (`src/main.ts:40-42`). The payload shapes in use are `{errors:{field:[msg]}}` (422, 403 login, 404 article), `{message:"..."}` (403 authorization) and `{}` (404 profile, update, delete, comment)
- Any other error (Prisma, TypeError) gives **500** with the JSON-encoded error **message string** (`src/main.ts:43-45`). This leaks internal Prisma messages, including query details. Not a contract to keep
- Malformed JSON body: the body-parser error carries a `status` (400) but no `errorCode`, so it falls to the 500 branch (inferred)
- Unknown routes give the Express default 404 HTML (no JSON handler)
- URL-encoded bodies are accepted as well as JSON (`src/main.ts:15`)
**Acceptance probes**:
- Given a validation failure, then 422 with `Content-Type: application/json` and an `errors` map
- Negative: Given an internal DB error, then 500 and the body does not contain SQL or Prisma internals (the target should assert this)
**Side effects**: none.

## F-15 Liveness and static images

**Goal**: Monitors and clients can hit `/` for liveness and fetch the bundled default avatar images.
**Invariants**:
- `GET /` returns `200 {status:"API is running on /api"}` (`src/main.ts:21-23`). There is no DB check
- Static files are served from `src/assets` at the root: `/images/smiley-cyrus.jpeg` and `/images/demo-avatar.png` (`src/main.ts:19`, `project.json:18`). Stored user `image` values point at `https://api.realworld.io/images/...` (`schema.prisma:48`, `seed.ts:21`), so these paths are a public URL contract if this deployment is api.realworld.io (UNKNOWN: which host this deployment serves)
- CORS allows any origin with default methods (`src/main.ts:13`)
**Acceptance probes**:
- Given the server is up, when GET `/`, then 200 with the exact JSON
- Given GET `/images/smiley-cyrus.jpeg`, then 200 `image/jpeg`
- Negative: Given GET `/images/../package.json`, then 404 (no traversal)
**Side effects**: none.

## F-16 Operator: migrate, seed, configure, deploy

**Goal**: An operator creates or migrates the schema, seeds demo content and runs the API with env-based configuration.
**Invariants**:
- The schema is owned by 4 Prisma migrations, tracked in the `_prisma_migrations` table (inferred from Prisma). Implicit join tables `_ArticleToTag`, `_UserFavorites` and `_UserFollows` use the column names `A` and `B` (A = lower model name alphabetically). The kept-schema assumption (charter) means the target must read and write these tables as they are
- Timestamps are `TIMESTAMP(3)` **without time zone**, written by Prisma in UTC (`initial:8-9`). The JSON output is ISO-8601 with `Z` and milliseconds (inferred from JS Date serialization)
- Seed (`npx prisma db seed`) creates 12 demo users, 144 articles with 4 random tags each, and 1,728 comments by calling the service functions (`seed.ts:39-52`). It is **not idempotent**: random data, so re-runs add more. Errors are logged and the exit code is still 0 (`seed.ts:53-56`)
- The demo content is what anonymous visitors see (F-06, F-11, F-12), so an empty DB without seed gives an empty public site
- Env: `DATABASE_URL`, `JWT_SECRET` (falls back to `superSecret`), `PORT` (default 3000), `NODE_ENV` (only affects Prisma client reuse) (`README.md:27-31`, `src/main.ts:53`, `prisma-client.ts:19`). The Dockerfile exposes 3000 and runs as a non-root user
**Acceptance probes**:
- Given an empty DB, when migrate and seed run, then 12 users have `demo=true`, 144 articles exist and anonymous `GET /api/articles` shows `articlesCount:144`
- Given an existing production DB, when the target boots against it, then no schema change is required for read and write parity
- Negative: Given `JWT_SECRET` is unset in production, then the target refuses to boot (see triage)
**Side effects**: DB schema and rows.

## Triage Questions

1. **F-06 / F-11 / F-12 (preserve? redesign?)** The demo visibility filter hides every real user's articles, comments and tags from everyone except the author. This contradicts the RealWorld spec the README claims to follow (`README.md:5`) and looks like abuse protection for the public demo host (inferred, no comment explains it). Keep it (it is then a business rule with probes above), make it configurable, or drop it so the target behaves like the spec? This decision blocks F-06, F-11 and F-12 parity tests.
2. **F-10 (redesign, security)** Favorite and unfavorite responses leak every favoriter's email and bcrypt hash plus internal ids (`Svc:597-603`). Recommend redesign: return the standard article shape. Needs explicit approval because the wire shape changes.
3. **F-09 (redesign?)** PUT without `tagList` wipes all tags (`Svc:343`). Very likely a bug. Recommend "omit `tagList` leaves tags unchanged", applied in one transaction.
4. **F-09 (preserve)** Slug algorithm `slugify(title)-authorId`, case-preserving. Keep it byte-compatible so existing URLs and new slugs match the legacy output? This needs a fixture corpus produced from slugify 1.6.6.
5. **F-01/F-03/F-05/F-10/F-11 (redesign)** Several client errors surface as 500: duplicate email or username on update, follow of an unknown user, favorite or comment on an unknown slug, missing body envelope, deleted-user token. Approve mapping them to 422, 404 and 401? Any client that keys on 500 would be affected (unlikely).
6. **F-02 (preserve?)** Invalid credentials return **403**. The RealWorld spec and many clients expect 401 or 422. Keep 403 for existing clients?
7. **F-11 (preserve?)** Comment create returns 200 (spec: 201), and delete ignores the `:slug` path segment. Keep, or enforce comment-belongs-to-article?
8. **F-03 (redesign?)** Update cannot clear `bio` or `image` (truthy-only) and hashes untrimmed passwords while login trims. Align trimming, and allow `null` to clear?
9. **F-01/F-03 (preserve?)** Registration and current-user responses include `id`, but login does not. Keep the inconsistency, or drop `id` everywhere (spec) or add it to login?
10. **F-13 (redesign, security)** The JWT secret falls back to `superSecret`. The target should fail to boot without a secret. Confirm the production secret will be carried over so live tokens survive cutover.
11. **F-05 (preserve?)** Self-follow is allowed. Keep?
12. **F-14 (redesign)** The 500 branch echoes internal error messages (Prisma query text) to clients. Replace with a generic body?
13. **F-06/F-07 (preserve?)** Pagination has no maximum `limit` and no stable tie-breaker. Add an `id DESC` tie-breaker (invisible to clients) and a cap such as 100 (visible)?
14. **F-16 (preserve?)** The seed is non-idempotent and random. Is seed part of production operations (re-seeding the demo host) or only for development?

## Coverage

| Surface | Mapped | Not mapped (why) |
|---------|--------|------------------|
| `POST /api/users`, `POST /api/users/login` | F-01, F-02 | — |
| `GET /api/user`, `PUT /api/user` | F-03 | — |
| `GET /api/profiles/:username` | F-04 | — |
| `POST/DELETE /api/profiles/:username/follow` | F-05 | — |
| `GET /api/articles` | F-06 | — |
| `GET /api/articles/feed` | F-07 | — |
| `GET /api/articles/:slug` | F-08 | — |
| `POST /api/articles`, `PUT/DELETE /api/articles/:slug` | F-09 | — |
| `POST/DELETE /api/articles/:slug/favorite` | F-10 | — |
| `GET/POST /api/articles/:slug/comments`, `DELETE .../comments/:id` | F-11 | — |
| `GET /api/tags` | F-12 | — |
| `auth.required` / `auth.optional` middleware, token minting | F-13 | — |
| Global error handler, body parsers | F-14 | — |
| `GET /`, `express.static(assets)`, CORS | F-15 | — |
| Prisma migrations (4), `schema.prisma`, `seed.ts`, Dockerfile, env vars | F-16 | — |
| `src/prisma/prisma-client.ts` dev global reuse | — | Runtime/platform mechanism with no user-visible capability (archaeologist's scope) |
| Nx / esbuild / jest / eslint configs (`nx.json`, `project.json` build targets, `jest*.ts`, `tsconfig*`) | — | Build tooling, no capability |
| `e2e/**` | F-15 (noted stale) | Template-generated test that does not match the app |
| `src/app/routes/**/*.model.ts`, `user-request.d.ts` | via F-01..F-12 | Types only |
| `project-logo.png`, `.vscode`, lint/prettier configs | — | Non-runtime |
| Dynamic or metaprogrammed routes | — | None found: all 19 routes are static in 4 controllers mounted under `/api` (`routes.ts:7-13`) |
| Out-of-scope domains | — | None (whole app in scope) |

Open UNKNOWNs: express-jwt 8.4.1 behavior for invalid tokens on optional routes (F-04 and others); the order of `tagList` and comments (no orderBy); which public host serves `/images/*`; whether the demo filter is a deliberate product rule.

## Triage Decisions

Recorded 2026-10-09 by `/rewrite:analyze --auto`. Every answer is the `--auto` default (`preserve`, bug-for-bug)
and is **ASSUMED** — none is approved. Items marked ⚠ have a security or product weight and should be decided
by a human before ADR-000 is accepted, because preserving them carries the risk forward.

| # | Capability | Question | Decision |
|---|------------|----------|----------|
| 1 | F-06/F-11/F-12 | Demo visibility filter | ASSUMED: preserve ⚠ (hides real users' content from each other) |
| 2 | F-10 | Favorite/unfavorite leaks emails + bcrypt hashes | ASSUMED: preserve ⚠ (security leak; `redesign` recommended by all analysts) |
| 3 | F-09 | PUT without `tagList` wipes tags | ASSUMED: preserve |
| 4 | F-09 | Slug algorithm byte-compatible with slugify 1.6.6 | ASSUMED: preserve |
| 5 | F-01/F-03/F-05/F-10/F-11 | Client errors surfacing as 500 | ASSUMED: preserve |
| 6 | F-02 | Invalid credentials → 403 | ASSUMED: preserve |
| 7 | F-11 | Comment POST 200; DELETE ignores slug | ASSUMED: preserve |
| 8 | F-03 | Update can't clear bio/image; untrimmed password on update | ASSUMED: preserve |
| 9 | F-01/F-03 | `id` in register/current-user but not login | ASSUMED: preserve |
| 10 | F-13 | JWT secret fallback `superSecret` | ASSUMED: preserve ⚠ (forgeable tokens if unset; fail-to-boot recommended) |
| 11 | F-05 | Self-follow allowed | ASSUMED: preserve |
| 12 | F-14 | 500 body echoes internal error text | ASSUMED: preserve ⚠ (information leak) |
| 13 | F-06/F-07 | No max `limit`, no tie-breaker | ASSUMED: preserve |
| 14 | F-16 | Seed non-idempotent/random | ASSUMED: preserve (dev + demo reseed) |
