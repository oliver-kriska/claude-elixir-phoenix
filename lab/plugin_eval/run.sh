#!/usr/bin/env bash
# Run the generated trigger suite through `claude plugin eval`, then analyze it.
#
#   SKILL="brief work" bash lab/plugin_eval/run.sh   # some skills (regenerates their cases)
#   TAG="trigger-pos perf" J=8 bash lab/plugin_eval/run.sh  # tags are OR-ed
#   MIN_RECALL=0.6 bash lab/plugin_eval/run.sh    # gate on per-skill recall
#   RUNS=3 TAG="val-perf" bash lab/plugin_eval/run.sh  # 3 runs per case (default 1)
#
# Runs from the repo root so case.yaml can load phx together with its ecto/lv
# dependencies. Every run is a real Sonnet session on your credentials: the full
# 502-case suite is roughly $45 at list price and ~50 minutes at J=8.
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1

TAG="${TAG:-trigger}"
J="${J:-8}"
MODEL="${MODEL:-claude-sonnet-5-5}"
MIN_RECALL="${MIN_RECALL:-}"
MAX_COST="${MAX_COST:-}"
RUNS="${RUNS:-}"

gen_args=()
read -r -a tags <<< "${TAG//,/ }"
if [ -n "${SKILL:-}" ]; then
  # SKILL="brief work" limits generation and the run to those skills.
  read -r -a skills <<< "${SKILL//,/ }"
  tags=("${skills[@]}")
  for s in "${skills[@]}"; do gen_args+=(--skill "$s"); done
fi
python3 -m lab.plugin_eval.generate "${gen_args[@]+"${gen_args[@]}"}" || exit $?

eval_args=(. --eval-dir lab/plugin_eval/cases --tag "${tags[@]}"
  --ablation none --scaffold --trust-plugin --no-publish --keep-temp
  --model "$MODEL" -j "$J" --threshold 0)
[ -n "$MAX_COST" ] && eval_args+=(--max-cost-usd "$MAX_COST")
[ -n "$RUNS" ] && eval_args+=(--runs "$RUNS")

started=$(date +%s)
claude plugin eval "${eval_args[@]}"
eval_status=$?

# The newest results dir created by this run.
results=""
for dir in lab/plugin_eval/cases/results/*/; do
  [ -f "$dir/aggregate-result.json" ] || continue
  [ "$(stat -f %m "$dir" 2>/dev/null || stat -c %Y "$dir")" -ge "$started" ] && results="$dir"
done
if [ -z "$results" ]; then
  echo "no results directory written (claude plugin eval exit $eval_status)" >&2
  exit "$(( eval_status == 0 ? 1 : eval_status ))"
fi

analyze_args=("$results" --archive --cleanup --json "$results/summary.json")
[ -n "$MIN_RECALL" ] && analyze_args+=(--min-recall "$MIN_RECALL")
python3 -m lab.plugin_eval.analyze "${analyze_args[@]}"
analyze_status=$?

# claude plugin eval exit 2 = partial (cost ceiling / auth); surface it first.
[ "$eval_status" -ne 0 ] && exit "$eval_status"
exit "$analyze_status"
