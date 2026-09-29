#!/usr/bin/env bash
# 22_cve_still_exposed — both locks vulnerable to the same CVE.
# Models the "you bumped, but not far enough" case: e.g., decimal 2.3.0 →
# 2.3.1 when the fix is only in 3.0.0+.
set -u

mkdir -p "${FIXTURE_DIR}"

cat > "${FIXTURE_DIR}/mix.lock.old" <<'EOF'
%{
  "decimal": {:hex, :decimal, "2.3.0", "abc...", [:mix], [], "hexpm", "abc..."},
}
EOF

cat > "${FIXTURE_DIR}/mix.lock.new" <<'EOF'
%{
  "decimal": {:hex, :decimal, "2.3.1", "def...", [:mix], [], "hexpm", "def..."},
}
EOF

# Both locks have the SAME CVE present (same GHSA id, different versions).
# diff_cves keys on (ghsa_id, package), so this is "still exposed".
cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-decimal-32686",
        "cve": "CVE-2026-32686",
        "title": "Decimal DoS via unbounded exponent",
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
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-decimal-32686",
        "cve": "CVE-2026-32686",
        "title": "Decimal DoS via unbounded exponent",
        "severity": "high",
        "patched_versions": ">= 3.0.0",
        "disclosure_date": "2026-05-07"
      },
      "dependency": {"package": "decimal", "version": "2.3.1"}
    }
  ]
}
EOF
