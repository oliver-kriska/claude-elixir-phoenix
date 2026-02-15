#!/usr/bin/env bash
# Fetch Claude Code documentation for plugin validation.
# Downloads all relevant pages, skips if cached and fresh.
#
# Usage:
#   ./scripts/fetch-claude-docs.sh              # Fetch all doc pages
#   ./scripts/fetch-claude-docs.sh --force      # Re-download even if cached
#   ./scripts/fetch-claude-docs.sh --index-only # Just fetch llms.txt index
#
# Output: .claude/docs-check/docs-cache/*.md
# These files are gitignored and used by /docs-check validation.

set -euo pipefail

DOCS_BASE_URL="https://code.claude.com/docs/en"
INDEX_URL="https://code.claude.com/docs/llms.txt"
CACHE_DIR=".claude/docs-check/docs-cache"
MAX_AGE_HOURS=24
FORCE=false
INDEX_ONLY=false

# All pages needed for plugin validation (~420KB total)
PAGES=(
  "sub-agents.md"          # Agent frontmatter schema
  "skills.md"              # Skill format and structure
  "hooks.md"               # Hook events and types
  "hooks-guide.md"         # Hook patterns and examples
  "plugins-reference.md"   # plugin.json schema
  "plugin-marketplaces.md" # marketplace.json schema
  "plugins.md"             # General plugin creation
  "settings.md"            # Permission modes
  "mcp.md"                 # MCP server config
)

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    --index-only) INDEX_ONLY=true ;;
    --help|-h)
      echo "Usage: $0 [--force] [--index-only]"
      echo ""
      echo "  --force       Re-download even if cached within ${MAX_AGE_HOURS}h"
      echo "  --index-only  Only fetch the llms.txt index file"
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

mkdir -p "$CACHE_DIR"

# Get file modification time (portable: Linux + macOS)
file_mtime() {
  if stat -c %Y "$1" >/dev/null 2>&1; then
    stat -c %Y "$1"     # Linux
  else
    stat -f %m "$1"     # macOS
  fi
}

# Check if a cached file is still fresh
is_fresh() {
  local file="$1"
  [ "$FORCE" = true ] && return 1
  [ ! -f "$file" ] && return 1
  local file_age=$(( $(date +%s) - $(file_mtime "$file") ))
  [ "$file_age" -lt $(( MAX_AGE_HOURS * 3600 )) ]
}

# Download a single page with retry
fetch_page() {
  local page="$1"
  local dest="${CACHE_DIR}/${page}"
  local url="${DOCS_BASE_URL}/${page}"

  if is_fresh "$dest"; then
    echo "  [cached] $page (< ${MAX_AGE_HOURS}h old)"
    return 0
  fi

  for attempt in 1 2 3; do
    if curl -sfL "$url" -o "$dest" 2>/dev/null; then
      local size
      size=$(wc -c < "$dest")
      echo "  [fetched] $page (${size} bytes)"
      return 0
    fi
    [ "$attempt" -lt 3 ] && sleep $(( attempt * 2 ))
  done

  echo "  [FAILED] $page — could not download after 3 attempts"
  rm -f "$dest"
  return 1
}

# Fetch the index
echo "=== Claude Code Documentation Fetcher ==="
echo ""

echo "Fetching index..."
if is_fresh "${CACHE_DIR}/llms.txt"; then
  echo "  [cached] llms.txt (< ${MAX_AGE_HOURS}h old)"
else
  if curl -sfL "$INDEX_URL" -o "${CACHE_DIR}/llms.txt" 2>/dev/null; then
    page_count=$(grep -c '\.md' "${CACHE_DIR}/llms.txt" 2>/dev/null || echo "?")
    echo "  [fetched] llms.txt (${page_count} pages indexed)"
  else
    echo "  [FAILED] Could not fetch llms.txt"
  fi
fi

if [ "$INDEX_ONLY" = true ]; then
  echo ""
  echo "Done (index only)."
  exit 0
fi

# Fetch all pages
echo ""
echo "Fetching doc pages..."
failed=0
for page in "${PAGES[@]}"; do
  fetch_page "$page" || (( failed++ )) || true
done

# Summary
echo ""
echo "=== Summary ==="
total_files=$(find "$CACHE_DIR" -name "*.md" -not -name "llms.txt" | wc -l)
total_size=$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1)
echo "  Cache: $CACHE_DIR"
echo "  Files: $total_files doc pages"
echo "  Size:  $total_size"
if [ "$failed" -gt 0 ]; then
  echo "  Failures: $failed (missing from cache — re-run or use --force)"
fi

# Show freshness of each cached file
echo ""
echo "=== Cache Status ==="
for page in "${PAGES[@]}"; do
  dest="${CACHE_DIR}/${page}"
  if [ ! -f "$dest" ]; then
    echo "  ❌ $page — missing (download failed)"
  else
    age_secs=$(( $(date +%s) - $(file_mtime "$dest") ))
    if [ "$age_secs" -lt 3600 ]; then
      echo "  ✅ $page — $(( age_secs / 60 ))m ago"
    elif [ "$age_secs" -lt 86400 ]; then
      echo "  ✅ $page — $(( age_secs / 3600 ))h ago"
    else
      echo "  ⚠️  $page — $(( age_secs / 86400 ))d ago (stale)"
    fi
  fi
done
