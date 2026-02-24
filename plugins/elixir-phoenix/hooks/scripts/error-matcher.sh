#!/usr/bin/env bash
# Error Matcher: Parse compile/credo errors and provide remediation instructions.
# Reads from stdin (PostToolUse hook input), checks for recent compile errors,
# and outputs structured remediation hints.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Only process Elixir files
echo "$FILE_PATH" | grep -qE '\.(ex|exs)$' || exit 0

# Skip if not in a Mix project
[ -f "mix.exs" ] || exit 0

# Check for recent compile errors (from verify-elixir.sh)
COMPILE_OUTPUT=$(mix compile 2>&1)
COMPILE_EXIT=$?

if [ $COMPILE_EXIT -eq 0 ]; then
  # No compile errors — check credo for the changed file
  CREDO_OUTPUT=$(mix credo "$FILE_PATH" --strict 2>&1)
  CREDO_EXIT=$?

  if [ $CREDO_EXIT -eq 0 ]; then
    exit 0
  fi

  # Parse credo output for remediation
  echo "$CREDO_OUTPUT" | while IFS= read -r line; do
    # Match credo issue format: [Priority] path:line:col message
    if echo "$line" | grep -qE '^\s*┃'; then
      continue
    fi

    # CyclomaticComplexity
    if echo "$line" | grep -q "CyclomaticComplexity"; then
      echo ""
      echo "REMEDIATION: Complex function detected"
      echo "  1. Extract conditional branches into private functions"
      echo "  2. Use pattern matching in function heads instead of case/cond"
      echo "  3. Consider 'with' chains for multi-step operations"
    fi

    # Nesting
    if echo "$line" | grep -q "Nesting"; then
      echo ""
      echo "REMEDIATION: Deep nesting detected"
      echo "  1. Extract inner blocks to named private functions"
      echo "  2. Use 'with' to flatten nested case/if chains"
      echo "  3. Use early returns via multi-clause functions"
    fi

    # UnusedEnumOperation
    if echo "$line" | grep -q "UnusedEnumOperation"; then
      echo ""
      echo "REMEDIATION: Enum operation result discarded"
      echo "  1. Assign the result: result = Enum.map(...)"
      echo "  2. If side-effect intended, use Enum.each/2 instead"
    fi

    # IoInspect
    if echo "$line" | grep -q "IoInspect\|IO.inspect"; then
      echo ""
      echo "REMEDIATION: Debug IO.inspect left in code"
      echo "  1. Remove IO.inspect() call"
      echo "  2. If needed for development, use dbg() (also flagged but clearer intent)"
    fi

    # Dbg
    if echo "$line" | grep -q "Dbg\|dbg()"; then
      echo ""
      echo "REMEDIATION: Debug dbg() left in code"
      echo "  1. Remove dbg() macro call"
    fi

    # WithSingleClause
    if echo "$line" | grep -q "WithSingleClause"; then
      echo ""
      echo "REMEDIATION: Single-clause 'with' — use 'case' instead"
      echo "  Pattern: case MyApp.do_thing() do"
      echo "    {:ok, result} -> result"
      echo "    {:error, reason} -> handle_error(reason)"
      echo "  end"
    fi

    # FilterCount
    if echo "$line" | grep -q "FilterCount"; then
      echo ""
      echo "REMEDIATION: filter |> count — use Enum.count/2"
      echo "  Pattern: Enum.count(list, &predicate/1)"
    fi

    # UnlessWithElse
    if echo "$line" | grep -q "UnlessWithElse"; then
      echo ""
      echo "REMEDIATION: unless...else is confusing — use if instead"
      echo "  Pattern: if condition, do: else_branch, else: unless_branch"
    fi
  done

  exit 0
fi

# Parse compile errors for remediation
echo "$COMPILE_OUTPUT" | while IFS= read -r line; do
  # Undefined function
  if echo "$line" | grep -q "undefined function"; then
    FUNC=$(echo "$line" | grep -oP 'undefined function \K\S+')
    echo ""
    echo "REMEDIATION: Undefined function $FUNC"
    echo "  1. Check spelling and arity — is it $FUNC or a different arity?"
    echo "  2. Is the module imported? Add: import MyApp.ModuleName"
    echo "  3. Is the module aliased? Add: alias MyApp.ModuleName"
    echo "  4. Does the function exist? grep -rn 'def ${FUNC%%/*}' lib/"
  fi

  # Module not available
  if echo "$line" | grep -q "module .* is not available"; then
    MOD=$(echo "$line" | grep -oP 'module \K\S+')
    echo ""
    echo "REMEDIATION: Module $MOD not available"
    echo "  1. Check if module exists: grep -rn 'defmodule $MOD' lib/"
    echo "  2. Check for typos in module name"
    echo "  3. Ensure file is in the correct directory path"
    echo "  4. Run: mix deps.compile (if it's a dependency module)"
  fi

  # Unused variable
  if echo "$line" | grep -q "variable .* is unused"; then
    VAR=$(echo "$line" | grep -oP 'variable "\K[^"]+')
    echo ""
    echo "REMEDIATION: Unused variable '$VAR'"
    echo "  1. Prefix with underscore: _$VAR"
    echo "  2. Or remove the variable if unneeded"
  fi

  # Pattern match warning
  if echo "$line" | grep -q "this clause cannot match"; then
    echo ""
    echo "REMEDIATION: Unreachable pattern match clause"
    echo "  1. Check clause ordering — more specific patterns first"
    echo "  2. Remove dead clause if truly unreachable"
    echo "  3. Check if a previous clause is too broad (catches everything)"
  fi

  # Deprecated function
  if echo "$line" | grep -q "is deprecated"; then
    echo ""
    echo "REMEDIATION: Deprecated function call"
    echo "  1. Check the deprecation message for the replacement function"
    echo "  2. Search hexdocs for the current API"
  fi

  # Missing required field in struct
  if echo "$line" | grep -q "the following keys must also be given"; then
    echo ""
    echo "REMEDIATION: Missing required struct fields"
    echo "  1. Add the missing fields listed in the error"
    echo "  2. Check @enforce_keys in the struct definition"
  fi
done

exit 0
