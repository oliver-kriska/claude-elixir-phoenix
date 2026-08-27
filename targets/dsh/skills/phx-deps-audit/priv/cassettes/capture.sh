#!/usr/bin/env bash
# Cassette capture helper: fetch hex.pm API responses for a package (+version)
# and update the SHA index in _meta.json. Idempotent — re-runs overwrite the
# cassette body but only update SHA when content changes.
#
# Usage:  bash capture.sh <pkg> [version]
#
# Writes to:
#   test-assets/hex-api-cassettes/<pkg>.packages.json
#   test-assets/hex-api-cassettes/<pkg>.releases.<version>.json   (if version given)
#   test-assets/hex-api-cassettes/_meta.json                       (SHA index)

set -u

pkg="${1:-}"
ver="${2:-}"

if [ -z "${pkg}" ]; then
  echo "usage: capture.sh <pkg> [version]" >&2
  exit 2
fi

# Resolve cassettes dir relative to this script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OUT_DIR="${SKILL_ROOT}/test-assets/hex-api-cassettes"
mkdir -p "${OUT_DIR}"

META="${OUT_DIR}/_meta.json"

# Bootstrap _meta.json if missing
if [ ! -f "${META}" ]; then
  echo '{"files": {}}' > "${META}"
fi

pkg_cassette="${pkg}.packages.json"
pkg_url="https://hex.pm/api/packages/${pkg}"

if ! curl -fsSL "${pkg_url}" | jq '.' > "${OUT_DIR}/${pkg_cassette}.tmp" 2>/dev/null; then
  echo "capture: failed to fetch ${pkg_url}" >&2
  rm -f "${OUT_DIR}/${pkg_cassette}.tmp"
  exit 1
fi
mv "${OUT_DIR}/${pkg_cassette}.tmp" "${OUT_DIR}/${pkg_cassette}"

if [ -n "${ver}" ]; then
  rel_cassette="${pkg}.releases.${ver}.json"
  rel_url="https://hex.pm/api/packages/${pkg}/releases/${ver}"
  if curl -fsSL "${rel_url}" | jq '.' > "${OUT_DIR}/${rel_cassette}.tmp" 2>/dev/null; then
    mv "${OUT_DIR}/${rel_cassette}.tmp" "${OUT_DIR}/${rel_cassette}"
  else
    echo "capture: failed to fetch ${rel_url} (continuing)" >&2
    rm -f "${OUT_DIR}/${rel_cassette}.tmp"
  fi
fi

# Update _meta.json with fresh SHAs
python3 - "${OUT_DIR}" "${META}" <<'PY'
import json
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

out_dir = Path(sys.argv[1])
meta_path = Path(sys.argv[2])
meta = json.loads(meta_path.read_text())
meta.setdefault("files", {})

now = datetime.now(timezone.utc).isoformat()
meta["captured_at"] = now
meta["capture_source"] = "https://hex.pm/api"

for cassette in out_dir.glob("*.json"):
    if cassette.name == "_meta.json":
        continue
    body = cassette.read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    name = cassette.name
    # Derive endpoint from filename: <pkg>.packages.json or <pkg>.releases.<ver>.json
    if name.endswith(".packages.json"):
        pkg = name[: -len(".packages.json")]
        endpoint = f"/api/packages/{pkg}"
    elif ".releases." in name:
        pkg, _, rest = name.partition(".releases.")
        ver = rest[: -len(".json")]
        endpoint = f"/api/packages/{pkg}/releases/{ver}"
    else:
        endpoint = name
    entry = meta["files"].setdefault(name, {})
    if entry.get("sha256") != sha:
        entry["sha256"] = sha
        entry["captured_at"] = now
    entry["endpoint"] = endpoint

meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
PY

echo "capture: ${pkg} ${ver:-(no version)} → ${OUT_DIR}"
