#!/usr/bin/env bash
# eef-cna-postgrex — CVE-2026-32687 (SQL injection in Notifications.listen/3).
# Disclosed 2026-05-12 — the day of the virgil dogfood. Patched in 0.22.1.
set -u
mkdir -p "${FIXTURE_DIR}"

cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-postgrex-32687",
        "cve": "CVE-2026-32687",
        "title": "Postgrex.Notifications.listen/3 SQL injection",
        "description": "Channel name was interpolated without quoting in LISTEN/UNLISTEN.",
        "severity": "critical",
        "patched_versions": ">= 0.22.1",
        "disclosure_date": "2026-05-12"
      },
      "dependency": {"package": "postgrex", "version": "0.22.0"}
    }
  ]
}
EOF

cat > "${FIXTURE_DIR}/cves_new.json" <<'EOF'
{"pass": true, "vulnerabilities": []}
EOF
