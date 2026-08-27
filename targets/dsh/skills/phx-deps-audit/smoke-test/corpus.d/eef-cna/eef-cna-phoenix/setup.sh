#!/usr/bin/env bash
# eef-cna-phoenix — CVE-2026-32689 (long-poll NDJSON DoS).
# Disclosed 2026-05-05. Patched in phoenix 1.8.7.
set -u
mkdir -p "${FIXTURE_DIR}"

cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-phoenix-32689",
        "cve": "CVE-2026-32689",
        "title": "Phoenix long-poll DoS via NDJSON",
        "description": "Long-poll transport accepts unbounded NDJSON; attacker can OOM the node.",
        "severity": "high",
        "patched_versions": ">= 1.8.7",
        "disclosure_date": "2026-05-05"
      },
      "dependency": {"package": "phoenix", "version": "1.8.5"}
    }
  ]
}
EOF

cat > "${FIXTURE_DIR}/cves_new.json" <<'EOF'
{"pass": true, "vulnerabilities": []}
EOF
