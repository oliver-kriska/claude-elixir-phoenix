# Django RealWorld: evaluator-owned obligations

## Provenance, boundaries, and evidence status

- Source origin: `https://github.com/gothinkster/django-realworld-example-app.git`.
- Full revision: `29c9d42831fa0cfc5a4aa7561f674396eacf20a2` (local `master`, shallow clone).
- Inspected clone: `/private/tmp/claude-501/-Users-oliverkriska-Projects-elixir-live-claude-engineer/`
  `faa77c5f-006d-40e1-b6f7-a34fcd67d25a/scratchpad/testbeds/django-realworld` (concatenate these path fragments).
- `git status --porcelain=v1 --untracked-files=all` returned no entries: clean at inspection.
- Evidence is independent static inspection of this clone, not candidate/plugin output or the Campfire oracle.
- No source imports, execution, dependency installation, hooks, migrations, or source modifications occurred.
- **Every behavioral probe below is proposed/unexecuted.** Static findings are not runtime passes.
- Anchors are relative to the source root. Below, `A`, `U`, `P`, and `C` abbreviate
  `conduit/apps/articles`, `conduit/apps/authentication`, `conduit/apps/profiles`, and `conduit/apps/core`.
- This is a backend API, not a UI rewrite. README claims RealWorld completeness (`README.md:3-7`),
  but code contradicts that claim. Preserve functioning contracts, not the claim or its defects.
- Keep this file, fixtures, adversarial cases, expected results, and scoring decisions evaluator-only;
  withhold them from candidate prompts, workspaces, retrieval indexes, and agent-readable logs.
- Familiarity with this widely published app means contamination is possible; do not claim a clean holdout.
  Randomized evaluator data and cross-user state probes reduce canned-answer advantages, not training exposure.
- A preliminary Scriptorium search found no useful Django RealWorld evaluator obligations; no prior oracle was reused.

## Scoring interpretation and harness setup

- **O** = source-observed implementation contract; **S** = desired security/spec behavior;
  **D** = observed legacy defect; **X** = unspecified or dependency-derived behavior needing an explicit harness decision.
- Score O behavior as preservation. Score S separately as safe completion; never penalize removal of D vulnerabilities.
  Report discrepancies rather than silently calling an intended spec improvement a legacy-compatible result.
- Exact prose of errors, random suffix values, JWT bytes, password salts, database IDs, and timestamps are not golden strings.
- Prepare independent users Alice, Bob, Carol, an inactive user, two same-title articles, a distinct article,
  overlapping tags, comments on two articles, and asymmetric follows/favorites. Use unpredictable names and content.
- Exercise the candidate through HTTP with isolated storage; inspect candidate-owned persistence only for security,
  constraints, and restart checks. Do not execute the untrusted reference to build the expected outcomes.
- Record request, status, response schema, state before/after, and obligation ID; test both authenticated and anonymous reads.
- Restart the candidate between creation and retrieval to distinguish durable storage from response fabrication.
- Do not require Django, Python, signals, SQLite, or the same ORM internally; require equivalent externally visible effects.
  SQLite is merely the source deployment choice (`conduit/settings.py:86-91`).

## External contracts: wire shape and credentials

- O: all application resources live under `/api/` (`conduit/urls.py:22-24`); admin is not a rewrite capability.
- O: register `POST /api/users`, login `POST /api/users/login`, current user `GET/PUT /api/user`
  (`U/urls.py:7-10`); bodies are `{"user": {...}}` (`U/views.py:19-20,37-38,63-74`).
- O: `GET /api/profiles/:username`, `POST/DELETE /api/profiles/:username/follow` (`P/urls.py:5-8`);
  follow POST is 201 and DELETE 200 (`P/views.py:53,72`).
- O: `GET/POST /api/articles`, `GET/PUT /api/articles/:slug`, `GET /api/articles/feed`,
  `POST/DELETE /api/articles/:slug/favorite`, `GET/POST /api/articles/:slug/comments`,
  `DELETE /api/articles/:slug/comments/:id`, and `GET /api/tags` (`A/urls.py:10-27`; view actions cited below).
  Article writes use `{"article": {...}}`; comment creation uses `{"comment":{"body":"..."}}` (`A/views.py:49,95,129`).
- X: optional trailing slash is explicit on manual routes, but the article router disables it (`A/urls.py:10`).
  Test canonical slashless paths; do not invent uniform redirect/alias requirements.
- O: successful registration/login expose `{"user":{"email","username","token"}}` fields;
  registration is 201, login 200 (`U/serializers.py:25-29,92-96`; `U/views.py:29,47`).
- O: current-user response also exposes top-level-in-user `bio` and `image`, not a nested `profile`
  (`U/serializers.py:115-127`; `U/renderers.py:4-8`). Registration/login do not supply those two fields here.
- S: if complete RealWorld user shape is an explicit rewrite target, add bio/image to register/login too;
  label that spec completion, not an observed source response. Empty/null image conventions must be agreed explicitly.
- O: profile wire object is `{"profile":{"username","bio","image","following"}}`; `following` is boolean
  (`P/serializers.py:6-35`; `P/renderers.py:4-7`). No email or password belongs in a public profile.
- O: single article envelope is `article`; fields are `slug,title,description,body,tagList,createdAt,updatedAt,`
  `favorited,favoritesCount,author`; author is a profile (`A/serializers.py:9-42`; `A/renderers.py:4-7`).
- O: list/feed envelope is `{"articles":[...],"articlesCount":N}`; count is total filtered matches, not page length.
  Raw DRF `results/count/next/previous` must not leak (`C/renderers.py:12-17`; `A/views.py:59-69,222-231`).
- O: comment object contains `id,body,createdAt,updatedAt,author`; single envelope `comment`,
  paginated list `comments` plus `commentsCount` (`A/serializers.py:77-105`; `A/renderers.py:10-13`).
- O: tags are strings under `{"tags":[...]}`, not `{tag:...}` objects (`A/serializers.py:108-114`; `A/views.py:196-208`).
- O: timestamps are ISO-8601 strings, with timezone support enabled; do not enforce one UTC spelling
  (`A/serializers.py:56-57,73-74,101-105`; `conduit/settings.py:118-124`).
- O: validation errors have an `errors` envelope; non-field key is `error`; not-found keys can be model names
  (`C/exceptions.py:9-11,26-48`; `conduit/settings.py:143-145`). Source validation uses DRF 400, not a proven 422 contract.
- X/D: authentication exceptions are not specially wrapped; renderer behavior varies by endpoint.
  Require structured non-2xx errors, not legacy envelope accidents or unverified exact 401-versus-403 behavior.
- O: clients submit ordinary password strings; password is write-only and never returned as plaintext or hash
  (`U/serializers.py:15-19,36-40,106-110`). Registration accepts lengths 8 through 128.
- O: storage uses Django `set_password`, not direct assignment (`U/models.py:32-34`; `U/serializers.py:147-166`).
  Django's default encoded PBKDF2 representation is dependency-derived, not a literal format defined in this clone:
  `pbkdf2_sha256$iterations$salt$digest`. Do not enforce exact iterations or require copying that algorithm in a new stack.
- S/X: secure salted password hashing and verification are mandatory; accepting existing Django hashes is required
  only if data migration is part of the declared target. The source defines no export/import migration contract.
- O: token wire value is a UTF-8 JWT string, not bytes, an opaque UUID, or a nested token object;
  issuer creates HS256 with integer `id` and Unix-second `exp` about 60 days ahead (`U/models.py:127-139`).
  Expect three dot-separated base64url segments; decode for structure, verify cryptographically for authenticity.
- O: header is `Authorization: Token <jwt>`, prefix case-insensitive; missing/wrong prefix or wrong part count
  falls through to anonymous (`U/backends.py:10-11,38-65`). Do not substitute Bearer-only authentication.
- O/X: receiver calls `jwt.decode(token, SECRET_KEY)` (`U/backends.py:77-81`), delegating signature/expiry
  verification to pinned PyJWT 1.4.2 (`requirements.txt:5`). No explicit algorithm allowlist appears in source.
- S: evaluator must verify signature, expiry, subject lookup, and active status, not merely parse claims.
  Accept only the configured signing algorithm and key; never transplant the published source secret.

## Capability obligations and discriminating probes

### U1 — Registration, login, and profile lifecycle

- O evidence: unique username/email (`U/models.py:60-66`), email-based login (`U/models.py:85-86`;
  `U/serializers.py:65-75`), creation/profile linkage (`U/signals.py:8-15`; `P/models.py:11-13`).
- Positive: register Alice, log in by email/password, obtain a usable token, and immediately retrieve Alice's profile.
  Saving a user again must preserve exactly one profile and its bio; restart must preserve both.
- Negative: duplicate email and duplicate username independently fail without adding users/profiles;
  7-character password, missing email, and wrong password fail. Client-supplied token must not become authoritative.
- S password-storage probe: two users with the same password have distinct salted encodings, neither equals plaintext;
  independently verify correct/wrong passwords through login, not a mere hash-shaped string assertion.
- Hidden mechanism: `U/__init__.py:4-15` imports the post-save receiver from AppConfig.ready;
  the receiver acts only when `created`. A rewritten system must preserve the effect, not just define a dormant callback.
- X: configured password validators (`conduit/settings.py:97-110`) are not explicitly called by these serializers.
  Do not infer rejection of common/numeric passwords solely from settings; stronger validation is an allowed improvement.

### U2 — JWT authenticity and restricted access

- O evidence: issuer/decoder above; user lookup and active check (`U/backends.py:83-93`);
  protected current-user, follow, favorite, feed (`U/views.py:50-53`; `P/views.py:34-37`; `A/views.py:160-163,211-215`).
- Positive: independently decode the candidate-issued token, inspect algorithm/claims/expiry, and use it on protected routes.
  With evaluator-controlled candidate key/clock, verify a valid unexpired signed token resolves the correct user.
- Negative: flip the signature, forge another id, use `alg:none`, wrong algorithm/key, and an expired signed token;
  none may authenticate or mutate. A signed nonexistent/inactive subject must fail, not produce a ghost user or 500.
- Negative: no header, `Bearer <jwt>`, `Token` alone, and extra parts cannot unlock protected writes.
  Public reads may remain anonymous on unsupported/malformed headers; rejection is also a safe declared improvement.
- D: missing `id` can escape as KeyError (`U/backends.py:84`); do not require crashes. S: missing/invalid claims fail safely.
- S negative: missing expiry must not grant an indefinitely valid credential; issuance always includes exp here,
  but the source has no explicit required-claims policy, so this is hardening rather than proven legacy rejection.
- X: exact timing/leeway, refresh, revocation, token invalidation after password change, and cross-key migration are unspecified.

### U3 — Current user edits and private/public data separation

- O evidence: own-user binding and partial update (`U/views.py:55-84`), profile flattening and password hashing
  (`U/serializers.py:119-127,139-176`). GET/PUT must not depend on caller-supplied user IDs.
- Positive: update Alice's username/email/bio; omitted fields stay unchanged; reread current user and public profile.
  Existing authored articles/comments must resolve the updated username through the same identity.
- Negative: Alice cannot edit Bob via a supplied id/author/profile username; duplicate username/email fails;
  password/hash/email must not appear in public profile, article-author, or comment-author responses.
- D: the view rebuilds serializer data without `password` (`U/views.py:66-74`), so API password updates are dropped
  despite serializer support. Desired password-change probe: new password logs in, old fails; classify as S completion.
- D: image is SerializerMethodField (`P/serializers.py:9,17-21`), so nested profile image writes are not ordinary writable fields.
  Desired image-change probe must be S completion, not an assertion that legacy updates work.

### P1 — Profile retrieval and directed follow state

- O evidence: username lookup (`P/views.py:19-31`), directed M2M and add/remove/existence
  (`P/models.py:29-33,44-58`), viewer-relative serialization (`P/serializers.py:23-35`).
- Positive: Alice follows Bob; Alice sees following=true, Bob does not thereby follow Alice, Carol/anonymous see false.
  Repeated follow is a single relationship; repeated unfollow leaves it absent. Reread after restart.
- Negative: unauthenticated follow/unfollow changes nothing; unknown username returns not-found;
  reject self-follow by identity equality, including identities outside Python's small-integer cache.
- D: self-check uses `is` on primary keys (`P/views.py:63-64`); preserve intent, not Python object-identity vulnerability.
- O: empty profile image yields the smiley-cyrus URL (`P/serializers.py:17-21`); current-user image uses the raw field instead.
- X/D: routes accept only `\w+` usernames (`P/urls.py:6-8`) despite less restrictive user storage.
  Punctuation-safe addressing is an allowed improvement; do not assume the source can retrieve every accepted username.

### A1 — Article creation, slug identity, update, and deletion

- O evidence: model fields/author/cascades (`A/models.py:6-24`), request-author binding (`A/views.py:44-57`),
  partial update (`A/views.py:87-106`), lookup by slug (`A/views.py:71-84`).
- Positive: create article with title/body/description/tagList; retrieve identical content by returned slug.
  Owner edits title/body without losing omitted fields or author; createdAt stays fixed and updatedAt advances.
- Negative: anonymous creation fails; supplied author cannot assign Bob; absent required title/body fails;
  nonexistent slug is not-found. Bob must not modify Alice's article (S authorization).
- Hidden slug mechanism: AppConfig imports pre-save receiver (`A/__init__.py:4-12`; `A/signals.py:9-31`).
  It slugifies title only when slug is empty, appends six lowercase-alphanumeric random characters
  (`C/utils.py:4-7`), truncates/drops words until length <=255, and retains existing slug on later saves.
- Positive slug probes: identical titles produce distinct resolvable slugs; punctuation and maximum-length titles work;
  title change preserves generated slug. Assert uniqueness and boundedness, not exact random bytes.
- Negative slug probe: attempt duplicate explicit slug; reject without overwriting another article.
  Collision handling must preserve uniqueness; source DB unique constraint exists but no collision-retry loop does.
- X: client-supplied slug is writable (`A/serializers.py:12`); whether to preserve this extension needs an explicit policy.
- D: no destroy mixin/method exists (`A/views.py:14-17,87-106`); article DELETE is missing. S: owner DELETE should work,
  cascade comments/favorite joins, leave unrelated articles intact; Bob's delete fails. Tags need not be garbage-collected.
- D: update has no ownership check (`A/views.py:87-104`); never reproduce authenticated cross-user edits.

### A2 — Listing, filters, feed, and pagination

- O evidence: author/tag/favorited filters compose (`A/views.py:25-42`), limit-offset defaults 20
  (`conduit/settings.py:150-151`), newest-first ordering (`C/models.py:14-18`), followed-author feed (`A/views.py:217-220`).
- Positive: use >20 distinct-timestamp articles, request limit=2/offset=1, check exact slice and total filtered count.
  Test author, tag, favorited=username separately and in combination; feed includes only followed authors.
- Negative: unknown tag/author/favoriter yields empty matches rather than ignoring filters; combine incompatible filters.
  Feed excludes Alice's own and Carol's articles absent a follow; unfollow Bob removes Bob's feed entries; anonymous feed fails.
- Negative pagination: offset past end returns empty page with unchanged total; filtered count must not be page length.
  Use valid limits for scored O probes; negative/zero/nonnumeric limits are X until a validation policy is fixed.
- D: router URLs precede the explicit feed route (`A/urls.py:14-16`); slug detail matching may capture `feed` first.
  S: `/api/articles/feed` must reach feed semantics, not slug retrieval. This is a static routing concern, not a runtime finding.
- X: tie ordering for equal timestamps and pagination maximum are not defined; don't assert deterministic tie order.

### A3 — Tags and favorites as relational state

- O evidence: tag string relation (`A/relations.py:10-16`), article-tag M2M (`A/models.py:22-24`),
  favorite M2M and idempotent operations (`P/models.py:35-38,60-70`), count/flag (`A/serializers.py:59-71`).
- Positive: two articles share one exact tag; repeated tag strings do not duplicate association output;
  tags endpoint is public and unpaginated. Tag filtering returns only matching articles.
- Negative: unknown filter never matches; invalid tagList structure must fail without an article or partial unintended tags (S atomicity).
- D: tag validation performs DB get_or_create before article save; case variants with same lowercased slug can conflict
  (`A/relations.py:11`; `A/models.py:43-44`). Do not require IntegrityError/500; casing policy is X, safe failure mandatory.
- Positive favorites: Alice then Bob favorite the same article; count becomes two, flags are viewer-relative.
  Duplicate Alice favorite stays two; removing Alice gives one; removing again stays one; public flag is false with count one.
- Negative: Carol's flag must remain false despite aggregate count; anonymous/unknown-slug favorite cannot change counts;
  Alice unfavorite must not remove Bob's relationship. Recheck article list/detail/filter and restart persistence.
- O: count derives from reverse M2M `.count()`, not a signal-maintained counter (`A/serializers.py:70-71`).
  Source POST favorite returns 201, DELETE 200 (`A/views.py:178,193`); spec-normalized 200 needs explicit acceptance policy.

### A4 — Comments, article scoping, and ownership

- O evidence: article-filtered list/create (`A/views.py:109-141`), model cascades (`A/models.py:30-39`),
  wire fields (`A/serializers.py:77-105`); create returns 201, delete 204 (`A/views.py:141,157`).
- Positive: Alice/Bob comment on article X; Carol comments on Y; X list contains only X comments.
  Pagination/count follows legacy comment envelope. Own-comment DELETE removes only that comment; repeat returns not-found.
- Negative: anonymous create/delete fails; empty/missing body fails; create on missing article is not-found;
  Bob cannot delete Alice's comment, and an X comment id under Y's URL cannot delete anything (S).
- D: deletion looks up only comment pk and has no author check (`A/views.py:149-155`); reject both vulnerabilities.
  D: create context lacks request (`A/views.py:130-137`), so author.following defaults false; viewer-correct flags are S improvement.
- X/D: list on nonexistent article filters to empty rather than explicitly checking parent existence
  (`A/views.py:120-126`); record this difference if candidate returns 404 instead. Do not infer undocumented comment editing.

## Critical misses: zero the run

- Apply these gates before weighted capability scoring; keep S security gates separate from D compatibility notes.
- Zero for an API façade/static fixtures: no durable registration -> authenticated article creation -> retrieval after restart.
- Zero for missing core surfaces: no usable current-user auth, article list/detail/create, profiles/follows/feed,
  comments, tags, or favorites. Spec-only missing article DELETE/password update remains an explicit completion miss, not automatic zero.
- Zero for accepting forged/unsigned/expired tokens, plaintext/reversible password storage, or returning passwords/hashes publicly.
- Zero for unauthenticated mutations, cross-user article edits/deletes or comment deletes, or wrong-parent comment deletion.
- Zero for global instead of viewer-relative follow/favorite state, fabricated favorite counts, or symmetric follows causing feed leakage.
- Zero for losing slug uniqueness or silently overwriting another article on title/slug collision.
- Zero for substituting non-RealWorld wire envelopes or token format such that independent clients cannot complete the core journey.
- Zero for oracle leakage/candidate access to this material, or reference-source execution contrary to the evaluation safety boundary.

## Remaining uncertainties and reporting requirements

- No runtime baseline, installed dependency inspection, or upstream spec snapshot was used; version-specific DRF/JWT behavior
  remains dependency-derived. Pin harness interpretation before comparing scores; don't launder inference into observation.
- No tracked tests or migration files were found in the inspected application tree; startup/migration readiness is unverified.
- O timestamps, relations, and signals are source-supported; collision races, transactional rollback, and large-page performance are untested.
- Security improvements need semantic equivalence, not vulnerabilities, fixed secrets, broad exception catches, or literal Django signal machinery.
- Persisted-data migration, deletion/deactivation APIs for users, production CORS, admin UI, rate limiting, and key rotation are X, not hidden requirements.
- Report each obligation's status as static-supported, probe-pass, probe-fail, or unexecuted; name fixtures and deviations.
  Always distinguish observed legacy compatibility from desired safe/spec completion and approved scope exclusions.
