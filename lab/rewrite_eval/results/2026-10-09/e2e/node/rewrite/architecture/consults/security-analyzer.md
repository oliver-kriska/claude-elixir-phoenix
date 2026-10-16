# Consult: security-analyzer (identity and auth compatibility)

**Scope**: consult only. No plan and no code. Code fragments are illustrative.
**Inputs**: ADR-000 (ASSUMED), contracts C-02, C-12..C-17, C-19, C-21, C-30, C-37, mechanisms M-07, M-08, M-09, M-20, kb/stacks/node.md.
**Pinned legacy versions** (package-lock.json): jsonwebtoken **9.0.2** (jws 3.2.2, jwa 1.4.1), express-jwt **8.4.1**, bcryptjs **2.4.3**, express 4.18.x.
**Anchors**: `S:` = SOURCE `src/app/routes/`. `src/main.ts` is relative to the SOURCE root.

Items marked **(verify)** come from library knowledge, not from reading code. Each one needs a golden test before cutover.

---

## Q1. Token compatibility (C-12, C-16, M-07/M-08)

### What legacy emits and accepts
- Sign (S:auth/token.utils.ts:3-6): `jwt.sign({user:{id}}, JWT_SECRET || 'superSecret', {expiresIn:'60d'})`.
  - Header is `{"alg":"HS256","typ":"JWT"}` (jsonwebtoken defaults to HS256 when it gets a string secret).
  - Payload is `{"user":{"id":<int>},"iat":<int>,"exp":<int>}`, where `iat = floor(now_ms/1000)` and `exp = iat + 5_184_000`.
  - There is no `nbf`, `iss`, `aud`, `sub`, `jti` or `kid`.
- Verify (S:auth/auth.ts:14-26): express-jwt 8.4.1 calls `jwt.decode(complete)` and then `jwt.verify(token, secret, {algorithms:['HS256']})`.
  - `clockTolerance` is 0. A token is expired when `now >= exp`.
  - A non-numeric `exp` or `nbf` is rejected. `iat` is not checked (a future `iat` passes).
  - Extra claims are ignored. A token with no `exp` is accepted.
  - The decoded payload goes in `req.auth`, and handlers read `req.auth?.user?.id`.

### Recommendation: Joken 2.6+/2.7 with an explicit minimal token config (not `default_claims`)
Joken is a thin layer over JOSE. `Joken.Signer.verify/2` calls `JOSE.JWT.verify_strict(jwk, [signer.alg], token)` **(verify)**. That is exactly the alg allow-list jsonwebtoken applies, so `alg:none`, HS384/HS512 and RS* tokens are rejected. JOSE also has unsecured signing (`none`) off by default. Using JOSE directly is equally exact but means hand-writing claim validation. Joken's only advantage is ergonomics. Either one interoperates byte-for-byte at the HMAC level.

How to get Joken to match legacy:
- **Do not use `use Joken.Config` with its default claims as-is.** `default_claims/1` adds `iss:"Joken"`, `aud:"Joken"`, `jti` and `nbf`. Node would accept them (it ignores extra claims, and the `nbf` would be valid), but the payload would no longer match the C-12 shape. Either use `default_claims(skip: [:aud, :iss, :jti, :nbf], default_exp: 5_184_000)`, or better, build the config explicitly:
  ```elixir
  # illustrative
  def token_config do
    %{}
    |> add_claim("iat", fn -> Joken.current_time() end)                  # integer seconds
    |> add_claim("exp", fn -> Joken.current_time() + 5_184_000 end, &(&1 > Joken.current_time()))
  end
  # mint:  generate_and_sign(%{"user" => %{"id" => user.id}}, signer)
  # signer: Joken.Signer.create("HS256", jwt_secret)   # raw UTF-8 bytes, same as Node
  ```
- **Exp boundary.** Node rejects when `now >= exp`. Joken's `&(&1 > now)` accepts only when `exp > now`. The two are the same rule.
- **Do not add an `iat` validator** such as "iat must be in the past". Node does not check `iat`, and a Node box with a clock a few seconds fast would then mint tokens the port rejects.
- **Leeway is 0 on both sides.** Under Replacement cutover there is no concurrent minting, so skew only matters if the hosts' clocks are wrong. Keep NTP on.
- **Integer types.** `iat`/`exp` must be integers (`Joken.current_time/0` returns them; do not use `DateTime`, floats or `System.os_time(:millisecond)`). `user.id` must be a JSON integer, not a string. Legacy feeds it straight into Prisma (`where:{id}`), and Prisma 500s on a string.
- **Nested map claim.** After verification, read `claims["user"]["id"]` and guard with `is_integer/1`. If it is not an integer, return 401 rather than crash. The only way to produce such a token is to hold the secret, and legacy 500s here, so it does not matter for parity.
- **Missing `exp`.** Legacy accepts a token with no `exp`. Joken skips validation for claims that are absent from the token **(verify)**. No legitimate token lacks `exp`, so I recommend explicitly rejecting tokens without `exp` (a deny-only deviation that affects only forged or hand-made tokens). Record it as a named compat behaviour.
- **Secret handling.** Pass the secret string as-is (UTF-8 bytes). Do not base64-decode it and do not use `JOSE.JWK.from_oct` with a decoded value. Load it in `runtime.exs` (see Q4/C-37), never through `config :joken, default_signer:` in compile-time config.
- **Key order and bytes.** Jason encodes small maps with sorted keys (`exp`,`iat`,`user`), so port tokens differ byte-wise from Node tokens for the same instant. That does not matter for verification. Golden tests should decode and compare claims, not compare token strings.
- **Constant-time comparison.** JOSE compares HMACs in constant time. Do not add a hand-rolled signature check.
- **Sliding renewal (C-16).** Every `GET/PUT /user`, login and register mints a new token, so two calls more than 1 s apart give different `iat`/`exp`. This is consistent with the Joken config above.

**Two-way test matrix (C-12 witness):**
- Node-minted (jsonwebtoken 9.0.2, test secret) → port `GET /api/user` gives 200.
- Port-minted → pinned Node `GET /api/user` gives 200.
- Each of the following gives 401 on both: tampered signature, `alg:none`, HS512 with the same secret, `exp = now`, `exp = now - 1`, a token signed with `superSecret` when the real secret differs, and a token with no `exp` (Node: 200, port: 401 by the deviation above; record it).

---

## Q2. Header parsing and optional/required semantics (C-13, C-14, M-07)

Legacy (S:auth/auth.ts:4-12; src/main.ts:33-38):
- The token is `authorization.split(' ')[1]`, used only when `split(' ')[0]` is exactly `Token` or `Bearer` (case-sensitive).
  - `token x` / `bearer x` → no token.
  - `Token  x` (two spaces) → `""` → no token.
  - `Token` → `undefined` → no token.
  - `Bearer a b` → token `a`.
- express-jwt: when there is no token, `credentialsRequired:true` raises an error and `false` calls `next()` (anonymous). When a token is present, it is **always verified**, and any failure raises `UnauthorizedError`. In both cases the error handler returns `401 {"status":"error","message":"missing authorization credentials"}`, even for an expired token.
- express-jwt also skips CORS preflights (`OPTIONS` with `access-control-request-headers` containing `authorization`). `cors()` answers preflights first anyway (C-31).
- Node discards duplicate `Authorization` headers and keeps the first.

Plug design: one module with `mode: :optional | :required`, used in two router pipelines.
```elixir
# illustrative
defp extract(conn) do
  case get_req_header(conn, "authorization") do
    [h | _] ->                                   # first header only (Node discards duplicates)
      case String.split(h, " ") do               # JS split(' '): no trim, no collapse
        [scheme, tok | _] when scheme in ["Token", "Bearer"] and tok != "" -> {:ok, tok}
        _ -> :none
      end
    [] -> :none
  end
end
# :none  + :optional → assign current_user_id: nil, continue
# :none  + :required → halt 401 (exact body)
# {:ok,t} + any mode → verify; error → halt 401 (exact body); ok → assign claims
```
- **This does not weaken security.** Rejecting a bad token on optional routes is the stricter behaviour. The risk is the opposite mistake: a "lenient optional" plug that silently drops to anonymous on a bad token. Keep fail-closed.
- **Exact 401 body.** Encode `{"status":"error","message":"missing authorization credentials"}` in that key order: use a prebuilt iodata literal or `Jason.OrderedObject`, because a plain map comes out as `message` first. The status code is what matters most; key order only matters for byte-golden tests.
- **Pipeline order must match Express.** CORS plug and `Plug.Parsers` (100 kb → 413) run in the endpoint before the router auth plug, as they do in Express (src/main.ts:13-15), so a 401 still carries `Access-Control-Allow-Origin: *`.
- **Do not look up the user in the plug** if you want strict C-15 parity, because legacy never checks the user exists. See Q4 for the option to 401 deleted users.
- Add `"authorization"` and `"token"` to log and parameter filtering (`:filter_parameters`, plus any request-header logging). Phoenix request logging is new (C-40 relax), so this keeps tokens out of logs that did not exist before.
- `/api/articles/feed` must resolve before `:slug` and use `:required` (C-36).

---

## Q3. bcryptjs `$2a$10$` and bcrypt_elixir (C-02, C-30, M-09)

- **Verifying legacy hashes.** `Bcrypt.verify_pass/2` (bcrypt_elixir 3.x) verifies `$2a$`, `$2b$` and `$2y$` hashes, reading the cost from the hash (so `$2a$10$` works) **(verify with a bcryptjs 2.4.3 fixture)**. Comparison is constant-time.
- **Prefix of new hashes.** bcrypt_elixir emits `$2b$` by default, and its default cost is 12 via `config :bcrypt_elixir, log_rounds`.
  - Recommendation: hash with `Bcrypt.hash_pwd_salt(pw, log_rounds: 10, legacy: true)`. That gives `$2a$10$...`, the same format family and cost as legacy (ADR Identity: "same cost"), and removes any rollback doubt.
  - If `legacy: true` is not used: bcryptjs 2.4.x accepts minor versions `a`, `b` and `y` in `compare` and keeps the minor version when it recomputes the hash, so Node rollback verifies `$2b$` **(verify: C-02 witness "hash created by port verifies in legacy bcrypt.compare")**.
  - Either way, add the bidirectional fixture test.
- **72-byte limit and UTF-8.** Both libraries hash UTF-8 bytes and truncate at 72 bytes (bcryptjs appends the NUL for minor ≥ `a`, as OpenBSD does). Add golden fixtures for a password over 72 bytes and for a non-ASCII password.
- **Pbkdf2/Argon2 are not fallbacks here.** Legacy only has bcrypt. Bringing them in only makes sense for a later rehash-on-login migration, which would break Node rollback during the observation window. Do not rehash or upgrade hashes until rollback is retired.
- **Trim semantics.** Register and login trim (S:auth/auth.service.ts:39-41, 85-86). `PUT /user` does not (S:auth/auth.service.ts:152-157, C-30).
  - JS `String.prototype.trim` and Elixir `String.trim/1` **remove different character sets**. JS removes `U+FEFF` (BOM) and Elixir does not. Elixir removes `U+0085` (NEL) and JS does not.
  - Write a `JsCompat.trim/1` with JS's exact class: `[\t\n\v\f\r \x{00A0}\x{1680}\x{2000}-\x{200A}\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}\x{FEFF}]`, anchored at both ends. Use it for email, username and password on register and login.
  - A password that differs only by NEL or BOM padding would otherwise verify differently across runtimes.
- **Other quirks to keep or decide on.**
  - A non-string `password` (e.g. a number) makes `.trim` throw, giving 500 on legacy (C-19 family).
  - Update uses a truthy check (`" "` is truthy and gets hashed untrimmed).
  - The C-30 asymmetry: a password set via PUT with surrounding spaces can never log in.
  - Fixing the asymmetry (trimming on update) cannot break any hash that currently works. It is a safe, recommended `change`, but it needs approval under A5.

---

## Q4. Risk statement for the ⚠ items kept under ASSUMED

| Item | Severity | Why | Minimum safe option that preserves compatibility (present to the user) |
|---|---|---|---|
| **C-21** favorite/unfavorite leak (S:article/article.service.ts:597-603, 643-649; M-20) | **High** (CWE-200 / OWASP A01+A02). It is effectively unauthenticated, because registration is open | Any self-registered account can favorite any article and collect the `email` and bcrypt `password` hash of every user who favorited it. Cost-10 hashes are crackable offline for weak passwords, and the emails enable phishing and credential stuffing. Porting it means re-implementing a credential leak on purpose | **Minimum:** keep the raw shape (`id`, `authorId`, `favoritedBy[]`) but strip `password`, `email` and `demo` from each `favoritedBy` entry. That removes the credentials with the smallest wire change. **Recommended:** return the plain C-20 `ArticleJSON`. Both need an approved `change`. Note that a Node rollback brings the leak back, so patching legacy as well is worth considering |
| **C-37** `superSecret` fallback (S:auth/auth.ts:16,21; S:auth/token.utils.ts:4) | **Critical if prod runs without `JWT_SECRET`** (anyone can forge `{user:{id:N}}` for any N, giving full account takeover). **Low if the variable is set** (latent misconfiguration trap) | The fallback is public in the repo | **Minimum:** in `:prod`, use `System.fetch_env!("JWT_SECRET")` in `runtime.exs` and also refuse to boot if the value is `"superSecret"` or shorter than 32 bytes. Keep the fallback in dev and test only. This preserves compatibility if prod sets the variable. First confirm offline whether a real prod token verifies under `superSecret`, without logging the token. **If prod does use `superSecret`:** rotate. Set a new `JWT_SECRET`, have the port verify against `[new, "superSecret"]` for 60 days and mint only with the new key. The cost is that a Node rollback would log out users holding `superSecret` tokens. Keeping it indefinitely is not defensible |
| **C-15** no revocation (and sliding renewal C-16) | **Medium** | A stolen token works for 60 days, and because every `GET /user` renews it, it effectively **never expires** while it is used. Password or email changes do not cut off an attacker. A token for a deleted user currently 500s | **Minimum (no DDL, two-way compatible):** keep stateless verification, plus (a) the auth plug or the context returns 401 instead of 500 for a missing user. Only a 500 path changes, so it needs a C-19 approval. Optionally (b) add a claim the port mints, such as `pv` = first 8 bytes of HMAC(secret, password_hash). jsonwebtoken ignores extra claims, so Node still accepts port tokens. The port enforces `pv` when present and accepts claim-less Node tokens until 60 days after cutover. The cost is one user load per authenticated request. Real revocation (a `password_changed_at` column or a denylist) needs DDL, so it waits until the schema freeze ends |
| **500 bodies echo internal errors** (src/main.ts:43-44, `res.status(500).json(err.message)`; C-19) | **Low–Medium** (CWE-209) | Prisma messages expose model and field names, the invocation, and sometimes argument values or constraint fields. Ecto/Postgrex messages would leak table, constraint, and sometimes value details in the same way | This **cannot be kept byte-for-byte anyway**, because Ecto messages differ from Prisma's. **Minimum:** keep status 500, `application/json` and a JSON-string body, with a fixed generic string (e.g. `"Internal Server Error"`). Log the real exception server-side with a request id. Set `debug_errors: false` in prod. Record it as a named relax under C-19. Clients branch on status (C-19: "low") |

Related, not ⚠ but worth stating:
- CORS `*` (C-31) is acceptable here because tokens are bearer headers, not cookies, and no credentials mode is used.
- Keep `superSecret` and real secrets out of `config/*.exs` that is compiled into the release.

---

## Q5. Timing and user enumeration at login (C-18)

- **Legacy behaviour** (S:auth/auth.service.ts:84-128).
  - Blank checks (422) run before the DB lookup.
  - Unknown email → **no bcrypt work** → fast 403.
  - Known email with a wrong password → bcryptjs cost-10 compare (pure JS, tens of ms) → slow 403.
  - Status and body are identical, so the only oracle is timing, which enumerates registered emails.
- **Parity-preserving fix (no wire change, no approval needed).** When the user is missing, call `Bcrypt.no_user_verify(log_rounds: 10)` so both paths cost one bcrypt-10. Keep the exact `403 {"errors":{"email or password":["is invalid"]}}` and the 422-before-lookup order. Match the email exactly (case-sensitive, C-05) after `JsCompat.trim/1`.
- **Limited benefit, stated honestly.** Register already enumerates explicitly (`422 email: has already been taken`, S:auth/auth.service.ts:28-35), and so does `PUT /user` (500 on a duplicate). The timing fix closes only the cheapest enumeration channel. Closing the others changes the wire and needs approval.
- **403 vs 401/422.** Keep 403 under A5. Changing the status gains no security, because the body is already generic.
- **Rate limiting.** Legacy has none. Adding a 429 on `/users/login` and `/users` is a wire change that needs approval. A proxy-level limit (or Hammer keyed on IP plus email) is the recommended option to present. bcrypt cost is also a CPU-DoS lever on login, so a limit protects availability too.
- Bcrypt runs as a NIF on dirty schedulers, so login latency will differ from Node. The perf baseline (A6) should include login at cost 10.

---

## Recommended tooling (run manually)
`mix sobelow --exit medium`, `mix deps.audit`, `mix hex.audit`. Add a CI golden-fixture suite: jsonwebtoken 9.0.2 and bcryptjs 2.4.3 run offline to produce fixtures, which are checked in as data (the legacy app is never executed in CI).
