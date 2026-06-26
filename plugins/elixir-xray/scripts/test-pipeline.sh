#!/usr/bin/env bash
# test-pipeline.sh — End-to-end test for the X-Ray plugin pipeline.
#
# Validates all scripts produce valid JSON, all agents/skills have correct
# frontmatter, hooks reference existing scripts, and merge-findings handles
# sample data correctly.
#
# Usage:
#   ./test-pipeline.sh [REPO_PATH]
#   ./test-pipeline.sh                  # defaults to repo root
#
# NOTE: no set -e — we continue on failures and report a summary.
set -u

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

REPO="${1:-$(cd "$(dirname "$0")/../../.." && pwd)}"
REPO="$(cd "$REPO" 2>/dev/null && pwd)" || {
    echo "Error: invalid repo path: $1" >&2
    exit 1
}

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPTS="$PLUGIN_DIR/scripts"
AGENTS_DIR="$PLUGIN_DIR/agents"
SKILLS_DIR="$PLUGIN_DIR/skills"
HOOKS_DIR="$PLUGIN_DIR/hooks"

TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# Counters — ALL tracking goes through pass()/fail() only
PASS=0
FAIL=0

pass() {
    PASS=$((PASS + 1))
    echo "  OK: $1"
}

fail() {
    FAIL=$((FAIL + 1))
    echo "  FAIL: $1"
}

section() {
    echo ""
    echo "=== $1 ==="
}

# ---------------------------------------------------------------------------
# Helper: validate JSON from stdin and check for expected keys (silent)
# ---------------------------------------------------------------------------

check_json_keys() {
    # Returns 0 if valid JSON with all specified keys, 1 otherwise.
    # Does NOT print anything — caller uses pass()/fail().
    local keys=("$@")

    local key_checks=""
    for key in "${keys[@]}"; do
        key_checks+="assert '$key' in d, 'missing key: $key'; "
    done

    python3 -c "
import json, sys
d = json.load(sys.stdin)
$key_checks
" 2>/dev/null
    return $?
}

# =========================================================================
# 1. Script Output Validation
# =========================================================================

section "Script Output Validation"

SCRIPT_PASS=0
SCRIPT_TOTAL=10

# --- analyze-git-history.py ---
echo "Testing analyze-git-history.py..."
if python3 "$SCRIPTS/analyze-git-history.py" "$REPO" --since "1 month ago" 2>/dev/null | \
    check_json_keys "total_commits" "fix_patterns" "hotspot_files" "commit_conventions" "fix_chains"; then
    SCRIPT_PASS=$((SCRIPT_PASS + 1))
    pass "git-history"
else
    fail "git-history"
fi

# --- analyze-prs.py ---
echo "Testing analyze-prs.py..."
if python3 "$SCRIPTS/analyze-prs.py" "$REPO" --limit 5 --timeout 15 2>/dev/null | \
    check_json_keys "total_prs_analyzed" "review_themes" "pr_size_stats" "high_friction_prs"; then
    SCRIPT_PASS=$((SCRIPT_PASS + 1))
    pass "prs"
else
    fail "prs"
fi

# --- analyze-code.py ---
# Requires Elixir project (lib/ + mix.exs). Non-Elixir repos get exit 1.
echo "Testing analyze-code.py..."
if [[ -d "$REPO/lib" && -f "$REPO/mix.exs" ]]; then
    if python3 "$SCRIPTS/analyze-code.py" "$REPO" 2>/dev/null | \
        check_json_keys "modules" "functions" "i18n" "testing" "documentation"; then
        SCRIPT_PASS=$((SCRIPT_PASS + 1))
        pass "code"
    else
        fail "code"
    fi
else
    if python3 "$SCRIPTS/analyze-code.py" "$REPO" 2>/dev/null; then
        fail "code (should have exited non-zero for non-Elixir repo)"
    else
        SCRIPT_PASS=$((SCRIPT_PASS + 1))
        pass "code (correctly rejected non-Elixir repo)"
    fi
fi

# --- analyze-config.sh ---
echo "Testing analyze-config.sh..."
if bash "$SCRIPTS/analyze-config.sh" "$REPO" 2>/dev/null | \
    check_json_keys "has_claude_dir" "claude_md" "skills" "agents" "hooks"; then
    SCRIPT_PASS=$((SCRIPT_PASS + 1))
    pass "config"
else
    fail "config"
fi

# --- analyze-architecture.sh ---
# Requires Elixir project.
echo "Testing analyze-architecture.sh..."
if [[ -d "$REPO/lib" && -f "$REPO/mix.exs" ]]; then
    if bash "$SCRIPTS/analyze-architecture.sh" "$REPO" 2>/dev/null | \
        check_json_keys "app_name" "contexts" "boundary_violations" "cycles"; then
        SCRIPT_PASS=$((SCRIPT_PASS + 1))
        pass "architecture"
    else
        fail "architecture"
    fi
else
    if bash "$SCRIPTS/analyze-architecture.sh" "$REPO" 2>/dev/null; then
        fail "architecture (should have exited non-zero for non-Elixir repo)"
    else
        SCRIPT_PASS=$((SCRIPT_PASS + 1))
        pass "architecture (correctly rejected non-Elixir repo)"
    fi
fi

# --- analyze-sessions.py ---
# Requires a session JSON file. Create a minimal valid one.
echo "Testing analyze-sessions.py..."
cat > "$TMPDIR_TEST/session.json" << 'SESSIONEOF'
{
  "messages": [
    {"type": "user", "content": "Fix the login bug", "timestamp": "2026-03-20T10:00:00Z"},
    {"type": "assistant", "content": "I'll look into the login issue using Read tool.", "timestamp": "2026-03-20T10:01:00Z"},
    {"type": "user", "content": "No, that's wrong, check the auth module instead", "timestamp": "2026-03-20T10:02:00Z"},
    {"type": "assistant", "content": "Let me Read the auth module.", "timestamp": "2026-03-20T10:03:00Z"}
  ]
}
SESSIONEOF
if python3 "$SCRIPTS/analyze-sessions.py" "$TMPDIR_TEST/session.json" --session-id test-123 2>/dev/null | \
    check_json_keys "session_id" "message_count" "friction_score" "session_type" "tool_usage"; then
    SCRIPT_PASS=$((SCRIPT_PASS + 1))
    pass "sessions"
else
    fail "sessions"
fi

# --- temporal-coupling.py ---
echo "Testing temporal-coupling.py..."
if python3 "$SCRIPTS/temporal-coupling.py" "$REPO" --since "1 month ago" 2>/dev/null | \
    check_json_keys "total_commits_analyzed" "total_files_tracked" "total_pairs_above_threshold" "coupled_pairs"; then
    SCRIPT_PASS=$((SCRIPT_PASS + 1))
    pass "temporal-coupling"
else
    fail "temporal-coupling"
fi

# --- hotspot-score.py ---
echo "Testing hotspot-score.py..."
if python3 "$SCRIPTS/hotspot-score.py" "$REPO" --since "1 month ago" 2>/dev/null | \
    check_json_keys "total_files_analyzed" "hotspots"; then
    SCRIPT_PASS=$((SCRIPT_PASS + 1))
    pass "hotspot-score"
else
    fail "hotspot-score"
fi

# --- quality-gate.py (measure mode) ---
echo "Testing quality-gate.py (measure)..."
if [[ -d "$REPO/lib" && -f "$REPO/mix.exs" ]]; then
    if python3 "$SCRIPTS/quality-gate.py" measure "$REPO" --baseline "$TMPDIR_TEST/baseline.json" 2>/dev/null && \
       [[ -f "$TMPDIR_TEST/baseline.json" ]] && \
       python3 -c "import json; d=json.load(open('$TMPDIR_TEST/baseline.json')); assert 'version' in d; assert 'categories' in d" 2>/dev/null; then
        SCRIPT_PASS=$((SCRIPT_PASS + 1))
        pass "quality-gate (measure)"
    else
        fail "quality-gate (measure)"
    fi
else
    # Non-Elixir: quality-gate still runs (measures 0 for all categories)
    # and creates a valid baseline. Verify it doesn't crash.
    python3 "$SCRIPTS/quality-gate.py" measure "$REPO" --baseline "$TMPDIR_TEST/baseline.json" 2>/dev/null
    exit_code=$?
    if [[ $exit_code -eq 0 && -f "$TMPDIR_TEST/baseline.json" ]] && \
       python3 -c "import json; d=json.load(open('$TMPDIR_TEST/baseline.json')); assert 'version' in d; assert 'categories' in d" 2>/dev/null; then
        SCRIPT_PASS=$((SCRIPT_PASS + 1))
        pass "quality-gate (measure, non-Elixir baseline)"
    elif [[ $exit_code -eq 2 || $exit_code -eq 1 ]]; then
        SCRIPT_PASS=$((SCRIPT_PASS + 1))
        pass "quality-gate (correctly rejected non-Elixir repo)"
    else
        fail "quality-gate (exit code: $exit_code)"
    fi
fi

# --- merge-findings.py ---
# Test with empty layers dir (valid, should produce empty findings).
echo "Testing merge-findings.py..."
mkdir -p "$TMPDIR_TEST/empty-layers"
if python3 "$SCRIPTS/merge-findings.py" "$TMPDIR_TEST/empty-layers" 2>/dev/null | \
    check_json_keys "total_findings" "findings" "themes" "contradictions"; then
    SCRIPT_PASS=$((SCRIPT_PASS + 1))
    pass "merge-findings"
else
    fail "merge-findings"
fi

echo ""
echo "Scripts: $SCRIPT_PASS/$SCRIPT_TOTAL passed"

# =========================================================================
# 2. Agent Frontmatter Validation
# =========================================================================

section "Agent Frontmatter Validation"

AGENT_PASS=0
AGENT_TOTAL=0
AGENT_EXPECTED=17

for agent_file in "$AGENTS_DIR"/*.md; do
    [[ -f "$agent_file" ]] || continue
    AGENT_TOTAL=$((AGENT_TOTAL + 1))
    agent_name="$(basename "$agent_file" .md)"
    errors=""

    # Check permissionMode: bypassPermissions
    if ! grep -q 'permissionMode:\s*bypassPermissions' "$agent_file" 2>/dev/null; then
        errors="${errors}missing permissionMode:bypassPermissions; "
    fi

    # Check model: field exists
    if ! grep -q '^model:' "$agent_file" 2>/dev/null; then
        errors="${errors}missing model: field; "
    fi

    # Check tools: field exists
    if ! grep -q '^tools:' "$agent_file" 2>/dev/null; then
        errors="${errors}missing tools: field; "
    fi

    # Line count check
    line_count=$(wc -l < "$agent_file" | tr -d ' ')
    # Orchestrators (contain "orchestrator" in name) get 535 limit, others 365
    if [[ "$agent_name" == *orchestrator* ]]; then
        max_lines=535
    else
        max_lines=365
    fi
    if [[ "$line_count" -gt "$max_lines" ]]; then
        errors="${errors}${line_count} lines exceeds limit of ${max_lines}; "
    fi

    if [[ -z "$errors" ]]; then
        AGENT_PASS=$((AGENT_PASS + 1))
        pass "$agent_name ($line_count lines)"
    else
        fail "$agent_name: $errors"
    fi
done

# Verify expected count
if [[ "$AGENT_TOTAL" -ne "$AGENT_EXPECTED" ]]; then
    echo "  WARNING: Expected $AGENT_EXPECTED agents, found $AGENT_TOTAL"
fi

echo ""
echo "Agents: $AGENT_PASS/$AGENT_TOTAL valid"

# =========================================================================
# 3. Skill Validation
# =========================================================================

section "Skill Validation"

SKILL_PASS=0
SKILL_TOTAL=0
SKILL_EXPECTED=4

while IFS= read -r skill_file; do
    [[ -f "$skill_file" ]] || continue
    SKILL_TOTAL=$((SKILL_TOTAL + 1))
    skill_dir="$(basename "$(dirname "$skill_file")")"
    errors=""

    # Check name: in frontmatter
    if ! grep -q '^name:' "$skill_file" 2>/dev/null; then
        errors="${errors}missing name: in frontmatter; "
    fi

    # Check description: in frontmatter
    if ! grep -q '^description:' "$skill_file" 2>/dev/null; then
        errors="${errors}missing description: in frontmatter; "
    fi

    # Line count check (command skills get 250 limit)
    line_count=$(wc -l < "$skill_file" | tr -d ' ')
    max_lines=250
    if [[ "$line_count" -gt "$max_lines" ]]; then
        errors="${errors}${line_count} lines exceeds limit of ${max_lines}; "
    fi

    if [[ -z "$errors" ]]; then
        SKILL_PASS=$((SKILL_PASS + 1))
        pass "$skill_dir ($line_count lines)"
    else
        fail "$skill_dir: $errors"
    fi
done < <(find "$SKILLS_DIR" -name "SKILL.md" -type f 2>/dev/null | sort)

# Verify expected count
if [[ "$SKILL_TOTAL" -ne "$SKILL_EXPECTED" ]]; then
    echo "  WARNING: Expected $SKILL_EXPECTED skills, found $SKILL_TOTAL"
fi

echo ""
echo "Skills: $SKILL_PASS/$SKILL_TOTAL valid"

# =========================================================================
# 4. Hook Validation
# =========================================================================

section "Hook Validation"

HOOK_PASS=0
HOOK_TOTAL=0

# 4a. hooks.json is valid JSON
HOOK_TOTAL=$((HOOK_TOTAL + 1))
HOOKS_JSON="$HOOKS_DIR/hooks.json"
if [[ -f "$HOOKS_JSON" ]] && \
   python3 -c "import json; json.load(open('$HOOKS_JSON'))" 2>/dev/null; then
    HOOK_PASS=$((HOOK_PASS + 1))
    pass "hooks.json is valid JSON"
else
    fail "hooks.json missing or invalid JSON"
fi

# 4b. All referenced scripts exist and are executable
HOOK_TOTAL=$((HOOK_TOTAL + 1))
referenced_scripts_ok=true
while IFS= read -r script_path; do
    [[ -z "$script_path" ]] && continue
    # Replace ${CLAUDE_PLUGIN_ROOT} with the actual plugin dir
    resolved="${script_path//\$\{CLAUDE_PLUGIN_ROOT\}/$PLUGIN_DIR}"
    if [[ ! -f "$resolved" ]]; then
        fail "referenced hook script not found: $script_path"
        referenced_scripts_ok=false
    elif [[ ! -x "$resolved" ]]; then
        fail "referenced hook script not executable: $script_path"
        referenced_scripts_ok=false
    fi
done < <(python3 -c "
import json
data = json.load(open('$HOOKS_JSON'))
for hook_type, entries in data.get('hooks', {}).items():
    for entry in entries:
        for hook in entry.get('hooks', []):
            cmd = hook.get('command', '')
            # Only script-file references — skip inline commands (echo, etc.)
            if cmd.startswith('\${CLAUDE_PLUGIN_ROOT}'):
                print(cmd)
" 2>/dev/null)

if [[ "$referenced_scripts_ok" == true ]]; then
    HOOK_PASS=$((HOOK_PASS + 1))
    pass "all referenced hook scripts exist and are executable"
fi

echo ""
echo "Hooks: $HOOK_PASS/$HOOK_TOTAL valid"

# =========================================================================
# 5. Merge Script Validation (with sample data)
# =========================================================================

section "Merge Script Validation (sample data)"

MERGE_PASS=0
MERGE_TOTAL=1

# Create 2 sample layer .md files with YAML frontmatter findings
mkdir -p "$TMPDIR_TEST/sample-layers"

cat > "$TMPDIR_TEST/sample-layers/git-history.md" << 'LAYER1EOF'
# Layer 1: Git History Findings

---
id: L1-001
layer: git-history
category: recurring-bugs
title: Recurring hardcoded gettext strings missing translation coverage
severity: medium
effort: small
automatable: yes
confidence: high
frequency: 12
artifact_types: [credo-check, ci-step]
evidence:
  - "12 commits with fix gettext in message"
  - "lib/my_app_web/live/dashboard_live.ex touched 8 times"
---

Gettext strings are frequently missed during feature development,
leading to recurring fix commits.

---
id: L1-002
layer: git-history
category: hotspots
title: High churn in auth module
severity: high
effort: medium
automatable: partial
confidence: medium
frequency: 25
artifact_types: [review-prompt]
evidence:
  - "lib/my_app/accounts/auth.ex changed 25 times in 6 months"
  - "Bug ratio: 0.4 (10 of 25 changes were fixes)"
---

The auth module is a significant hotspot with high bug ratio.
LAYER1EOF

cat > "$TMPDIR_TEST/sample-layers/code-docs.md" << 'LAYER2EOF'
# Layer 3: Code & Docs Findings

---
id: L3-001
layer: code-docs
category: recurring-bugs
title: Hardcoded gettext strings missing translation in heex templates
severity: medium
effort: small
automatable: yes
confidence: high
frequency: 8
artifact_types: [credo-check]
evidence:
  - "8 hardcoded UI strings in .heex files"
  - "lib/my_app_web/templates/dashboard/index.html.heex:15"
---

Multiple .heex templates contain hardcoded English strings
that should use gettext for internationalization.

---
id: L3-002
layer: code-docs
category: security
title: Missing authorization in handle_event callbacks
severity: critical
effort: medium
automatable: partial
confidence: high
frequency: 5
artifact_types: [credo-check, review-prompt, claude-md-rule]
evidence:
  - "5 handle_event functions without authorization check"
  - "lib/my_app_web/live/admin_live.ex:45"
  - "lib/my_app_web/live/settings_live.ex:22"
---

Several LiveView handle_event callbacks lack authorization checks,
violating Iron Law #11.
LAYER2EOF

# Run merge-findings on the sample layers
echo "Testing merge-findings.py with sample data..."
merge_output=$(python3 "$SCRIPTS/merge-findings.py" "$TMPDIR_TEST/sample-layers" 2>/dev/null)
merge_exit=$?

# Write validation script to a temp file to avoid shell quoting issues
cat > "$TMPDIR_TEST/validate-merge.py" << 'VALIDATEEOF'
import json, sys

d = json.load(sys.stdin)

# Check required top-level keys
for key in ('total_findings', 'findings', 'themes', 'contradictions'):
    assert key in d, 'missing key: ' + key

assert isinstance(d['findings'], list), 'findings is not a list'
assert isinstance(d['themes'], list), 'themes is not a list'
assert isinstance(d['contradictions'], list), 'contradictions is not a list'

# Should have parsed findings (4 input findings, some may merge)
assert d['total_findings'] > 0, 'expected >0 findings, got %d' % d['total_findings']
assert d['total_findings'] <= 4, 'expected <=4 findings, got %d' % d['total_findings']

# Verify findings have expected fields
for f in d['findings']:
    for fkey in ('id', 'priority_score', 'severity', 'layers', 'category', 'title'):
        assert fkey in f, 'finding missing ' + fkey
    assert f['priority_score'] > 0, 'priority_score should be > 0'

# Verify findings are sorted by priority descending
scores = [f['priority_score'] for f in d['findings']]
assert scores == sorted(scores, reverse=True), 'findings not sorted by priority'

# Verify the critical severity finding exists somewhere in the results
severities = [f['severity'] for f in d['findings']]
assert 'critical' in severities, 'expected a critical finding in output'

# Verify deduplication: L1-001 and L3-001 share category (recurring-bugs)
# and similar titles (5+ shared significant words), so should merge
assert d['total_findings'] < 4, (
    'expected deduplication to merge gettext findings, got %d' % d['total_findings']
)

# Verify v2.0 fields present in output
for f in d['findings']:
    assert 'related_to' in f, 'finding missing related_to field'
    assert 'theme' in f, 'finding missing theme field'

sys.exit(0)
VALIDATEEOF

if [[ $merge_exit -eq 0 ]] && echo "$merge_output" | python3 "$TMPDIR_TEST/validate-merge.py" 2>/dev/null; then
    MERGE_PASS=1
    pass "merge-findings (sample data)"
else
    fail "merge-findings (sample data)"
    # Debug: show merge output on failure
    if [[ -n "$merge_output" ]]; then
        echo "    merge exit=$merge_exit, output length=${#merge_output}"
        echo "$merge_output" | python3 "$TMPDIR_TEST/validate-merge.py" 2>&1 | head -5 | sed 's/^/    /'
    else
        echo "    merge exit=$merge_exit, no output"
    fi
fi

echo ""
echo "Merge: $MERGE_PASS/$MERGE_TOTAL passed"

# =========================================================================
# Summary
# =========================================================================

TOTAL=$((PASS + FAIL))

echo ""
echo "==========================================="
echo "       Inspector Pipeline Test"
echo "==========================================="
echo "  Scripts:  $SCRIPT_PASS/$SCRIPT_TOTAL passed"
echo "  Agents:   $AGENT_PASS/$AGENT_TOTAL valid"
echo "  Skills:   $SKILL_PASS/$SKILL_TOTAL valid"
echo "  Hooks:    $HOOK_PASS/$HOOK_TOTAL valid"
echo "  Merge:    $MERGE_PASS/$MERGE_TOTAL passed"
echo "-------------------------------------------"
echo "  Total:    $PASS/$TOTAL passed, $FAIL failed"
echo "==========================================="

if [[ $FAIL -eq 0 ]]; then
    echo ""
    echo "ALL PASSED"
    exit 0
else
    echo ""
    echo "$FAIL FAILURES"
    exit 1
fi
