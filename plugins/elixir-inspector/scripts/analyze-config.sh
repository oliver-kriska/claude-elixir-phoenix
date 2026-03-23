#!/usr/bin/env bash
# analyze-config.sh — Analyze .claude/ directory configuration
#
# Extracts skills, agents, hooks, commands, rules, and directory structure
# from a project's .claude/ configuration. Outputs deterministic JSON.
#
# Usage:
#   ./analyze-config.sh /path/to/repo
#   ./analyze-config.sh                   # defaults to current directory
#   ./analyze-config.sh --help

# NOTE: no set -e or pipefail — analysis commands (grep, find, mix) may return
# non-zero on no matches, and we handle all errors gracefully
set -u

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'USAGE'
Usage: analyze-config.sh [REPO_PATH]

Analyze .claude/ directory configuration for an Elixir/Phoenix project.
Extracts skills, agents, hooks, commands, rules, and directory structure.

Arguments:
  REPO_PATH   Path to the repository root (default: current directory)

Output:
  JSON to stdout with keys:
    has_claude_dir, claude_md, skills, skill_count, agents, agent_count,
    hooks, commands, has_solutions, has_plans, plan_count, subdirectories

Examples:
  ./analyze-config.sh /path/to/my-project
  ./analyze-config.sh > config.json
USAGE
    exit 0
fi

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

REPO_PATH="${1:-.}"
REPO_PATH="$(cd "$REPO_PATH" 2>/dev/null && pwd)" || {
    echo '{"error": "Invalid repository path: '"$1"'"}' >&2
    exit 1
}

CLAUDE_DIR="$REPO_PATH/.claude"

# ---------------------------------------------------------------------------
# JSON helpers — proper escaping without jq dependency
# ---------------------------------------------------------------------------

json_escape() {
    # Escape backslash, double-quote, and control characters for JSON strings
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    s="${s//$'\n'/\\n}"
    s="${s//$'\r'/\\r}"
    s="${s//$'\t'/\\t}"
    printf '%s' "$s"
}

json_string() {
    printf '"%s"' "$(json_escape "$1")"
}

json_array_from_lines() {
    # Convert newline-separated input to JSON array of strings
    local first=true
    printf '['
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        if [[ "$first" == true ]]; then
            first=false
        else
            printf ','
        fi
        json_string "$line"
    done
    printf ']'
}

# ---------------------------------------------------------------------------
# Check .claude/ directory
# ---------------------------------------------------------------------------

if [[ ! -d "$CLAUDE_DIR" ]]; then
    cat <<'EOF'
{
  "has_claude_dir": false,
  "claude_md": {"exists": false, "lines": 0, "sections": [], "rules_found": [], "rule_count": 0},
  "skills": [],
  "skill_count": 0,
  "agents": [],
  "agent_count": 0,
  "hooks": {"exists": false, "types": []},
  "commands": [],
  "has_solutions": false,
  "has_plans": false,
  "plan_count": 0,
  "subdirectories": []
}
EOF
    exit 0
fi

# ---------------------------------------------------------------------------
# Subdirectories
# ---------------------------------------------------------------------------

subdirs=""
if [[ -d "$CLAUDE_DIR" ]]; then
    subdirs=$(find "$CLAUDE_DIR" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; 2>/dev/null | sort)
fi

# ---------------------------------------------------------------------------
# CLAUDE.md analysis
# ---------------------------------------------------------------------------

CLAUDE_MD="$REPO_PATH/CLAUDE.md"
claude_md_exists=false
claude_md_lines=0
claude_md_sections="[]"
claude_md_rules="[]"
claude_md_rule_count=0

if [[ -f "$CLAUDE_MD" ]]; then
    claude_md_exists=true
    claude_md_lines=$(wc -l < "$CLAUDE_MD" | tr -d ' ')

    # Extract section headers (lines starting with #)
    claude_md_sections=$(grep -E '^#{1,6} ' "$CLAUDE_MD" 2>/dev/null | head -50 | json_array_from_lines)

    # Extract rule lines (containing MUST, NEVER, ALWAYS, DO NOT — case sensitive)
    rules_raw=$(grep -E '\b(MUST|NEVER|ALWAYS|DO NOT)\b' "$CLAUDE_MD" 2>/dev/null | head -100 || true)
    claude_md_rules=$(echo "$rules_raw" | json_array_from_lines)
    claude_md_rule_count=$(echo "$rules_raw" | grep -c . 2>/dev/null || echo 0)
fi

# Also check .claude/CLAUDE.md (some projects put it there)
CLAUDE_MD_ALT="$CLAUDE_DIR/CLAUDE.md"
if [[ "$claude_md_exists" == false && -f "$CLAUDE_MD_ALT" ]]; then
    claude_md_exists=true
    CLAUDE_MD="$CLAUDE_MD_ALT"
    claude_md_lines=$(wc -l < "$CLAUDE_MD" | tr -d ' ')
    claude_md_sections=$(grep -E '^#{1,6} ' "$CLAUDE_MD" 2>/dev/null | head -50 | json_array_from_lines)
    rules_raw=$(grep -E '\b(MUST|NEVER|ALWAYS|DO NOT)\b' "$CLAUDE_MD" 2>/dev/null | head -100 || true)
    claude_md_rules=$(echo "$rules_raw" | json_array_from_lines)
    claude_md_rule_count=$(echo "$rules_raw" | grep -c . 2>/dev/null || echo 0)
fi

# ---------------------------------------------------------------------------
# YAML frontmatter parser (simple: extract name: and description: between --- markers)
# ---------------------------------------------------------------------------

parse_frontmatter() {
    local file="$1"
    local in_frontmatter=false
    local name=""
    local description=""
    local line_num=0

    while IFS= read -r line; do
        line_num=$((line_num + 1))
        if [[ "$line" == "---" ]]; then
            if [[ "$in_frontmatter" == true ]]; then
                # End of frontmatter
                break
            elif [[ $line_num -le 2 ]]; then
                in_frontmatter=true
                continue
            fi
        fi
        if [[ "$in_frontmatter" == true ]]; then
            # Extract name: value (strip quotes)
            if [[ "$line" =~ ^name:[[:space:]]*(.*) ]]; then
                name="${BASH_REMATCH[1]}"
                name="${name#\"}"
                name="${name%\"}"
                name="${name#\'}"
                name="${name%\'}"
                name="$(echo "$name" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            fi
            # Extract description: value (strip quotes)
            if [[ "$line" =~ ^description:[[:space:]]*(.*) ]]; then
                description="${BASH_REMATCH[1]}"
                description="${description#\"}"
                description="${description%\"}"
                description="${description#\'}"
                description="${description%\'}"
                description="$(echo "$description" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            fi
        fi
    done < "$file"

    # Output as tab-separated: name\tdescription
    printf '%s\t%s' "$name" "$description"
}

# ---------------------------------------------------------------------------
# Skills analysis
# ---------------------------------------------------------------------------

skills_json="[]"
skill_count=0

if [[ -d "$CLAUDE_DIR/skills" ]]; then
    skills_json="["
    first=true

    while IFS= read -r skill_file; do
        [[ -z "$skill_file" ]] && continue

        # Get relative path from repo root
        rel_path="${skill_file#"$REPO_PATH/"}"

        # Parse frontmatter
        fm=$(parse_frontmatter "$skill_file")
        fm_name=$(echo "$fm" | cut -f1)
        fm_desc=$(echo "$fm" | cut -f2-)

        # If no name in frontmatter, derive from directory name
        if [[ -z "$fm_name" ]]; then
            fm_name=$(basename "$(dirname "$skill_file")")
        fi

        if [[ "$first" == true ]]; then
            first=false
        else
            skills_json+=","
        fi

        skills_json+=$(printf '{"name":%s,"description":%s,"path":%s}' \
            "$(json_string "$fm_name")" \
            "$(json_string "$fm_desc")" \
            "$(json_string "$rel_path")")

        skill_count=$((skill_count + 1))
    done < <(find "$CLAUDE_DIR/skills" -name "SKILL.md" -type f 2>/dev/null | sort)

    skills_json+="]"
fi

# ---------------------------------------------------------------------------
# Agents analysis
# ---------------------------------------------------------------------------

agents_json="[]"
agent_count=0

if [[ -d "$CLAUDE_DIR/agents" ]]; then
    agents_json="["
    first=true

    while IFS= read -r agent_file; do
        [[ -z "$agent_file" ]] && continue

        rel_path="${agent_file#"$REPO_PATH/"}"

        fm=$(parse_frontmatter "$agent_file")
        fm_name=$(echo "$fm" | cut -f1)
        fm_desc=$(echo "$fm" | cut -f2-)

        # If no name in frontmatter, derive from filename
        if [[ -z "$fm_name" ]]; then
            fm_name=$(basename "$agent_file" .md)
        fi

        if [[ "$first" == true ]]; then
            first=false
        else
            agents_json+=","
        fi

        agents_json+=$(printf '{"name":%s,"description":%s,"path":%s}' \
            "$(json_string "$fm_name")" \
            "$(json_string "$fm_desc")" \
            "$(json_string "$rel_path")")

        agent_count=$((agent_count + 1))
    done < <(find "$CLAUDE_DIR/agents" -name "*.md" -type f 2>/dev/null | sort)

    agents_json+="]"
fi

# ---------------------------------------------------------------------------
# Hooks analysis
# ---------------------------------------------------------------------------

hooks_exists=false
hooks_types="[]"

# Check for hooks.json in .claude/ or .claude/hooks/
HOOKS_FILE=""
if [[ -f "$CLAUDE_DIR/hooks.json" ]]; then
    HOOKS_FILE="$CLAUDE_DIR/hooks.json"
elif [[ -f "$CLAUDE_DIR/hooks/hooks.json" ]]; then
    HOOKS_FILE="$CLAUDE_DIR/hooks/hooks.json"
fi

if [[ -n "$HOOKS_FILE" ]]; then
    hooks_exists=true
    # Extract hook type keys from the hooks object
    # Look for keys like "PreToolUse", "PostToolUse", etc. at top level of "hooks" object
    hooks_types=$(grep -oE '"(PreToolUse|PostToolUse|PreToolUseFailure|PostToolUseFailure|SubagentStart|SessionStart|Stop|PreCompact|UserPromptSubmit|Notification)"' "$HOOKS_FILE" 2>/dev/null \
        | sort -u \
        | tr -d '"' \
        | json_array_from_lines)
fi

# Also check if hooks directory has shell scripts (alternative hook setup)
if [[ "$hooks_exists" == false && -d "$CLAUDE_DIR/hooks" ]]; then
    hook_scripts=$(find "$CLAUDE_DIR/hooks" -name "*.sh" -type f 2>/dev/null | head -1)
    if [[ -n "$hook_scripts" ]]; then
        hooks_exists=true
        hooks_types='["custom"]'
    fi
fi

# ---------------------------------------------------------------------------
# Commands analysis
# ---------------------------------------------------------------------------

commands_json="[]"

if [[ -d "$CLAUDE_DIR/commands" ]]; then
    commands_json="["
    first=true

    while IFS= read -r cmd_file; do
        [[ -z "$cmd_file" ]] && continue

        rel_path="${cmd_file#"$REPO_PATH/"}"
        cmd_name=$(basename "$cmd_file" .md)

        if [[ "$first" == true ]]; then
            first=false
        else
            commands_json+=","
        fi

        commands_json+=$(printf '{"name":%s,"path":%s}' \
            "$(json_string "$cmd_name")" \
            "$(json_string "$rel_path")")
    done < <(find "$CLAUDE_DIR/commands" -name "*.md" -type f 2>/dev/null | sort)

    commands_json+="]"
fi

# ---------------------------------------------------------------------------
# Solutions and Plans
# ---------------------------------------------------------------------------

has_solutions=false
if [[ -d "$CLAUDE_DIR/solutions" ]]; then
    # Check it's not empty
    sol_count=$(find "$CLAUDE_DIR/solutions" -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$sol_count" -gt 0 ]]; then
        has_solutions=true
    fi
fi

has_plans=false
plan_count=0
if [[ -d "$CLAUDE_DIR/plans" ]]; then
    # Count plan directories (each plan is a directory with plan.md)
    plan_count=$(find "$CLAUDE_DIR/plans" -name "plan.md" -type f 2>/dev/null | wc -l | tr -d ' ')
    if [[ "$plan_count" -gt 0 ]]; then
        has_plans=true
    else
        # Also count bare .md files in plans/ that might be plans
        plan_count=$(find "$CLAUDE_DIR/plans" -maxdepth 1 -name "*.md" -type f 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$plan_count" -gt 0 ]]; then
            has_plans=true
        fi
    fi
fi

# ---------------------------------------------------------------------------
# Assemble subdirectories JSON
# ---------------------------------------------------------------------------

subdirs_json=$(echo "$subdirs" | json_array_from_lines)

# ---------------------------------------------------------------------------
# Output JSON
# ---------------------------------------------------------------------------

cat <<ENDJSON
{
  "has_claude_dir": true,
  "claude_md": {
    "exists": $claude_md_exists,
    "lines": $claude_md_lines,
    "sections": $claude_md_sections,
    "rules_found": $claude_md_rules,
    "rule_count": $claude_md_rule_count
  },
  "skills": $skills_json,
  "skill_count": $skill_count,
  "agents": $agents_json,
  "agent_count": $agent_count,
  "hooks": {
    "exists": $hooks_exists,
    "types": $hooks_types
  },
  "commands": $commands_json,
  "has_solutions": $has_solutions,
  "has_plans": $has_plans,
  "plan_count": $plan_count,
  "subdirectories": $subdirs_json
}
ENDJSON
