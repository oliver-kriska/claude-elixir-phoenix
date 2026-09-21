#!/usr/bin/env bash
# /phx:deps-audit smoke runner — Phase 2 harness.
#
# Loads fixtures from fixtures.d/<name>/ (each with setup.sh + expected.txt)
# and asserts each rule's detector output against the expected counts.
#
# Fixture conventions:
#   - setup.sh receives $FIXTURE_DIR (absolute path) and creates files in it.
#     A single-target fixture writes lib/*.ex directly under $FIXTURE_DIR.
#     A diff fixture (e.g., rule 5) writes ${FIXTURE_DIR}/old/ and /new/.
#   - expected.txt: one assertion per line, "# comments" allowed.
#       Format: rule:N op:OP count:K
#       OP ∈ {>=, ==, <=, >, <}. Default count comparator is >=1.
#       Single-line shorthand: "rule:N" => "rule:N op:>= count:1".
#
# Usage:
#   bash smoke-test/runner.sh                     # run all fixtures
#   bash smoke-test/runner.sh fixtures.d/00_clean # run a single fixture dir
#   FIXTURES_DIR=corpus.d bash smoke-test/runner.sh  # alt fixture root

set -u

HARNESS_ROOT="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=lib/detectors.sh
. "${HARNESS_ROOT}/lib/detectors.sh"

FIXTURES_DIR="${FIXTURES_DIR:-${HARNESS_ROOT}/fixtures.d}"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

red()   { printf '\033[31m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }

fail_count=0
pass_count=0

count_for_rule() {
  # Dispatches to count_rule_N. Rule 5 is special — it takes old/new.
  local rule="$1" dir="$2"
  case "${rule}" in
    5)
      [ -d "${dir}/old" ] && [ -d "${dir}/new" ] \
        || { echo "0"; return; }
      count_rule_5 "${dir}/old" "${dir}/new"
      ;;
    *)
      "count_rule_${rule}" "${dir}"
      ;;
  esac
}

compare() {
  local actual="$1" op="$2" expected="$3"
  case "${op}" in
    '>=') [ "${actual}" -ge "${expected}" ] ;;
    '==') [ "${actual}" -eq "${expected}" ] ;;
    '<=') [ "${actual}" -le "${expected}" ] ;;
    '>')  [ "${actual}" -gt "${expected}" ] ;;
    '<')  [ "${actual}" -lt "${expected}" ] ;;
    *) return 1 ;;
  esac
}

run_fixture() {
  local fixture_path="$1"
  local fixture_name
  fixture_name="$(basename "${fixture_path}")"

  # Phase 5: CVE-diff fixtures (2X_cve_*) are exercised by
  # cve-diff-runner.sh — they use cve-diff: assertions, not rule:N
  # detector counts. Skip them here to avoid silent passes.
  case "${fixture_name}" in
    2[0-9]_cve_*) return ;;
  esac

  local setup="${fixture_path}/setup.sh"
  local expected="${fixture_path}/expected.txt"

  [ -f "${setup}" ]    || { echo "  $(red 'SKIP'): ${fixture_name} missing setup.sh"; return; }
  [ -f "${expected}" ] || { echo "  $(red 'SKIP'): ${fixture_name} missing expected.txt"; return; }

  local fixture_work="${WORK}/${fixture_name}"
  mkdir -p "${fixture_work}"
  # shellcheck disable=SC1090
  FIXTURE_DIR="${fixture_work}" bash "${setup}"

  local line rule op expected_count actual ok=1
  while IFS= read -r line; do
    case "${line}" in
      ''|'#'*) continue ;;
    esac
    rule=$(echo "${line}" | sed -nE 's/.*rule:([0-9]+).*/\1/p')
    op=$(echo "${line}" | sed -nE 's/.*op:([><=!]+).*/\1/p')
    expected_count=$(echo "${line}" | sed -nE 's/.*count:([0-9]+).*/\1/p')
    [ -z "${rule}" ] && continue
    [ -z "${op}" ] && op='>='
    [ -z "${expected_count}" ] && expected_count=1

    actual=$(count_for_rule "${rule}" "${fixture_work}")
    if compare "${actual}" "${op}" "${expected_count}"; then
      echo "  $(green 'ok'  ) ${fixture_name} rule:${rule} ${op} ${expected_count} (got ${actual})"
    else
      echo "  $(red   'fail') ${fixture_name} rule:${rule} ${op} ${expected_count} (got ${actual})"
      ok=0
    fi
  done < "${expected}"

  if [ "${ok}" -eq 1 ]; then
    pass_count=$((pass_count + 1))
  else
    fail_count=$((fail_count + 1))
  fi
}

main() {
  local fixtures=()
  if [ "$#" -gt 0 ]; then
    fixtures+=("$1")
  else
    while IFS= read -r d; do
      fixtures+=("${d}")
    done < <(find "${FIXTURES_DIR}" -mindepth 1 -maxdepth 1 -type d | sort)
  fi

  [ "${#fixtures[@]}" -eq 0 ] && { echo "no fixtures under ${FIXTURES_DIR}"; exit 1; }

  echo "Running ${#fixtures[@]} fixture(s) under ${FIXTURES_DIR}:"
  for f in "${fixtures[@]}"; do
    run_fixture "${f}"
  done

  echo
  echo "smoke: ${pass_count} pass, ${fail_count} fail"

  if [ "${SKIP_SARIF:-0}" != "1" ] && [ -x "${HARNESS_ROOT}/sarif-round-trip.sh" ]; then
    echo
    echo "SARIF round-trip:"
    if "${HARNESS_ROOT}/sarif-round-trip.sh"; then
      :
    else
      fail_count=$((fail_count + 1))
    fi
  fi

  if [ "${SKIP_GATE_TEST:-0}" != "1" ] && [ -x "${HARNESS_ROOT}/gate-test.sh" ]; then
    echo
    if "${HARNESS_ROOT}/gate-test.sh"; then
      :
    else
      fail_count=$((fail_count + 1))
    fi
  fi

  [ "${fail_count}" -eq 0 ]
}

main "$@"
