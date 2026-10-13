# Divergences — Conduit (django-realworld → Phoenix)

Every behaviour the target changes against legacy @ 29c9d42831fa. **Approval is `pending` on every row**: ADR-000 is ASSUMED under `--auto`, and
no agent message counts as the user's approval. Legacy behaviour marked *(lib)* or "inferred" in the analysis is unverified until an isolated legacy
run (contracts Q7).

## Designed changes (in the architecture, pending approval)

| ID | Ledger | Legacy behavior | New behavior | Reason | Consumers | Approval |
|----|--------|-----------------|--------------|--------|-----------|----------|
| DV-01 | C-14, M-06, C-11 | tokens signed with the committed `SECRET_KEY`; legacy tokens valid for up to 60 days | new `JWT_SECRET` from env; legacy-signed tokens rejected (403 under the C-16 status quo); every client logs in once | security defect: anyone can forge tokens (ADR-000, ADR-006) | every logged-in client | pending (ASSUMED in ADR-000) |
| DV-02 | C-15 | HS384/HS512 tokens signed with the key also verify *(lib)* | HS256 only | security defect, forgery class (ADR-006) | none known (only HS256 is issued) | pending (ASSUMED in ADR-000) |
| DV-03 | C-32, M-27 | any signed-in user can update any article, slug included | author only; others get 403 (body shape: DV-P6) | security defect, authz bypass (ADR-008) | non-authors lose write access | pending (ASSUMED in ADR-000) |
| DV-04 | C-33, M-27 | any signed-in user can delete any comment by id via any article slug | comment author only; comment must belong to the URL's article (404 otherwise); others 403 | security defect, authz bypass (ADR-008) | non-authors lose delete access | pending (ASSUMED in ADR-000) |
| DV-05 | C-34 | Django technical 404/500 pages with URL list, settings, traceback | JSON 404/500, no stack, headers or route list | security defect, information exposure (ADR-009, ADR-011) | none legitimate | pending (ASSUMED in ADR-000) |
| DV-06 | C-44 | only `DJANGO_SETTINGS_MODULE`; secrets hard-coded | required `JWT_SECRET`, `SECRET_KEY_BASE`, `DATABASE_PATH`, `PHX_HOST`, `PORT`; optional `CORS_ORIGINS`, `JWT_SECRET_PREVIOUS`; boot fails closed | consequence of C-14, C-34 (ADR-011) | operators | pending (ASSUMED in ADR-000) |
| DV-07 | C-45 | `GET /api/` API root, `.json` suffix routes, `?format=` | not served (JSON 404) | incidental, relaxed (ADR-009) | none found | pending |
| DV-08 | C-46, M-34 | browsable HTML API on `Accept: text/html` | JSON only | incidental, relaxed | none found | pending |
| DV-09 | C-47 | DRF `OPTIONS` metadata JSON | OPTIONS answered only as CORS preflight | incidental, relaxed | none found | pending |
| DV-10 | C-48 | HTML 404 pages; `APPEND_SLASH` redirects on non-API paths | JSON 404; no redirects | incidental, relaxed | none found | pending |
| DV-11 | C-49 | `isoformat()` text: `+00:00`, microseconds omitted when zero | always `YYYY-MM-DDTHH:MM:SS.ffffff+00:00` (C-30 kept) | incidental, relaxed | none found (clients parse ISO 8601) | pending |
| DV-12 | C-50 | `json.dumps` separators, `ensure_ascii` | Jason default encoding (compact, UTF-8) | incidental, relaxed | none found | pending |
| DV-13 | C-51 | only `X-Frame-Options: SAMEORIGIN` | Phoenix `put_secure_browser_headers` (includes x-frame-options, x-content-type-options, …) | incidental, relaxed | none found | pending |
| DV-14 | C-52, M-33, R-11, R-41 | Django admin at `/admin/` with session login | retired; operator release tasks instead | incidental per ADR-000; **purpose unknown** (OD-5) (ADR-012) | unknown operators | pending |
| DV-15 | C-53 | Django framework tables used by admin/permissions | tables left in place, unmapped, never written | incidental, relaxed (ADR-004) | none (API never reads them) | pending |
| DV-16 | C-54 | `PATCH /api/user` behaves like PUT | PUT only; PATCH → JSON 404 | incidental, relaxed | none found (spec defines PUT) | pending |
| DV-17 | C-55 | `is_staff`/`is_superuser`/`last_login` carry Django semantics | columns kept, written with legacy defaults, no behaviour | incidental, relaxed (ADR-012) | none found | pending |
| DV-18 | C-56 | `[-\w]+` vs `[^/.]+` slug patterns per route | one matcher (any path segment) on all article routes | incidental, relaxed | client-set slugs containing `.` become reachable | pending |
| DV-19 | C-17 | `/api/articles/` and `/api/articles/<slug>/` → HTML 404 *(lib)* | trailing slash accepted on every route (VO-08) | Phoenix default; relaxed inside the kept C-17 row by ADR-000 | none found | pending |
| DV-20 | M-21, M-01, M-18, M-20, C-05 | autocommit: partial writes possible (user without profile, article with some tags) | each multi-write operation commits atomically | strengthening (ADR-010) | none rely on partial state | pending |
| DV-21 | M-26 | FKs declared but not enforced; orphans tolerated | `foreign_keys` ON (ecto_sqlite3 default, VO-04); parent deletes remove children explicitly; orphans must be resolved before cutover | strengthening (ADR-004) | write paths only; pre-cutover orphan scan | pending |
| DV-22 | R-10 | rollback journal (Django default); a plain file copy is a backup | WAL with `synchronous: :full`; `-wal`/`-shm` files beside `db.sqlite3`; backups via `VACUUM INTO`; rollback hand-back resets journal mode | readers no longer block the writer (ADR-003); measurement-gated | operators who copy the file | pending |
| DV-23 | M-12 | ties beyond `-created_at, -updated_at` undefined | `desc: :id` tiebreak | deterministic paging (incidental widening) | none | pending |
| DV-24 | C-03, M-11 | Django writes `HH:MM:SS` without fraction when microseconds are 0 | port always writes 6 fraction digits; reads both | ordering parity across legacy and port rows (ADR-005) | none (C-03 sorting kept) | pending |
| DV-25 | M-05 | `exp` from host-local `datetime.now().strftime('%s')` (host-TZ dependent, glibc-only) | `exp` = UTC epoch seconds + 60 days | platform artifact removed (ADR-006) | clients on a non-UTC legacy host saw shifted expiry | pending |

## Proposed by consults, NOT adopted (the design keeps the legacy or open behaviour until the user decides)

| ID | Ledger | Legacy behavior | Proposed behavior | Source | Status in the design | Approval |
|----|--------|-----------------|-------------------|--------|----------------------|----------|
| DV-P1 | C-08 | case-variant tag → 500 | reuse the existing tag by lowercase slug (no 5xx) | ecto-schema-designer Q3 | ledger UNDECIDED; alternative is 400 | pending (UNDECIDED in ADR-000) |
| DV-P2 | C-09 | slug suffix collision → 500 | retry generation up to N times, then 4xx | ecto-schema-designer Q3 | ledger UNDECIDED | pending (UNDECIDED in ADR-000) |
| DV-P3 | C-24 | no max `limit` | cap (e.g. 1000) | security-analyzer Q5 | not built; C-24 is a kept contract, so a cap needs a new ADR moving it to "Changed" | pending |
| DV-P4 | — (new) | no rate limiting | Hammer 7.5.0 on login (IP + lowercased email) and register (IP); 429 `{"user":{"detail":"Request was throttled. Expected available in N seconds."}}` | security-analyzer Q5 | not built; tied to OD-2; adds a status code to C-25/C-13 surfaces | pending |
| DV-P5 | C-11 | PyJWT 1.4.2 accepts a token without `exp` | reject tokens missing `exp` | security-analyzer Q2 | verifier does not require `exp` until approved (ADR-006) | pending |
| DV-P6 | C-32, C-33 | no 403 exists on these routes (legacy allowed the action) | 403 body: `{"article":{"detail":"You do not have permission to perform this action."}}` on article update; bare `{"detail":…}` on comment delete | security-analyzer Q4 | 403 status designed (ASSUMED, DV-03/04); body text and shape frozen only after approval | pending |
| DV-P7 | C-02, M-16 | new hashes at 30,000 PBKDF2 iterations | ~600,000 iterations with rehash on login | security-analyzer Q1 | configured 30,000 (legacy); conflicts with ADR-000 no-regression goal for login; OD-2 in ADR-007 | pending |
| DV-P8 | C-41 | comment `author` key → 500; non-object JSON body → 500; request body limit per Django defaults (verify) | `author` ignored (201); non-object body → 400 field-required; `Plug.Parsers` `length:` ~1 MB | security-analyzer Q5 | ledger UNDECIDED; a 500 is never reproduced; body limit value open | pending (UNDECIDED in ADR-000) |

## Undecided defects with no divergence yet

These change behaviour only once decided; each blocks only its slice (ledger rows UNDECIDED):
C-16 (403 vs 401; bad token on public endpoints), C-35 (feed shadowing), C-36 (article DELETE), C-37 (PUT `/api/user` password and image),
C-38 (self-follow for every id; purge of existing self-follow rows), C-39 (profile route charset), C-40 (bio/image on register and login),
and whether an article's author may delete others' comments on it (T-02 note, ADR-008).
