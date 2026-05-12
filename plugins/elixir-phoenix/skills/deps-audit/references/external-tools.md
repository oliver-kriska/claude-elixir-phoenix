# External Tool Wrappers

Three external CVE scanners layered on top of the 8 MVP rules. All optional
except `mix hex.audit` (ships with mix). **Never auto-install** — detect,
warn with install instructions, skip cleanly.

## 1. `mix hex.audit` — retired-package check

Ships with Mix. Zero-config. Detects packages explicitly retired by their
maintainers via Hex.pm (security, deprecated, invalid, renamed, etc.).

```bash
hex_audit() {
  mix hex.audit 2>&1 | tee .claude/deps-audit/cache/hex-audit.txt
}
```

Output format (line per retirement):

```
phoenix_html 2.14.3
  Reason: invalid
  Message: Upgrade to 4.x for new HTML escaping API
```

Parse with awk:

```bash
awk '
  /^[a-z_][a-z0-9_]* [0-9]/ { pkg=$1; ver=$2 }
  /Reason:/ { reason=$2 }
  /Message:/ { msg=substr($0, 11); print pkg"|"ver"|"reason"|"msg }
' .claude/deps-audit/cache/hex-audit.txt
```

Severity mapping: `security` → BLOCK · `invalid` / `deprecated` / `renamed`
→ WARN.

**FP rate:** ~0%. Always integrate.

## 2. `mix_audit` — CVE check via GitHub Advisory Database

Hex package (`{:mix_audit, "~> 2.1", only: [:dev, :test], runtime: false}`).
Checks GHSA `pkg:hex` advisories.

```bash
mix_audit_run() {
  if ! mix help deps.audit >/dev/null 2>&1; then
    cat >&2 <<'EOF'
WARN: mix_audit not installed — skipping CVE check via GHSA.

To enable:
  mix archive.install hex mix_audit
  # or add to mix.exs:
  # {:mix_audit, "~> 2.1", only: [:dev, :test], runtime: false}
EOF
    return 0
  fi

  mix deps.audit --format json 2>/dev/null \
    > .claude/deps-audit/cache/mix-audit.json
}
```

Output is JSON:

```json
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {"id": "GHSA-xxxx-xxxx-xxxx", "cve": "CVE-2026-12345",
                   "title": "...", "description": "...",
                   "severity": "high", "patched_versions": "~> 1.2.3"},
      "dependency": {"package": "...", "version": "..."}
    }
  ]
}
```

Severity mapping: `critical` / `high` → BLOCK · `moderate` → WARN ·
`low` → INFO.

**FP rate:** ~0% (advisory DB is curated). Coverage gap: GHSA has fewer Hex
entries than npm/RustSec, so absence is not proof of safety.

## 3. `osv-scanner` — CVE check via OSV.dev

Standalone Go binary (`go install github.com/google/osv-scanner@latest`).
v2.3.5+ supports Elixir/Hex.

```bash
osv_scan() {
  if ! command -v osv-scanner >/dev/null 2>&1; then
    cat >&2 <<'EOF'
WARN: osv-scanner not installed — skipping CVE check via OSV.dev.

To enable:
  go install github.com/google/osv-scanner@latest
  # or: brew install osv-scanner
EOF
    return 0
  fi

  osv-scanner \
    --lockfile mix.lock \
    --format json \
  > .claude/deps-audit/cache/osv-scan.json 2>/dev/null || true
}
```

Output is JSON with `results[].packages[].vulnerabilities[]`. Each
vulnerability has `id` (OSV ID), `aliases` (CVE list), `severity` (array of
CVSS strings).

Severity mapping: parse highest CVSS score from `severity[].score`:

- ≥ 9.0 → BLOCK (critical)
- ≥ 7.0 → BLOCK (high)
- ≥ 4.0 → WARN (medium)
- < 4.0 → INFO (low)

**FP rate:** ~0%. **Why integrate both `mix_audit` and `osv-scanner`?** GHSA
and OSV.dev have non-overlapping coverage. Running both catches more
real-world CVEs.

## Aggregation into findings format

Each external-tool finding maps to the same shape as MVP-rule findings,
with `rule_id = "ext:<tool>"`:

```elixir
%{
  rule_id: "ext:hex-audit" | "ext:mix-audit" | "ext:osv-scanner",
  severity: :block | :warn | :info,
  file: nil,         # CVEs are package-level, not file-level
  line: nil,
  snippet: "<advisory-id>",
  message: "<title or description>"
}
```

Attach to the per-package finding list before scoring.

## Parallelism

All three tools run independently. Spawn in background:

```bash
hex_audit &           pid_hex=$!
mix_audit_run &       pid_mix=$!
osv_scan &            pid_osv=$!

wait $pid_hex $pid_mix $pid_osv
```

`mix hex.audit` and `mix deps.audit` may contend on the `mix` lock; if so,
serialize the two mix-based scanners and only parallelize `osv-scanner`.

## Exit-code handling

| Tool | 0 | Non-zero |
|------|---|----------|
| `mix hex.audit` | No retirements | Retirements found (informational, NOT fatal) |
| `mix deps.audit` | No CVEs | CVEs found |
| `osv-scanner` | No CVEs | CVEs found OR scan error |

Treat non-zero as "findings to parse", not "skill failure". The skill itself
returns 0 unless the *audit infrastructure* fails (missing `mix`, bad
network, corrupt cache).

## Why not Snyk / Phylum / Endor?

| Tool | Why skipped |
|------|-------------|
| Snyk CLI | Paid for org use, signal duplicates `mix_audit` for free |
| Phylum | Thin Hex support (per 2026 research) |
| Endor Labs | No reliable BEAM reachability — not credible |
| Semgrep SC | Paid tier; OSS Semgrep covered separately in Phase 2 |
| Socket.dev | No Hex support; we **reimplement** their signal model |

## Future: SARIF output (Phase 2)

`osv-scanner --format sarif` and `mix deps.audit --format sarif` (proposed)
would let us emit a single SARIF file for GitHub Code Scanning. Deferred to
Phase 2 alongside Semgrep ruleset.
