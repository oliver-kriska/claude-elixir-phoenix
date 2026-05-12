---
name: phx:deps-audit
description: Audit Hex dep updates for supply-chain security risk — bidi chars, compile-time exec, maintainer changes, typosquats, CVEs. Use after mix deps.update or to review PRs touching mix.lock.
effort: medium
argument-hint: "[--base <ref> | --preview [pkg...]] [--json]"
allowed-tools: Read, Grep, Glob, Bash, WebFetch
---

# Hex Dependency Audit

Non-mutating supply-chain audit for Hex packages. Runs an 8-rule MVP catalogue
against changed packages, enriches with Hex API metadata, wraps existing tools
(`mix hex.audit`, `mix_audit`, OSV-Scanner), and emits a triage table.

## When to Use

- After `mix deps.update` or `mix deps.get` brought in new versions
- On PRs that touch `mix.lock` (pre-merge gate)
- Before manually updating a single package (`--preview <pkg>`)
- When investigating a dependency you don't recognize

## Iron Laws

1. **NEVER claim a diff is clean without inspecting it.** Run all 8 rules
   on the unpacked NEW tarball. "Looks fine" without a tool run is a false
   pass.
2. **NEVER auto-install `mix_audit` / `osv-scanner`.** Detect, warn with
   install instructions, skip cleanly if missing. Respect the user's env.
3. **NEVER promote a finding to BLOCK without rule citation.** Every finding
   shows `rule_id`, `severity`, `file:line`, `snippet`, `message`. No
   handwaving.
4. **NEVER fetch from Hex API without rate-limiting.** Cap at 5 req/sec.
   Cache metadata 7 days, top-500 list 1 day.
5. **NEVER run the audit on already-committed lock changes silently** —
   tell the user which mode (A/B/C) is active and which `(old, new)` pairs
   resolved.
6. **No LLM detection.** This skill is deterministic. LLM triage is Phase 2.

## Operating Modes

| Mode | Trigger | Old source | New source |
|------|---------|-----------|-----------|
| **B** (default) | `/phx:deps-audit` | `git show HEAD:mix.lock` | working `mix.lock` |
| **C** (PR) | `/phx:deps-audit --base main` | `git show <ref>:mix.lock` | working `mix.lock` |
| **A** (preview) | `/phx:deps-audit --preview httpoison` | locked version | Hex API latest |

See `${CLAUDE_SKILL_DIR}/references/operating-modes.md` for full resolver logic.

## Execution Flow

### Step 1: Resolve the diff

Parse the `mix.lock` Erlang term format for both old and new sources. Emit a
list of `{pkg, old_version, new_version}` tuples. Surface
new-only and removed-only packages separately (a removed package is not
audited; a brand-new package gets `old_version = nil` and skips diff-only
rules).

See `${CLAUDE_SKILL_DIR}/references/diff-resolver.md` for shell + `mix run -e` snippets per mode and the JSON output contract.

### Step 2: Fetch tarballs (cached)

For each `(pkg, old, new)`:

```
mix hex.package fetch <pkg> <old> --unpack -o .claude/deps-audit/cache/<pkg>/<old>/
mix hex.package fetch <pkg> <new> --unpack -o .claude/deps-audit/cache/<pkg>/<new>/
```

Skip fetch if cache exists. Prune cache entries >30 days old. See
`${CLAUDE_SKILL_DIR}/references/tarball-fetcher.md` for the bulk-fetch
wrapper, parallelism cap, and failure modes.

### Step 3: Run the 8 MVP rules on each NEW tarball

| # | Rule | Sev | Method |
|---|------|-----|--------|
| 1 | Bidi Unicode control chars in `.ex`/`.exs`/`.erl` | BLOCK | grep |
| 2 | `Code.eval_*` / `:erlang.apply` with non-literal MFA at module scope | BLOCK | AST (Sourceror or regex+scope) |
| 3 | `System.cmd` / `:os.cmd` / `Port.open` at compile time | BLOCK | AST |
| 4 | `:erlang.binary_to_term/1` on literal without `:safe` | BLOCK | AST |
| 5 | New `:git`/`:path` dep in `mix.exs` (vs old) | BLOCK | AST diff |
| 6 | Maintainer change between versions | BLOCK | Hex API |
| 7 | Base64 blobs >256 chars outside `priv/static/`, `test/fixtures/`, `assets/` | WARN | regex |
| 8 | Levenshtein ≤2 from top-500 + download delta >1000× | BLOCK | Hex API + fuzzy |

Full catalogue (35 rules, MVP marked) in `${CLAUDE_SKILL_DIR}/references/heuristics.md`.
Bash + `mix run -e` implementations for all 8 MVP rules in
`${CLAUDE_SKILL_DIR}/references/rules-impl.md` (single-pass NEW + diff rules +
Hex API rules, with `run_all_rules` master loop).

### Step 4: External tool wrappers (parallel)

- `mix hex.audit` — retired-package check, always available
- `mix_audit` — CVE check via GHSA, if installed (else warn)
- `osv-scanner` — CVE check via OSV.dev, if installed (else warn)

See `${CLAUDE_SKILL_DIR}/references/external-tools.md` for detection, output parsing, and severity mapping per tool.

### Step 5: Hex API enrichment (per package)

- `GET /api/packages/:name` — owners, downloads, inserted_at
- `GET /api/packages/:name/releases/:version` — per-release publisher
- Compute: `days_since_publish`, `owner_age_days`, `download_velocity`

Cap at 5 req/sec. Cache 7 days under `.claude/deps-audit/cache/hex-api/`.
See `${CLAUDE_SKILL_DIR}/references/hex-api.md` for endpoint contracts,
caching strategy, Rule 6/8 detection, and Levenshtein implementation.

### Step 6: Score & render

Per-package weighted sum: BLOCK = 10, WARN = 3, INFO = 1.
Risk band: 0 clean · 1–5 low · 6–15 medium · 16+ high.

Output:

1. **Stdout:** markdown table — `pkg | old → new | risk | findings | diff.hex.pm | maintainer-change` plus a per-package detail section for any non-clean row.
2. **Sidecar:** `.claude/deps-audit/last-run.json` with full structured findings (consumed by future Phase 3 PreToolUse hook).

`--json` flag emits JSON to stdout instead of markdown. See
`${CLAUDE_SKILL_DIR}/references/output-renderer.md` for table format,
sidecar schema, exit-code rubric, and `--quiet` mode.

## What This Skill Will NOT Do

- Modify `mix.lock`, `mix.exs`, or any project file (non-mutating by design)
- Run network calls beyond Hex API GET requests
- Auto-install missing tools
- Block `mix deps.get` / `mix deps.update` (Phase 3 hook does that)

## References

- `${CLAUDE_SKILL_DIR}/references/heuristics.md` — full 35-rule catalogue
- `${CLAUDE_SKILL_DIR}/references/rules-impl.md` — bash + `mix run -e` implementations for the 8 MVP rules
- `${CLAUDE_SKILL_DIR}/references/operating-modes.md` — Mode A/B/C resolver
- `${CLAUDE_SKILL_DIR}/references/diff-resolver.md` — shell snippets, lock parser, JSON output contract
- `${CLAUDE_SKILL_DIR}/references/tarball-fetcher.md` — `mix hex.package fetch` wrapper, parallel fetch, cache pruning
- `${CLAUDE_SKILL_DIR}/references/external-tools.md` — `mix hex.audit`, `mix_audit`, `osv-scanner` wrappers
- `${CLAUDE_SKILL_DIR}/references/hex-api.md` — endpoint contracts, rate limit, Rule 6/8 helpers
- `${CLAUDE_SKILL_DIR}/references/output-renderer.md` — markdown layout, JSON schema v1, exit-code rubric
- `${CLAUDE_SKILL_DIR}/references/testing.md` — smoke-test runner, fixture coverage matrix, why heredocs not `.ex`
