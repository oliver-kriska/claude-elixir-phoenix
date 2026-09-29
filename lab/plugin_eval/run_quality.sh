#!/usr/bin/env bash
# Run the output-quality suite (lab/plugin_eval/quality/) with and without the
# plugin, then print per-case WITH / W/OUT / Δ and per-grader pass rates.
#
#   bash lab/plugin_eval/run_quality.sh                      # every case, 1 run per arm
#   CASE=review-orders RUNS=3 bash lab/plugin_eval/run_quality.sh   # CASE is a name glob
#   MAX_COST=10 J=2 bash lab/plugin_eval/run_quality.sh
#
# Cases invoke a skill explicitly (`/phx:review ...`), so they measure what the
# skill produces, not whether it routes. The no-plugin arm gets the same text;
# without the plugin, Claude treats the unknown slash command as a plain request.
# Every run is a real session on your credentials (~$0.5–2 per run at list price).
set -uo pipefail

cd "$(dirname "$0")/../.." || exit 1

J="${J:-4}"
RUNS="${RUNS:-1}"
MODEL="${MODEL:-claude-sonnet-5-5}"
JUDGE="${JUDGE:-sonnet}"
MAX_COST="${MAX_COST:-15}"
EVAL_DIR=lab/plugin_eval/quality

# Write/Edit for the implementation cases; git for review's diff. mix is not
# granted: the fixture has no deps and the sandbox has no network, so every
# compile would fail — prompts say so and both arms skip it.
eval_args=(. --eval-dir "$EVAL_DIR"
  --ablation with-without --scaffold --trust-plugin --no-publish --keep-temp
  --model "$MODEL" --judge-model "$JUDGE" --runs "$RUNS" -j "$J" --threshold 0
  --max-cost-usd "$MAX_COST")
[ -n "${CASE:-}" ] && eval_args+=(--case "$CASE")
# --allow-tools takes a list, so it goes last.
eval_args+=(--allow-tools Write Edit "Bash(git *)")

started=$(date +%s)
claude plugin eval "${eval_args[@]}"
eval_status=$?

results=""
for dir in "$EVAL_DIR"/results/*/; do
  [ -f "$dir/aggregate-result.json" ] || continue
  [ "$(stat -f %m "$dir" 2>/dev/null || stat -c %Y "$dir")" -ge "$started" ] && results="$dir"
done
if [ -z "$results" ]; then
  echo "no results directory written (claude plugin eval exit $eval_status)" >&2
  exit "$(( eval_status == 0 ? 1 : eval_status ))"
fi

python3 -m lab.plugin_eval.quality "$results" --archive --cleanup --json "$results/summary.json"
summary_status=$?

# claude plugin eval exit 2 = partial (cost ceiling / auth); surface it first.
[ "$eval_status" -ne 0 ] && exit "$eval_status"
exit "$summary_status"
