# VCR cassettes — Hex API fixtures for Rules 6 + 8

Rules 6 (maintainer change) and 8 (typosquat) hit the Hex API. To keep
smoke fast and offline, we ship JSON cassettes that mock the two
endpoints those rules consume.

## Iron Laws

1. **Cassettes are SHA-pinned.** Each cassette has a `_meta.sha`
   recording the sha256 of the response body at capture time. Rules
   that depend on a cassette validate the SHA before consuming it —
   silent corruption is worse than no cassette.
2. **NEVER auto-refresh.** Cassettes are committed artifacts. A
   maintainer's owner-change in real life MUST update a cassette
   in a real PR with an explicit reviewer — not via a CI auto-bump.
3. **Cassette mode opts in via env var.** `HEX_API_BASE` defaults
   to `https://hex.pm/api`; tests set
   `HEX_API_BASE=file://test-assets/hex-api-cassettes/`. Production
   audits never touch the cassettes.
4. **Empty cassette ≠ no maintainer.** When a cassette is absent,
   skip the rule with a logged warning, never silently pass.

## Endpoints covered

| Endpoint | Cassette filename | Used by |
|----------|-------------------|---------|
| `GET /api/packages/:name` | `<pkg>.packages.json` | Rule 6, Rule 8 |
| `GET /api/packages/:name/releases/:version` | `<pkg>.releases.<v>.json` | Rule 6 |

## Cassette layout

```text
plugins/elixir-phoenix/skills/deps-audit/test-assets/hex-api-cassettes/
├── phoenix.packages.json
├── phoenix.releases.1.7.20.json
├── phoenix.releases.1.7.21.json
├── jason.packages.json
├── jason.releases.1.4.4.json
├── phoeniix.packages.json          # synthetic typosquat for Rule 8
└── _meta.json                       # SHA index, capture timestamps
```

## `_meta.json` shape

```json
{
  "captured_at": "2026-05-12T18:00:00Z",
  "capture_source": "https://hex.pm/api",
  "files": {
    "phoenix.packages.json": {
      "sha256": "abc123...",
      "endpoint": "/api/packages/phoenix",
      "captured_at": "2026-05-12T18:00:00Z"
    }
  }
}
```

## Response shape — `<pkg>.packages.json`

Mirrors `hex.pm` API verbatim (only fields we consume):

```json
{
  "name": "phoenix",
  "downloads": {
    "all": 192345678,
    "recent": 2345678
  },
  "owners": [
    {"username": "chrismccord", "email": "chris@example.com"},
    {"username": "team-phoenix", "email": "team@example.com"}
  ],
  "inserted_at": "2014-04-21T22:33:00Z",
  "updated_at": "2026-04-15T10:00:00Z",
  "latest_stable_version": "1.7.21"
}
```

## Response shape — `<pkg>.releases.<v>.json`

```json
{
  "version": "1.7.21",
  "inserted_at": "2026-04-15T10:00:00Z",
  "publisher": {
    "username": "chrismccord",
    "email": "chris@example.com"
  },
  "checksum": "0123456789abcdef...",
  "retired": null
}
```

## Capturing a cassette

```bash
# Helper script — capture.sh
pkg=$1
ver=$2
out_dir=plugins/elixir-phoenix/skills/deps-audit/test-assets/hex-api-cassettes

curl -fsSL "https://hex.pm/api/packages/${pkg}" \
  | jq '.' > "${out_dir}/${pkg}.packages.json"

if [ -n "${ver}" ]; then
  curl -fsSL "https://hex.pm/api/packages/${pkg}/releases/${ver}" \
    | jq '.' > "${out_dir}/${pkg}.releases.${ver}.json"
fi

# Update _meta.json with sha + timestamp.
python3 -c "
import json, hashlib, sys
from datetime import datetime, timezone
meta_path = '${out_dir}/_meta.json'
meta = json.load(open(meta_path)) if open(meta_path, 'r').readable() else {'files': {}}
for fname in ['${pkg}.packages.json', '${pkg}.releases.${ver}.json']:
    path = '${out_dir}/' + fname
    try:
        body = open(path, 'rb').read()
        meta['files'][fname] = {
            'sha256': hashlib.sha256(body).hexdigest(),
            'captured_at': datetime.now(timezone.utc).isoformat()
        }
    except FileNotFoundError:
        pass
meta['captured_at'] = datetime.now(timezone.utc).isoformat()
json.dump(meta, open(meta_path, 'w'), indent=2)
"
```

## Consumer pattern (Rules 6 + 8)

```bash
hex_api_get() {
  local endpoint="$1"
  if [[ "${HEX_API_BASE:-https://hex.pm/api}" == file://* ]]; then
    local base="${HEX_API_BASE#file://}"
    local cassette
    cassette=$(printf '%s' "${endpoint}" \
      | sed -E 's|^/api/packages/([^/]+)$|\1.packages.json|;
                s|^/api/packages/([^/]+)/releases/(.+)$|\1.releases.\2.json|')
    cat "${base}/${cassette}" 2>/dev/null || {
      echo "cassette missing: ${cassette}" >&2
      return 1
    }
  else
    curl -fsSL "${HEX_API_BASE:-https://hex.pm/api}${endpoint}"
  fi
}
```

## Cassettes shipped with Phase 2

Phase 2 ships cassettes for:

- The 10 synthetic malicious fixtures' supporting packages
- A sample of 5 benign top-100 packages for smoke calibration
- The 5 real-world calibration packages (`hex_core`, `hex`, `rebar3`,
  `tls_certificate_check`, plus mix.lock crossing CVE-2026-23940)

Full top-100 cassettes are NOT shipped — they regenerate via the seed
job (see `seed.md`).

## Validation in smoke

The smoke `runner.sh` does not currently consume cassettes (Rules 6 + 8
aren't in the offline smoke surface). When Phase 2 wires them in,
`runner.sh` will gain:

```bash
export HEX_API_BASE="file://${HARNESS_ROOT}/../test-assets/hex-api-cassettes"
```

Per-fixture `expected.txt` then asserts on `rule:6` / `rule:8` counts.
