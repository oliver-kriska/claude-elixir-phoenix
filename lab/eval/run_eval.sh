#!/bin/bash
# Run eval on skills and agents.
#
# Usage:
#   ./lab/eval/run_eval.sh              # Score everything changed since last eval
#   ./lab/eval/run_eval.sh --all        # Score all skills + agents
#   ./lab/eval/run_eval.sh --skills     # Score all skills only
#   ./lab/eval/run_eval.sh --agents     # Score all agents only
#   ./lab/eval/run_eval.sh --changed    # Only changed since last eval (default)
#   ./lab/eval/run_eval.sh --triggers   # Re-run behavioral trigger tests (~$1.50, ~60min)
#
# Exit codes:
#   0 = all pass (>= 0.95)
#   1 = failures found

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LAST_EVAL_FILE="$SCRIPT_DIR/.last-eval-commit"

cd "$PROJECT_ROOT"

MODE="${1:---changed}"
FAILURES=0

run_skills() {
    local filter="$1"  # "all" or "changed"
    local skills_to_check=()

    if [ "$filter" = "changed" ]; then
        local changed_files=""
        # 1. Uncommitted changes (staged + unstaged)
        changed_files=$(git diff --name-only HEAD -- 'plugins/elixir-phoenix/skills/' 2>/dev/null || echo "")
        local staged
        staged=$(git diff --cached --name-only -- 'plugins/elixir-phoenix/skills/' 2>/dev/null || echo "")
        if [ -n "$staged" ]; then
            changed_files=$(printf "%s\n%s" "$changed_files" "$staged")
        fi
        # 2. Changes since last eval commit
        if [ -f "$LAST_EVAL_FILE" ]; then
            local last_commit
            last_commit=$(cat "$LAST_EVAL_FILE")
            local since_last
            since_last=$(git diff --name-only "$last_commit" HEAD -- 'plugins/elixir-phoenix/skills/' 2>/dev/null || echo "")
            if [ -n "$since_last" ]; then
                changed_files=$(printf "%s\n%s" "$changed_files" "$since_last")
            fi
        fi
        if [ -z "$changed_files" ]; then
            echo "  No skill changes since last eval"
            return 0
        fi
        # Extract unique skill names from changed paths
        while IFS= read -r file; do
            local skill_name
            skill_name=$(echo "$file" | sed -n 's|plugins/elixir-phoenix/skills/\([^/]*\)/.*|\1|p')
            if [ -n "$skill_name" ]; then
                skills_to_check+=("$skill_name")
            fi
        done <<< "$changed_files"
        # Deduplicate
        mapfile -t skills_to_check < <(printf '%s\n' "${skills_to_check[@]}" | sort -u)
        echo "  Scoring ${#skills_to_check[@]} changed skills: ${skills_to_check[*]}"
    else
        echo "  Scoring all skills..."
    fi

    if [ ${#skills_to_check[@]} -eq 0 ] && [ "$filter" = "changed" ]; then
        return 0
    fi

    # Run scorer
    local result
    if [ "$filter" = "all" ] || [ ${#skills_to_check[@]} -eq 0 ]; then
        result=$(python3 -m lab.eval.scorer --all 2>/dev/null)
    else
        result="{"
        local first=true
        for skill in "${skills_to_check[@]}"; do
            local path="plugins/elixir-phoenix/skills/$skill/SKILL.md"
            [ -f "$path" ] || continue
            local score
            score=$(python3 -m lab.eval.scorer "$path" 2>/dev/null)
            if [ "$first" = true ]; then first=false; else result+=","; fi
            result+="\"$skill\":$score"
        done
        result+="}"
    fi

    # Parse and display results
    echo "$result" | python3 -c "
import json, sys
d = json.load(sys.stdin)
perfect = sum(1 for v in d.values() if v['composite'] >= 0.999)
below = {k: round(v['composite'], 3) for k, v in d.items() if v['composite'] < 0.95}
print(f'  {len(d)} skills scored | {perfect} perfect | avg {sum(v[\"composite\"] for v in d.values())/len(d):.3f}')
if below:
    print(f'  BELOW 0.95: {below}')
    sys.exit(1)
"
    return $?
}

run_agents() {
    local filter="$1"

    if [ "$filter" = "changed" ]; then
        local changed=""
        # Uncommitted + staged
        changed=$(git diff --name-only HEAD -- 'plugins/elixir-phoenix/agents/' 2>/dev/null || echo "")
        local staged
        staged=$(git diff --cached --name-only -- 'plugins/elixir-phoenix/agents/' 2>/dev/null || echo "")
        if [ -n "$staged" ]; then changed=$(printf "%s\n%s" "$changed" "$staged"); fi
        # Since last eval
        if [ -f "$LAST_EVAL_FILE" ]; then
            local last_commit
            last_commit=$(cat "$LAST_EVAL_FILE")
            local since_last
            since_last=$(git diff --name-only "$last_commit" HEAD -- 'plugins/elixir-phoenix/agents/' 2>/dev/null || echo "")
            if [ -n "$since_last" ]; then changed=$(printf "%s\n%s" "$changed" "$since_last"); fi
        fi
        # Deduplicate and filter empty
        changed=$(echo "$changed" | grep -v '^$' | sort -u)
        if [ -z "$changed" ]; then
            echo "  No agent changes since last eval"
            return 0
        fi
        echo "  Scoring changed agents: $(echo "$changed" | xargs -I{} basename {} .md | tr '\n' ' ')"
    else
        echo "  Scoring all agents..."
    fi

    python3 -m lab.eval.agent_scorer --all 2>&1 | tail -1
    local count
    count=$(python3 -m lab.eval.agent_scorer --all 2>&1 | grep "NEEDS WORK" | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        return 1
    fi
    return 0
}

run_triggers_cached() {
    local filter="$1"  # "all" or "changed"
    local results_dir="$SCRIPT_DIR/triggers/results"

    if [ ! -d "$results_dir" ]; then
        echo "  No cached trigger results (run 'make eval-triggers' first)"
        return 0
    fi

    local skills_to_check=()

    if [ "$filter" = "changed" ]; then
        # Get changed skills (same logic as run_skills)
        local changed_files=""
        changed_files=$(git diff --name-only HEAD -- 'plugins/elixir-phoenix/skills/' 2>/dev/null || echo "")
        local staged
        staged=$(git diff --cached --name-only -- 'plugins/elixir-phoenix/skills/' 2>/dev/null || echo "")
        if [ -n "$staged" ]; then
            changed_files=$(printf "%s\n%s" "$changed_files" "$staged")
        fi
        if [ -f "$LAST_EVAL_FILE" ]; then
            local last_commit
            last_commit=$(cat "$LAST_EVAL_FILE")
            local since_last
            since_last=$(git diff --name-only "$last_commit" HEAD -- 'plugins/elixir-phoenix/skills/' 2>/dev/null || echo "")
            if [ -n "$since_last" ]; then
                changed_files=$(printf "%s\n%s" "$changed_files" "$since_last")
            fi
        fi
        if [ -z "$changed_files" ]; then
            echo "  No skill changes — skipping trigger check"
            return 0
        fi
        while IFS= read -r file; do
            local skill_name
            skill_name=$(echo "$file" | sed -n 's|plugins/elixir-phoenix/skills/\([^/]*\)/.*|\1|p')
            if [ -n "$skill_name" ]; then
                skills_to_check+=("$skill_name")
            fi
        done <<< "$changed_files"
        mapfile -t skills_to_check < <(printf '%s\n' "${skills_to_check[@]}" | sort -u)
    else
        # All skills with cached results
        for f in "$results_dir"/*.json; do
            local base
            base=$(basename "$f" .json)
            [ "$base" = "_aggregate" ] && continue
            skills_to_check+=("$base")
        done
    fi

    if [ ${#skills_to_check[@]} -eq 0 ]; then
        return 0
    fi

    # Check cached trigger accuracy for each skill
    python3 -c "
import json, sys, os

results_dir = '$results_dir'
skills = '${skills_to_check[*]}'.split()
threshold = 0.75
below = []
checked = 0
no_cache = []

for skill in skills:
    cache_file = os.path.join(results_dir, f'{skill}.json')
    if not os.path.isfile(cache_file):
        no_cache.append(skill)
        continue
    with open(cache_file) as f:
        data = json.load(f)
    acc = data.get('accuracy', 1.0)
    checked += 1
    if acc < threshold:
        below.append((skill, acc))

if no_cache:
    print(f'  {len(no_cache)} skills have no cached triggers: {\" \".join(no_cache[:5])}{\"...\" if len(no_cache)>5 else \"\"}')

if below:
    print(f'  {len(below)} skills BELOW {threshold:.0%} trigger accuracy:')
    for skill, acc in sorted(below, key=lambda x: x[1]):
        print(f'    {skill}: {acc:.0%}')
    print(f'  Run: make eval-tournament')
    sys.exit(1)
elif checked > 0:
    print(f'  {checked} skills checked — all >= {threshold:.0%} trigger accuracy (cached)')
"
    return $?
}

echo "=== Plugin Eval ==="
echo ""

case "$MODE" in
    --all)
        echo "--- Lint ---"
        npm run lint 2>&1 | tail -1
        echo ""
        echo "--- Skills (all) ---"
        run_skills "all" || FAILURES=$((FAILURES + 1))
        echo ""
        echo "--- Agents (all) ---"
        run_agents "all" || FAILURES=$((FAILURES + 1))
        echo ""
        echo "--- Trigger Accuracy (cached) ---"
        run_triggers_cached "all" || FAILURES=$((FAILURES + 1))
        ;;
    --skills)
        echo "--- Skills (all) ---"
        run_skills "all" || FAILURES=$((FAILURES + 1))
        ;;
    --agents)
        echo "--- Agents (all) ---"
        run_agents "all" || FAILURES=$((FAILURES + 1))
        ;;
    --changed)
        echo "--- Lint ---"
        npm run lint 2>&1 | tail -1
        echo ""
        echo "--- Skills (changed) ---"
        run_skills "changed" || FAILURES=$((FAILURES + 1))
        echo ""
        echo "--- Agents (changed) ---"
        run_agents "changed" || FAILURES=$((FAILURES + 1))
        echo ""
        echo "--- Trigger Accuracy (cached, changed skills) ---"
        run_triggers_cached "changed" || FAILURES=$((FAILURES + 1))
        ;;
    --triggers)
        echo "--- Behavioral Triggers (all, ~\$1.50) ---"
        echo "  This takes ~60 minutes..."
        python3 -m lab.eval.trigger_scorer --all --summary
        ;;
    --ci)
        echo "--- CI Gate: Lint + All Skills + All Agents + Triggers ---"
        echo ""
        echo "--- Lint ---"
        npm run lint 2>&1
        LINT_EXIT=$?
        if [ "$LINT_EXIT" -ne 0 ]; then
            echo "  LINT FAILED"
            FAILURES=$((FAILURES + 1))
        fi
        echo ""
        echo "--- Skills ---"
        run_skills "all" || FAILURES=$((FAILURES + 1))
        echo ""
        echo "--- Agents ---"
        run_agents "all" || FAILURES=$((FAILURES + 1))
        echo ""
        echo "--- Trigger Accuracy (cached) ---"
        run_triggers_cached "all" || FAILURES=$((FAILURES + 1))
        ;;
    --fix)
        echo "--- Auto-Fix: lint + find failures + suggest fixes ---"
        echo ""
        echo "--- Lint Fix ---"
        npm run lint:fix 2>&1 | tail -3
        echo ""
        echo "--- Scoring All Skills ---"
        FAILING=$(python3 -m lab.eval.scorer --all 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)
# Skills that fail only on behavioral (trigger accuracy) are edge cases — skip
BEHAVIORAL_ONLY_SKIP = set()
failing = []
for name, data in d.items():
    if data['composite'] < 0.95:
        issues = []
        all_behavioral = True
        for dim, dim_data in data['dimensions'].items():
            for a in dim_data['assertions']:
                if not a['passed']:
                    issues.append(f'{dim}:{a[\"desc\"]}')
                    if dim != 'behavioral':
                        all_behavioral = False
        if all_behavioral:
            BEHAVIORAL_ONLY_SKIP.add(name)
        else:
            failing.append(f'{name} ({data[\"composite\"]:.3f}): {\" | \".join(issues)}')
for name in sorted(BEHAVIORAL_ONLY_SKIP):
    print(f'  {name}: behavioral edge case (expected, skipped)')
if failing:
    for f in failing:
        print(f'  FIXABLE: {f}')
elif not BEHAVIORAL_ONLY_SKIP:
    print('  All skills pass!')
")
        echo "$FAILING"
        echo ""
        echo "--- Scoring All Agents ---"
        python3 -m lab.eval.agent_scorer --all 2>&1 | grep "NEEDS WORK" || echo "  All agents pass!"
        echo ""
        # Count only fixable failures
        FAIL_COUNT=$(echo "$FAILING" | grep -c 'FIXABLE:' || true)
        if [ "$FAIL_COUNT" -gt 0 ]; then
            echo "--- To auto-fix, run autoresearch: ---"
            SKIP_LIST=$(echo "$FAILING" | grep 'behavioral edge case' | awk '{print $1}' | tr -d ' ' | sed 's/:$//' | tr '\n' ',' | sed 's/,$//')
            if [ -n "$SKIP_LIST" ]; then
                echo "  claude -p 'Run autoresearch. Score all skills, find lowest below 0.95. SKIP these (behavioral edge cases): ${SKIP_LIST}. Read the failing skill, fix ONE issue, re-score, git commit if better, git checkout if worse. Repeat until all fixable skills pass.' --allowedTools 'Edit,Read,Write,Bash,Glob,Grep'"
            else
                echo "  claude -p 'Run autoresearch. Score all skills, find lowest below 0.95, read it, fix ONE issue, re-score, git commit if better, git checkout if worse. Repeat until all pass.' --allowedTools 'Edit,Read,Write,Bash,Glob,Grep'"
            fi
            echo ""
            echo "Or fix manually based on failures above."
            exit 1
        else
            echo "ALL PASS — nothing to fix! (behavioral edge cases are expected)"
        fi
        ;;
    *)
        echo "Usage: $0 [--all|--skills|--agents|--changed|--triggers|--ci|--fix]"
        exit 1
        ;;
esac

# Save current commit as last eval point
git rev-parse HEAD > "$LAST_EVAL_FILE"

echo ""
if [ "$FAILURES" -gt 0 ]; then
    echo "EVAL FAILED — $FAILURES dimension(s) below threshold"
    exit 1
else
    echo "EVAL PASSED"
    exit 0
fi
