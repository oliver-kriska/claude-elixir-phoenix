#!/usr/bin/env bash
# Compilation verification — runs mix compile and pipes errors to error-matcher.
# Format-only verification still runs via format-elixir.sh.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only verify Elixir files
echo "$FILE_PATH" | grep -qE '\.(ex|exs)$' || exit 0

# Skip if not in a Mix project
[ -f "mix.exs" ] || exit 0

# Run compilation check
OUTPUT=$(mix compile --warnings-as-errors 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
  echo "$OUTPUT"
  # Error-matcher handles remediation output separately
  exit 1
fi

exit 0
