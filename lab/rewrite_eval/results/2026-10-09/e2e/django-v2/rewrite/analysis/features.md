# Features — Conduit (django-realworld)

Source: $S/testbeds/django-realworld @ `29c9d42831fa0cfc5a4aa7561f674396eacf20a2` · Stack: Django 1.10.5 + DRF 3.4.4 + PyJWT 1.4.2, SQLite · Capabilities: 15

Shape: **SPA + JSON API** (app-shapes.md section 2). There is no server-rendered UI. The machine consumer is a RealWorld frontend (CORS origin `localhost:4000`, settings.py:132). The only non-API surfaces are the stock Django admin at `/admin/` and `manage.py`.

Evidence base: **the source has no legacy tests** (no `tests.py` or `tests/` dir, and `.gitignore` only lists coverage artefacts). Every invariant below is `observed` from code reading or `inferred` from Django/DRF 1.10/3.4 framework behavior. None is test-asserted. Probes marked **(verify)** depend on framework internals and should be confirmed against a running legacy instance under an isolation decision before they become parity gates.

## Actors

| Actor | How identified | Notes |
|-------|----------------|-------|
| Anonymous visitor | No `Authorization` header, or a header that is not `Token <jwt>` (backends.py:41-65 returns `None`) | Read-only access to articles, comments, profiles and tags. Can register and log in |
| Registered user | `Authorization: Token <jwt>`. HS256 JWT `{id, exp}` signed with `SECRET_KEY` (models.py:127-139, backends.py:72-93). The prefix is matched case-insensitively | Owns a Profile (created by a post_save signal). Every write needs a valid token |
| Deactivated user | `User.is_active=False` (authentication/models.py:74) | Token rejected (backends.py:89-91). Login fails. **No API or admin surface sets this flag** (see F-15) |
| Operator / superuser | `manage.py createsuperuser` → `create_superuser` (authentication/models.py:38-53). Session login at `/admin/` | No `admin.py` registers app models. UNKNOWN: whether the swapped custom `User` appears in the admin |
| RealWorld frontend (machine consumer) | Browser origin `localhost:4000` / `0.0.0.0:4000` (CORS whitelist, settings.py:132-135) | Depends on the JSON envelope, error shape, status codes and URL forms in F-14 |

## Capability Map

| ID | Capability (goal) | Actors | Entry anchors | Side effects | Legacy tests | Triage |
|----|-------------------|--------|---------------|--------------|--------------|--------|
| F-01 | A visitor registers with email, username and password. An account and an empty profile exist, and a usable token is returned at once | Anonymous | `POST /api/users` authentication/urls.py:9 → views.py:13-29 | Profile row created (signals.py:8-15) | none | preserve |
| F-02 | A user logs in with email and password and receives a fresh 60-day token | Anonymous | `POST /api/users/login` authentication/urls.py:10 → views.py:32-47 | none | none | preserve (T-17) |
| F-03 | Every request carrying `Token <jwt>` is attributed to that active user. Invalid, expired, orphaned or deactivated tokens are refused | All API callers | backends.py:10-93, settings.py:147-149 | none | none | redesign? (T-05, T-06, T-16, T-19) |
| F-04 | A signed-in user views and edits their own account (email, username, bio). The response carries a refreshed token | Registered user | `GET/PUT/PATCH /api/user` authentication/urls.py:8 → views.py:50-84 | User + Profile rows updated | none | redesign? (T-07) |
| F-05 | Anyone views a user's public profile and sees whether they follow that user | Anonymous, Registered | `GET /api/profiles/:username` profiles/urls.py:6 → views.py:13-31 | none | none | preserve (T-12) |
| F-06 | A signed-in user follows or unfollows another user. Following yourself is refused | Registered | `POST/DELETE /api/profiles/:username/follow` profiles/urls.py:7 → views.py:34-72 | follow edge added/removed | none | redesign (T-08) |
| F-07 | A signed-in user publishes an article with title, description, body and tags. It gets a unique URL slug | Registered | `POST /api/articles` articles/urls.py:10-14 → views.py:44-57 | slug generated (articles/signals.py:9-31). Tags created on demand (relations.py:10-13) | none | preserve (T-09, T-10, T-11) |
| F-08 | A signed-in user revises an existing article. **Legacy: any signed-in user can revise any article, and articles cannot be deleted** | Registered | `PUT /api/articles/:slug` articles/views.py:87-106. DELETE has no handler (views.py:14-17) | article row, tags replaced (inferred) | none | redesign (T-01, T-03) |
| F-09 | Anyone reads a single article with its author card, favorite count and tag list | Anonymous, Registered | `GET /api/articles/:slug` articles/views.py:71-84 | none | none | preserve |
| F-10 | Anyone browses the global article list newest-first, filters it by tag, author or favoriting user, and pages through it | Anonymous, Registered | `GET /api/articles?tag=&author=&favorited=&limit=&offset=` articles/views.py:25-42, 59-69, settings.py:150-151 | none | none | preserve (T-13) |
| F-11 | A signed-in user sees a newest-first paged feed of articles by authors they follow | Registered | `GET /api/articles/feed` articles/urls.py:16 → views.py:211-231 | none | none | redesign (T-04) |
| F-12 | A signed-in user favorites or unfavorites an article. Counts and the `favorited` flag reflect it | Registered | `POST/DELETE /api/articles/:slug/favorite` articles/urls.py:18-19 → views.py:160-193 | favorite edge added/removed | none | preserve |
| F-13 | Anyone reads an article's comments. A signed-in user adds a comment or deletes one. **Legacy: any signed-in user can delete any comment** | Anonymous (read), Registered (write) | `GET/POST /api/articles/:slug/comments` articles/urls.py:21-22 → views.py:109-141. `DELETE /api/articles/:slug/comments/:id` urls.py:24-25 → views.py:144-157 | comment row created/deleted | none | redesign (T-02, T-15) |
| F-14 | RealWorld frontends get one predictable JSON contract: object envelopes, paged lists with counts, `errors` bodies, and URLs that accept an optional trailing slash. Browsers on the whitelisted origin may call it | RealWorld frontend | core/renderers.py:6-29, core/exceptions.py:3-50, the 4 `renderers.py`, settings.py:132-151, conduit/urls.py:22-24 | none | none | preserve with fixes (T-05, T-18) |
| F-15 | An operator provisions the schema and a superuser and can sign into the admin site | Operator | `manage.py` (stock), `create_superuser` authentication/models.py:38-53, `/admin/` conduit/urls.py:20, migrations ×7 | DB schema, superuser row | none | redesign? (T-16, T-20) |

Popular tags (`GET /api/tags`) belongs with F-10 browsing and is detailed under F-10.

---

## F-01 Register

**Goal**: A visitor registers with email, username and password. An account and an empty profile exist, and a usable token is returned at once.
**Sub-behaviors**: create user. Auto-create the profile. Return `{user: {email, username, token}}` with 201.
**Invariants**:
- Email and username are both unique. Duplicates fail with 400 `{"errors": {"email": [...]}}` / `{"username": [...]}` (ModelSerializer UniqueValidator from the model `unique=True` constraints, authentication/models.py:60,66).
- Password is 8 to 128 chars and never echoed (serializers.py:15-19). The `AUTH_PASSWORD_VALIDATORS` (settings.py:97-110) are **not** applied because the serializer never calls `validate_password` (inferred; see T-14).
- Only the email domain is lowercased (`normalize_email`, models.py:32). The local part keeps its case.
- The request body must be nested under `user`. A missing key behaves like `{}` and gives 400 field errors (views.py:20).
- Exactly one Profile per User: `OneToOneField` (profiles/models.py:11-13), created by the `post_save` signal only when `created` (authentication/signals.py:14-15). Transactionality is `unknown`: the views do not use `atomic`, so a profile insert failure may leave a user without a profile.
- Register response has **no** `bio`/`image` keys, unlike `GET /api/user` (serializers.py:29).
- No username character rules beyond max 255. Usernames with `-`, `.`, `@` or spaces can register but cannot be addressed by profile URLs (see T-12).
**Acceptance probes**:
- Given no users, when POST `/api/users` `{"user":{"email":"a@X.COM","username":"alice","password":"password1"}}`, then 201, body `user.email == "a@x.com"`, `user.username == "alice"`, `user.token` decodes (HS256) to `{id, exp≈now+60d}`, and `GET /api/profiles/alice` returns 200.
- Negative: Given `alice` exists, when registering username `alice` with another email, then 400 and `errors.username` is present.
- Negative: password `short`, then 400 with `errors.password`.
- Negative: body without the `user` wrapper, then 400 (all fields required).
**Side effects**: Profile row insert (signal).

## F-02 Log in

**Goal**: A user logs in with email and password and receives a fresh 60-day token.
**Sub-behaviors**: credential check, then return `{user: {email, username, token}}` with 200 (views.py:44-47, serializers.py:92-96).
**Invariants**:
- Email lookup is exact (`USERNAME_FIELD='email'`, models.py:85, via Django `ModelBackend`). Login with a differently-cased email fails (inferred; see T-17).
- Bad credentials give 400 `{"errors": {"error": ["A user with this email and password was not found."]}}`. The `error` key comes from `NON_FIELD_ERRORS_KEY` (settings.py:145, serializers.py:73-76).
- Deactivated users cannot log in. Django 1.10 `ModelBackend.user_can_authenticate` rejects them first, so they likely get the "not found" message rather than "deactivated" (serializers.py:82-85, inferred).
- Each login mints a new token. Old tokens stay valid until expiry, because there is no revocation list.
**Acceptance probes**:
- Given alice/password1, when POST `/api/users/login` `{"user":{"email":"a@x.com","password":"password1"}}`, then 200 with a valid token for alice's id.
- Negative: wrong password, then 400 and `errors.error[0] == "A user with this email and password was not found."`.
- Negative: Given alice is deactivated, then login gives 400 and no token.
**Side effects**: none (`last_login` is not updated because `authenticate()` alone does not call `login()`; inferred).

## F-03 Token identity on every request

**Goal**: Every request carrying `Token <jwt>` is attributed to that active user. Invalid, expired, orphaned or deactivated tokens are refused.
**Invariants**:
- Header form is exactly two space-separated parts with prefix `Token`, case-insensitive (backends.py:38-65). `Bearer x`, a bare `x`, or three parts are treated as **anonymous**, not as an error.
- Token: HS256, payload `{"id": <user pk>, "exp": <unix seconds>}`, expiry 60 days from issue (models.py:132-137). Signed with the hard-coded `SECRET_KEY` (settings.py:23). Keeping already-issued tokens valid after cutover needs the same key and claim layout (contract, see T-16).
- `exp` is computed from **local** `datetime.now()` with `strftime('%s')` (models.py:132-136). That is platform-dependent and host-TZ-dependent (inferred).
- Decoding uses `jwt.decode(token, SECRET_KEY)` with no `algorithms=` pin (backends.py:78). UNKNOWN: whether PyJWT 1.4.2 accepts other HMAC algorithms or `none` here (T-19).
- Refusals: decode failure gives "Invalid authentication. Could not decode token.", a missing user gives "No user matching this token was found.", and `is_active=False` gives "This user has been deactivated." (backends.py:79-91).
- Status for refusals is **403, not 401**. `JWTAuthentication` defines no `authenticate_header`, so DRF downgrades `AuthenticationFailed`/`NotAuthenticated` to 403 (inferred from DRF 3.4 `APIView.handle_exception`, **verify**).
- Authentication runs eagerly on every DRF view. A **bad token fails even public endpoints** (`GET /api/articles`, `/api/tags`, register, login) with 403 instead of being treated as anonymous (inferred, **verify**; T-06).
- No CSRF on the API: DRF views are csrf-exempt and no SessionAuthentication is configured (settings.py:147-149).
**Acceptance probes**:
- Given a valid token for alice, when GET `/api/user` with `Authorization: token <jwt>` (lowercase prefix), then 200 for alice.
- Given header `Bearer <jwt>`, when GET `/api/user`, then refused as unauthenticated ("Authentication credentials were not provided.").
- Negative: Given a token with `exp` in the past, then refused with "Invalid authentication. Could not decode token."
- Negative: Given alice is deactivated after her token was issued, when she calls any authenticated endpoint, then refused with "This user has been deactivated."
- Negative: Given a token for a deleted user id, then "No user matching this token was found."
- Negative: Given a garbage token, when GET `/api/tags`, then refused (legacy, **verify**). The target behavior depends on T-06.
**Side effects**: none.

## F-04 Own account

**Goal**: A signed-in user views and edits their own account (email, username, bio). The response carries a refreshed token.
**Sub-behaviors**: GET (views.py:55-61). PUT and PATCH both go to the same handler (views.py:63-84; DRF `partial_update` delegates to `update`).
**Invariants**:
- Response `{user: {email, username, token, bio, image}}` (serializers.py:124-127). `image` is the **raw stored value** (often `""`). Profile/author cards substitute a default smiley URL instead (profiles/serializers.py:17-21).
- A **new token is minted on every GET/PUT** (`token` property, models.py:100-109), giving sliding 60-day expiry for active clients.
- Omitted fields keep current values (views.py:66-74).
- **Password changes are silently ignored**: the view never copies `password` into `serializer_data` (views.py:66-74), even though `UserSerializer.update` handles it (serializers.py:147-161). Observed. See T-07.
- **Image changes are silently ignored**: the nested `ProfileSerializer.image` is a read-only `SerializerMethodField` (profiles/serializers.py:9), so validation drops it (inferred). See T-07.
- Email/username uniqueness gives 400 field errors. Email is not normalized on update (setattr, serializers.py:153-156).
- User save and profile save are separate statements with no transaction (serializers.py:166,174). Partial update on failure is `unknown`.
- Unauthenticated gives 403 `{"user": {"detail": "Authentication credentials were not provided."}}` (F-14 envelope quirk, inferred).
**Acceptance probes**:
- Given alice, when PUT `/api/user` `{"user":{"bio":"hi"}}`, then 200, `user.bio=="hi"`, email and username unchanged, and the token is valid.
- Given alice and bob, when alice PUTs `username: "bob"`, then 400 `errors.username`.
- Legacy quirk (keep or fix per T-07): when alice PUTs `{"user":{"password":"newpassword"}}`, then 200 but login with `newpassword` fails and the old password still works.
- Negative: with no token, then refused (403 legacy) and nothing changes.
**Side effects**: none beyond row updates.

## F-05 View profile

**Goal**: Anyone views a user's public profile and sees whether they follow that user.
**Invariants**:
- Response `{profile: {username, bio, image, following}}` (profiles/serializers.py:14). `image` defaults to `https://static.productionready.io/images/smiley-cyrus.jpg` when blank (serializers.py:17-21). `following` is `false` for anonymous callers (serializers.py:26-30).
- URL username must match `\w+` (profiles/urls.py:6). Other usernames get a Django-level 404 (HTML debug page under `DEBUG=True`), not the JSON error (inferred; T-12).
- Unknown username gives 404 `{"errors": {"profile": "A profile with this username does not exist."}}`. The key `profile` is the queryset model's verbose_name (core/exceptions.py:35-45, views.py:15,25).
- Deactivated users' profiles are still visible. There is no `is_active` filter anywhere in reads (observed absence). Same for their articles and comments. Note that the authentication/models.py:68-73 comment claims deactivated users "won't show up on the site anymore", and the code does not do this (T-20).
**Acceptance probes**:
- Given alice with a blank image, when an anonymous caller GETs `/api/profiles/alice`, then 200 with `image == smiley URL` and `following == false`.
- Given bob follows alice, when bob GETs it, then `following == true`.
- Negative: GET `/api/profiles/nobody` gives 404 with `errors.profile`.
**Side effects**: none.

## F-06 Follow / unfollow

**Goal**: A signed-in user follows or unfollows another user. Following yourself is refused.
**Invariants**:
- Directed relation, not symmetric (profiles/models.py:29-33). Follow is idempotent (M2M `add`) and unfollow of a non-followed user is a no-op (models.py:44-50).
- POST gives **201**, DELETE gives **200**, both returning the followee's profile with `following` updated (views.py:53,72).
- Self-follow guard: `follower.pk is followee.pk` (views.py:63). This is identity comparison on ints and only holds for CPython's small-int cache (pk ≤ 256). **Users with pk > 256 can follow themselves** (inferred defect; T-08). Error shape is `{"errors": ["You can not follow yourself."]}` (a list, because the ValidationError has no field; core/exceptions.py:26-33).
- Unknown username gives 404 `{"errors": {"detail": "A profile with this username was not found."}}`. This APIView has no `queryset`, so the generic shape applies (core/exceptions.py:47-48).
**Acceptance probes**:
- Given alice and bob, when bob POSTs `/api/profiles/alice/follow`, then 201, `profile.following == true`, and repeating it is still 201 with a single edge.
- When bob DELETEs it, then 200 and `following == false`. Repeating gives 200.
- Negative: alice POSTs `/api/profiles/alice/follow`, then 400 "You can not follow yourself." for **every** pk (target fixes the defect).
- Negative: anonymous POST gives a refusal and no edge.
**Side effects**: follow edge insert/delete.

## F-07 Publish article

**Goal**: A signed-in user publishes an article with title, description, body and tags. It gets a unique URL slug.
**Invariants**:
- Body under `article`. `title` and `body` are required. `description` is optional and defaults to `""` (serializers.py:11; TextField default). `tagList` is optional (serializers.py:19).
- Slug = `slugify(title)` + `-` + 6 random `[a-z0-9]` chars, truncated to ≤255 at hyphen boundaries (articles/signals.py:9-31, core/utils.py:4-7). Generated **only when slug is empty**. A collision is not retried and hits the unique constraint, giving a 500 (inferred; T-11).
- **Client may supply `slug`** (writable `SlugField(required=False)`, serializers.py:12), which bypasses generation (T-10).
- Tags are found or created by `(tag=name, slug=name.lower())` (relations.py:10-13). Name matching is case-sensitive while `Tag.slug` is unique, so posting `Django` after `django` exists gives an IntegrityError and a 500 (inferred; T-09). Tags are never deleted.
- Article insert and tag inserts are not in one transaction (serializers.py:49-52). Partial state on failure is `unknown`.
- Response 201 `{article: {author, body, createdAt, description, favorited, favoritesCount, slug, tagList, title, updatedAt}}`. Timestamps use Python `isoformat()` in UTC: `2017-04-27T10:00:00.123456+00:00` (microseconds, `+00:00`, not `Z`) (serializers.py:56-57,73-74, settings.py:118,124).
- `tagList` order in the response follows the M2M query order. UNKNOWN: whether it matches the input order (Tag default ordering is `-created_at`, migrations 0003:25).
**Acceptance probes**:
- Given alice, when she POSTs `{"article":{"title":"How to train","description":"d","body":"b","tagList":["dragons","training"]}}`, then 201 and the slug matches `^how-to-train-[a-z0-9]{6}$`. `tagList` contains both tags, `favorited == false`, `favoritesCount == 0`, and `author.username == "alice"`.
- Given a 300-char title with no hyphens, then the slug length is ≤ 255 and ends with `-xxxxxx`.
- Negative: missing title gives 400 `errors.title`. Anonymous POST gives a refusal and no row.
- Negative (target decision T-09): Given tag `django` exists, when posting tag `Django`, then **not** a 500.
**Side effects**: Tag rows created on demand.

## F-08 Revise (and delete) article

**Goal**: The author of an article revises it. Legacy reality: any signed-in user can revise any article, and articles cannot be deleted.
**Invariants**:
- Only `PUT /api/articles/:slug` is routed. The viewset has no `partial_update`/`destroy`, so PATCH and DELETE give 405 (views.py:14-17. DRF router maps only methods that exist; inferred).
- **No ownership check**: `IsAuthenticatedOrReadOnly` only (views.py:21,87-106). Observed defect (T-01).
- Partial semantics (`partial=True`). Changing the title does **not** change the slug (the signal only fires when slug is empty). The slug itself may be overwritten by the client (T-10).
- `tagList` on update: DRF 3.4 default `ModelSerializer.update` assigns the M2M directly, so tags are replaced (inferred, **verify**).
- `updatedAt` advances on any save (`auto_now`, core/models.py:9).
- Unknown slug gives 404 `{"errors": {"article": "An article with this slug does not exist."}}`.
- Deleting a profile cascades to its articles, comments and favorite edges (CASCADE, migrations articles/0001:28, 0002:24-25). This is reachable only via the admin or shell.
**Acceptance probes**:
- Given alice's article, when alice PUTs `{"article":{"body":"new"}}`, then 200, body updated, slug unchanged, `updatedAt > createdAt`.
- Negative (target, T-01): when bob PUTs to alice's article, then 403 and the article is unchanged. **Legacy returns 200 and applies the change.**
- Negative: DELETE `/api/articles/:slug` gives 405 in legacy. The target depends on T-03.
**Side effects**: none.

## F-09 Read article

**Goal**: Anyone reads a single article with its author card, favorite count and tag list.
**Invariants**:
- `favorited` is true only for an authenticated caller who favorited it. `favoritesCount` = number of favoriting profiles (serializers.py:59-71). `author.following` follows the F-05 rules.
- The route regex is `[^/.]+` with no trailing slash for the detail route (DRF router `trailing_slash=False`, urls.py:10). The format-suffix variant `/api/articles/<slug>.json` also exists (DefaultRouter, inferred).
**Acceptance probes**:
- Given bob favorited alice's article, when bob GETs it, then `favorited == true`, `favoritesCount == 1`. An anonymous caller sees `favorited == false`, `favoritesCount == 1`.
- Negative: an unknown slug gives 404 with `errors.article`.
**Side effects**: none.

## F-10 Browse articles and tags

**Goal**: Anyone browses the global article list newest-first, filters it by tag, author or favoriting user, and pages through it. Anyone lists all tags.
**Sub-behaviors**: list, filter (`tag`, `author`, `favorited`, combinable with AND), paginate (`limit`, `offset`), list tags (`GET /api/tags`, articles/views.py:196-208).
**Invariants**:
- Order is `-created_at, -updated_at` (TimestampedModel Meta, core/models.py:18; migrations articles/0001:32). Ties beyond that are undefined.
- Page size defaults to 20 with LimitOffset pagination (settings.py:150-151). **No max `limit`** (T-13). Envelope `{articles: [...], articlesCount: <total matching>}`. `next`/`previous` are dropped by the renderer (core/renderers.py:13-17).
- `tag` filter is an exact, case-sensitive match on the tag name (views.py:32-34). `author` and `favorited` are exact usernames (views.py:28-40). An unknown filter value gives an empty list, not 404.
- Tags: `{"tags": ["a", "b"]}`, unpaged, all tags ever created including orphans, ordered newest-first (Tag ordering, migrations 0003:25). It uses DRF default renderers (no custom envelope), so the browsable HTML renderer also answers `Accept: text/html` (incidental).
**Acceptance probes**:
- Given 25 articles, when GET `/api/articles`, then 20 items newest-first and `articlesCount == 25`. `?limit=10&offset=20` returns 5.
- Given articles tagged `dragons` by alice and favorited by bob, then `?tag=dragons&author=alice&favorited=bob` returns only those.
- Negative: `?author=nobody` gives 200, `articles == []`, `articlesCount == 0`.
- Given tags created in order a, b, then GET `/api/tags` returns `{"tags":["b","a"]}` (legacy order; decide whether to keep it).
**Side effects**: none.

## F-11 Personal feed

**Goal**: A signed-in user sees a newest-first paged feed of articles by authors they follow.
**Invariants**:
- Requires authentication (views.py:212). Articles where author ∈ the caller's follows (views.py:217-220). Same envelope, paging and order as F-10.
- **Route shadowing**: the router's detail pattern `^articles/(?P<slug>[^/.]+)$` is included before `^articles/feed/?$` (urls.py:14 vs 16). `GET /api/articles/feed` therefore resolves to *retrieve article with slug "feed"* and returns 404, and only `GET /api/articles/feed/` reaches the feed (inferred from URL order, **verify**; T-04).
**Acceptance probes**:
- Given bob follows alice and alice has 2 articles and carol 1, when bob GETs the feed, then 2 articles, `articlesCount == 2`.
- Given bob follows nobody, then `articles == []`.
- Negative: anonymous gets a refusal.
- Negative (target, T-04): `GET /api/articles/feed` without a trailing slash returns the feed, not a 404.
**Side effects**: none.

## F-12 Favorite / unfavorite

**Goal**: A signed-in user favorites or unfavorites an article. Counts and the `favorited` flag reflect it.
**Invariants**:
- POST gives 201 and DELETE gives 200, both returning the full article (views.py:178,193). Both are idempotent (M2M add/remove, profiles/models.py:60-66).
- Authors may favorite their own articles (no guard).
- Unknown slug gives 404 `{"errors": {"detail": "An article with this slug was not found."}}` (generic shape, because the APIView has no queryset).
- Favoriting does not change the article's `updatedAt` (M2M edge only).
**Acceptance probes**:
- Given bob and alice's article, when bob POSTs favorite twice, then 201 both times and `favoritesCount == 1`.
- When bob DELETEs, then 200, `favorited == false`, `favoritesCount == 0`.
- Negative: anonymous POST gives a refusal and the count is unchanged.
**Side effects**: favorite edge insert/delete.

## F-13 Comments

**Goal**: Anyone reads an article's comments. A signed-in user adds a comment, and the comment's author (target) deletes it.
**Sub-behaviors**: list (GET), add (POST), delete (DELETE by id).
**Invariants**:
- List: newest-first (Comment ordering, migrations 0002:28), **paginated** with default 20 (ListCreateAPIView plus global pagination), envelope `{comments: [...], commentsCount: N}`. The RealWorld spec expects all comments (T-15). An unknown article slug gives an empty list, not 404 (views.py:120-126).
- Comment shape `{id, author{profile}, body, createdAt, updatedAt}` (serializers.py:84-91).
- Add: body under `comment`, `body` required. Unknown article gives 404 `{"errors": {"comment": "An article with this slug does not exist."}}`. The key is `comment` because the view's queryset model is Comment (core/exceptions.py:38-45; inferred). Returns 201. If the client sends `author` in the body, the writable nested field collides with the context author, giving a TypeError and a 500 (inferred, serializers.py:78,97-99).
- Delete: **any signed-in user can delete any comment**, and the `:slug` in the URL is never checked against the comment's article (views.py:144-157). Observed defect (T-02). Returns 204 with an empty body. Unknown id gives 404 `{"errors": {"comment": "A comment with this ID does not exist."}}`.
- Deleting an article (admin/shell only) cascades its comments.
**Acceptance probes**:
- Given alice's article, when bob POSTs `{"comment":{"body":"nice"}}`, then 201, `comment.author.username == "bob"`, and an anonymous GET lists it first.
- Given 25 comments, legacy GET returns 20 and `commentsCount == 25` (target per T-15).
- Negative: anonymous POST gives a refusal.
- Negative (target, T-02): carol deletes bob's comment, giving 403, and the comment still exists. **Legacy: 204 and deleted.**
- Negative (target): DELETE `/api/articles/other-slug/comments/<id of comment on alice's article>` gives 404.
**Side effects**: comment row insert/delete.

## F-14 API contract for RealWorld frontends

**Goal**: RealWorld frontends get one predictable JSON contract: object envelopes, paged lists with counts, `errors` bodies, and URLs that accept an optional trailing slash. Browsers on the whitelisted origin may call it.
**Invariants**:
- Success envelopes: a single object under `user`/`profile`/`article`/`comment`. Lists under `articles`+`articlesCount` and `comments`+`commentsCount`. Tags under `tags` (core/renderers.py:12-29, the 4 renderers).
- Validation errors: `{"errors": {<field>: [msgs], "error": [non-field msgs]}}` or `{"errors": [msgs]}` for a bare ValidationError. Status 422 is **not** used (RealWorld spec uses 422; legacy uses 400) (core/exceptions.py:9-33).
- NotFound: `{"errors": {<model verbose_name>: msg}}` when the view has a queryset, otherwise `{"errors": {"detail": msg}}` (core/exceptions.py:35-50).
- **Every other error** (auth refusal, 403, 405, parse error) keeps DRF's `{"detail": msg}`, and the view's renderer then wraps it under the object label, e.g. `{"article": {"detail": "Method \"DELETE\" not allowed."}}` or `{"user": {"detail": "Authentication credentials were not provided."}}` (core/renderers.py:23-29; inferred, **verify**; T-18).
- URLs: hand-written routes accept an optional trailing slash (`/?$`). Router routes (`/api/articles`, `/api/articles/:slug`) do not (articles/urls.py:10). `GET /api/` serves the DRF API-root index (DefaultRouter, incidental).
- CORS: only origins `0.0.0.0:4000` and `localhost:4000` (settings.py:132-135). Credentials and headers use django-cors-middleware 1.3.1 defaults (UNKNOWN exact header list).
- Request bodies are JSON or form (DRF default parsers). The resource payload is nested under a key (`user`/`article`/`comment`).
**Acceptance probes**:
- For every endpoint, the response `Content-Type` is JSON and the top-level key matches the table above (contract snapshot suite).
- Given the origin `http://localhost:4000`, a preflight for `PUT /api/user` with an `Authorization` header is allowed. Negative: origin `http://evil.test` gets no `Access-Control-Allow-Origin`.
- Negative: a malformed JSON body gives 400 with a body that has no stack trace.
**Side effects**: none.

## F-15 Operator provisioning and admin

**Goal**: An operator provisions the schema and a superuser and can sign into the admin site.
**Sub-behaviors**: `manage.py migrate` (7 migrations across articles/authentication/profiles), `manage.py createsuperuser` (custom manager requires username, email and password; models.py:38-53), `/admin/` session login (conduit/urls.py:20), `django_extensions` dev commands (requirements.txt:3).
**Invariants**:
- Superuser = `is_staff=True, is_superuser=True`. Admin login uses Django sessions and CSRF (settings.py:51-60).
- No `admin.py` exists in any app, so Articles, Comments, Tags and Profiles are **not** manageable in the admin. UNKNOWN: whether the custom `User` shows up (the stock `auth.admin` registers the default `User`, which is swapped out here). Deactivating a user therefore has no evidenced UI; it is possible only via the shell (T-20).
- Config is hard-coded: `SECRET_KEY`, `DEBUG=True`, `ALLOWED_HOSTS=[]`, SQLite file `db.sqlite3` (settings.py:23-28,86-91). There are no env vars.
**Acceptance probes**:
- Given an empty DB, when the operator runs the target's migrate and create-admin tasks, then an admin can authenticate and API registration works.
- Negative: a non-staff API user cannot sign into the admin surface.
**Side effects**: schema, superuser row.

---

## Triage Questions

Default is `preserve`. Each item cites code, because no legacy tests exist.

1. **T-01 F-08 (redesign)** Any authenticated user can edit any article (articles/views.py:87-106, permission `IsAuthenticatedOrReadOnly` only). Suggest restricting edits to the author with 403. This looks like a security defect and the RealWorld spec implies author-only.
2. **T-02 F-13 (redesign)** Any authenticated user can delete any comment, and the URL slug is ignored (views.py:144-157). Suggest author-only (perhaps also the article author) and requiring that the slug match.
3. **T-03 F-08 (redesign?)** `DELETE /api/articles/:slug` returns 405. Deletion was never implemented (viewset lacks `DestroyModelMixin`, views.py:14-17). The RealWorld spec and stock frontends call it. Add author-only delete with cascading comments and favorites, or keep the 405?
4. **T-04 F-11 (redesign)** `GET /api/articles/feed` is probably shadowed by the article-detail route and returns 404, so only `/feed/` works (urls.py:14-16). Verify on a running legacy instance, then fix in the target.
5. **T-05 F-03/F-14 (redesign?)** Missing or invalid credentials return 403, not 401 (no `authenticate_header`). The RealWorld spec and some frontends expect 401 to trigger re-login. Keep 403 or move to 401?
6. **T-06 F-03 (redesign?)** A bad or expired token on a **public** endpoint (article list, tags, login, register) is refused instead of being treated as anonymous. A stale token in a frontend therefore breaks even login. Keep it?
7. **T-07 F-04 (redesign)** `PUT /api/user` silently ignores `password` (views.py:66-74) and `image` (read-only method field, profiles/serializers.py:9). The RealWorld spec allows both. Enable them, or document that they are unsupported?
8. **T-08 F-06 (drop defect)** The self-follow guard uses `is` (views.py:63) and fails for pk > 256. The target should refuse self-follow for every user. Should existing self-follow edges in the data be purged at migration?
9. **T-09 F-07 (redesign)** Tags differing only by case cause an IntegrityError and a 500 (relations.py:11 vs unique `Tag.slug`). Canonicalize case-insensitively (reuse the existing tag) or reject with 400?
10. **T-10 F-07/F-08 (preserve?)** Clients can set or overwrite `slug` on create and update (serializers.py:12). That allows vanity URLs and also slug hijack or rename that breaks links. Keep, or make the slug server-owned?
11. **T-11 F-07 (preserve?)** Slug suffix collisions are not retried, giving a 500 (signals.py:15-31; ~2.2e9 space so rare). The slug does not follow title edits. Keep both? The suggestion is to retry on conflict in the target (a strengthening).
12. **T-12 F-05/F-06 (redesign?)** Profile URLs accept only `\w+` usernames (profiles/urls.py:6,7) while registration accepts any characters. Such users have unreachable profiles. Restrict usernames at registration, or widen the URL pattern?
13. **T-13 F-10 (redesign?)** `limit` is unbounded (LimitOffsetPagination with no `max_limit`). Add a cap such as 100?
14. **T-14 F-01 (preserve?)** The configured Django password validators (common-password, numeric, similarity) are never applied. Only the 8-char minimum holds. Keep the weaker rule for parity, or enforce stronger validation (changes the registration contract)?
15. **T-15 F-13 (redesign?)** Comments are paginated (20) with `commentsCount`. The RealWorld spec returns all comments without a count, so stock frontends show at most 20. Return all comments?
16. **T-16 F-03/F-15 (contract decision)** Tokens are HS256 and signed with a hard-coded, committed `SECRET_KEY`. Should the target accept existing tokens (same key and claims, so a leaked key keeps working), or rotate the key and force every user to log in again at cutover?
17. **T-17 F-02 (preserve?)** Login email matching is case-sensitive, while registration lowercases only the domain. Users who typed different casing cannot log in. Normalize in the target?
18. **T-18 F-14 (preserve?)** Non-validation errors render as `{"<object>": {"detail": ...}}` instead of `{"errors": ...}`, and validation errors use 400 rather than the spec's 422. Do any clients rely on these shapes? Keep them for parity or align with the spec?
19. **T-19 F-03 (redesign)** The JWT decode does not pin `algorithms` (backends.py:78). The target should accept HS256 only. UNKNOWN: whether legacy accepted other algorithms, so check whether any client relies on that.
20. **T-20 F-05/F-15 (preserve?)** Deactivation exists only as a flag. No surface sets it, and deactivated users' content and profiles stay publicly visible, contrary to the comment at authentication/models.py:68-73. Does the target need a deactivation surface, and should reads hide deactivated users?

## Coverage

Budget used: about 46 source files and about 65 KB of source read, plus inventory, charter, budget and KB headings. Well under the 200-file / 1 MB budget. Stop condition: every surface mapped.

| Surface | Mapped | Not mapped (why) |
|---------|--------|------------------|
| `POST /api/users`, `POST /api/users/login` | F-01, F-02 | — |
| `GET/PUT/PATCH /api/user` | F-04 | — |
| `GET /api/profiles/:u`, `POST/DELETE /api/profiles/:u/follow` | F-05, F-06 | — |
| `GET/POST /api/articles`, `GET/PUT /api/articles/:slug` (router) | F-07..F-10 | DELETE/PATCH have no handler (T-03) |
| `GET /api/articles/feed` | F-11 | Shadowing needs runtime verification (T-04) |
| `POST/DELETE /api/articles/:slug/favorite` | F-12 | — |
| `GET/POST /api/articles/:slug/comments`, `DELETE …/comments/:id` | F-13 | — |
| `GET /api/tags` | F-10 | — |
| JWT auth backend, exception handler, renderers, CORS | F-03, F-14 | Exact django-cors-middleware 1.3.1 default headers: UNKNOWN (dependency not read) |
| Signals (`post_save` User → Profile, `pre_save` Article slug) | F-01, F-07 | Mechanism detail belongs to the archaeologist |
| DefaultRouter extras: `GET /api/` API root, `.json` format-suffix routes, browsable HTML renderer | F-14 (noted as incidental) | No consumer evidenced. The contract-surveyor should classify them |
| `/admin/` Django admin | F-15 | Which models are registered for the swapped `User`: UNKNOWN (framework internals not read) |
| `manage.py` (migrate, createsuperuser, django_extensions commands) | F-15 | django_extensions commands are dev tooling with no app-specific commands found |
| Background jobs, mailers, cron, websockets, caches | — | None exist (no Celery, no email backend usage, no channels) |
| Legacy tests | — | **None exist in the source.** Every invariant is code-read or framework-inferred. Probes marked (verify) need an isolated legacy run |
| Migration vs model drift: `follows` migration (profiles/0002:18) omits `symmetrical=False` | — | Referred to the archaeologist/data-compat. Runtime uses the model's asymmetric definition |

## Triage Decisions

Answered under `--auto` (2026-10-09) using the compatibility-bar class defaults: ordinary behaviour → `preserve` (ASSUMED), defect → `UNDECIDED`, security defect → `change → safe behaviour` (ASSUMED, never preserve). Every ASSUMED value needs approval in ADR-000.

| ID | Class | Decision | Note |
|----|-------|----------|------|
| T-01 | security defect (authz bypass) | change → author-only article update, 403 otherwise — ASSUMED | C-32, M-27 |
| T-02 | security defect (authz bypass) | change → comment delete limited to the comment author and scoped to the URL's article — ASSUMED | C-33, M-27; whether the article author may also delete is UNDECIDED |
| T-03 | defect (spec gap) | UNDECIDED | article DELETE 405 (C-36) |
| T-04 | defect | UNDECIDED | feed route shadowing (C-35), unverified (lib) |
| T-05 | defect (contracts.md classes C-16 as defect) | UNDECIDED | C-16, M-10; aligned with ADR-000 |
| T-06 | defect (part of C-16) | UNDECIDED | C-16; aligned with ADR-000 |
| T-07 | defect | UNDECIDED | PUT /api/user ignores password/image (C-37) |
| T-08 | defect | UNDECIDED | `is` self-follow guard (C-38); data purge also UNDECIDED |
| T-09 | defect (500 on input) | UNDECIDED | case-variant tags (C-08) |
| T-10 | ordinary | preserve client-writable slug — ASSUMED | after T-01, only the author can change it |
| T-11 | split | slug fixed on title edit: preserve — ASSUMED; suffix-collision 500: defect → UNDECIDED | signals.py:15-31 |
| T-12 | defect | UNDECIDED | `\w+` profile route vs any-char usernames (C-39) |
| T-13 | ordinary | preserve unbounded `limit` — ASSUMED | C-24 |
| T-14 | ordinary | preserve 8-char minimum only — ASSUMED | |
| T-15 | ordinary | preserve comment paging at 20 + `commentsCount` — ASSUMED | C-23 |
| T-16 | security defect (secret exposure, token forgery) | change → rotate key, legacy tokens rejected, clients log in again — ASSUMED | C-14, C-11; never preserve the committed key |
| T-17 | ordinary | preserve case-sensitive email login — ASSUMED | C-04 |
| T-18 | ordinary | preserve legacy error shapes and 400 validation status — ASSUMED | C-26, M-08/M-09 |
| T-19 | security defect (token forgery class) | change → accept HS256 only — ASSUMED | M-05 |
| T-20 | ordinary | preserve (no deactivation surface; reads not filtered) — ASSUMED | |
| (C-34) | security defect (secret exposure via DEBUG pages) | change → JSON 500, no debug pages — ASSUMED | not in the T-list; added from contracts.md |
