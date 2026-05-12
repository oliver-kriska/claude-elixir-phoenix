# Output Renderer

Two outputs from every audit:

1. **Stdout** — markdown table + per-package detail (terminal-first)
2. **Sidecar** — `.claude/deps-audit/last-run.json` (machine-readable)

## Scoring weights & risk bands

```
BLOCK = 10 points
WARN  =  3 points
INFO  =  1 point

Per-package risk = sum of findings' points

Risk band:
   0          → clean
   1–5        → low
   6–15       → medium
   16+        → high
```

Risk emoji used in markdown for skim-readability:

| Band | Emoji | Meaning |
|------|-------|---------|
| clean | ✅ | No findings |
| low | 🟢 | INFO / minor WARN |
| medium | 🟡 | Multiple WARNs or 1 BLOCK |
| high | 🔴 | Multiple BLOCKs |

(Emoji is the *only* place this skill uses Unicode glyphs in output; the
rest of the renderer is ASCII to keep diff/grep-friendly.)

## Markdown table — top section

```markdown
# Hex Dependency Audit — Mode B (working vs HEAD)

Audited 4 changed · 1 added · 0 removed packages.
Tools run: mix hex.audit ✓ · mix_audit ✓ · osv-scanner ✗ (not installed)

| Package | Change | Risk | Findings | diff.hex.pm |
|---------|--------|------|----------|-------------|
| phoenix | 1.7.14 → 1.7.20 | ✅ clean | — | [view](https://diff.hex.pm/diff/phoenix/1.7.14..1.7.20) |
| ecto    | 3.13.2 → 3.13.4 | 🟢 low (3) | 1× WARN: base64 in priv/img | [view](https://diff.hex.pm/diff/ecto/3.13.2..3.13.4) |
| req     | 0.5.0 → 0.5.1 | 🔴 high (23) | 2× BLOCK · 1× WARN — maintainer changed | [view](https://diff.hex.pm/diff/req/0.5.0..0.5.1) |
| **new_logger** (added) | — → 0.1.0 | 🔴 high (10) | 1× BLOCK: typosquat of `logger` (50× DLs) | [view](https://hex.pm/packages/new_logger) |
```

## Markdown — per-package detail (only for non-clean)

For every row with score > 0, emit a detail section in order:

```markdown
## req — 🔴 high (score 23)

Maintainer changed: alice_dev → bob_unknown (between 0.5.0 and 0.5.1)

### Findings

- **BLOCK · rule 6 · maintainer change**
  `release publisher`: bob_unknown (was alice_dev)
  GHSA: n/a · CVE: n/a

- **BLOCK · rule 3 · System.cmd at compile time**
  `lib/req/setup.ex:14`
      System.cmd("curl", ["-fsSL", url])
  Triggered inside `__before_compile__/1`.

- **WARN · rule 7 · base64 blob >256 chars**
  `lib/req/templates.ex:42`
      "TG9yZW0gaXBzdW0gZG9sb3Igc2l0IGFtZXQs..." (412 chars)
```

Layout rules:

- Header includes risk emoji, band name, and score in parens
- One blank line between findings
- Code blocks for snippets are indented 4 spaces, never fenced
  (so they render cleanly even when output is piped through grep)
- File:line shown as plain `path:line` for terminal hyperlinking
- diff.hex.pm link **only** appears in the top table, not per-finding

## Markdown footer

```markdown
---

**Aggregate risk:** 🔴 high (1 package over threshold)

Re-run after fix: `/phx:deps-audit`
Inspect one package: `/phx:deps-audit --preview req`
Compare against main: `/phx:deps-audit --base origin/main`

Detailed findings: `.claude/deps-audit/last-run.json`
```

## `--json` flag

Replaces the markdown stdout with the same data the sidecar would receive.
Useful for CI consumers. Schema:

```json
{
  "version": 1,
  "generated_at": "2026-05-12T10:32:18Z",
  "mode": "B",
  "base": "HEAD",
  "tools": {
    "hex_audit": {"available": true, "ran": true},
    "mix_audit": {"available": true, "ran": true},
    "osv_scanner": {"available": false, "ran": false}
  },
  "summary": {
    "changed": 4, "added": 1, "removed": 0,
    "packages_with_findings": 2,
    "highest_risk_band": "high",
    "blocks_total": 3, "warns_total": 2, "infos_total": 0
  },
  "packages": [
    {
      "pkg": "req",
      "old_version": "0.5.0",
      "new_version": "0.5.1",
      "diff_url": "https://diff.hex.pm/diff/req/0.5.0..0.5.1",
      "risk_score": 23,
      "risk_band": "high",
      "maintainer_change": {"from": "alice_dev", "to": "bob_unknown"},
      "findings": [
        {
          "rule_id": 6,
          "severity": "block",
          "file": null, "line": null,
          "snippet": "alice_dev → bob_unknown",
          "message": "Maintainer changed between 0.5.0 and 0.5.1"
        },
        {
          "rule_id": 3,
          "severity": "block",
          "file": "lib/req/setup.ex", "line": 14,
          "snippet": "System.cmd(\"curl\", [\"-fsSL\", url])",
          "message": "System.cmd at compile time (inside __before_compile__/1)"
        }
      ],
      "external_findings": []
    }
  ]
}
```

Schema versioned with `"version": 1` so Phase 3 hook can detect
incompatible upgrades without parsing.

## Sidecar file

Always written to `.claude/deps-audit/last-run.json` regardless of `--json`
flag. Phase 3 PreToolUse hook reads this file to detect "recently audited"
state — if `generated_at` is within the last 10 minutes AND the working
`mix.lock` has the same SHA-256, allow `mix deps.get`/`update` without
re-audit prompt.

## Quiet mode

`--quiet` suppresses clean rows from the markdown table. Useful for
CI/pre-commit hooks that should only chime on findings.

## Exit code rubric

| Outcome | Exit code |
|---------|-----------|
| All packages clean | 0 |
| Some WARNs, no BLOCKs | 0 |
| Any BLOCK finding | 2 |
| Audit infrastructure failed (missing tools, bad network) | 3 |

Exit `2` is the conventional CC plugin convention for "findings present,
human review needed." Exit `3` separates "you can't trust this audit" from
"this audit caught something."

## Implementation entry point

The renderer reads `.claude/deps-audit/cache/findings.json` (a flat array
written by each rule + tool wrapper) and the original `diff.json` from the
resolver, then emits both outputs.

```bash
render() {
  local fmt="${1:-markdown}"
  local findings=".claude/deps-audit/cache/findings.json"
  local diff=".claude/deps-audit/cache/diff.json"

  case "${fmt}" in
    markdown) render_markdown "${diff}" "${findings}" ;;
    json)     render_json     "${diff}" "${findings}" ;;
  esac

  write_sidecar "${diff}" "${findings}" > .claude/deps-audit/last-run.json
}
```

`render_markdown` and `render_json` are jq programs (kept inline in
the skill body — see [implementation skeleton in heuristics.md](heuristics.md)
for the per-rule shape contract findings must obey).

## Anti-pattern: emoji-only signals

Some renderers use emoji as the *only* severity marker. Don't. Always
include the band name in text (`high`, `medium`, etc.) so the output is
greppable and accessible to terminals without emoji rendering.
