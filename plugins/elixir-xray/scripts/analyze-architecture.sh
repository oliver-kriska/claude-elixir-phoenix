#!/usr/bin/env bash
# Analyze Elixir project architecture using mix xref and file analysis.
# Deterministic analysis — no LLM, no external dependencies.
# Outputs JSON to stdout.
# NOTE: no set -e or pipefail — analysis commands (mix xref, grep, find) may
# return non-zero on no matches, and we handle all errors gracefully
set -u

REPO_PATH="${1:-.}"
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

json_escape() {
  # Escape a string for safe JSON embedding.
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

make_relative() {
  # Convert an absolute path to a path relative to REPO_PATH.
  # Pure bash — no python3 dependency.
  local abs="$1"
  printf '%s' "${abs#"$REPO_PATH/"}"
}

# ---------------------------------------------------------------------------
# Validate project
# ---------------------------------------------------------------------------

if [[ ! -d "$REPO_PATH/lib" ]] || [[ ! -f "$REPO_PATH/mix.exs" ]]; then
  echo '{"error": "Not an Elixir project (missing lib/ or mix.exs)"}' >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Detect app name from mix.exs
# ---------------------------------------------------------------------------

APP_NAME=""
# Try to get app name from `app:` in mix.exs project definition
# Use sed instead of grep -P for macOS compatibility (BSD grep lacks PCRE)
APP_NAME=$(sed -n 's/.*app:[[:space:]]*:\([a-z_][a-z0-9_]*\).*/\1/p' "$REPO_PATH/mix.exs" 2>/dev/null | head -1)
if [[ -z "$APP_NAME" ]]; then
  # Fallback: first non-web directory under lib/
  for d in "$REPO_PATH/lib"/*/; do
    dirname="$(basename "$d")"
    if [[ "$dirname" != *_web ]] && [[ "$dirname" != .* ]]; then
      APP_NAME="$dirname"
      break
    fi
  done
fi

if [[ -z "$APP_NAME" ]]; then
  APP_NAME="app"
fi

# ---------------------------------------------------------------------------
# Check if mix is available
# ---------------------------------------------------------------------------

MIX_AVAILABLE=false
if command -v mix &>/dev/null && [[ -f "$REPO_PATH/mix.exs" ]]; then
  MIX_AVAILABLE=true
fi

# ---------------------------------------------------------------------------
# 1. Context health
# ---------------------------------------------------------------------------

CONTEXTS_JSON="["
first_ctx=true
APP_DIR="$REPO_PATH/lib/$APP_NAME"

if [[ -d "$APP_DIR" ]]; then
  for ctx_dir in "$APP_DIR"/*/; do
    [[ -d "$ctx_dir" ]] || continue
    ctx_name="$(basename "$ctx_dir")"

    # Count .ex files
    mod_count=$(find "$ctx_dir" -name '*.ex' -type f 2>/dev/null | wc -l | tr -d ' ')
    [[ "$mod_count" -eq 0 ]] && continue

    # Count public functions (def but not defp)
    pub_fns=$(grep -rE '^\s*def\s+[a-z]' "$ctx_dir" --include='*.ex' 2>/dev/null | grep -vE '^\s*defp\s' | wc -l | tr -d ' ')

    rel_path="lib/$APP_NAME/$ctx_name/"

    if [[ "$first_ctx" = true ]]; then
      first_ctx=false
    else
      CONTEXTS_JSON+=","
    fi

    CONTEXTS_JSON+=$(printf '{"name":"%s","modules":%d,"public_functions":%d,"path":"%s"}' \
      "$(json_escape "$ctx_name")" "$mod_count" "$pub_fns" "$(json_escape "$rel_path")")
  done
fi
CONTEXTS_JSON+="]"

# ---------------------------------------------------------------------------
# 2. Boundary violations
# ---------------------------------------------------------------------------

REPO_IN_WEB="["
first_viol=true
WEB_DIR="$REPO_PATH/lib/${APP_NAME}_web"

if [[ -d "$WEB_DIR" ]]; then
  # Repo calls in web layer
  while IFS=: read -r file line match; do
    [[ -z "$file" ]] && continue
    rel_file="$(make_relative "$file")"
    escaped_match="$(json_escape "$match")"
    if [[ "$first_viol" = true ]]; then
      first_viol=false
    else
      REPO_IN_WEB+=","
    fi
    REPO_IN_WEB+=$(printf '{"file":"%s","line":%s,"match":"%s"}' \
      "$(json_escape "$rel_file")" "$line" "$escaped_match")
  done < <(grep -rn 'Repo\.' "$WEB_DIR" --include='*.ex' 2>/dev/null | head -50 || true)
fi
REPO_IN_WEB+="]"

ECTO_IN_WEB="["
first_ecto=true
if [[ -d "$WEB_DIR" ]]; then
  while IFS=: read -r file line match; do
    [[ -z "$file" ]] && continue
    rel_file="$(make_relative "$file")"
    escaped_match="$(json_escape "$match")"
    if [[ "$first_ecto" = true ]]; then
      first_ecto=false
    else
      ECTO_IN_WEB+=","
    fi
    ECTO_IN_WEB+=$(printf '{"file":"%s","line":%s,"match":"%s"}' \
      "$(json_escape "$rel_file")" "$line" "$escaped_match")
  done < <(grep -rnE 'Ecto\.(Query|Changeset|Multi)' "$WEB_DIR" --include='*.ex' 2>/dev/null | head -50 || true)
fi
ECTO_IN_WEB+="]"

# ---------------------------------------------------------------------------
# 3. Circular dependencies (via mix xref)
# ---------------------------------------------------------------------------

CYCLES_COUNT=0
CYCLES_DETAILS=""
if [[ "$MIX_AVAILABLE" = true ]]; then
  cd "$REPO_PATH"
  cycles_output=$(mix xref graph --format cycles 2>/dev/null || echo "")
  if [[ -n "$cycles_output" && "$cycles_output" != *"no cycles"* ]]; then
    CYCLES_COUNT=$(echo "$cycles_output" | grep -c '^Cycle' 2>/dev/null || echo "0")
    CYCLES_DETAILS="$(json_escape "$cycles_output")"
  fi
fi

# ---------------------------------------------------------------------------
# 4. Coupling stats (via mix xref)
# ---------------------------------------------------------------------------

COUPLING_STATS=""
if [[ "$MIX_AVAILABLE" = true ]]; then
  cd "$REPO_PATH"
  stats_output=$(mix xref graph --format stats 2>/dev/null || echo "")
  COUPLING_STATS="$(json_escape "$stats_output")"
fi

# ---------------------------------------------------------------------------
# 5. Generic names
# ---------------------------------------------------------------------------

GENERIC_JSON="["
first_gen=true
for pattern in utils helpers services common shared misc; do
  while IFS= read -r found_dir; do
    [[ -z "$found_dir" ]] && continue
    rel="$(make_relative "$found_dir")"
    if [[ "$first_gen" = true ]]; then
      first_gen=false
    else
      GENERIC_JSON+=","
    fi
    GENERIC_JSON+="\"$(json_escape "$rel/")\""
  done < <(find "$REPO_PATH/lib" -type d -name "$pattern" 2>/dev/null || true)
done

# Also check for modules named Utils, Helpers, etc.
for pattern in Utils Helpers Services Common Shared Misc; do
  while IFS= read -r found_file; do
    [[ -z "$found_file" ]] && continue
    rel="$(make_relative "$found_file")"
    if [[ "$first_gen" = true ]]; then
      first_gen=false
    else
      GENERIC_JSON+=","
    fi
    GENERIC_JSON+="\"$(json_escape "$rel")\""
  done < <(find "$REPO_PATH/lib" -type f -name "$(echo "$pattern" | tr '[:upper:]' '[:lower:]').ex" 2>/dev/null || true)
done
GENERIC_JSON+="]"

# ---------------------------------------------------------------------------
# 6. Dead code (via mix xref)
# ---------------------------------------------------------------------------

DEAD_CODE_JSON="["
first_dead=true
if [[ "$MIX_AVAILABLE" = true ]]; then
  cd "$REPO_PATH"
  unreachable_output=$(mix xref unreachable 2>/dev/null || echo "")
  while IFS= read -r dead_line; do
    [[ -z "$dead_line" ]] && continue
    if [[ "$first_dead" = true ]]; then
      first_dead=false
    else
      DEAD_CODE_JSON+=","
    fi
    DEAD_CODE_JSON+="\"$(json_escape "$dead_line")\""
  done <<< "$unreachable_output"
fi
DEAD_CODE_JSON+="]"

# ---------------------------------------------------------------------------
# 7. Ash detection
# ---------------------------------------------------------------------------

ASH_DETECTED=false
if grep -rqE 'use Ash\.(Resource|Domain)' "$REPO_PATH/lib" --include='*.ex' 2>/dev/null; then
  ASH_DETECTED=true
fi

# ---------------------------------------------------------------------------
# 8. Oban workers
# ---------------------------------------------------------------------------

OBAN_COUNT=0
OBAN_FILES_JSON="["
OBAN_LARGE_JSON="["
first_oban=true
first_oban_large=true

while IFS= read -r worker_file; do
  [[ -z "$worker_file" ]] && continue
  OBAN_COUNT=$((OBAN_COUNT + 1))
  rel="$(make_relative "$worker_file")"

  if [[ "$first_oban" = true ]]; then
    first_oban=false
  else
    OBAN_FILES_JSON+=","
  fi
  OBAN_FILES_JSON+="\"$(json_escape "$rel")\""

  # Check size
  line_count=$(wc -l < "$worker_file" | tr -d ' ')
  if [[ "$line_count" -gt 200 ]]; then
    if [[ "$first_oban_large" = true ]]; then
      first_oban_large=false
    else
      OBAN_LARGE_JSON+=","
    fi
    OBAN_LARGE_JSON+=$(printf '{"file":"%s","lines":%d}' "$(json_escape "$rel")" "$line_count")
  fi
done < <(grep -rlE 'use Oban\.Worker' "$REPO_PATH/lib" --include='*.ex' 2>/dev/null || true)

OBAN_FILES_JSON+="]"
OBAN_LARGE_JSON+="]"

# ---------------------------------------------------------------------------
# 9. Large modules (>300 lines)
# ---------------------------------------------------------------------------

LARGE_JSON="["
first_large=true
while IFS= read -r ex_file; do
  [[ -z "$ex_file" ]] && continue
  line_count=$(wc -l < "$ex_file" | tr -d ' ')
  if [[ "$line_count" -gt 300 ]]; then
    rel="$(make_relative "$ex_file")"
    if [[ "$first_large" = true ]]; then
      first_large=false
    else
      LARGE_JSON+=","
    fi
    LARGE_JSON+=$(printf '{"file":"%s","lines":%d}' "$(json_escape "$rel")" "$line_count")
  fi
done < <(find "$REPO_PATH/lib" -name '*.ex' -type f 2>/dev/null || true)
LARGE_JSON+="]"

# ---------------------------------------------------------------------------
# Output JSON
# ---------------------------------------------------------------------------

cat <<ENDJSON
{
  "app_name": "$(json_escape "$APP_NAME")",
  "contexts": $CONTEXTS_JSON,
  "boundary_violations": {
    "repo_in_web": $REPO_IN_WEB,
    "ecto_in_web": $ECTO_IN_WEB
  },
  "cycles": {
    "count": $CYCLES_COUNT,
    "details": "$CYCLES_DETAILS"
  },
  "coupling_stats": "$COUPLING_STATS",
  "generic_names": $GENERIC_JSON,
  "dead_code_modules": $DEAD_CODE_JSON,
  "ash_detected": $ASH_DETECTED,
  "oban_workers": {
    "count": $OBAN_COUNT,
    "files": $OBAN_FILES_JSON,
    "large_workers": $OBAN_LARGE_JSON
  },
  "large_modules": $LARGE_JSON,
  "mix_available": $MIX_AVAILABLE
}
ENDJSON
