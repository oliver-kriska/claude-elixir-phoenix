#!/usr/bin/env bash
# 21_cve_introduced — regression: clean OLD lock, vulnerable NEW lock.
# Models the case where a "minor" update introduced a CVE (very rare in
# practice — usually a backdoored release or downgrade attack).
set -u

mkdir -p "${FIXTURE_DIR}"

cat > "${FIXTURE_DIR}/mix.lock.old" <<'EOF'
%{
  "examplepkg": {:hex, :examplepkg, "1.0.0", "abc...", [:mix], [], "hexpm", "abc..."},
}
EOF

cat > "${FIXTURE_DIR}/mix.lock.new" <<'EOF'
%{
  "examplepkg": {:hex, :examplepkg, "1.0.1", "def...", [:mix], [], "hexpm", "def..."},
}
EOF

# OLD: clean.
cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{"pass": true, "vulnerabilities": []}
EOF

# NEW: vulnerable.
cat > "${FIXTURE_DIR}/cves_new.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-examplepkg-9999",
        "cve": "CVE-2026-99999",
        "title": "ExamplePkg backdoor in 1.0.1",
        "description": "Compromised release introduces RCE",
        "severity": "critical",
        "patched_versions": "< 1.0.1 || > 1.0.1",
        "disclosure_date": "2026-05-10"
      },
      "dependency": {"package": "examplepkg", "version": "1.0.1"}
    }
  ]
}
EOF
