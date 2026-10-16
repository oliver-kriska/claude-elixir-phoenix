# Node/Express RealWorld: evaluator-owned obligations

## Evidence boundary and custody

- Source origin: `https://github.com/gothinkster/node-express-realworld-example-app.git`.
- Full inspected revision: `30b68e1e881462b2f4164ea09ab4c4f5699c7b0b`.
- Dirty state: **clean**; read-only `git status --porcelain=v1 --untracked-files=all`
  returned no entries before and after inspection. Ignored files were not inventoried.
- Clone: `/private/tmp/claude-501/-Users-oliverkriska-Projects-elixir-live-claude-engineer/`
  `faa77c5f-006d-40e1-b6f7-a34fcd67d25a/scratchpad/testbeds/node-express-realworld`
  (join those two segments without a space).
- Static file reads and read-only Git only; no installation, imports, execution, hooks, source edits, or source test runs occurred.
- Derived independently from implementation/schema/migrations/tests; no plugin-generated output or Campfire oracle was read.
- **Evaluator-only material**: withhold this file, fixture specifics, negative cases, and scoring decisions from every fresh candidate context/workspace.
- Widely known RealWorld code may appear in training/prior sessions; independent authorship is not proof the app or candidate is uncontaminated.
- All behavioral probes are **PROPOSED / UNEXECUTED**; static evidence is not an HTTP, database, cryptographic, persistence, or concurrency test pass.

## Classification and execution policy

- **O** = observed source behavior worth preserving; **S** = desired safety invariant;
  **W** = RealWorld-style wire/spec intent; **D** = observed legacy defect;
  **U** = unspecified or unresolved policy. Do not score D as required fidelity.
- README claims RealWorld adherence (`README.md:5`), but no pinned external spec
  is bundled. W assertions here describe the source-supported interface, not a full spec audit.
- Default compatibility profile preserves O, including demo visibility and ten-item
  defaults, except identified D. A spec-normalizing profile must be declared before a run;
  do not silently switch to public-all visibility, limit 20, or different slug rules.
- Use an evaluator-owned isolated candidate database and real HTTP entrypoints.
  Never run this clone's seed, Nx scripts, Dockerfile, or test setup to obtain fixtures.
- Proposed fixtures: normal accounts A/B/C, demo account D, unique credentials,
  two articles per normal author, at least 12 demo articles with distinct timestamps,
  shared and unique tags, and comments by each account on two different articles.
- Create normal fixtures through the candidate API. Provision D through an approved
  evaluator-only database adapter; public registration must not set `demo=true`.
- Capture IDs/slugs from actual responses or evaluator DB reads, not fixed seed IDs.
  Use unrelated users/content to expose constant responses and reversed relations.
- For each capability below, run the positive sequence and its negative discriminator;
  inspect fresh reads after mutation and after a candidate restart where relevant.
- Do not grant behavioral credit for documentation, helper names, mocked repositories,
  a route inventory, compilation, or a token that merely contains two dots.

## External contracts and hidden mechanisms

- Mount: `/api` (`src/app/routes/routes.ts:7-13`); JSON envelopes:
  `user`, `profile`, `article`, `comment`, `comments`, `tags`, or `articles` plus `articlesCount`.
- Requests wrap fields in `user`, `article`, or `comment`; filters/pagination are query parameters. Comment IDs are numeric; article routes use slugs.
- Users: `email,username,bio,image,token`; registration/current-user/update also expose `id`, login does not
  (`src/app/routes/auth/auth.service.ts:69-81,114-120,136-148,170-182`).
- Profiles/authors: only `username`, nullable `bio`/`image`, boolean `following`
  (`src/app/routes/profile/profile.utils.ts:4-10`). No password/email/token leakage.
- Articles: `slug,title,description,body,tagList,createdAt,updatedAt,favorited,favoritesCount,author`
  (`src/app/routes/article/article.mapper.ts:3-14`). Tags are strings, flags booleans, count integer;
  Date values become timestamp strings. No snake_case or raw relation objects.
- Comments: `id,createdAt,updatedAt,body,author` (`src/app/routes/article/article.service.ts:460-468,513-524`); tags return string arrays.
- Statuses: registration/article creation 201, article deletion 204; login/read/update/follow/favorite/comment creation 200; comment deletion 200 `{}`
  (`src/app/routes/auth/auth.controller.ts:14-68`; `src/app/routes/article/article.controller.ts:71-78,129-139,170-200`).
- Validation: 422 `{ "errors": { "field": ["message"] } }`; wrong credentials: 403 `errors["email or password"]`; missing article/profile reads: 404.
- Auth errors: 401 `{status:"error",message:"missing authorization credentials"}` (`src/main.ts:34-44`); legacy errors do not share one RealWorld envelope.
- Passwords: bcrypt cost 10, not plaintext/recoverable encryption (`src/app/routes/auth/auth.service.ts:58-64,110-119,155-166`).
  Migrated data must verify existing bcrypt hashes; a fresh store may use a documented stronger hash.
- Signing: `jsonwebtoken.sign({user:{id}}, secret, {expiresIn:'60d'})` (`src/app/routes/auth/token.utils.ts:3-6`), no explicit signing algorithm.
- Verification: delegated to `express-jwt`, explicit HS256 allowlist (`src/app/routes/auth/auth.ts:14-25`), not a decode-only custom parser.
- Lock: bcryptjs 2.4.3 (`package-lock.json:4792-4793`), express-jwt 8.4.1 (`package-lock.json:6033-6041`),
  jsonwebtoken 9.0.2 (`package-lock.json:7752-7769`), slugify 1.6.6 (`package-lock.json:9135-9141`). Library behavior was not executed.
- Proposed JWT contract: compact signed HS256, numeric `user.id`, library-issued `iat`/`exp`, interval 5,184,000 seconds;
  independently verify signature with the configured test secret, then exercise expiry through HTTP.
- Exact `Token <jwt>` and `Bearer <jwt>` schemes are extracted; absent credentials mean anonymous on optional routes, unauthorized on required ones
  (`src/app/routes/auth/auth.ts:4-24`). Optional must not ignore an invalid supplied JWT.
- PostgreSQL: unique email/username/slug/tag name, implicit favorite/follow/tag joins, cascading article/comment ownership
  (`src/prisma/schema.prisma:1-55`); alternate storage must preserve outcomes.
- Unique favorite/follow pairs and cascade FKs: `src/prisma/migrations/20210924225358_initial/migration.sql:78-114`;
  unique tag pairs: `20211001143221_implicit_tags/migration.sql:18-36` in that directory. Repeated connections must not inflate counts.

## Capability probes (all proposed / unexecuted)

### C01 — Registration and credential authentication [O/W/S]

- Evidence: `src/app/routes/auth/auth.service.ts:9-128`;
  `src/app/routes/auth/auth.controller.ts:14-37`; `src/prisma/schema.prisma:43-55`.
- Positive: register A and B; login A; verify returned identity/token and stored hash;
  restart, then log in again. Default bio is null and image uses the schema default URL.
- Negative: blank/whitespace email, username, password each produce 422; duplicate
  email and duplicate username fail separately; wrong password/unknown email produce 403.
- Negative: register identical passwords for A/B; hashes must not equal plaintext or
  each other; no response may contain a password/hash. Submitted `demo:true` is ignored.

### C02 — Actual JWT verification and route authentication [O/S]

- Evidence: `src/app/routes/auth/auth.ts:4-25`, `token.utils.ts:3-6` in that directory;
  `src/app/routes/auth/auth.controller.ts:45-68`; `src/main.ts:34-38`.
- Positive: independently verify emitted JWT; call `/api/user` with Token and Bearer;
  compare identity with A, and check generated current-user tokens remain usable.
- Negative: missing token, malformed token, changed payload with old signature,
  wrong-secret signature, `alg:none`, and correctly signed expired JWT all fail 401.
- Negative: the expired/forged JWT also fails on optional `/api/articles`;
  a legitimately signed token naming a nonexistent user must not impersonate anyone or cause 500.
- S: provision a nondefault secret; missing production secret fails closed, not by
  recreating the source's publicly known fallback. Token text need not be byte-identical.

### C03 — Current-user read and scoped partial update [O/W/S]

- Evidence: `src/app/routes/auth/auth.service.ts:131-183`; `src/app/routes/auth/auth.controller.ts:45-68`.
- Positive: A updates email/username/bio/image and then password; omitted fields stay
  unchanged, new credentials log in, old password fails, B's identity is unaffected.
- Negative: payload `id` or another user's identity must not change the token-selected
  account; unauthenticated update fails; conflicting email/username cannot create duplicates.
- Probe explicit empty/null bio and image separately as D/U, not baseline fidelity;
  password change revocation of already issued tokens is U, not an assumed requirement.

### C04 — Public profiles and directional follow relations [O/W/S]

- Evidence: `src/app/routes/profile/profile.controller.ts:14-64`;
  `profile.service.ts:5-59` and `profile.utils.ts:4-10` in the same directory.
- Positive: A follows B; B's profile is following=true to A, false anonymously and to C;
  repeat follow, then unfollow twice; verify persisted state through fresh profile reads.
- Negative: A-following-B does not make B-following-A true; C's relationships remain
  unchanged; unauthenticated mutation fails; missing profile read is 404, never a fake user.
- S: public profiles never expose the full selected User record, despite DB includes.

### C05 — Article creation, tags, slug identity and detail [O/W]

- Evidence: `src/app/routes/article/article.service.ts:162-274`;
  `src/app/routes/article/article.controller.ts:71-98`; `src/prisma/schema.prisma:11-24`.
- Positive: A creates `Simple Title` with shared/new tags; slug is formed by
  `slugify(title)` with no options plus `-<A id>`; GET by returned slug round-trips all fields.
- Negative: repeat A's title or another title normalizing to the same slug gets 422;
  B's same title has a distinct suffix; unknown slug gets 404; missing required text gets 422.
- Test case/punctuation/accent titles to detect invented lowercase/UUID rules; exact
  slugify character mappings require independent reference expectations before scoring.
- Negative: unauthenticated creation fails; client-supplied author/id/slug cannot
  impersonate B; nonarray/omitted tagList becomes [] under observed compatibility.

### C06 — Owner-only article update/delete and lifecycle [O/W/S]

- Evidence: `src/app/routes/article/article.service.ts:289-414`; `src/prisma/schema.prisma:26-34`.
- Positive: A edits title/body/description; returned slug changes by the same slug rule,
  createdAt stays fixed, updatedAt advances; new slug resolves and old slug becomes 404.
- Positive: delete A's article; detail is absent and related comments/favorite joins
  no longer refer to it; shared tags still support B's surviving article.
- Negative: B's edit/delete gets 403 without changing text, timestamps, tags or joins;
  rename collision gets 422 with original state intact; missing target gets 404.
- D: body-only edits currently clear tags. Desired partial update preserves omitted
  tags; explicit [] clears them, explicit nonempty tags replaces associations atomically.

### C07 — Filtered list, visibility and pagination [O/W]

- Evidence: `src/app/routes/article/article.service.ts:8-110`; `src/app/routes/article/article.controller.ts:30-37`.
- Positive: anonymously list demo-author articles; A sees demo plus A's own;
  combine exact author/tag/favorited filters with AND; order is createdAt descending.
- Positive: default page is at most 10; `limit=2&offset=2` returns the appropriate slice;
  articlesCount counts the entire filtered visible set, not this page; far offset yields [].
- Negative: A cannot see B's normal article in lists even with author=B/favorited=A,
  but direct slug GET is public. Unknown filter value yields []/0, not an unfiltered result.
- Negative: use 12+ rows to reject a hard-coded page/count; change each filter alone
  to ensure it is applied. Zero/NaN currently fall back through `Number(value) || default`.
- U: negative/fractional/oversized/repeated query parameters and timestamp ties need
  a declared validation/tie-break policy; do not mandate legacy Prisma failures.

### C08 — Follow-derived feed [O/W/S]

- Evidence: `src/app/routes/article/article.controller.ts:45-60` (before slug route);
  `src/app/routes/article/article.service.ts:113-159`.
- Positive: A follows B, receives B's articles (including non-demo ones), newest first;
  pagination/count use the same followed-author set; unfollow removes B's articles.
- Negative: C and unfollowed D do not appear; A's own articles appear only if an
  applicable follow relation exists; empty following gives []/0; no JWT gives 401.
- Negative: `/api/articles/feed` must not be interpreted as the article slug `feed`.

### C09 — Favorite consistency and privacy [O/W/S]

- Evidence: `src/app/routes/article/article.service.ts:562-652`;
  `src/app/routes/article/article.mapper.ts:11-13`; unique join evidence above.
- Positive: A/B favorite one article; global count moves 0→1→2; A unfavorites and
  count becomes 1. Detail/list/feed and mutation replies agree on viewer-specific flags.
- Negative: repeat A's favorite/unfavorite does not add/subtract twice; C/anonymous
  favorited=false even when count>0; A unfavoriting must not remove B's relation.
- Negative: unknown slug/unauthenticated calls do not mutate state; inspect every
  nested mutation response for leaked hashes/email/raw favoritedBy (a source D).

### C10 — Comments, author projection and article scoping [O/W/S]

- Evidence: `src/app/routes/article/article.controller.ts:149-200`; `src/app/routes/article/article.service.ts:416-560`.
- Positive: A adds a comment; retrieve by article; ID/body/timestamps/author round-trip;
  own/demo comments are visible under compatibility; owner deletes and a fresh read omits it.
- Negative: empty body gets 422; unauthenticated writes fail; B cannot delete A's
  comment (legacy lookup returns 404); unknown article must not create orphan comments.
- Negative: deletion under article X with an ID belonging to article Y must not delete
  Y's comment even if caller owns it. Fix source's ignored slug, do not clone that vulnerability.
- Probe normal B comments hidden from A versus visible demo comments; D/U: missing
  article comment reads omit the comments key rather than returning a deliberate 404.

### C11 — Popular visible tags and relationship reuse [O/W]

- Evidence: `src/app/routes/tag/tag.controller.ts:13-19`, `tag.service.ts:4-37`
  in that directory; `src/app/routes/article/article.service.ts:203-207,335-357`.
- Positive: tags are unique names associated with demo/current-user articles, top 10
  sorted by total article relation count; shared tags reuse one identity across articles.
- Negative: tag found only on B's normal article is absent for anonymous/A; orphan tag
  is absent; deleting one shared-tag article must not erase the surviving association.
- Negative: more than ten eligible tags exposes missing cap; use distinct frequencies
  because tie ordering is U. Ranking count includes all articles, not only visible ones.

### C12 — Middleware, errors, assets and persistent integration [O/W/S]

- Evidence: `src/main.ts:13-47,53-57`; `src/app/routes/routes.ts:7-13`;
  `src/prisma/prisma-client.ts:17-21`; `project.json:16-19`; `package.json:5-14`.
- Positive: JSON and URL-encoded envelopes parse; browser CORS/preflight works;
  `/` returns `{status:"API is running on /api"}`; `/images/smiley-cyrus.jpeg` is served.
- Positive: candidate honors configured port/database/secret; all capability sequences
  survive a restart without losing users, relationships, or content.
- Negative: invalid JSON, unauthenticated writes, and service validation failures
  produce bounded errors, not success/hangs or leaked stack traces/database secrets.
- No tracked application hook files were found. Auth/parser/error/static middleware
  and DB constraints are the mechanisms; seed runs only by explicit Prisma configuration,
  not automatically on every boot. No requirement to reproduce Nx or dependency hooks.

## Legacy defects and uncertainty register

- D/security: favorite replies spread the included raw article with `favoritedBy:true`,
  potentially exposing full users including password hashes (`article.service.ts:597-603,643-649`
  under `src/app/routes/article/`). Require safe article projection instead.
- D/security: `deleteComment` never receives slug (`article.controller.ts:195`); its
  author-constrained lookup makes its later 403 check unreachable (`article.service.ts:527-552`).
- D/security: hard-coded `superSecret` fallback is not required fidelity; cryptographic
  verification, expiration enforcement and ownership protection are required.
- D: article tag disconnect and update are separate nontransactional writes
  (`src/app/routes/article/article.service.ts:276-286,343-357`); failed edit must not lose tags.
- D/U: create/login trim passwords but update hashes them without trimming;
  truthy-only updates cannot clear bio/image/text. Use ordinary nonblank passwords for core
  scoring; document normalization/clearing decisions separately, not as invented parity.
- O/spec tension: demo-only public lists/comments/tags and top-ten tags are deliberate
  source filters, not blanket privacy: direct article/profile reads and feed differ.
  Preserve the declared compatibility profile or explicitly preselect spec normalization.
- U/D: many missing relations, duplicate updates and invalid inputs escape as ORM errors;
  error middleware emits err.message (`src/main.ts:40-44`). Desired controlled 4xx responses
  need not reproduce raw errors, 500s, omitted keys, or inconsistent error envelopes.
- Existing tests are not a behavioral oracle: Prisma is deep-mocked
  (`src/tests/prisma-mock.ts:6-15`), tag coverage is TODO (`src/tests/services/tag.service.test.ts:1-5`),
  favorites mostly check property presence (`src/tests/services/article.service.test.ts:60-69`).
  E2E root expectation is stale (`e2e/src/server/server.spec.ts:3-8` versus `src/main.ts:21-23`).
- U: self-follow prohibition, logout/revocation, rate limits, email verification,
  Unicode normalization, tag ordering, article rename redirects, and user deletion lack contracts.
  Do not fabricate mandatory endpoints or require identical implementation technology.

## Critical misses: zero the run

- Zero for accepting forged/expired/unsigned JWTs, identity taken from client fields,
  cross-user article/comment mutation, or cross-article comment deletion.
- Zero for plaintext/recoverable password storage or any response leaking passwords,
  hashes, signing secrets, or private raw user relations; do not waive because source leaks.
- Zero for missing any core domain (users/auth, profiles/follows, articles, comments,
  favorites, tags/feed), fake constant results, or process-only persistence masquerading as DB state.
- Zero for absent RealWorld envelopes/routes or broken relational consistency making
  follow/feed, favorite/count, ownership, or pagination outcomes fundamentally wrong.
- Zero for candidate/evaluator leakage: consuming this obligation file, hidden fixture
  answers, or oracle/plugin outputs as test expectations invalidates a fresh run.
- Evaluator setup failure or an unexecuted probe is **not** a demonstrated candidate
  failure. Report not-run/blocked explicitly; attach request/response and state evidence
  for each executed obligation before making a pass, fail, or zero-score claim.
