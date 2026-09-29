#!/usr/bin/env bash
# eef-cna-bandit — CVE-2026-39805 (HTTP request smuggling).
# One of 5 CVEs disclosed against bandit 1.10.3 on 2026-05-01.
# Patched in bandit 1.11.0.
set -u
mkdir -p "${FIXTURE_DIR}"

cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-bandit-39805",
        "cve": "CVE-2026-39805",
        "title": "Bandit HTTP/1.1 request smuggling",
        "description": "Inconsistent chunked-encoding parsing enables request smuggling.",
        "severity": "high",
        "patched_versions": ">= 1.11.0",
        "disclosure_date": "2026-05-01"
      },
      "dependency": {"package": "bandit", "version": "1.10.3"}
    },
    {
      "advisory": {
        "id": "GHSA-bandit-39804",
        "cve": "CVE-2026-39804",
        "title": "Bandit WebSocket frame parsing crash",
        "severity": "moderate",
        "patched_versions": ">= 1.11.0",
        "disclosure_date": "2026-05-01"
      },
      "dependency": {"package": "bandit", "version": "1.10.3"}
    }
  ]
}
EOF

cat > "${FIXTURE_DIR}/cves_new.json" <<'EOF'
{"pass": true, "vulnerabilities": []}
EOF
