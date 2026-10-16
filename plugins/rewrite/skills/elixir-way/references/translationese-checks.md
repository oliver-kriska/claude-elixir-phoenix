# Translationese Checks

Translationese is Elixir that compiles, passes parity tests, and still has the legacy runtime's architecture.
Run these probes on the **target** tree, never on the legacy app.
They cover the gap that idiom-level review leaves. In Campfire, four `/phx:review` rounds ran over a
hand-rolled router, a GenServer that owned the database and a Redis job list. No track reported that
Phoenix, Ecto and Oban were missing, because every track reviewed idioms inside the architecture it was given.

## How to Run

- Run every command from the target project root. All patterns are valid ripgrep (tested with rg 15.2).
- No `rg` on PATH: run the identical pattern with the Grep tool (`output_mode: "content"`), never a rewritten regex.
- Exit codes: `0` found a hit, `1` found nothing, `2` means a missing path or a bad regex. Drop paths that
  do not exist (`config`, `c_src`, `native`, `.github`) instead of reading `2` as a clean result.
- The patterns contain no `|`, so they survive markdown tables. Alternation is repeated `-e`.
  Intersection is `$(rg -l A lib)` passed to a second `rg`. `\x7c` matches a literal pipe.
- **An empty inner `rg -l` makes the outer `rg` search `.`**. Run the inner command first. If it lists
  nothing, record the check as "pattern absent".
- Multiline checks use `-U`. `.` never crosses a newline, so line windows are written as `(?:.*\n){0,N}?`.
- A count is a lead, not a finding. Read every hit before you report it. Confirm the exact text with Read,
  because proxies that collapse output can turn near-identical lines into a phantom match.
- A probe is a discovery lead. A finding needs an obligation that applies to this target's shape
  (app-shapes.md) and a guarantee the code leaves unmet. A justified exception (a small Plug API, direct SQL in
  an integration, a non-durable timer) whose approved KEEP or SHIM row or accepted ADR names the guarantees it
  owns and their tests is **no finding**: list it as checked, citing the row ID.
- Report each check as a hit with `file:line`, `pattern absent; Elixir-way gap: <what is missing>`,
  `pattern absent; target present`, or `not applicable to this shape: <evidence>`.
- Severity: **BLOCKER** fails review and verify. **WARNING** needs a fix or a ledger justification.
  **SUGGESTION** is advisory. The column gives the level once the two conditions above hold.
- Emulated legacy framework behavior (headers, error pages, URL matching, error wording) is justified only for a
  `contract` with a named consumer. An `incidental` default or a `defect` is a finding, inside `compat/` too.
- SHIM code lives under `lib/**/compat/**`, and the leakage checks exclude that path.

## 1. Framework Absence

A missing framework is a lead. T02–T04 become findings only when the shape calls for the framework and no
accepted ADR records the guarantees the hand-written code owns and how they are tested.

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T01 | Framework deps declared | `rg -n -e '\{:phoenix,' -e '\{:ecto_sql,' -e '\{:ecto_sqlite3,' -e '\{:oban,' mix.exs` (a missing dep while T02–T04 hit) | BLOCKER | Phoenix 1.8.15, Ecto 3.14.2 + ecto_sql 3.14.0 / ecto_sqlite3 0.25.0, Oban 2.24.1. Campfire shipped HTTP, DB and jobs with none of them |
| T02 | HTTP without Phoenix | `rg -l -e 'use Plug\.Router' -e 'send_resp\(' -e 'WebSock' lib` | BLOCKER if T01 lacks `:phoenix` | Phoenix.Router, controllers, Channels or LiveView |
| T03 | Database without Ecto | `rg -l -e 'Exqlite\.Sqlite3\.' -e 'Postgrex\.query' -e 'MyXQL\.query' -e ':esqlite' lib` | BLOCKER if T01 lacks `:ecto_sql` | Ecto Repo + schemas + contexts |
| T04 | Jobs without Oban | `rg -l -e '"B?[LR]POP"' -e '"[LR]PUSH"' -e 'resque:' -e 'send_after\(self\(\), :poll' lib` | BLOCKER if T01 lacks `:oban` | Oban workers inserted in `Ecto.Multi` |
| T05 | String-keyed rows in the core | `rg -c '\w\["[a-z_]+"\]' lib -g '!*_controller.ex'` | WARNING | Ecto schemas; string keys only at the params edge |
| T06 | Legacy tree mirrored | `rg --files lib -g '**/models/**' -g '**/services/**' -g '**/concerns/**' -g '**/helpers/**'` | WARNING | Contexts by capability (`lib/app/chat.ex`), schemas inside them |

## 2. Hand-Rolled Framework Primitives

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T07 | Plug.Router size (>20 routes) | `rg -c '^\s*[a-z]+ "/' $(rg -l 'use Plug\.Router' lib)` | WARNING; BLOCKER without an ADR | `Phoenix.Router` with pipelines and `~p` verified routes |
| T08 | Source router emulated | `rg -n -e 'RouteRecognition' -e 'endpoint_class' -e 'ActionDispatch' -e 'urlpatterns' -e 're_path' -e 'Legacy\w*Route' lib` | BLOCKER unless a `contract` row names the consumer of the matching behavior | Phoenix routes written for the contract, checked by a golden URL test |
| T09 | Generated mirrors of source | `rg --files lib -g '**/generated/**'` | WARNING | Hand-authored routes/schemas; generated tables only as test oracles |
| T10 | GenServer owns the DB | `rg -l -e 'Exqlite\.Sqlite3\.' -e 'Postgrex\.query' -e ':esqlite' $(rg -l 'use GenServer' lib)` | BLOCKER | Ecto Repo: DBConnection runs the query in the caller (Campfire C1/C2) |
| T11 | SQL routed by its text | `rg -n -i -e 'starts_with\?\(.*"select' -e 'starts_with\?\(.*"with' -e '~r/\^\\s\*select' lib` | BLOCKER | A reader Repo chosen at the call site (see sqlite-on-beam.md) |
| T12 | Job queue emulated | `rg -n -e 'resque:' -e 'sidekiq' -e '_aj_globalid' -e 'gid://' -e '"B?[LR]POP"' -e '"[LR]PUSH"' -e 'BLMOVE' lib` | BLOCKER unless a SHIM row | Oban; legacy queues are drained, never consumed |
| T13 | Non-durable Redis behind jobs | `rg -n -e 'appendonly no' -e 'save \x27\x27' -e 'save ""' -g '!lib' -g '!test' .` | BLOCKER if T12 hits | Oban in the domain DB. Campfire ran Redis with `--save '' --appendonly no` |
| T14 | Polling loops | `rg -n -e 'send_after\(self\(\), :poll' -e 'Process\.sleep\(' -e ':timer\.sleep\(' lib` | WARNING | PubSub notify, Oban, or a timer with a runtime reason. A 50 ms poll capped Campfire at 20 jobs/s |
| T15 | Legacy realtime protocol | `rg -n -e 'actioncable-v1-json' -e '@behaviour WebSock' -e ':cowboy_websocket' -e '"identifier"' lib` | WARNING; SHIM only with coexistence clients | Phoenix Channels or LiveView |
| T16 | Redis call sites | `rg -n 'Redix\.' lib config mix.exs` | WARNING per unclassified site | Classify by role (infrastructure.md) |
| T17 | Public ETS | `rg -n ':ets\.new\(.*:public' lib` | WARNING | Cachex 4.1.1 with `limit`, or a `:protected` table owned by a supervised process |
| T18 | Single-process limiter | `rg -n -e 'Map\.filter\(' -e 'Enum\.filter\(' $(rg -l 'def handle_call' lib -g '*{rate,limit,throttl}*')` | WARNING | Hammer 7.5.0 ETS backend or `:ets.update_counter/4` (Campfire C6) |
| T19 | Manual HTML and CSRF | `rg -n -e 'EEx\.function_from_' -e 'EEx\.eval_' -e 'name="authenticity_token"' -e 'def html_escape' lib` | BLOCKER | HEEx, `<.form>`, `Plug.CSRFProtection` |

## 3. OTP Hazards

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T20 | Caller code runs in a shared server | `rg -n -e 'def handle_call\(\{:transaction' -e 'def handle_call\(\{:\w+,\s*\w*fun\w*' -e 'def handle_call\(\{:\w+,\s*\w*callback' lib` | BLOCKER | Run caller functions in the caller: `Repo.transact/2`, DBConnection checkout |
| T21 | Owner reraises | `rg -n -e '\breraise\b' -e ':erlang\.raise\(' $(rg -l 'use GenServer' lib)` | BLOCKER in `handle_call`/`handle_cast` | Return the error to the caller. In Campfire one bad bind crashed the shared DB server for everyone (C3) |
| T22 | Call timeouts | compare `rg -n 'GenServer\.call\(' lib` with `rg -n -e 'GenServer\.call\(.*, \d[\d_]*\)' -e 'GenServer\.call\(.*, :infinity\)' -e 'GenServer\.call\(.*timeout\w*\)' lib` | WARNING | One budget per owner, below the request timeout; `:infinity` needs a written reason |
| T23 | Unbounded `Task.await` | `rg -n -e 'Task\.await\(\w+\)' -e 'Task\.await_many\(\w+\)' lib test` | SUGGESTION | An explicit timeout, `Task.yield/2` + `Task.shutdown/2`, `Task.async_stream/3` with `:timeout` |
| T24 | Unsupervised processes | `rg -n -e 'GenServer\.start\(' -e 'Agent\.start\(' -e 'Task\.start\(' -e '\bspawn\(' -e '\bspawn_link\(' lib` | WARNING (Iron Law 14) | A child spec under a supervisor; `Task.Supervisor.start_child/2` |
| T25 | Start or block in `init/1` | `rg -U -n -e 'def init\(.*\n(?:.*\n){0,12}?.*start_link\(' -e 'def init\(.*\n(?:.*\n){0,12}?.*receive do' lib` | WARNING | `handle_continue/2`; a supervised sibling |
| T26 | Restart intensity unstated | `rg -n 'max_restarts' lib` (absent while shared owners sit under the root) | SUGGESTION | State the rationale; test a crash burst |
| T27 | Gated on scheduler count | `rg -n 'schedulers_online\(\)\s*[<>=]' lib` | WARNING | Log the gate at boot. Campfire's 1-CPU benchmark never ran the new read path |
| T28 | Process dictionary as a request global | `rg -n -e 'Process\.put\(:current' -e 'Process\.put\(:tenant' -e 'Process\.put\(:locale' -e 'Process\.put\(:\w*transaction' lib` | WARNING | An explicit `scope` argument; capture the locale before spawning (Iron Law 25) |
| T29 | Env read at runtime | `rg -n 'System\.\w+_env!?\(' lib -g '!**/application.ex' -g '!**/release.ex'` | WARNING | `config/runtime.exs` + Application env. Campfire's clock read env on every call (C11) |
| T30 | Atoms from input | `rg -n -e 'String\.to_atom\(' -e 'List\.to_atom\(' -e 'binary_to_atom\(' lib` | BLOCKER on user input (Iron Law 10) | `String.to_existing_atom/1`, an explicit map, `Ecto.Enum` |
| T31 | Broad rescue | `rg -U -n 'rescue\s+[_a-z]\w*\s*->' lib` | WARNING | Rescue named exception structs and log each one. A dismissed `rescue _ ->` later caused a parity regression |
| T32 | Errors matched by string | `rg -n -e 'String\.contains\?\(inspect\(' -e 'UNIQUE constraint failed' -e 'duplicate key value' lib` | WARNING | `unique_constraint/3`; match exception structs |
| T33 | Assertive match on external I/O | `rg -n -e '\{:ok, _\w*\} = Redix\.' -e '\{:ok, _\w*\} = Req\.' -e '\{:ok, _\w*\} = Finch\.' -e '\{:ok, _\w*\} = HTTPoison\.' lib` | WARNING in request paths | `with` + an explicit error branch, or an Oban job with retries |

## 4. Shared-Cache Hazards

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T34 | Per-request values near caches | `rg -n -i -e csrf -e authenticity_token -e 'conn\.host' -e forwarded -e current_user -e current_scope -e locale $(rg -l -e 'Cachex\.' -e ':ets\.insert' -e 'FragmentCache' -e ':persistent_term\.put' lib)` | BLOCKER if the value is cached but not in the key | Key on every input, or render the per-request parts outside the cache. One user's CSRF token reached another user in Campfire (B1) |
| T35 | URLs built from request headers | `rg -n -e 'get_req_header\(conn, "host"\)' -e 'get_req_header\(conn, "x-forwarded-host"\)' -e 'conn\.host' lib -g '!**/endpoint.ex'` | BLOCKER when cached or rendered | Endpoint `url:` config, `url(~p"/...")` (Campfire B3, host poisoning) |
| T36 | Whole-table wipe | `rg -n ':ets\.delete_all_objects\(' lib` | WARNING | Bounded, incremental eviction (Cachex `limit`, `ttl`) |
| T37 | Errors cached | `rg -n -B6 'rescue' $(rg -l -e 'Cachex\.fetch' -e 'FragmentCache\.' -e ':ets\.insert' lib)` | WARNING | Have the Cachex fallback return `{:ignore, value}` on failure; test fail-then-recover |
| T38 | Whole-response cache | `rg -n -e 'ResponseCache' -e 'response_cache' -e 'data_version' lib` | WARNING; BLOCKER during coexistence | No response cache while another writer (the legacy app, admin SQL) exists; ETag instead |

## 5. Security Fail-Open

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T39 | Control allows on error | `rg -n -e '\{:error, _\w*\}\s*->\s*true' -e '\{:error, _\w*\}\s*->\s*:ok' -e '\{:error, _\w*\}\s*->\s*:allow' lib -g '*{rate,limit,throttl,auth,session,csrf,guard,polic}*'` | BLOCKER | Deny, log and alert. Campfire's limiter allowed requests when Redis errored (B4) |
| T40 | HTML by interpolation | `rg -n -e '~s\(.*="#\{' -e '\braw\(' lib` | BLOCKER for untrusted content (Iron Law 12) | HEEx auto-escaping |
| T41 | SQL interpolation | `rg -n -e 'query!?\(.*"[^"]*#\{' -e 'prepare\(.*"[^"]*#\{' -e 'execute\(.*"[^"]*#\{' lib` | BLOCKER until each value is proven internal (Iron Law 5) | Ecto with `^`, bind parameters, and an allowlist map for `ORDER BY` |
| T42 | CSRF wiring | `rg -n -e 'protect_from_forgery' -e 'CSRFProtection' -e 'sec-fetch-site' lib` (no `:protect_from_forgery` in a browser pipeline) | BLOCKER | The Phoenix `:browser` pipeline; a header-only check needs an ADR |
| T43 | Hand-built download header | `rg -n 'put_resp_header\(conn, "content-disposition"' lib` | WARNING | `Phoenix.Controller.send_download/3` (it encodes the filename) |
| T44 | Untrusted deserialization | `rg -n -e 'binary_to_term\(' -e 'Marshal\.load' -e 'Marshal\.decode' lib` | BLOCKER on external input | JSON; `binary_to_term(bin, [:safe])` only for trusted data; never parse Marshal |

## 6. Source-Framework Leakage

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T45 | Source names in the core | `rg -n -w -e Rails -e ActiveSupport -e ActionCable -e ActiveJob -e ActiveRecord -e Marshal -e Rack -e Django -e Laravel -e Express -e DRF -e Symfony -e Spring lib -g '!**/compat/**'` | WARNING | A boundary adapter in `lib/app/compat/`, with a SHIM row and a removal milestone or a permanent-adapter support policy |
| T46 | Compat share | `rg --stats -c '' lib -g '**/compat/**'` vs `rg --stats -c '' lib` (read "matched lines") | SUGGESTION | A share that keeps growing means the core is absorbing the legacy contract; review the SHIM list |
| T47 | Legacy crypto codecs in the core | `rg -n -e 'MessageVerifier' -e 'MessageEncryptor' -e 'KeyGenerator' lib -g '!**/compat/**'` | WARNING | One-way readers in compat (data-compat.md); `Phoenix.Token`/`Plug.Crypto` for new data |
| T67 | Legacy framework defaults emulated without a consumer | `rg -n -i -e '"x-powered-by"' -e '"server", "' -e 'Cannot GET' -e 'Cannot POST' -e 'W/\\?"' -e 'OrderedObject' -e 'downcase.*request_path' -e 'downcase.*path_info' -e 'path_info.*downcase' lib` (compat included) | WARNING per hit without a `contract` row naming its consumer | Drop an `incidental` default with a recorded divergence. An Express RealWorld port emulated `X-Powered-By`, weak ETags, case-insensitive paths and `Cannot GET` pages with no consumer |
| T68 | Legacy defect reproduced | `rg -n -i -e 'bug-for-bug' -e 'legacy bug' -e 'legacy quirk' -e 'CPython' lib` | BLOCKER for a `defect` in domain code | Fix it with a divergence. A consumer that depends on it gets an approved edge SHIM, never domain logic. A Django RealWorld port encoded CPython small-int `is` semantics in `follow/2` |

## 7. Native Ports and NIFs for Solved Problems

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T48 | Native sources | `rg --files -g '*.{c,cc,cpp,rs,zig}' native c_src` | WARNING; ADR with a measurement | Floki or LazyHTML (HTML), Image/Vix (images), Req (HTTP), `:crypto` |
| T49 | Ports and NIF loading | `rg -n -e 'Port\.open\(' -e 'load_nif\(' -e 'use Rustler' lib` | WARNING | Same as T48; each port has a supervised owner, a timeout and an EPIPE path |
| T50 | NIF on a normal scheduler | `rg -n '\{"\w+",\s*\d+,\s*\w+\s*(?:,\s*0\s*)?\}' native c_src` | BLOCKER for calls longer than ~1 ms | `ERL_NIF_DIRTY_JOB_CPU_BOUND` or `IO_BOUND`; Rustler `schedule = "DirtyCpu"` |
| T51 | In-place library install | `rg -n -e '^\s*cp\s.*\.so\b' -e '^\s*cp\s.*\.dylib\b' -g 'Makefile*' -g '*.mk' .` | WARNING | Build into `priv/` with elixir_make; swap the release atomically. Overwriting a loaded `.so` can crash a running node |

## 8. Gate Gaming

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T52 | Credo checks disabled | `rg -n -e 'disabled:\s*\[' -e '\{Credo\.Check\.[\w.]+,\s*false\}' .credo.exs` | WARNING | Diff against `mix credo gen.config`; one justification per disabled check |
| T53 | Inline suppressions | `rg -n -e 'credo:disable-for' -e '@dialyzer' lib` | WARNING | Fix the code, or give each suppression a ledger justification |
| T54 | Deprecation sidestep | `rg -n 'Map\.from_struct.*\x7c> Map\.get\(' lib` | WARNING | The struct field or the documented API (Campfire F10) |
| T55 | Gate deps declared | `rg -n -e '\{:credo,' -e '\{:dialyxir,' -e '\{:sobelow,' -e '\{:mix_audit,' mix.exs` | BLOCKER when a gate invariant 9 requires for this shape is missing (sobelow applies to Phoenix targets only) | Add with `only: [:dev, :test], runtime: false` |
| T56 | Gates wired into one alias | `rg -n -e 'precommit' -e '"credo' -e '"dialyzer' -e '"sobelow' -e '"deps\.audit' mix.exs .github` | BLOCKER when absent | The Phoenix 1.8 `precommit` alias, extended and run in CI |
| T57 | Warnings as errors | `rg -n 'warnings-as-errors' mix.exs .github Makefile` | WARNING when absent | `mix compile --warnings-as-errors` in precommit and CI |

## 9. Test Smells

| # | Check | rg pattern | Severity | Elixir-way replacement |
|---|-------|------------|----------|------------------------|
| T58 | Oracle silently skipped | `rg -n 'File\.[a-z_]+\?\(' test` (guarding a generator or a test body) | WARNING | Fail when the oracle is missing; skip only with a tag and a reason. Campfire's `media_test` passed with zero cases (F4) |
| T59 | Sleeps | `rg -n -e 'Process\.sleep\(' -e ':timer\.sleep\(' test` | WARNING | `assert_receive` with a timeout, `Oban.Testing`, `start_supervised` |
| T60 | Serial suite (>30%) | `rg -l 'async: false' test -g '*_test.exs'` vs `rg --files test -g '*_test.exs'` | WARNING | Sandbox `async: true`. The ecto_sqlite3 sandbox cannot run DB tests async, so count non-DB files only |
| T61 | Global env mutation | `rg -n -e 'System\.put_env\(' -e 'Application\.put_env\(' test` | WARNING | Pass config as arguments; otherwise `async: false` + an `on_exit` restore |
| T62 | Tests write evidence | `rg -n -e 'File\.write!?\(.*parity/' -e 'File\.write!?\(.*results/' -e 'File\.write!?\(.*evidence/' test` | BLOCKER | A separate script produces evidence; tests never rewrite files that claims cite |
| T63 | Vacuous assertions | `rg -n -e 'assert true\b' -e 'assert System\.\w+\(\)' test` | WARNING | Assert behavior. `assert System.schedulers_online() == 1` held only on the benchmark box |
| T64 | Registry leaks | `rg -n 'Registry\.register\(' test` | SUGGESTION | A per-test registry via `start_supervised`, or unique names |
| T65 | ETS reach-in | `rg -n ':ets\.\w+\([A-Z][\w.]*,' test` | SUGGESTION | Test through the public API |
| T66 | Test helpers in lib | `rg -n -e 'def \w*fixture\w*\(' -e 'def \w*seed\w*\(' -e 'def reset\w*\(' lib` | WARNING | `test/support`, `priv/repo/seeds.exs` (Campfire E4) |

## Invariants That Fail Verify

The probes find candidates. These invariants decide PASS or FAIL. Each needs evidence: a test, a
command output, or a cited dependency source line. "Standard OTP behaviour" is not evidence.

1. **Claims match evidence.** Re-derive every number in the README or plan ("N tests", "Nx faster") from its
   cited artifact. Every cited path must exist. A total-parity claim is blocked while any scope file says
   `pending`, `TODO` or `skipped`.
2. **Accepted risks are explicit.** A PASS can exclude a finding only through an `AR-NN` record in
   `verify/accepted-risks.md` with Owner, Scope, Rationale, Review and Approved; a record without `Approved`
   excludes nothing. "Inherited" is never a reason by itself. A run with open departures reports
   "PASS WITH DOCUMENTED RISKS".
3. **No per-request value in shared state.** Cache keys and values, ETS and `persistent_term` never hold a
   CSRF token, request host, current user or locale unless that value is part of the key. Test: two sessions
   on two hosts get different tokens.
4. **Caller errors stay with the caller.** No caller-supplied function runs inside a shared process. With
   fault injection (raise, throw, exit, invalid bind), the owner pid is unchanged, no supervisor restart is
   counted, and the caller gets the original exception.
5. **Durable side effects commit atomically.** The domain write and its Oban insert share one `Ecto.Multi`.
   Required infrastructure is validated at boot. Test: kill the node between commit and perform, and the
   job still exists. Kill it mid-perform too: with `lifeline:` configured the job reruns after `rescue_after`,
   and the effect's idempotency key absorbs the repeat.
6. **Security fails closed.** Rate limiting, auth and CSRF deny when a backend errors.
7. **Every source dependency has a why.** Redis, Sidekiq, memcached, Nginx/Thruster, Nokogiri and similar
   each have a ledger row with a purpose and a verdict before planning.
8. **The architecture-fit question comes first.** One review track asks only "should this be
   Phoenix/Ecto/Oban/PubSub instead?", and it runs before any idiom-level review.
9. **Gates are wired and honest.** format, `compile --warnings-as-errors`, credo, dialyzer, sobelow and
   `deps.audit` run through one alias. Disabled checks are diffed and justified. The review runner can
   actually execute the security tools.
10. **Oracle tests fail loudly.** A missing oracle fails the test or skips it with a stated reason. Tests
    never write evidence artifacts.
11. **Return contracts are single-shaped.** No `list | {:error, _}` mixes. Enqueue and publish results are
    matched, or the API raises.
12. **Degraded modes are visible.** Every `rescue` logs. Boot logs each disabled path: read pool off, Redis
    absent, jobs disabled, scheduler gate.
13. **Build and runtime are separate.** Release images reset build-only env such as `ERL_FLAGS`. Deploys
    swap the whole artifact set atomically, with file modes checked.
14. **Defects are not ported.** A `defect` contract (a legacy bug, security hole or runtime artifact) is fixed
    with a divergence. A named consumer that depends on it gets an approved edge SHIM, never domain logic.

## Iron Laws Mapped Onto Non-Ecto, Non-LiveView Code

The Iron Law track keeps running when the target has no Ecto queries or LiveViews: apply the equivalents below
to whatever code owns each concern. Missing Ecto is a finding only through T03 and the rules in How to Run.

| Iron Law | Equivalent in hand-rolled code | Probe |
|----------|--------------------------------|-------|
| 5 Pin values with `^` | Every `#{}` in a SQL string is proven internal; user values are bind params. Campfire `chat.ex:62` interpolated `op` and `order` | T41 |
| 6 Separate queries for has_many | A per-row DB call inside `Enum` or `for` (Campfire `push.ex:43`) | `rg -U -n -e 'Enum\.\w+\(.*fn.*\n(?:.*\n){0,6}?.*Repo\.\w+\(' -e 'Enum\.\w+\(.*fn.*\n(?:.*\n){0,6}?.*DB\.\w+\(' -e 'for .*<-.*\n(?:.*\n){0,6}?.*Repo\.\w+\(' lib` |
| 7–9 Oban job rules | Hand-rolled payloads: idempotency key, string keys, IDs not structs, and a round-trip test | T12, T04 |
| 10 No `String.to_atom` on input | The same rule in routers, socket frames, job payloads | T30 |
| 11 Authorize every `handle_event` | Authorize every channel `join`, stream subscribe and socket message, and again on reconnect | `rg -n -e 'def join\(' -e 'def handle_in\(' -e 'def websocket_handle\(' lib` |
| 12 No `raw/1` with untrusted content | `~s` HTML, `EEx.eval_*`, hand-written escaping | T19, T40 |
| 13, 14 Processes need a reason and a supervisor | A GenServer per domain noun; bare `start` or `spawn` | T10, T24 |
| 16 `@external_resource` for compile-time files | Any module attribute filled by `File.read` (missed in all four Campfire rounds) | `rg --files-without-match '@external_resource' $(rg -l '@\w+\s+File\.read' lib)` |
| 20 Wrap third-party APIs | Redix, Req or ExAws called from many modules | `rg -l -e 'Redix\.' -e 'Req\.' -e 'HTTPoison\.' -e 'ExAws\.' lib` (more than one file per client) |
| 22 Verify before claiming done | A parity or speed claim without a test or benchmark run | Invariant 1 |
| 24 Match errors explicitly | Match exception structs and error tuples, never `inspect/1` text | T32 |
| 25 Capture the locale before spawning | Locale, tenant or scope read from the process dictionary inside a Task | T28 |
