# Consult: security-analyzer — legacy crypto, capabilities, abuse controls

**Scope**: ADR-000 Identity (ASSUMED: keep sessions and hashes, keep all signed URLs), contracts C-07, C-08, C-10, C-20..C-24, C-27, C-42, C-43, C-57, and mechanisms M-07, M-27, M-29, M-36..M-38, M-44.
**Source**: reference @ `90b330024dec`. Rails is **`main` @ `1a02651ac37f` (8.2.0.alpha)**, `config.load_defaults 8.2`. No gems are vendored in the reference tree, so every claim about framework defaults is *inferred* until it is checked against the pinned gem source or a vector.

Confidence labels:
- **confirmed**: read directly in app code.
- **inferred**: Rails framework default as I know it for 7.1+/8.x, not checked against the pinned commit.
- **needs-vector**: must be pinned by a known-answer vector from the pinned image before code ships.

---

## Answers

### Q1. How to verify and mint each legacy artifact

**Common facts**

- `SECRET_KEY_BASE` comes from the env (C-51). There are no `secret_key_base` rotations, no cookie rotators and no custom `key_generator_hash_digest_class`, `cookies_serializer` or `message_serializer` settings anywhere in `config/`. **confirmed** (grep over `config/`, `app/`, `lib/`)
- Rails' application key generator is `CachingKeyGenerator(KeyGenerator(secret_key_base, iterations: 1000, hash_digest_class: SHA256))`. SHA256 has been the default since `load_defaults 7.0`. `generate_key(salt)` returns 64 bytes by default. **inferred / needs-vector**
- Elixir equivalent: `Plug.Crypto.KeyGenerator.generate(skb, salt, iterations: 1000, length: 64 | 32, digest: :sha256)`. This is the same PBKDF2 construction, so it can be bit-exact.
- The 7.1+ metadata envelope is JSON `{"_rails":{"data":<value>,"pur":<purpose>,"exp":<ISO8601 ms Z | absent>}}`. The legacy envelope (pre-7.1, and still used by cookie jars, inferred) is `{"_rails":{"message":b64(serialized value),"exp":…,"pur":…}}`. Every reader must accept the shape the vectors show and **reject any other shape**. **needs-vector**
- `MessageVerifier` wire format is `<base64(payload)>--<hex HMAC(payload)>`. With `url_safe: true` the payload is base64url without padding. Compare the HMAC with `Plug.Crypto.secure_compare/2`.

| Artifact | Key salt | Length | HMAC/cipher | Payload and purpose | Expiry | Confidence |
|---|---|---|---|---|---|---|
| `session_token` cookie (C-20) | `"signed cookie"` | 64 | HMAC-**SHA1** (`signed_cookie_digest` unset → `"SHA1"`), hex digest | Legacy envelope: `message = b64(JSON string "<token>")`, `pur = "cookie.session_token"`, `exp` = 20 years (`.permanent`). Cookie value is URL-encoded (`%3D`). Attributes: HttpOnly, SameSite=Lax, path `/`, Secure under `force_ssl` | 20 y | Cookie call: **confirmed** (authentication.rb:93-99). Format matches `test/performance/create_dummy_cookies.rb` (SHA1 HMAC, NullSerializer, JSON-quoted token, purpose `cookie.session_token`), but that script uses KeyGenerator's *class default* digest with a dummy secret, so the PBKDF2 digest is **needs-vector** |
| `_campfire_session` (C-21) | `"authenticated encrypted cookie"` | 32 | AES-256-GCM; wire `b64(ct)--b64(iv)--b64(tag)` | Envelope with `pur = "cookie._campfire_session"`, JSON session hash (`_csrf_token`, `return_to_after_authenticating`) | `expire_after: 20.years` | Store and name: **confirmed** (session_store.rb). Crypto: **inferred / needs-vector**. **Recommendation: do not implement** (see Q2) |
| `signed_id` avatar (C-23) | `"active_record/signed_id"` (`signed_id_verifier_secret`), or `Rails.application.message_verifiers["active_record/signed_id"]` if this Rails commit routes signed ids through the verifier factory | 64 | HMAC-SHA256, `url_safe: true`, JSON serializer | `data = <user id integer>`, `pur = "user/avatar"` (`base_class.name.underscore + "/" + purpose`), no `exp` | none, so **deterministic**: one stable token per user | Call sites: **confirmed** (user/avatar.rb:11-18). Everything else **needs-vector** (the 8.1/8.2 verifier wiring is the biggest uncertainty) |
| `signed_id` transfer (C-24) | same as avatar | 64 | same | `pur = "user/transfer"`, `exp = now + 4h` | 4 h | **confirmed** call site (transferable.rb). Format **needs-vector** |
| Active Storage blob signed id (C-27) | same verifier as `signed_id` | 64 | same | `pur = "active_storage/blob/blob_id"` (Blob overrides `signed_id(purpose: :blob_id)`), no `exp` (`urls_expire_in` unset) | none | `rails_blob_path` use: **confirmed** (attachment_presentation.rb:33,84,105; _actions.html.erb:33,38). Purpose string and any fallback to the old `ActiveStorage.verifier`: **needs-vector** |
| AS variation key (representations: thumb, video poster) | `"ActiveStorage"` (`Rails.application.message_verifier("ActiveStorage")`) | 64 | HMAC (digest per the 8.2 verifier factory, SHA1 historically), JSON or `json_allow_marshal` | `pur = "variation"`, transformations hash | none | **needs-vector**. URLs are rendered per request and **not stored in bodies**, so this is low risk |
| AS disk-service URL `/rails/active_storage/disk/:encoded_key/*` | `"ActiveStorage"` | 64 | as above | `pur = "blob_key"`, `{key, disposition, filename, content_type, service_name}` | about 5 min | Transient. The port can use its own format (Q2) |
| Action Text sgid (C-10) | `"signed_global_ids"` (`SignedGlobalID.verifier = app.message_verifier(:signed_global_ids)`) | 64 | HMAC (factory digest), not URL-safe | 7.1+: `{"_rails":{"data":"gid://campfire/User/<id>","pur":"attachable"}}`, no `exp` (`attachable_sgid` passes `expires_in: nil`). Rails 7 era: `"_rails.message"` = b64(**Marshal**(gid)) | none, so deterministic | Tolerant reader: **confirmed** (lib/rails_ext/action_text_attachables.rb). Minting format: **needs-vector** |
| `variant_records.variation_digest` (C-11, related) | n/a | n/a | `SHA1.base64digest(Marshal.dump(transformations))` | **Marshal encoder only** (deterministic, write-side), needed to find existing variant rows | n/a | **inferred / needs-vector**, already noted in kb/stacks/rails.md |

**Verification algorithm (all signed artifacts)**

1. URL-decode the value (cookies only).
2. Split on the **last** `"--"`. Reject anything other than exactly one data part and one 40-hex (SHA1) or 64-hex (SHA256) digest.
3. Recompute the HMAC with the per-artifact key and `secure_compare`.
4. Base64-decode strictly. Use url-safe decoding only where the artifact is `url_safe`.
5. Decode the JSON with Jason and a size cap.
6. Require the `_rails` map. Check `pur` for an exact string match and `exp` > now (UTC). A missing `exp` is allowed **only** for the no-expiry purposes (avatar, blob, sgid).
7. Extract the value with an explicit type check: binary token, or positive integer id.

`"message"` envelopes are base64-decoded once more and then JSON-decoded; they are never Marshal-decoded. For C-20 only, after signature verification, the token is looked up with `sessions.token = ?`. The DB row is the authority (C-08).

**Minting (session cookie)**: build the legacy envelope with `exp` = now + 20 years as ISO8601 with ms and `Z`, JSON-encode, Base64-strict, append `--` and the hex HMAC-SHA1, then URL-encode. Session tokens use `has_secure_token`, which is 24 characters of base58 in Rails ≥7.1 (**inferred**, check the length of existing rows). Generate them without modulo bias (rejection sampling over `:crypto.strong_rand_bytes`).

**What only the vectors can settle**: the PBKDF2 digest, the cookie HMAC digest, legacy vs 7.1 envelope per artifact, the `exp` string format, whether signed ids go through `message_verifiers` on this Rails `main` commit, the exact blob purpose string, the digest and serializer of `message_verifier(:signed_global_ids)` and `("ActiveStorage")`, and base64 padding and URL-safety per artifact.

### Q2. Compat-namespace verifiers vs port-owned formats

Rule: **anything that persists outside the process, or that Rails must read after a rollback, is minted and verified in Rails format by a narrow per-purpose codec in `Campfire.Compat.Rails.*`**. Anything transient that only the port itself reads uses `Phoenix.Token` or Plug with **distinct salts**.

| Artifact | Verify legacy | Mint format | Why | Confidence |
|---|---|---|---|---|
| `session_token` | Yes (`Compat.Rails.SessionCookie.verify/1`) | **Rails format** | ADR-000 rollback: users stay logged in. It also becomes the port's *only* auth cookie (no parallel phx.gen.auth token), with `sessions` as the sole authority, so HTTP and the `/cable` shim cannot disagree | confirmed (ADR) |
| `_campfire_session` | **No** | **Not minted.** The port's Plug session uses a **different cookie name** (e.g. `_campfire_px`) for CSRF, flash and return_to | C-21 already treats losing it as one stale-form 422 plus a lost redirect. Because the port never overwrites the Rails cookie, the browser keeps it, and **after a rollback Rails CSRF continuity is restored for free**. A decrypt-only reader would add AES-GCM plus a session-hash parser for no durable benefit | inferred |
| avatar `signed_id` | Yes | **Rails format** (deterministic) | URLs are stored by bot clients (`avatar_url`), possibly in Lexxy mention markup inside bodies (contracts Q2), and in HTTP caches and ETags. Rails must serve port-minted ones after a rollback | needs-vector |
| transfer `signed_id` | Yes | **Rails format** | Same codec as avatar, so it costs nothing extra. A port-owned format would only break links outstanding for 4 h at rollback, which is acceptable as a fallback if vectors are delayed | needs-vector |
| blob signed id (redirect URL) | Yes | **Rails format** | Shared or copied links never expire (C-27) and Rails must read port-rendered ones after a rollback | needs-vector |
| variation key | Yes (best effort) | Rails format **if** the vector shows deterministic JSON; otherwise port-owned | Re-rendered on every page and not durable. Legacy keys that turn out to be **Marshal** → 404/re-render, never decoded | needs-vector |
| disk-service URL | No (5-min TTL) | Port-owned `Phoenix.Token` (`max_age: 300`), or stream the bytes directly from the redirect endpoint | Transient. Old disk URLs in browsers expire within minutes | inferred |
| Action Text sgid | User: **extract without verifying** (legacy behavior). Others: verify, else render as missing attachable | **Rails 7.1+ JSON format**, signed | Mentions are written into stored bodies by the client from autocomplete and `_mention` partials. Rails' tolerant reader on rollback needs the `_rails.data` or `_rails.message` JSON shape | confirmed reader / needs-vector writer |
| variation_digest | n/a | Marshal **encoder** for the transformation hash only, in compat | Required to reuse existing `active_storage_variant_records` rows | inferred |

Placement:
- One module per purpose (`SessionCookie`, `SignedId.Avatar`, `SignedId.Transfer`, `SignedId.Blob`, `GlobalId.Attachable`, `ActiveStorage.VariationKey`), all built on one private `Compat.Rails.MessageVerifier`.
- The private verifier takes **purpose as a required argument with no default**. There is **no public "verify anything" function**.
- Derive the keys once at boot into `:persistent_term`. PBKDF2 at 1000 iterations is too slow to run per request.
- T45 and T47 checks: no `MessageVerifier` or `KeyGenerator` naming outside `compat/`.
- Retirement condition: the rollback window closes **and** no durable artifacts remain (avatar, blob and sgid have no expiry, so they are effectively permanent: **KEEP**, not SHIM).

### Q3. Security risks of carrying these over, and what to do within the bar

1. **Non-constant-time bot key lookup** (`active_bots.find_by(id:, bot_token:)`, user/bot.rb:20-23). **confirmed**
   - Practical exploitability is low: the token is 12 alphanumeric characters (about 71 bits), the SQLite B-tree comparison is over the network, and timing noise dominates.
   - Fix within the bar (no wire change): parse `"<id>-<token>"` strictly. Ruby `split("-")` takes the first two parts, and AR casts `"5abc"` to 5. The port should require a positive integer id, a non-empty `[A-Za-z0-9]{12}` token, and should strip the key.
   - Load the bot by `id` from active bots, then `Plug.Crypto.secure_compare(stored, presented)`. An empty or nil token is rejected before any query (regression 3d0a10d).
   - Keep 403 for bot keys on non-bot routes (C-34), including `?bot_key=`.
   - Scrub `/<id>-<token>` path segments and `bot_key` params from Logger, Plug/Phoenix request logs, Sentry and telemetry metadata (C-57). Phoenix `filter_parameters` cannot see path segments.
   - Optional: a per-IP failure counter on bot routes (beyond the bar, record as a tightening).
2. **Marshal-format sgids (Rails 7 bodies)**. **confirmed**
   - Never call any Marshal decoder.
   - Mirror the legacy regex extraction, but tighten it to `gid://campfire/User/(\d+)` for the unsigned path, and resolve with an explicit allowlist (`"User" => User`). Never `String.to_atom` or `Module.concat` on the GID model name. Legacy `GlobalID.find` constantizes any model name before filtering to User.
   - Base64: strict first, then url-safe fallback, with the decoded size capped.
   - Ship the contract's fixtures: current sgid, Rails 7 sgid with an invalid signature, Room sgid with a bad signature.
3. **Unsigned mention fallback** (User sgids accepted without a signature). **confirmed**
   - Impact is bounded. Push and webhook recipients go through `room.users.where(id: mentioned)` (message/mentionee.rb:5), so a forged mention cannot notify or webhook a non-member.
   - The remaining exposure is display: a crafted body renders any user's name and avatar URL (enumeration of names and avatar tokens of non-room or deactivated users), and it can spoof a mention chip.
   - Within the bar: keep the tolerance (C-10), keep the room scoping in the port's mentionee query (test: a forged mention of a non-member produces no push and no webhook), and render mention HTML from the DB user, never from the attachment's inner HTML.
   - Optional tightening, which needs approval: tolerate unsigned User sgids only in bodies created before cutover, and require valid signatures on new writes. The port mints signed sgids itself, so legitimate clients are unaffected.
4. **CSRF token compatibility.**
   - Never cross-verify Rails masked or per-form tokens. Plug.CSRFProtection owns CSRF.
   - Render `<meta name="csrf-token" content={get_csrf_token()}>` (used by `file_uploader.js`, `@rails/request.js` and Turbo through the `X-CSRF-Token` header: **confirmed** in file_uploader.js:16 and vendor request.js), and `<meta name="csrf-param" content="_csrf_token">`. Hidden form fields are `_csrf_token`.
   - Map `Plug.CSRFProtection.InvalidCSRFTokenError` to **422** with a reload prompt. Rails `with: :exception` returns 422 and Plug returns 403 by default.
   - Exempt bot-key routes, `/service-worker` and `/webmanifest` (C-22), and **only** bot-key routes among POSTs.
   - **Verify**: Rails `main`/8.2 may add `Sec-Fetch-Site`-based forgery verification under `load_defaults 8.2`. Grep the pinned actionpack `request_forgery_protection.rb`. If it rejects cross-site requests by header, mirror that as an extra check; if it accepts same-origin requests without a token, the port stays stricter, which is fine because all bundled JS sends the token. **needs-vector / source check**
5. **Key-domain confusion.** Phoenix's own `Plug.Crypto` defaults (PBKDF2-SHA256, 1000 iterations) are *the same KDF* Rails uses. The port's salts must never reuse `"signed cookie"`, `"authenticated encrypted cookie"`, `"active_record/signed_id"`, `"signed_global_ids"` or `"ActiveStorage"`. Use `"campfire/px/<purpose>"` salts so a token minted for one purpose can never verify as another.
6. **SECRET_KEY_BASE length.** Rails accepts any length, but Plug's cookie session raises below 64 bytes. Do not crash existing installs: feed the raw `SECRET_KEY_BASE` to the compat codecs, and give the endpoint `secret_key_base` the raw value when it is ≥64 bytes, or a 64-byte PBKDF2 expansion of it otherwise. Never log it, and fail boot only if it is absent.
7. **Permanent bearer capabilities.** Blob URLs are unauthenticated and never expire. Avatar tokens never expire. Transfer links are **reusable** for 4 h, not single-use (`User.active.find_by_transfer_id`, then a new session, with no consumption record). All three are kept by the bar. Document them in SECURITY.md as known behavior, and keep `User.active` on transfer and `find_signed!` → 404 on avatar.
8. **Cookie attributes and socket origin.**
   - `session_token`: HttpOnly, SameSite=Lax, path `/`, and `secure` unless `DISABLE_SSL` (Rails `force_ssl` marks every cookie Secure), plus HSTS in the same mode.
   - The `/cable` shim authenticates by cookie, so set Phoenix socket `check_origin: :conn`. The host is operator-chosen, so a static list is impossible.
   - Logout (C-43) deletes the cookie with the same path and no domain, deletes the `sessions` row, deletes the push subscription **scoped to `user_id`** (sessions_controller.rb:37), then broadcasts disconnect. A realtime failure must not block the 302.
9. **return_to open redirect.** Rails stores the full `request.url`. The port should store **path + query only** and redirect only to local paths.
10. **Password verification timing (C-07).** `User.active.authenticate_by` is timing-safe. Mirror it with `Bcrypt.no_user_verify/0` when there is no user, the user is inactive, or the digest is NULL (bots). The bcrypt 72-byte truncation is kept (C-07).
11. **IP identity for bans and rate limits.** Rails `remote_ip` trusts loopback and private proxies and takes the rightmost untrusted `X-Forwarded-For` entry.
    - Mirror it exactly (a `remote_ip`-style plug with Rails' trusted-proxy list).
    - Store and compare IP strings in Rails' textual form, including IPv6 compression, case and IPv4-mapped forms. `bans.ip_address` and `sessions.ip_address` are exact-string matched.
    - A mismatch either lets clients spoof XFF to evade bans and limits, or bans the proxy. Ban validation rejecting private IPs would hide the second failure.

### Q4. Login rate limiting and banned-IP blocking without Redis

**Legacy semantics** (**confirmed** at sessions_controller.rb:3 and block_banned_requests.rb, plus **inferred** Rails `rate_limit` internals):
- Key is `rate-limit:sessions:<remote_ip>`, stored in `Rails.cache` (Redis, non-persistent).
- The counter increments on **every** `POST /session`, success included, *before* the action runs.
- The TTL is set when the key is created, so the window is fixed and starts at the first hit.
- When count > 10 within 3 min, the response is 429 rendering the login page with the flash "Too many requests or unauthorized."
- State is lost on restart, which is identical with ETS.

**Recommendation (single node, ONCE)**
- **Login limiter**:
  - Store a tiny `Campfire.RateLimit` ETS table owned by a supervised GenServer (`:set, :public, read_concurrency, write_concurrency, decentralized_counters`).
  - Increment atomically with `:ets.update_counter(tab, key, {2, 1}, {key, 0, window_start})`. If `now - window_start >= window`, reset with `:ets.insert` (accept the benign reset race) or use a CAS through `:ets.select_replace`.
  - A periodic sweep with `:ets.select_delete` removes expired keys, which bounds memory under IP-spray.
  - Run it as a plug only on `POST /session`, keyed by the Rails-equivalent remote IP.
  - Hammer 7 (`Hammer.ETS`, `:fix_window`) is acceptable if you accept clock-aligned buckets: worst case is about 20 attempts across a bucket edge, which is a minor deviation, so record it.
  - No Redis, no DB writes (SQLite single-writer), no `:persistent_term` (writes trigger global GC).
- **Banned IPs**:
  - The DB `bans` table stays the authority. Admins write it, and Rails must read it after a rollback.
  - Check on **non-GET/HEAD only**, returning **429**. GETs still work (C-42).
  - Simplest correct option: an indexed `SELECT 1 FROM bans WHERE ip_address = ? LIMIT 1` (the index `index_bans_on_ip_address` exists, **confirmed** in schema.rb:68). It runs only on mutating requests.
  - If measured hot: a read-through ETS set loaded at boot and rebuilt by the `ban`/`unban` context functions *after commit*, plus a PubSub broadcast. Never cache negative lookups without invalidation.
  - Ban and deactivate must, in one transaction, create bans from the session IPs, delete the sessions, set the status, and enqueue content removal (Oban, same transaction). After commit they broadcast the socket disconnect (C-28, M-07).

---

## Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Crypto parameters guessed wrong → every user logged out at cutover, or **Rails rejects port-minted cookies after a rollback** | High | Vectors in both directions (Rails→port and port→Rails) are a gate before the identity slice |
| R2 | A general "verify any Rails message" helper is reused for a new purpose → a token for one capability is accepted for another (avatar token as transfer = **login**) | Critical | Purpose required per module, exact-match `pur`, wrong-purpose vectors (avatar token against the transfer endpoint → 400) |
| R3 | Marshal decoding introduced "for compatibility" | Critical (RCE) | T44 check is a blocker; regex/allowlist extraction only; the Marshal *encoder* is limited to variation_digest |
| R4 | Phoenix salts collide with Rails salts (same KDF) | High | Distinct `campfire/px/*` salts and a unit test asserting the salt set is disjoint |
| R5 | `remote_ip` resolution differs → XFF spoofing bypasses bans and limits, or proxy IP gets banned | High | Port Rails' trusted-proxy rules; vector requests through Thruster |
| R6 | Bot key logged (paths, Sentry breadcrumbs, telemetry) | High | Logger filter plus Sentry `before_send` scrub; C-57 log grep test |
| R7 | Forged mention notifies non-members | Medium (prevented today) | Keep the room-scoped mentionee query, with a regression test |
| R8 | CSRF 403 vs 422 status, or exemption list widened beyond bot routes | Medium | Explicit exempt list and a test that a cookie-authenticated POST without a token is rejected |
| R9 | `SECRET_KEY_BASE` < 64 bytes crashes the Plug session at boot on some installs | Medium | Derived endpoint secret (Q3.6) |
| R10 | Transfer links reusable within 4 h; blob and avatar capabilities permanent | Low (kept by the bar) | Document. Single-use transfer is a later ADR |
| R11 | Rails `main` pin (unreleased) has undocumented changes to message verifiers or CSRF (`Sec-Fetch-Site`) | Medium | Read the pinned actionpack, activesupport, activerecord, activestorage and globalid sources in the image, and generate vectors from that exact image |

## Test vectors needed

Generate everything in the **pinned Rails image** (`rails runner`) with a fixed test `SECRET_KEY_BASE` (both 128-hex and a short <64-byte value) and a frozen clock. Store them as JSON fixtures in `test/fixtures/compat/rails/`.

1. **Key derivation**: `Rails.application.key_generator.generate_key(salt, 64|32)` hex for each salt: `"signed cookie"`, `"authenticated encrypted cookie"`, `"active_record/signed_id"`, `"signed_global_ids"`, `"ActiveStorage"`. Also record `ActiveSupport::KeyGenerator.hash_digest_class`, `Rails.application.config.action_dispatch.signed_cookie_digest`, `ActiveSupport::Messages::Metadata.use_message_serializer_for_metadata`, `config.active_support.message_serializer`, and `ActiveRecord::Base.signed_id_verifier.inspect` (digest, url_safe, serializer).
2. **session_token**: Set-Cookie header from a real login (raw, URL-encoded value). Variants: valid, tampered byte, `exp` in the past, purpose `cookie.other`, signed with another secret, and a legacy-format sample if any still exists in production copies. **Reverse direction**: a port-minted cookie fed into `cookies.signed[:session_token]` in Rails resolves to the same `Session`.
3. **_campfire_session** (only if Q2 is overridden): an encrypted cookie containing `_csrf_token` and `return_to_after_authenticating`.
4. **Avatar**: `User.find(1).avatar_token` for ids 1, 2 and 9999999 (byte-equality with the port's mint); tampered → 404; a transfer token on the avatar route → 404.
5. **Transfer**: `transfer_id` at T0, verified at T0+4h-1s (ok) and T0+4h+1s (nil); an avatar token on the transfer route → 400.
6. **Blob**: `blob.signed_id`, plus a full `rails_blob_path(..., disposition: "attachment")` and a representation URL (`representation(:thumb)`) with its variation key. Note whether the variation key payload is JSON or Marshal.
7. **sgid**: `User.find(1).attachable_sgid` (byte-equality); a Rails-7-era Marshal sgid from a production-shaped DB with a corrupted signature; a `Room` sgid with a bad signature; a body using url-safe base64.
8. **variation_digest**: `ActiveStorage::Variation.new(transformations).digest` for the `square`, `thumb`, `large`, `small` and video-preview transformations.
9. **CSRF**: confirm in the pinned actionpack whether `load_defaults 8.2` enables `Sec-Fetch-Site` verification, and the HTTP status for a missing token.
10. **remote_ip**: a table of (REMOTE_ADDR, X-Forwarded-For) → `request.remote_ip` including IPv6 and IPv4-mapped cases, plus `Ban` validation results for the same strings.
11. **Rate limit**: 11 POSTs within 3 min → the 11th is 429. Wait for the window → 200/401. Confirm the counter includes successful logins.

## Recommendations (prioritized)

1. **Gate the identity slice on vectors 1, 2, 4, 5, 6 and 7**, in both directions (Rails→port verify, port→Rails verify).
2. **Build `Campfire.Compat.Rails`**: one private HMAC/envelope codec, plus thin per-purpose public modules (session cookie, avatar, transfer, blob, attachable sgid, variation key). Keys go in `:persistent_term` at boot. Use `secure_compare`, exact purpose and expiry checks, strict base64, size caps, and **no Marshal decode anywhere**.
3. **Treat `session_token` as the port's only auth cookie**, minted in Rails format, with the `sessions` row as the authority. The `/cable` shim and HTTP share one `Auth.fetch_session(conn_cookies)`.
4. **Do not read or write `_campfire_session`.** Use a distinctly named Plug session for CSRF, flash and return_to. Plug.CSRFProtection with `csrf-token` and `csrf-param` meta tags, 422 on failure, and an explicit exemption list (bot routes, `/service-worker`, `/webmanifest`).
5. **Mint every durable capability (avatar, blob, sgid, transfer) in Rails format** while the rollback window is open. Use `Phoenix.Token` with `campfire/px/*` salts only for new, transient capabilities (disk URLs).
6. **Bot auth**: strict parse, then fetch by id, then `secure_compare`. Scrub keys from all log and error sinks.
7. **Mentions**: allowlisted User-only tolerant extraction, a room-scoped mentionee query, and mention chips rendered from the DB user.
8. **Abuse controls**: an ETS fixed-window limiter on `POST /session` (10 per 3 min per IP, 429 with the login page), and an indexed DB ban check on non-GET/HEAD (429). Use a Rails-equivalent `remote_ip` resolution and Rails-equivalent IP string normalization.
9. **Boot safety**: derive the endpoint secret when `SECRET_KEY_BASE` is under 64 bytes, and refuse to boot if it is missing.
10. **Document the kept, knowingly weak behaviors in SECURITY.md**: permanent blob and avatar capabilities, reusable 4 h transfer links, tolerated unsigned User mentions, and the bot-key-in-path design.

## Tools to recommend

The user should run these manually (this agent has no Bash access): `mix sobelow --exit medium`, `mix deps.audit`, `mix hex.audit`. Add a CI grep for T44 (`binary_to_term|Marshal`) and T47 (`MessageVerifier|KeyGenerator` outside `compat/`).
