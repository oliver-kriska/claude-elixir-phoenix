#!/usr/bin/env bash
# PostToolUseFailure hook: Structured error consolidation (Critic pattern).
# Inspired by AutoHarness (Lou et al., 2026) Critic→Refiner architecture:
# When repeated failures occur, consolidate error history into structured
# analysis instead of raw retry. Prevents debugging loops.
#
# Complements elixir-failure-hints.sh (generic hints) with failure-specific
# consolidation that detects REPEATED errors and escalates to structured analysis.
#
# Also registered on PostToolUse (Bash, mix): a success resets that command’s
# count, so "attempt #N" means consecutive failures, not lifetime failures.

INPUT=$(cat)
EVENT=$(echo "$INPUT" | jq -r '.hook_event_name // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
ERROR=$(echo "$INPUT" | jq -r '.error // empty')
SESSION=$(echo "$INPUT" | jq -j '.session_id // "nosession"' | tr -c '[:alnum:]-' '_')

# Only handle mix-related commands
echo "$COMMAND" | grep -qE '^mix\b|MIX_ENV=\S+ mix' || exit 0

# Per-session state: a count shared across sessions would escalate a fresh
# session’s first failure straight to the loop analysis.
FAILURE_BASE="${TMPDIR:-/tmp}/.claude-elixir-failures"
FAILURE_DIR="$FAILURE_BASE/$SESSION"

# Extract the mix subcommand for tracking (ERE for macOS compat)
MIX_CMD=$(echo "$COMMAND" | grep -oE '(MIX_ENV=[^ ]+ )?mix [^ ]+' | head -1)
# Create a stable key from the command (replace non-alphanum with _)
CMD_KEY=$(echo "$MIX_CMD" | tr -c '[:alnum:]' '_')

FAILURE_LOG="$FAILURE_DIR/${CMD_KEY}.log"
COUNT_FILE="$FAILURE_DIR/${CMD_KEY}.count"

if [[ "$EVENT" == "PostToolUse" ]]; then
  rm -f "$COUNT_FILE" "$FAILURE_LOG"
  exit 0
fi

mkdir -p "$FAILURE_DIR"
find "$FAILURE_BASE" -type f -mtime +1 -delete 2>/dev/null

# Increment failure count
if [[ -f "$COUNT_FILE" ]]; then
  COUNT=$(cat "$COUNT_FILE")
  COUNT=$((COUNT + 1))
else
  COUNT=1
fi
echo "$COUNT" > "$COUNT_FILE"

# Log this error (keep last 5 for consolidation)
{
  echo "--- Failure #${COUNT} at $(date +%H:%M:%S) ---"
  echo "Command: $COMMAND"
  echo "$ERROR" | head -20
  echo ""
} >> "$FAILURE_LOG"
# Trim to last 5 failures
tail -100 "$FAILURE_LOG" > "$FAILURE_LOG.tmp" && mv "$FAILURE_LOG.tmp" "$FAILURE_LOG"

# First failure: let elixir-failure-hints.sh handle it (generic hints)
if [[ "$COUNT" -lt 2 ]]; then
  exit 0
fi

# 2nd failure: warn about pattern
if [[ "$COUNT" -eq 2 ]]; then
  HINT="REPEATED FAILURE (attempt #${COUNT}): Same command failed before.
Before retrying, compare this error with the previous one:
- Identical: the last fix didn’t address the root cause. Re-read the error.
- Different: progress is being made, but a new issue appeared.
- Consider: /phx:investigate for structured root-cause analysis."

  echo "$HINT" | jq -Rs '{hookSpecificOutput: {hookEventName: "PostToolUseFailure", additionalContext: .}}'
  exit 0
fi

# 3rd+ failure: escalate with consolidated error history (Critic pattern)
# Extract unique error signatures from the log
ERROR_SUMMARY=$(grep -A2 'Failure #' "$FAILURE_LOG" 2>/dev/null | grep -v '^--$' | tail -30)

CRITIC_ANALYSIS="DEBUGGING LOOP DETECTED (attempt #${COUNT}): ${MIX_CMD} has failed ${COUNT} times.

CRITIC ANALYSIS — Consolidated error history:
${ERROR_SUMMARY}

STRUCTURED RECOVERY — this fix has failed ${COUNT} times, so change the approach rather than retrying it:
1. Read the full error output from attempt #1 (the root cause is usually there)
2. Check whether the errors are identical (same root cause) or different (cascading)
3. If identical: your mental model of the code is wrong. Re-read the source file
4. If cascading: fix the first error only; downstream errors often resolve with it
5. Consider: /phx:investigate for structured root-cause analysis
6. Consider: grep .claude/solutions/ for previously solved similar errors"

echo "$CRITIC_ANALYSIS" | jq -Rs '{hookSpecificOutput: {hookEventName: "PostToolUseFailure", additionalContext: .}}'
