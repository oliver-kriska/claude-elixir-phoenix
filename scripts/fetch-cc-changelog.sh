#!/usr/bin/env bash
# Fetch Claude Code changelog and extract entries newer than last checked version.
#
# Usage:
#   ./scripts/fetch-cc-changelog.sh              # Show new entries since last check
#   ./scripts/fetch-cc-changelog.sh --force      # Re-download even if cached
#   ./scripts/fetch-cc-changelog.sh --all        # Show all entries (ignore last checked)
#   ./scripts/fetch-cc-changelog.sh --set 2.1.85 # Set last checked version manually
#   ./scripts/fetch-cc-changelog.sh --versions   # List all versions in changelog
#
# State: .claude/cc-changelog/last-checked-version.txt
# Cache: .claude/cc-changelog/changelog-cache.md
# Output: new changelog entries to stdout (for skill consumption)

set -euo pipefail

CHANGELOG_URL="https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
STATE_DIR=".claude/cc-changelog"
STATE_FILE="${STATE_DIR}/last-checked-version.txt"
CACHE_FILE="${STATE_DIR}/changelog-cache.md"
MAX_AGE_HOURS=1
FORCE=false
SHOW_ALL=false
SET_VERSION=""
LIST_VERSIONS=false

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    --all) SHOW_ALL=true ;;
    --versions) LIST_VERSIONS=true ;;
    --set)
      # Next arg is the version — handled below
      ;;
    --set=*) SET_VERSION="${arg#--set=}" ;;
    --help|-h)
      echo "Usage: $0 [--force] [--all] [--set VERSION] [--versions]"
      echo ""
      echo "  --force       Re-download changelog even if cached"
      echo "  --all         Show all entries (ignore last checked version)"
      echo "  --set VER     Set last checked version (e.g., --set=2.1.85)"
      echo "  --versions    List all version numbers in changelog"
      exit 0
      ;;
    *)
      # Handle --set followed by version as separate arg
      if [[ "${prev_arg:-}" == "--set" ]]; then
        SET_VERSION="$arg"
      fi
      ;;
  esac
  prev_arg="$arg"
done

mkdir -p "$STATE_DIR"

# Handle --set: update state and exit
if [[ -n "$SET_VERSION" ]]; then
  echo "$SET_VERSION" > "$STATE_FILE"
  echo "Last checked version set to: $SET_VERSION"
  exit 0
fi

# Get file modification time (portable: Linux + macOS)
file_mtime() {
  if stat -c %Y "$1" >/dev/null 2>&1; then
    stat -c %Y "$1"
  else
    stat -f %m "$1"
  fi
}

# Check if cache is still fresh
is_fresh() {
  [ "$FORCE" = true ] && return 1
  [ ! -f "$CACHE_FILE" ] && return 1
  local file_age=$(( $(date +%s) - $(file_mtime "$CACHE_FILE") ))
  [ "$file_age" -lt $(( MAX_AGE_HOURS * 3600 )) ]
}

# Fetch changelog
if is_fresh; then
  echo "=== CC Changelog (cached, < ${MAX_AGE_HOURS}h old) ===" >&2
else
  echo "=== Fetching CC Changelog ===" >&2
  for attempt in 1 2 3; do
    if curl -sfL "$CHANGELOG_URL" -o "$CACHE_FILE" 2>/dev/null; then
      size=$(wc -c < "$CACHE_FILE" | tr -d ' ')
      echo "  Downloaded: ${size} bytes" >&2
      break
    fi
    if [ "$attempt" -eq 3 ]; then
      echo "  FAILED: Could not fetch changelog after 3 attempts" >&2
      exit 1
    fi
    sleep $(( attempt * 2 ))
  done
fi

# Extract all version numbers
versions=$(grep -E '^## [0-9]+\.[0-9]+\.[0-9]+' "$CACHE_FILE" | sed 's/^## //' | tr -d ' ')

if [ -z "$versions" ]; then
  echo "ERROR: No version headers found in changelog" >&2
  exit 1
fi

latest_version=$(echo "$versions" | head -1)

# Handle --versions
if [ "$LIST_VERSIONS" = true ]; then
  echo "Versions in changelog (newest first):"
  echo "$versions" | head -30
  total=$(echo "$versions" | wc -l | tr -d ' ')
  echo "... ($total total versions)"
  exit 0
fi

# Read last checked version
if [ -f "$STATE_FILE" ]; then
  last_checked=$(cat "$STATE_FILE" | tr -d '[:space:]')
else
  last_checked="0.0.0"
  echo "  No previous check found — will show recent entries" >&2
fi

echo "" >&2
echo "  Latest CC version:  $latest_version" >&2
echo "  Last checked:       $last_checked" >&2

# Semver comparison: returns 0 if v1 <= v2
# Handles CC's habit of skipping version numbers
version_lte() {
  local v1="$1" v2="$2"
  local v1_major v1_minor v1_patch v2_major v2_minor v2_patch
  IFS='.' read -r v1_major v1_minor v1_patch <<< "$v1"
  IFS='.' read -r v2_major v2_minor v2_patch <<< "$v2"
  if [ "$v1_major" -lt "$v2_major" ] 2>/dev/null; then return 0; fi
  if [ "$v1_major" -gt "$v2_major" ] 2>/dev/null; then return 1; fi
  if [ "$v1_minor" -lt "$v2_minor" ] 2>/dev/null; then return 0; fi
  if [ "$v1_minor" -gt "$v2_minor" ] 2>/dev/null; then return 1; fi
  if [ "$v1_patch" -le "$v2_patch" ] 2>/dev/null; then return 0; fi
  return 1
}

# Check if up to date
if [ "$SHOW_ALL" = false ] && version_lte "$latest_version" "$last_checked"; then
  echo "" >&2
  echo "  UP TO DATE — no new versions since $last_checked" >&2
  echo "---"
  echo "STATUS: UP_TO_DATE"
  echo "LATEST: $latest_version"
  echo "CHECKED: $last_checked"
  exit 0
fi

# Count new versions (versions strictly newer than last_checked)
if [ "$SHOW_ALL" = true ]; then
  new_count=$(echo "$versions" | wc -l | tr -d ' ')
  echo "  Showing all $new_count versions" >&2
else
  new_count=0
  while read -r v; do
    if version_lte "$v" "$last_checked"; then
      break
    fi
    new_count=$(( new_count + 1 ))
  done <<< "$versions"
  echo "  New versions: $new_count" >&2
fi

echo "" >&2

# Extract new entries (from top of file until we hit a version <= last_checked)
echo "---"
echo "STATUS: NEW_VERSIONS"
echo "LATEST: $latest_version"
echo "CHECKED: $last_checked"
echo "NEW_COUNT: $new_count"
echo "---"
echo ""

if [ "$SHOW_ALL" = true ]; then
  cat "$CACHE_FILE"
else
  # Print everything from start until we hit a version <= last_checked
  # Uses awk with split() for semver comparison
  awk -v last="$last_checked" '
    BEGIN {
      split(last, lv, ".")
      last_maj = lv[1]+0; last_min = lv[2]+0; last_pat = lv[3]+0
    }
    /^## [0-9]+\.[0-9]+\.[0-9]+/ {
      ver = $2
      gsub(/[[:space:]]/, "", ver)
      split(ver, cv, ".")
      cur_maj = cv[1]+0; cur_min = cv[2]+0; cur_pat = cv[3]+0
      if (cur_maj < last_maj) exit
      if (cur_maj == last_maj && cur_min < last_min) exit
      if (cur_maj == last_maj && cur_min == last_min && cur_pat <= last_pat) exit
    }
    { print }
  ' "$CACHE_FILE"
fi
