#!/usr/bin/env bash
# eef-cna-cowlib — CVE-2026-43968 (CR injection in cookie headers).
# Disclosed 2026-05-11. Patched in cowlib 2.15.0.
set -u
mkdir -p "${FIXTURE_DIR}"

cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-cowlib-43968",
        "cve": "CVE-2026-43968",
        "title": "Cowlib cookie header CR injection",
        "description": "Cookie attribute parsing allowed embedded CR/LF.",
        "severity": "moderate",
        "patched_versions": ">= 2.15.0",
        "disclosure_date": "2026-05-11"
      },
      "dependency": {"package": "cowlib", "version": "2.13.0"}
    }
  ]
}
EOF

cat > "${FIXTURE_DIR}/cves_new.json" <<'EOF'
{"pass": true, "vulnerabilities": []}
EOF
