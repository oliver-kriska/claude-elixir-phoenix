#!/usr/bin/env bash
# 20_cve_patched — OLD lock vulnerable to decimal CVE-2026-32686.
# NEW lock has the patched version (decimal 3.0.0+). Asserts diff_cves.py
# emits exactly one `patched` finding for the matching GHSA/CVE.
set -u

mkdir -p "${FIXTURE_DIR}"

# Synthesize mock mix.lock files. These are NOT consumed by mix_audit
# directly in this fixture (we mock its JSON output instead) — they're
# kept as fixture documentation of the upgrade we're modeling.
cat > "${FIXTURE_DIR}/mix.lock.old" <<'EOF'
%{
  "decimal": {:hex, :decimal, "2.3.0", "abc...", [:mix], [], "hexpm", "abc..."},
}
EOF

cat > "${FIXTURE_DIR}/mix.lock.new" <<'EOF'
%{
  "decimal": {:hex, :decimal, "3.0.0", "def...", [:mix], [], "hexpm", "def..."},
}
EOF

# Mock cves_old.json: vulnerable decimal 2.3.0 → CVE-2026-32686 hit.
cat > "${FIXTURE_DIR}/cves_old.json" <<'EOF'
{
  "pass": false,
  "vulnerabilities": [
    {
      "advisory": {
        "id": "GHSA-decimal-32686",
        "cve": "CVE-2026-32686",
        "title": "Decimal DoS via unbounded exponent",
        "description": "Parsing 1e1000000000 OOMs the BEAM",
        "severity": "high",
        "patched_versions": ">= 3.0.0",
        "disclosure_date": "2026-05-07"
      },
      "dependency": {"package": "decimal", "version": "2.3.0"}
    }
  ]
}
EOF

# Mock cves_new.json: clean (no vulnerabilities — patched in 3.0.0).
cat > "${FIXTURE_DIR}/cves_new.json" <<'EOF'
{"pass": true, "vulnerabilities": []}
EOF
