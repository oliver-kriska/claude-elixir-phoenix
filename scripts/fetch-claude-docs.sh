#!/usr/bin/env bash
# Fetch Claude Code documentation for plugin validation.
# Downloads only the pages needed, skips if cached and fresh.
#
# Usage:
#   ./scripts/fetch-claude-docs.sh              # Fetch core pages only
#   ./scripts/fetch-claude-docs.sh --all        # Fetch core + optional pages
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
FETCH_ALL=false
INDEX_ONLY=false

# Core pages — always fetched (mapped to plugin component types)
CORE_PAGES=(
  "sub-agents.md"          # Agent frontmatter schema
  "skills.md"              # Skill format and structure
  "hooks.md"               # Hook events and types
  "plugins-reference.md"   # plugin.json schema
  "plugin-marketplaces.md" # marketplace.json schema
)

# Optional pages — fetched with --all flag
OPTIONAL_PAGES=(
  "plugins.md"             # General plugin creation
  "hooks-guide.md"         # Deep hook patterns
  "settings.md"            # Permission modes
  "mcp.md"                 # MCP server config
)

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=true ;;
    --all) FETCH_ALL=true ;;
    --index-only) INDEX_ONLY=true ;;
    --help|-h)
      echo "Usage: $0 [--all] [--force] [--index-only]"
      echo ""
      echo "  --all         Fetch core + optional doc pages"
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

# Check if a cached file is still fresh
is_fresh() {
  local file="$1"
  if [ "$FORCE" = true ]; then
    return 1
  fi
  if [ ! -f "$file" ]; then
    return 1
  fi
  # Check if file is younger than MAX_AGE_HOURS (portable: Linux + macOS)
  local file_age file_mtime
  if stat -c %Y "$file" >/dev/null 2>&1; then
    file_mtime=$(stat -c %Y "$file")     # Linux
  else
    file_mtime=$(stat -f %m "$file")     # macOS
  fi
  file_age=$(( $(date +%s) - file_mtime ))
  local max_age_secs=$(( MAX_AGE_HOURS * 3600 ))
  [ "$file_age" -lt "$max_age_secs" ]
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
    if [ "$attempt" -lt 3 ]; then
      sleep $(( attempt * 2 ))
    fi
  done

  echo "  [FAILED] $page — could not download after 3 attempts"
  echo "FETCH_FAILED: $url ($(date -Iseconds))" > "$dest"
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

# Fetch core pages
echo ""
echo "Fetching core pages..."
failed=0
for page in "${CORE_PAGES[@]}"; do
  fetch_page "$page" || (( failed++ )) || true
done

# Fetch optional pages if requested
if [ "$FETCH_ALL" = true ]; then
  echo ""
  echo "Fetching optional pages..."
  for page in "${OPTIONAL_PAGES[@]}"; do
    fetch_page "$page" || (( failed++ )) || true
  done
fi

# Summary
echo ""
echo "=== Summary ==="
total_files=$(find "$CACHE_DIR" -name "*.md" -not -name "llms.txt" | wc -l)
total_size=$(du -sh "$CACHE_DIR" 2>/dev/null | cut -f1)
echo "  Cache: $CACHE_DIR"
echo "  Files: $total_files doc pages"
echo "  Size:  $total_size"
if [ "$failed" -gt 0 ]; then
  echo "  Failures: $failed (check FETCH_FAILED entries)"
fi

# Show freshness of each cached file
echo ""
echo "=== Cache Status ==="
for f in "$CACHE_DIR"/*.md; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  if grep -q "FETCH_FAILED" "$f" 2>/dev/null; then
    echo "  ❌ $name — download failed"
  else
    if stat -c %Y "$f" >/dev/null 2>&1; then
      age_secs=$(( $(date +%s) - $(stat -c %Y "$f") ))
    else
      age_secs=$(( $(date +%s) - $(stat -f %m "$f") ))
    fi
    if [ "$age_secs" -lt 3600 ]; then
      echo "  ✅ $name — $(( age_secs / 60 ))m ago"
    elif [ "$age_secs" -lt 86400 ]; then
      echo "  ✅ $name — $(( age_secs / 3600 ))h ago"
    else
      echo "  ⚠️  $name — $(( age_secs / 86400 ))d ago (stale)"
    fi
  fi
done
