#!/usr/bin/env bash
# Full verification pipeline in one pass.
# Returns only failures to minimize context usage.
# Eliminates 4-6 sequential tool round-trips (composition tax).
#
# Usage: bash verify-all.sh [--scope path/to/file.ex ...]
# Exit code: 0 = all pass, 1 = failure (details in output)

set -euo pipefail

# Parse optional --scope for targeted verification
SCOPE_FILES=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope) shift; SCOPE_FILES="$SCOPE_FILES $1"; shift ;;
    *) SCOPE_FILES="$SCOPE_FILES $1"; shift ;;
  esac
done

[ -f "mix.exs" ] || { echo "ERROR: No mix.exs found"; exit 1; }

RESULTS=""
FAILED=0
PASS="✅"
FAIL="❌"
SKIP="⏭️"

# Step 1: Compile
OUTPUT=$(mix compile --warnings-as-errors 2>&1) || {
  RESULTS="$RESULTS\n| Compile | $FAIL | $(echo "$OUTPUT" | grep -c 'error\|warning') issues |"
  RESULTS="$RESULTS\n\n### Compile Errors\n\`\`\`\n$OUTPUT\n\`\`\`"
  FAILED=1
}
[ $FAILED -eq 0 ] && RESULTS="$RESULTS\n| Compile | $PASS | Clean |"

# Step 2: Format
if [ -n "$SCOPE_FILES" ]; then
  FORMAT_OUTPUT=$(mix format --check-formatted $SCOPE_FILES 2>&1) || {
    RESULTS="$RESULTS\n| Format | $FAIL | Files need formatting |"
    RESULTS="$RESULTS\n\n### Format Issues\n\`\`\`\n$FORMAT_OUTPUT\n\`\`\`"
    FAILED=1
  }
else
  FORMAT_OUTPUT=$(mix format --check-formatted 2>&1) || {
    RESULTS="$RESULTS\n| Format | $FAIL | Files need formatting |"
    RESULTS="$RESULTS\n\n### Format Issues\n\`\`\`\n$FORMAT_OUTPUT\n\`\`\`"
    FAILED=1
  }
fi
echo "$RESULTS" | grep -q "Format" || RESULTS="$RESULTS\n| Format | $PASS | Clean |"

# Step 3: Credo (optional — skip if not installed)
if mix help credo >/dev/null 2>&1; then
  CREDO_OUTPUT=$(mix credo --strict 2>&1) || {
    ISSUE_COUNT=$(echo "$CREDO_OUTPUT" | grep -cE '^\s+┃' || echo "?")
    RESULTS="$RESULTS\n| Credo | $FAIL | $ISSUE_COUNT issues |"
    RESULTS="$RESULTS\n\n### Credo Issues\n\`\`\`\n$(echo "$CREDO_OUTPUT" | head -40)\n\`\`\`"
    FAILED=1
  }
  echo "$RESULTS" | grep -q "Credo" || RESULTS="$RESULTS\n| Credo | $PASS | Clean |"
else
  RESULTS="$RESULTS\n| Credo | $SKIP | Not installed |"
fi

# Step 4: Tests
if [ -n "$SCOPE_FILES" ]; then
  # Find related test files for scoped verification
  TEST_FILES=""
  for f in $SCOPE_FILES; do
    BASE=$(basename "$f" .ex)
    FOUND=$(find test -name "${BASE}_test.exs" 2>/dev/null | head -1)
    [ -n "$FOUND" ] && TEST_FILES="$TEST_FILES $FOUND"
  done
  if [ -n "$TEST_FILES" ]; then
    TEST_OUTPUT=$(mix test $TEST_FILES --trace 2>&1) || {
      FAIL_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+ failures?' | head -1 || echo "?")
      RESULTS="$RESULTS\n| Test | $FAIL | $FAIL_COUNT |"
      RESULTS="$RESULTS\n\n### Test Failures\n\`\`\`\n$(echo "$TEST_OUTPUT" | tail -30)\n\`\`\`"
      FAILED=1
    }
  else
    TEST_OUTPUT=$(mix test --trace 2>&1) || {
      FAIL_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+ failures?' | head -1 || echo "?")
      RESULTS="$RESULTS\n| Test | $FAIL | $FAIL_COUNT |"
      RESULTS="$RESULTS\n\n### Test Failures\n\`\`\`\n$(echo "$TEST_OUTPUT" | tail -30)\n\`\`\`"
      FAILED=1
    }
  fi
else
  TEST_OUTPUT=$(mix test --trace 2>&1) || {
    FAIL_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+ failures?' | head -1 || echo "?")
    RESULTS="$RESULTS\n| Test | $FAIL | $FAIL_COUNT |"
    RESULTS="$RESULTS\n\n### Test Failures\n\`\`\`\n$(echo "$TEST_OUTPUT" | tail -30)\n\`\`\`"
    FAILED=1
  }
fi
echo "$RESULTS" | grep -q "Test" || {
  TEST_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+ tests?' | head -1 || echo "?")
  RESULTS="$RESULTS\n| Test | $PASS | $TEST_COUNT |"
}

# Output
if [ $FAILED -eq 0 ]; then
  printf "## Verification: ✅ ALL PASS\n\n| Step | Status | Details |\n|------|--------|---------|"
  printf "$RESULTS\n"
else
  printf "## Verification: ❌ FAIL\n\n| Step | Status | Details |\n|------|--------|---------|"
  printf "$RESULTS\n"
  exit 1
fi
