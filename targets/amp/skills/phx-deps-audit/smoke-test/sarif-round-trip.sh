#!/usr/bin/env bash
# SARIF round-trip smoke: build a synthetic NDJSON covering all 8 rules,
# generate SARIF via findings_to_sarif.py, validate structure, re-parse and
# assert per-finding fields.
#
# Bare-bones structural validation (no jsonschema dep required). When
# jsonschema is installed locally, layers in schema validation too.
#
# Usage:  bash smoke-test/sarif-round-trip.sh

set -u

HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "${HARNESS_ROOT}/.." && pwd)"
SCRIPTS="${SKILL_ROOT}/scripts"

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

FINDINGS="${WORK}/findings.jsonl"
OUT="${WORK}/out.sarif"

red()   { printf '\033[31m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }

fail=0
ok()   { echo "  $(green 'ok'  ) $1"; }
nope() { echo "  $(red   'fail') $1"; fail=$((fail+1)); }

# Build synthetic NDJSON: one finding per rule (1..8) covering every shape
cat >"${FINDINGS}" <<'JSON'
{"rule_id":1,"severity":"block","file":"lib/init.ex","line":3,"snippet":"foo‮bar","message":"Bidi RLO","package":"phoenix_extras","version":"0.2.0","differential":"new"}
{"rule_id":2,"severity":"block","file":"lib/init.ex","line":12,"snippet":"Code.eval_string(payload)","message":"Dynamic eval","package":"phoenix_extras","version":"0.2.0"}
{"rule_id":3,"severity":"block","file":"lib/init.ex","line":14,"snippet":"System.cmd(\"curl\", [...])","message":"Compile-time exec","package":"phoenix_extras","version":"0.2.0"}
{"rule_id":4,"severity":"block","file":"lib/util.ex","line":7,"snippet":":erlang.binary_to_term(blob)","message":"Unsafe deserialization","package":"phoenix_extras","version":"0.2.0"}
{"rule_id":5,"severity":"warn","file":"mix.exs","line":9,"snippet":"{:dep, git: \"...\"}","message":"New :git dep","package":"phoenix_extras","version":"0.2.0"}
{"rule_id":6,"severity":"block","message":"Maintainer change","package":"phoenix_extras","version":"0.2.0"}
{"rule_id":7,"severity":"warn","file":"lib/blob.ex","line":1,"snippet":"<base64 blob>","message":"Large base64","package":"phoenix_extras","version":"0.2.0"}
{"rule_id":8,"severity":"block","message":"Typosquat candidate","package":"phx_extras","version":"0.2.0"}
JSON

# Step 1: invoke converter
if ! python3 "${SCRIPTS}/findings_to_sarif.py" "${FINDINGS}" "${OUT}" --plugin-version "3.0.0" 2>/dev/null; then
  nope "findings_to_sarif.py failed to run"
  exit 1
fi
ok "findings_to_sarif.py wrote ${OUT}"

# Step 2: SARIF parses as JSON
if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${OUT}" 2>/dev/null; then
  nope "SARIF output is not valid JSON"
  exit 1
fi
ok "SARIF parses as JSON"

# Step 3: structural checks via jq
SARIF_VERSION=$(jq -r '.version' "${OUT}")
[ "${SARIF_VERSION}" = "2.1.0" ] && ok "version: 2.1.0" || nope "version != 2.1.0 (got ${SARIF_VERSION})"

DRIVER=$(jq -r '.runs[0].tool.driver.name' "${OUT}")
[ "${DRIVER}" = "phx-deps-audit" ] && ok "driver.name: phx-deps-audit" || nope "driver.name != phx-deps-audit"

RULES_COUNT=$(jq '.runs[0].tool.driver.rules | length' "${OUT}")
[ "${RULES_COUNT}" -eq 8 ] && ok "8 unique rules registered" || nope "expected 8 rules, got ${RULES_COUNT}"

RESULTS_COUNT=$(jq '.runs[0].results | length' "${OUT}")
[ "${RESULTS_COUNT}" -eq 8 ] && ok "8 results emitted" || nope "expected 8 results, got ${RESULTS_COUNT}"

# Step 4: per-result assertions
MISSING_RULEID=$(jq '[.runs[0].results[] | select(.ruleId == null)] | length' "${OUT}")
[ "${MISSING_RULEID}" -eq 0 ] && ok "every result has ruleId" || nope "${MISSING_RULEID} results missing ruleId"

VALID_LEVELS=$(jq -r '[.runs[0].results[].level] | unique | join(",")' "${OUT}")
case "${VALID_LEVELS}" in
  *error*) ok "level: error present" ;;
  *) nope "no error-level result" ;;
esac
case "${VALID_LEVELS}" in
  *"unknown"*|*"none"*) nope "invalid level value in ${VALID_LEVELS}" ;;
  *) ok "all levels are valid SARIF (error|warning|note)" ;;
esac

MISSING_LINE=$(jq '[.runs[0].results[]
                   | select(.locations[0].physicalLocation.region.startLine == null)
                   | select(.ruleId | endswith("rule-6") or endswith("rule-8") | not)
                  ] | length' "${OUT}")
[ "${MISSING_LINE}" -eq 0 ] && ok "every file-scoped result has startLine" \
  || nope "${MISSING_LINE} file-scoped results missing startLine"

MISSING_RULE_REF=$(jq -r '
  [.runs[0].results[].ruleId] as $used
  | [.runs[0].tool.driver.rules[].id] as $defined
  | $used - $defined | length' "${OUT}")
[ "${MISSING_RULE_REF}" -eq 0 ] && ok "every result.ruleId references a registered rule" \
  || nope "${MISSING_RULE_REF} results reference undefined rule"

# Step 5: ruleId stability (prefix MUST be phx-deps-audit/rule-)
WRONG_PREFIX=$(jq '[.runs[0].results[]
                    | select(.ruleId | startswith("phx-deps-audit/rule-") | not)
                  ] | length' "${OUT}")
[ "${WRONG_PREFIX}" -eq 0 ] && ok "all ruleIds use phx-deps-audit/rule-<N> prefix" \
  || nope "${WRONG_PREFIX} ruleIds use wrong prefix"

# Step 6: optional schema validation (only if jsonschema installed)
if python3 -c 'import jsonschema' 2>/dev/null; then
  if python3 -m jsonschema -i "${OUT}" \
       "https://json.schemastore.org/sarif-2.1.0.json" 2>/dev/null; then
    ok "SARIF 2.1.0 schema validation passed"
  else
    nope "SARIF 2.1.0 schema validation failed"
  fi
else
  echo "  $(green 'skip') jsonschema not installed (pip install jsonschema)"
fi

echo
if [ "${fail}" -eq 0 ]; then
  echo "sarif round-trip: $(green 'PASS') (8 results, all assertions)"
  exit 0
else
  echo "sarif round-trip: $(red 'FAIL') (${fail} assertion(s) failed)"
  exit 1
fi
