#!/usr/bin/env bash
# SubagentStart hook: Inject Iron Laws into all spawned subagents via additionalContext.
# Addresses the #1 session analysis finding: zero skill auto-loading in subagents.
#
# Reads `iron-laws/laws.yaml` (Phase 2D source-of-truth) when available; falls
# back to a hardcoded bullet list if the YAML file or python+yaml are missing.

set -eu

# Resolve repo root from CLAUDE_PLUGIN_ROOT or by walking up from this script.
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
  PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT"
else
  PLUGIN_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
fi
REPO_ROOT="$(cd "$PLUGIN_ROOT/../.." && pwd)"
LAWS_YAML="$REPO_ROOT/iron-laws/laws.yaml"

render_from_yaml() {
  python3 - "$LAWS_YAML" <<'PY'
import json
import sys
import yaml

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}

laws = data.get("laws") or []
# Only emit laws with an explicit `shortform`. Laws without shortform are
# either merged into a sibling law's shortform (e.g. laws 7/8/9 merged into
# 7's shortform) or intentionally not part of the SubagentStart context.
bullets = [f"- {law['shortform']}" for law in laws if law.get("shortform")]

prefix = "Elixir/Phoenix Iron Laws (NON-NEGOTIABLE):"
content = prefix + "\n" + "\n".join(bullets)

# Match jq's envelope shape: pretty-printed with 2-space indent, raw UTF-8 (no
# ensure_ascii escaping). This keeps the wire-level output byte-identical to
# the hardcoded fallback path.
print(json.dumps(
    {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": content,
        }
    },
    ensure_ascii=False,
    indent=2,
))
PY
}

render_hardcoded() {
  jq -n '{hookSpecificOutput: {hookEventName: "SubagentStart", additionalContext:
"Elixir/Phoenix Iron Laws (NON-NEGOTIABLE):
- NO unconditional DB queries in mount — use assign_async (or connected? + cache-backed branch for SEO routes)
- ALWAYS use streams for lists >100 items
- CHECK connected?/1 before PubSub subscribe
- NEVER use :float for money — use :decimal or :integer (cents)
- ALWAYS pin values with ^ in queries — never interpolate user input
- SEPARATE QUERIES for has_many, JOIN for belongs_to
- Jobs MUST be idempotent, args use STRING keys, never store structs in args
- NO String.to_atom with user input — atom exhaustion DoS
- AUTHORIZE in EVERY LiveView handle_event
- NEVER use raw/1 with untrusted content — XSS
- NO process without runtime reason — processes model concurrency/state/isolation
- SUPERVISE ALL LONG-LIVED PROCESSES
- NO IMPLICIT CROSS JOINS — from(a in A, b in B) without on: creates Cartesian product
- @external_resource FOR COMPILE-TIME FILES
- DEDUP BEFORE cast_assoc WITH SHARED DATA
- HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS
- WRAP THIRD-PARTY LIBRARY APIs behind project-owned modules
- NEVER use assign_new for values refreshed every mount
- VERIFY BEFORE CLAIMING DONE — run mix compile && mix test, never say should work"}}'
}

if [ -f "$LAWS_YAML" ] && command -v python3 >/dev/null 2>&1 && python3 -c "import yaml" 2>/dev/null; then
  render_from_yaml
else
  render_hardcoded
fi
