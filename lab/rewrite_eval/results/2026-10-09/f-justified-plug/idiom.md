# Idiom Audit — S-01

Target: target/ @ 2222222222222222222222222222222222222222 (clean) · Source @ 3333333333333333333333333333333333333333 · Scope: 1 file (lib/health_router.ex; test/health_router_test.exs read as evidence) · Findings: BLOCKER 0 / WARNING 0 / NOTE 3

Static review only. Nothing was compiled, run or executed. This is not production parity certification.

## Findings

### I-01 [NOTE] Framework-absence probes T01-T04 cannot be fully evaluated: no mix.exs in the packet
**Where**: target/ (no `mix.exs`) · **Violates**: none (ADR-001 accepts plain Plug) · **Origin**: slice
**Why it matters**: T02 hits (`use Plug.Router` at lib/health_router.ex:2, `send_resp(` at :9 and :13). T02 would be a BLOCKER if T01 lacked `:phoenix`, but ADR-001 explicitly justifies plain Plug, so it drops to not-a-finding (M-01 cites ADR-001). T01 itself ("Phoenix/Ecto/Oban missing while T02-T04 hit") is unverifiable because the dependency manifest is not in the packet. T03 (database) and T04 (jobs) found no hits, so the absence of `:ecto_sql` and `:oban` removes no guarantee.
**Direction**: when the full project is audited, confirm `mix.exs` declares `:plug` (and the host's Bandit/`plug_cowboy`) and nothing implies a hand-rolled HTTP server.
```elixir
# nothing to change in the router; verify in mix.exs:
{:plug, "~> 1.16"}, {:bandit, "~> 1.5"}
```

### I-02 [NOTE] 404 fallback sets no content-type, while the legacy source returned text/plain
**Where**: lib/health_router.ex:12-14 vs source/service.py:4 · **Violates**: none (C-02 pins only the status; M-01 "response shape" is slightly wider) · **Origin**: slice
**Why it matters**: the source returns `404, "text/plain", "not found"`. The target `send_resp(conn, 404, "not found")` sets no content-type. C-02 and `C-02` test assert only the status, so no stated contract is broken. A client that depended on the media type would see a difference.
**Direction**: if M-01 "response shape" is meant to include the 404 media type, add it to C-02 and the test; otherwise record that it was left out on purpose.
```elixir
match _ do
  conn
  |> put_resp_content_type("text/plain")
  |> send_resp(404, "not found")
end
```

### I-03 [NOTE] Serving and supervision are claimed by the host, not verifiable here
**Where**: .claude/rewrite/architecture/ADR-001.md (host Bandit child), architecture.md (process table) · **Violates**: none · **Origin**: slice
**Why it matters**: ADR-001 and architecture.md state that the host owns the listener, TLS and shutdown and that this module starts no process. The code agrees: probes for `use GenServer|Agent`, `Task.start|spawn|:timer.send_interval`, and `Process.put/get` found nothing. The host supervision tree is outside the packet, and ADR-001 says it is not claimed verified. That stays an open item, not a pass.

## Decisions Checked
| Ledger/ADR | Expected | Found | Result |
|------------|----------|-------|--------|
| M-01 (MAP, C-01, C-02) | `Plug.Router` dispatch for GET /health and a 404 fallback | `use Plug.Router`, `get "/health"` at :5, `match _` at :12; 1 route, far below the T07 limit of 20 | Consistent |
| C-01 | 200, JSON media type, body `{"status":"ok"}`, liveness only | `put_resp_content_type("application/json")`, `send_resp(200, ~s({"status":"ok"}))`; no downstream calls (no Repo, Redix, HTTP client hits). Test C-01 asserts status, body and content-type prefix | Consistent |
| C-02 | Unknown paths and POST /health return 404 | `get` matches only GET; the catch-all `match _` returns 404 for everything else. Test C-02 covers GET /private and POST /health | Consistent (HEAD and other methods also 404, matching the source) |
| ADR-001 (plain Plug, no Ecto/Oban/Phoenix) | No persistence, jobs, GenServer, custom parser, queue, crypto or auth framework | Probes T03, T04, T10, T12, T14, T24, T28, T29, T30, T35, T39-T41, T44, T45 found no hits in lib/. No `rescue`/`catch` (T31). No `compat/` tree, no legacy-name leakage | Consistent |
| Architecture process table | No process created in this module | No process-creating constructs | Consistent |
| Test smells T58, T59, T63 | No skipped oracle, sleeps or vacuous assertions | No hits in test/ | Consistent |

No architectural violations were found in this scope. The module is a stateless plug with no cache, no authorization surface, no transaction, no job and no broadcast, so the Section 4 guarantee checks (atomicity, after-commit effects, cache keys, authorization, SQLite) do not apply. They are "pattern absent; target present" for the relevant probes, not an exclusion from review.

## Not Checked
- `mix.exs`, `config/` and the host application's supervision tree (Bandit child, TLS, graceful shutdown): not in the packet, so T01, T26 and T55-T57 gate wiring and the "supervised listener" claim in ADR-001 are unverified.
- Whether the tests pass: not run by design. The tests were read as evidence of intent only.
- Performance, load behavior and production parity: out of scope and not claimed.
- Legacy-side routing behavior beyond `source/service.py:1-4` (for example HEAD handling in the real source server).
