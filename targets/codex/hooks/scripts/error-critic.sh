#!/usr/bin/env bash
# PostToolUseFailure hook: Structured error consolidation (Critic pattern).
# Inspired by AutoHarness (Lou et al., 2026) Critic→Refiner architecture:
# When repeated failures occur, consolidate error history into structured
# analysis instead of raw retry. Prevents debugging loops.
#
# Complements elixir-failure-hints.sh (generic hints) with failure-specific
# consolidation that detects REPEATED errors and escalates to structured analysis.

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
ERROR=$(echo "$INPUT" | jq -r '.error // empty')

# Only handle mix-related failures
echo "$COMMAND" | grep -qE '^mix\b|MIX_ENV=\S+ mix' || exit 0

# Use temp dir for failure tracking (persists within session)
FAILURE_DIR="/tmp/.claude-elixir-failures"
mkdir -p "$FAILURE_DIR"

# Extract the mix subcommand for tracking (ERE for macOS compat)
MIX_CMD=$(echo "$COMMAND" | grep -oE '(MIX_ENV=[^ ]+ )?mix [^ ]+' | head -1)
# Create a stable key from the command (replace non-alphanum with _)
CMD_KEY=$(echo "$MIX_CMD" | tr -c '[:alnum:]' '_')

FAILURE_LOG="$FAILURE_DIR/${CMD_KEY}.log"
COUNT_FILE="$FAILURE_DIR/${CMD_KEY}.count"

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
Before retrying, pause and analyze:
- Is the error message identical to the previous failure?
- If yes: your fix didn't address the root cause. Re-read the error carefully.
- If different: progress is being made, but a new issue appeared.
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

STRUCTURED RECOVERY (do NOT retry the same approach):
1. STOP retrying the same fix — it has failed ${COUNT} times
2. Read the FULL error output from attempt #1 (root cause is usually there)
3. Check if errors are IDENTICAL (same root cause) or DIFFERENT (cascading)
4. If identical: your mental model of the code is wrong. Re-read the source file
5. If cascading: fix the FIRST error only, ignore downstream errors
6. Consider: /phx:investigate for structured root-cause analysis
7. Consider: grep .claude/solutions/ for previously solved similar errors"

echo "$CRITIC_ANALYSIS" | jq -Rs '{hookSpecificOutput: {hookEventName: "PostToolUseFailure", additionalContext: .}}'
