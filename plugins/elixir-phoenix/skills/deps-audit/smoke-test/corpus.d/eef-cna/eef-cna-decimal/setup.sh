#!/usr/bin/env bash
# eef-cna-decimal — CVE-2026-32686 (DoS via unbounded exponent).
# Real disclosure: 2026-05-07. Patched in decimal 3.0.0.
set -u
mkdir -p "${FIXTURE_DIR}"

cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-decimal-32686",
        "cve": "CVE-2026-32686",
        "title": "Decimal DoS: unbounded exponent OOMs BEAM",
        "description": "Decimal.new/1 with strings like \"1e1000000000\" exhausts memory.",
        "severity": "high",
        "patched_versions": ">= 3.0.0",
        "disclosure_date": "2026-05-07"
      },
      "dependency": {"package": "decimal", "version": "2.3.0"}
    }
  ]
}
EOF

cat > "${FIXTURE_DIR}/cves_new.json" <<'EOF'
{"pass": true, "vulnerabilities": []}
EOF
