#!/usr/bin/env bash
# PostToolUse hook: Cross-project edit metrics (JSONL).
#
# The previous progress.md appender was removed in v2.8.3 — it picked the
# most recently modified progress.md across ALL plans, which wrote entries
# into unrelated plans whenever the user had more than one in flight
# (issue #38). The /phx:work skill logs structured progress entries itself,
# so the hook-driven append was both redundant and wrong.
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -n "$FILE_PATH" && -n "${CLAUDE_PLUGIN_DATA}" ]]; then
  METRICS_FILE="${CLAUDE_PLUGIN_DATA}/skill-metrics/edits-$(date '+%Y-%m').jsonl"
  echo "{\"ts\":\"$(date -Iseconds)\",\"file\":\"$FILE_PATH\",\"project\":\"$(basename "$(pwd)")\"}" >> "$METRICS_FILE" 2>/dev/null || true
fi
