# Security consult: auth, tokens, secrets, authz (Conduit Phoenix rewrite)

Scope: answers the 5 consult questions under ADR-000 (ASSUMED). Each answer is a recommendation, its reason, its risk, and whether it is a **KEEP** or a **CHANGE** relative to legacy.
Evidence: contracts.md C-02, C-10..C-16, C-26, C-31..C-34, C-41; runtime.md R-33/R-34; SOURCE authentication/{backends,serializers,models}.py, articles/views.py:87-157, core/exceptions.py.

---

## Q1. Password verification (C-02), and the rehash policy

**Recommendation: use `pbkdf2_elixir` (comeonin family) to verify. Keep writing Django-format `pbkdf2_sha256` hashes, but with a higher iteration count. On a successful login, rehash any hash whose iteration count is below the target. Put a small `Conduit.Accounts.Password` dispatcher in front of the library.**

- **Verify.** `Pbkdf2.verify_pass(password, stored)` detects the `pbkdf2_` prefix. It treats the Django salt as the raw string (Django does too, it does not base64-decode it), uses `:crypto.pbkdf2_hmac` with sha256 and the iteration count taken from the hash, and compares in constant time. Do not hand-roll this. A raw `:crypto.pbkdf2_hmac` verifier is ~15 lines but adds risk: the salt encoding, the compare, and the output length must all match Django exactly.
  - **Gate before calling the library.** Run the stored value through a strict pattern match: `~r/\Apbkdf2_sha256\$(\d{1,7})\$([^$]+)\$([A-Za-z0-9+\/]+=*)\z/`. Anything else returns `false` after a dummy verify:
    - unusable `!…` hashes (Django `set_unusable_password`);
    - empty or NULL values;
    - other Django hashers.
  - Reason: the library splits on `$` and pattern-matches. On `!xyz` it can raise a MatchError, which becomes a 500 and a login oracle.
  - **Iteration ceiling.** Cap the parsed iteration count, e.g. at 2,000,000. A tampered row must not become a CPU DoS.
- **Mandatory witness test.** Make a fixture hash with Django 1.10 `make_password('correct horse')`, produced offline, never by executing SOURCE:
  - `'correct horse'` → true;
  - `'wrong'` → false;
  - `'!xyz'` → false, no raise.
- **New hashes.** Use `Pbkdf2.hash_pwd_salt(pw, format: :django, digest: :sha256, rounds: target)` to get `pbkdf2_sha256$<target>$<salt>$<b64>`.
  - Why Django format rather than Argon2/Bcrypt:
    - the column contract stays one format;
    - Django 1.10 can still verify every hash the port writes (its default hasher accepts any iteration count), so a data hand-back stays possible;
    - there is one library and no multi-format dispatcher.
  - Legacy has no `PASSWORD_HASHERS` override, so Argon2 hashes would lock users out of any reverse path.
  - Argon2 is stronger against GPUs. If the ADR prefers it, use a prefix-dispatching verifier (`$argon2id$` → Argon2, `pbkdf2_sha256$` → Pbkdf2, else false) and accept that the change is one-way.
- **Target iterations.** Make it app config. Suggested: 600_000 (OWASP 2023, PBKDF2-HMAC-SHA256). Benchmark it in slice 0.
  - **Conflict with ADR-000 perf goal:** login p95 will regress roughly 20x against 30k iterations. Record it as an explicit carve-out (security over perf) or pick a lower target. This is a **CHANGE**.
- **Rehash on login.** After a successful verify, if the stored iteration count is below target:
  - update **only** the `password` column (`Repo.update_all` on that id, or a changeset that casts only `password`);
  - if the update fails, log it but do not fail the login.
- **Timing-safe "no such user" path.** Use one code path for all three cases (unknown email, inactive user, wrong password):
  ```elixir
  user = Repo.get_by(User, email: email)        # case-sensitive exact, KEEP (C-04)
  cond do
    user && Password.verify(user, pw) && user.is_active -> {:ok, user}
    user -> {:error, :invalid_credentials}
    true -> Pbkdf2.no_user_verify(rounds: target); {:error, :invalid_credentials}
  end
  ```
  - All three return 400 `{"errors":{"error":["A user with this email and password was not found."]}}` (C-13, KEEP). Inactive users get the bad-credentials message because Django's `ModelBackend` filters them out.
  - Residual risk is low and should be recorded: the `no_user_verify` cost (target rounds) differs from legacy rows at 30k. Registration already discloses email existence ("already exists", C-26), so timing parity is hygiene, not a boundary.
- Mark `field :password, :string, redact: true` on the schema.

## Q2. JWT (C-10, C-11, C-15)

**Recommendation: use Joken (JOSE underneath) with a hand-built token config and no default claims. Wrap it in `Conduit.Auth.Token` with strict claim matching.** A minimal hand-rolled HS256 module is acceptable but not preferred.

- **Why Joken.** `Joken.Signer.verify` calls `JOSE.JWT.verify_strict(jwk, [signer_alg], token)`, which pins the algorithm. It rejects:
  - HS384 and HS512 tokens, closing C-15;
  - `alg:none`.

  The JWS header JOSE produces is `{"alg":"HS256","typ":"JWT"}`.
- **Avoid `use Joken.Config` defaults.** `default_claims/1` adds `iss`, `aud`, `iat`, `nbf` and `jti`, which breaks C-11. Either:
  - call `default_claims(skip: [:aud, :iss, :jti, :nbf, :iat], default_exp: 60 * 86_400)`; or
  - generate claims yourself: `%{"id" => user.id, "exp" => System.system_time(:second) + 60 * 86_400}` → `Joken.encode_and_sign(claims, signer)`.
- **Verify path, all in the wrapper:**
  1. `Joken.verify(token, signer)` (signature and alg pinned).
  2. Pattern match `%{"id" => id, "exp" => exp} when is_integer(id) and id > 0 and is_integer(exp)`.
     - Do not rely on Joken to fail on missing claims. Claim validators only run for claims present in the token.
     - A missing `exp` is **rejected**. This is a CHANGE (PyJWT 1.4 accepted tokens with no expiry) with no legitimate consumer, because legacy always minted `exp`.
  3. `exp > now` with leeway 0.
  4. `Repo.get(User, id)`. Never `get!`, and never pass a string id.
  5. `is_active` check.

  Messages to KEEP (C-12, C-15 single-message behaviour):
  - any decode, signature or exp failure → "Invalid authentication. Could not decode token.";
  - user missing → "No user matching this token was found.";
  - user inactive → "This user has been deactivated.".
- **Header parsing (C-10, KEEP):**
  ```elixir
  case get_req_header(conn, "authorization") do
    [value | _] ->
      case String.split(value) do            # whitespace split, trims
        [prefix, token] -> if String.downcase(prefix) == "token", do: {:token, token}, else: :anonymous
        _ -> :anonymous                       # 0, 1, or >2 parts
      end
    [] -> :anonymous
  end
  ```
  - The plug assigns a tri-state, `:anonymous | {:ok, user} | {:error, msg}`. Route pipelines decide what `{:error, _}` means on public endpoints. That keeps C-16 (403 on a bad token even on public GETs, UNDECIDED) a one-line policy switch instead of a structural choice.
  - Cowboy's default 4 KB header-value limit already bounds the token length.
- **Hand-rolled alternative** (no deps, ~40 lines):
  - `:crypto.mac(:hmac, :sha256, key, h <> "." <> p)`;
  - `Base.url_decode64(padding: false)`;
  - `Plug.Crypto.secure_compare/2`;
  - a byte-exact header check.

  Only consider it if the dependency is unwanted. The risks are in the details: padding tolerance, header check, compare.

## Q3. Secret management (C-14, C-34, C-44)

**Recommendation: read every secret in `config/runtime.exs` (prod block) with `System.fetch_env!`. Validate at boot and fail closed. Never use `Application.compile_env` for secrets, because it bakes them into the release.**

| Env var | Fail-closed rule at boot |
|---|---|
| `JWT_SECRET` | missing, or under 32 bytes → raise. Optional hardening: raise if `:crypto.hash(:sha256, secret)` equals a stored fingerprint of the leaked legacy key. Store only the hash, never the value. |
| `SECRET_KEY_BASE` | missing, or under 64 bytes → raise (Phoenix needs it even without sessions). Keep it **separate** from `JWT_SECRET` so each rotates independently. |
| `DATABASE_PATH` | missing → raise. Do not default to a relative `db.sqlite3`. |
| `PHX_HOST`, `PORT` | `PHX_HOST` missing → raise. |
| `CORS_ORIGINS` | ADR keeps the `:4000` origins as defaults, so a default is allowed. Parse it strictly (comma list of full origins). Reject `*`, because legacy never allowed a wildcard. |
| `JWT_SECRET_PREVIOUS` | optional, verify-only |

- **Rotation.** Sign with `JWT_SECRET`. Verify with `JWT_SECRET`, then `JWT_SECRET_PREVIOUS` if it is set.
  - No `kid` header is needed, because C-11 fixes the header shape. Try both keys; HS256 makes that cheap.
  - Remove the previous key after 60 days (the maximum token lifetime).
  - Emergency rotation: set a new key with no previous key, and every client re-logs once.
  - `SECRET_KEY_BASE` rotation has no client impact (no sessions or cookies).
- **Dev and test.** Commit only obviously fake values in `config/dev.exs` and `config/test.exs`.
- **No debug pages (C-34, CHANGE):**
  - `debug_errors: false` in prod;
  - `Plug.Debugger` in dev only;
  - an `ErrorJSON` that never echoes headers or stack traces.
- **Logging.**
  - `config :phoenix, :filter_parameters, ["password", "token"]`;
  - never log the `authorization` request header;
  - redact `password` in Ecto.

## Q4. Authorization for C-32 and C-33 (CHANGE toward safe, ASSUMED)

**Recommendation: checks live in the context and take a `%Conduit.Accounts.Scope{user, profile}` (Phoenix 1.8 scope style). Controllers never compare ids. Contexts return tagged errors, and a FallbackController maps them onto the legacy envelopes.**

- **C-32.** `Articles.update_article(%Scope{} = s, slug, attrs)`:
  1. Fetch by slug. Nil → `{:error, :not_found}` → 404 `{"errors":{"article":"An article with this slug does not exist."}}` (KEEP).
  2. `article.author_id != s.profile.id` → `{:error, :forbidden}`.
     - Ownership is on the **profile** id: `Article.author` and `Comment.author` are FKs to `profiles_profile`.
  3. The changeset casts **only** `title, description, body, slug` plus `tagList` handling, and never `author_id`.
- **C-33.** `Articles.delete_comment(%Scope{} = s, slug, comment_id)`:
  - Use one scoped query: `from c in Comment, join: a in assoc(c, :article), where: a.slug == ^slug and c.id == ^id`.
  - Nil (unknown comment, unknown slug, or a comment from another article) → 404 `{"errors":{"comment":"A comment with this ID does not exist."}}`. Same message as legacy, and no new error text.
  - Author mismatch → `{:error, :forbidden}`.
  - **Order is not-found first, then forbidden**, which matches the C-33 witness.
  - Parse `comment_id` with `Integer.parse` and require the full string to be consumed. Garbage → 404, never a raise.
- **403 body.** The legacy envelope comes from DRF's `PermissionDenied`, so use DRF's own default text: "You do not have permission to perform this action."
  - Article update (ArticleJSONRenderer label) → `{"article":{"detail":"You do not have permission to perform this action."}}`.
  - Comment delete (default renderer, no label) → bare `{"detail":"You do not have permission to perform this action."}`.
  - Implementation: each controller sets its label (`plug :put_error_label, "article"` or `nil`). `FallbackController` renders `{:error, :forbidden | :unauthenticated | :not_found}` through one `Conduit.Compat.Errors` module, the same module that serves C-16 and C-26 golden files.
- An unauthenticated caller on either route keeps the legacy 403 "Authentication credentials were not provided." (C-16 status quo). That is the pipeline's job, before the context is called.
- **Tests:**
  - B updates A's article → 403 and the row is unchanged;
  - B deletes A's comment → 403 and the row still exists;
  - A deletes their own comment through another article's slug → 404;
  - PUT with an `author` key → ignored.

## Q5. Other items the architecture must cover

| Item | Recommendation | Keep/Change |
|---|---|---|
| CORS (C-31) | Use `Corsica` or `CORSPlug` with an explicit origin list from `CORS_ORIGINS`.<br>Defaults: `http(s)://localhost:4000` and `http(s)://0.0.0.0:4000`, because legacy matched netloc with any scheme.<br>`allow_credentials: false`; allow headers `authorization, content-type`.<br>Preflight is answered before the auth plug.<br>Never reflect an arbitrary Origin. | KEEP |
| Unbounded `limit` (C-24) | The ADR keeps "no max". Flag it as a DoS risk: `limit=10^9` serialises the whole table with its preloads.<br>Recommend a pending divergence with a high cap (e.g. 1000) or a decision record.<br>Either way, parse strictly: a non-integer or negative `limit`/`offset` falls back to the default, with no raise and no `String.to_atom`. | KEEP now; CHANGE proposed |
| Input crashes (C-41) | Fetch every wrapper with `case params["user"] do %{} = m -> m; _ -> %{} end`. A top-level JSON array arrives as `_json`, so the wrapper is missing and the request becomes a 400 field-required response, not a 500.<br>Cast only the whitelisted fields, so a comment `author` key is ignored (201).<br>Turn malformed JSON (`Plug.Parsers.ParseError`) into 400 with the labelled `detail` envelope.<br>Set `Plug.Parsers` `length:` to about 1 MB (default 8 MB). | CHANGE (defect fix, UNDECIDED in ADR; low risk) |
| Login / register rate limiting | Legacy has none. Raising the PBKDF2 cost makes `/api/users/login` a CPU amplifier, so add `Hammer` keyed by IP plus lowercased email (login) and by IP (register).<br>Return 429 with a DRF-style throttle body `{"user":{"detail":"Request was throttled. Expected available in N seconds."}}`.<br>Size the limits generously, e.g. 10/min per IP+email. | CHANGE (new status code; needs a pending divergence) |
| Debug / technical pages (C-34) | Covered in Q3. JSON 404 for unknown routes (C-48 relaxed). | CHANGE (ASSUMED) |
| Token revocation (C-12) | Stateless tokens plus a per-request `is_active` check. Password change does not revoke tokens. Record it as accepted risk (contracts Decision 9). | KEEP |
| SQL / atoms | All filters (`tag`, `author`, `favorited`) use `^`. No `String.to_atom` on params or labels: labels are compile-time literals. | n/a (enforce in review) |
| Headers / TLS | API only, with no CSRF surface (no cookies). Add `x-content-type-options: nosniff`.<br>If TLS terminates at the app or a trusted proxy, use `force_ssl` with HSTS (`PHX_HOST`). C-51 relaxed. | CHANGE (minor) |
| Supply chain | Add `mix sobelow --exit medium`, `mix deps.audit` and `mix hex.audit` to CI. | new |

## Risks summary
1. The PBKDF2 iteration increase conflicts with ADR-000's "no login regression" goal. It needs an explicit carve-out.
2. Writing Django format keeps reversibility. Choosing Argon2 is one-way and needs the dispatcher.
3. C-16 (403 on a bad token on public endpoints) stays UNDECIDED. The tri-state auth plug keeps it a policy flag.
4. Rate limiting and the `limit` cap are behaviour changes and need divergence entries before they ship.
