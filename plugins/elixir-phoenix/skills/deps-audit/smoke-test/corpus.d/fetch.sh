#!/usr/bin/env bash
# corpus.d/fetch.sh — fetch real Hex tarballs into the local cache for
# calibration runs. NOT executed by default `runner.sh` (those fixtures
# are deliberately offline). Invoked manually or by the LLM-triage and
# benign-FP-corpus targets.
#
# Usage:
#   bash smoke-test/corpus.d/fetch.sh phoenix 1.7.21
#   bash smoke-test/corpus.d/fetch.sh --batch corpus.d/batch.txt
#   bash smoke-test/corpus.d/fetch.sh --prune  # drop tarballs >30 days old
#
# Cache layout:
#   ${AUDIT_TMPDIR}/corpus/<pkg>/<version>/
#     ├── <pkg>-<version>.tar          # raw Hex tarball
#     └── contents/                    # extracted source
#
# Soft dependency: requires a Mix project context for `mix hex.package fetch`.
# If invoked outside a Mix project, falls back to direct repo.hex.pm download.

set -u

CACHE_ROOT="${HEX_AUDIT_CACHE:-${HOME}/.cache/phx-deps-audit/corpus}"
mkdir -p "${CACHE_ROOT}"

fail() { echo "fetch: $*" >&2; exit 1; }
info() { echo "fetch: $*" >&2; }

fetch_one() {
  local pkg="$1" ver="$2"
  local dest="${CACHE_ROOT}/${pkg}/${ver}"
  if [ -d "${dest}/contents" ]; then
    info "cached: ${pkg} ${ver}"
    return 0
  fi
  mkdir -p "${dest}/contents"

  if command -v mix >/dev/null 2>&1 && [ -f mix.exs ]; then
    # In a Mix project — use the canonical tool.
    mix hex.package fetch "${pkg}" "${ver}" --output "${dest}/${pkg}-${ver}.tar" \
      --unpack >/dev/null 2>&1 || fail "mix hex.package fetch failed for ${pkg} ${ver}"
    # mix --unpack writes to a folder named ${pkg}-${ver}/; move into contents/
    if [ -d "${dest}/${pkg}-${ver}" ]; then
      mv "${dest}/${pkg}-${ver}"/* "${dest}/contents/" 2>/dev/null || true
      rmdir "${dest}/${pkg}-${ver}" 2>/dev/null || true
    fi
  else
    # Fallback: download tarball directly via curl. No checksum verification
    # at this level — production audits validate via hex_metadata.config.
    local url="https://repo.hex.pm/tarballs/${pkg}-${ver}.tar"
    info "no mix project; falling back to direct download ${url}"
    curl -fsSL "${url}" -o "${dest}/${pkg}-${ver}.tar" \
      || fail "curl failed for ${pkg} ${ver}"
    (cd "${dest}/contents" && tar -xf "../${pkg}-${ver}.tar") \
      || fail "tar extraction failed for ${pkg} ${ver}"
    # Hex inner archive is contents.tar.gz inside the outer tar
    if [ -f "${dest}/contents/contents.tar.gz" ]; then
      tar -xzf "${dest}/contents/contents.tar.gz" -C "${dest}/contents/" \
        || fail "inner contents.tar.gz extraction failed"
    fi
  fi
  info "fetched: ${pkg} ${ver}"
}

prune() {
  # Drop tarballs older than 30 days (cache TTL).
  find "${CACHE_ROOT}" -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true
  info "pruned entries older than 30 days"
}

main() {
  case "${1:-}" in
    --prune) prune ;;
    --batch)
      [ -f "$2" ] || fail "batch file not found: $2"
      while IFS=' ' read -r pkg ver; do
        [ -z "${pkg}" ] && continue
        [[ "${pkg}" =~ ^# ]] && continue
        fetch_one "${pkg}" "${ver}"
      done < "$2"
      ;;
    '')
      fail "usage: fetch.sh <pkg> <version> | --batch <file> | --prune"
      ;;
    *)
      [ -n "${2:-}" ] || fail "version required"
      fetch_one "$1" "$2"
      ;;
  esac
}

main "$@"
