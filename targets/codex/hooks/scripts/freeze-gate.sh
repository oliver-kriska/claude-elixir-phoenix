#!/usr/bin/env bash
# PreToolUse hook: scoped edit lock ("freeze").
#
# Implements the on-demand / skill-scoped hook pattern from Anthropic's
# "how we use skills" — a guard you switch on for a focused task instead of
# leaving always-on. CC has no native skill-scoped hooks, so this is driven by
# a sentinel file the /phx:freeze skill writes (via Bash, never Edit/Write, so
# this gate can't block the skill from toggling itself).
#
# Sentinel: $proj/.claude/.freeze
#   - missing            => no-op (hook dormant; safe to ship enabled)
#   - present + empty     => ALL Edit/Write/NotebookEdit denied (investigation)
#   - present + path lines => only edits under a listed prefix are allowed
#
# Deny is emitted as permissionDecision:"deny" + additionalContext (CC 2.1.110+
# preserves additionalContext on blocked calls) so Claude stops retrying.

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
case "$TOOL" in
  Edit|Write|NotebookEdit) ;;
  *) exit 0 ;;
esac

proj="${CLAUDE_PROJECT_DIR:-$PWD}"
SENTINEL="$proj/.claude/.freeze"
[[ -f "$SENTINEL" ]] || exit 0

FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' 2>/dev/null)
[[ -n "$FILE_PATH" ]] || exit 0

# Normalize the target to an absolute path for prefix comparison.
case "$FILE_PATH" in
  /*) abs="$FILE_PATH" ;;
  *)  abs="$proj/$FILE_PATH" ;;
esac

emit_deny() {
  local reason="$1"
  local ctx="Edit freeze is active ($reason). Do not retry this edit. The user must run '/phx:freeze off' to lift the lock, or '/phx:freeze <dir>' to allow a directory. If this edit is necessary, ask the user rather than retrying."
  jq -nc --arg reason "$reason" --arg ctx "$ctx" \
    '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: $reason,
        additionalContext: $ctx
      }
    }'
  exit 0
}

# Collect non-empty, non-comment allow-list entries. The `|| [[ -n "$line" ]]`
# tail catches a final line with no trailing newline.
allow=()
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line#"${line%%[![:space:]]*}"}"   # ltrim
  line="${line%"${line##*[![:space:]]}"}"     # rtrim
  [[ -z "$line" || "$line" == \#* ]] && continue
  allow+=("$line")
done < "$SENTINEL"

# Empty sentinel => total edit freeze.
if [[ ${#allow[@]} -eq 0 ]]; then
  emit_deny "all edits are frozen"
fi

# Scoped freeze: allow only paths at or under a listed prefix.
for prefix in "${allow[@]}"; do
  case "$prefix" in
    /*) full="$prefix" ;;
    *)  full="$proj/$prefix" ;;
  esac
  if [[ "$abs" == "$full" || "$abs" == "$full"/* ]]; then
    exit 0
  fi
done

emit_deny "edits limited to: ${allow[*]}"
