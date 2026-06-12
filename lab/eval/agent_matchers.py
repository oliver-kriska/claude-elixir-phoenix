"""Agent-specific matchers for evaluating plugin agents.

Extends the base matchers with agent frontmatter checks:
tools validation, read-only enforcement, permission mode, model appropriateness.
"""

import os
from lab.eval.matchers import parse_frontmatter


# Valid Claude Code tools that agents can declare
VALID_TOOLS = {
    "Read", "Write", "Edit", "Bash", "Grep", "Glob", "Agent",
    "NotebookEdit", "WebFetch", "WebSearch", "LS",
}

# Keywords that indicate a read-only/analysis agent
READONLY_KEYWORDS = {"review", "analyze", "audit", "check", "judge", "inspect", "trace", "scan"}

# Agents that need Write despite having read-only keywords (orchestrators, research)
WRITE_EXEMPT_NAMES = {
    "workflow-orchestrator", "planning-orchestrator", "context-supervisor",
    "phoenix-patterns-analyst",  # writes analysis output files
    # elixir-xray generators (Write needed for artifact generation)
    "credo-generator", "cicd-generator", "claudemd-generator",
    "review-prompt-generator", "skill-generator",
    # elixir-xray orchestrators (Write needed for consolidated output)
    "l1-orchestrator", "l2-orchestrator", "l3-orchestrator",
    "l4-orchestrator", "l5-orchestrator", "l6-orchestrator",
}

# Expected model per effort level
MODEL_EFFORT_MAP = {
    "haiku": "low",
    "sonnet": "medium",
    "opus": "high",
}

# Agents that are orchestrators (higher line limits, opus justified)
ORCHESTRATOR_NAMES = {
    "workflow-orchestrator", "planning-orchestrator", "parallel-reviewer",
    "deep-bug-investigator", "call-tracer", "context-supervisor",
    "docs-validation-orchestrator",
    # elixir-xray orchestrators (both cases: score_agent uses raw name,
    # agent_model_appropriate lowercases)
    "l1-orchestrator", "l2-orchestrator", "l3-orchestrator",
    "l4-orchestrator", "l5-orchestrator", "l6-orchestrator",
    "L1-orchestrator", "L2-orchestrator", "L3-orchestrator",
    "L4-orchestrator", "L5-orchestrator", "L6-orchestrator",
}


def agent_tools_valid(content: str, **_) -> tuple[bool, str]:
    """Check that listed tools are real Claude Code tools."""
    fm = parse_frontmatter(content)
    tools_raw = fm.get("tools", "")
    if not tools_raw:
        return False, "No tools field in frontmatter"

    if isinstance(tools_raw, list):
        tools = [t.strip() for t in tools_raw]
    else:
        tools = [t.strip() for t in str(tools_raw).split(",")]

    invalid = [t for t in tools if t and t not in VALID_TOOLS]
    if invalid:
        return False, f"Invalid tools: {invalid} (valid: {sorted(VALID_TOOLS)})"
    return True, f"All {len(tools)} tools valid"


def agent_readonly_enforced(content: str, **_) -> tuple[bool, str]:
    """Check that review/analysis agents block Edit and NotebookEdit.

    Write is optional — review agents may need Write to save their own
    findings file (e.g., `.claude/plans/{slug}/reviews/elixir.md`). The
    critical protection is blocking source code modification (Edit) and
    notebook modification (NotebookEdit), upholding Review Iron Law #1.
    """
    fm = parse_frontmatter(content)
    name = str(fm.get("name", "")).lower()
    desc = str(fm.get("description", "")).lower()

    # Determine if this is a read-only agent
    is_readonly = any(kw in name or kw in desc for kw in READONLY_KEYWORDS)
    if not is_readonly:
        return True, "Not a read-only agent — skipping disallowedTools check"

    # Exempt agents that need Write despite having read-only keywords
    if name in WRITE_EXEMPT_NAMES or any(n in name for n in WRITE_EXEMPT_NAMES):
        return True, f"Agent '{name}' exempt from read-only enforcement (needs Write for output)"

    disallowed_raw = fm.get("disallowedTools", "")
    if not disallowed_raw:
        return False, f"Read-only agent '{fm.get('name')}' missing disallowedTools (should block Edit, NotebookEdit)"

    if isinstance(disallowed_raw, list):
        disallowed = [t.strip() for t in disallowed_raw]
    else:
        disallowed = [t.strip() for t in str(disallowed_raw).split(",")]

    required = {"Edit", "NotebookEdit"}
    missing = required - set(disallowed)
    if missing:
        return False, f"Read-only agent missing disallowed: {sorted(missing)}"
    return True, f"Read-only agent correctly blocks source modification: {sorted(required)}"


def agent_bypass_permissions(content: str, **_) -> tuple[bool, str]:
    """Check that agent has permissionMode: bypassPermissions.

    Without this, background agents get 'Bash command permission check failed'
    when skill content contains shell-like patterns.
    """
    fm = parse_frontmatter(content)
    mode = fm.get("permissionMode", "")
    if mode == "bypassPermissions":
        return True, "permissionMode: bypassPermissions set"
    return False, f"permissionMode is '{mode}' (must be 'bypassPermissions' for background agents)"


def agent_model_appropriate(content: str, **_) -> tuple[bool, str]:
    """Check that model matches effort level and agent role.

    haiku = low (mechanical), sonnet = medium (specialist), opus = high (orchestrator/security).
    """
    fm = parse_frontmatter(content)
    model = str(fm.get("model", "")).lower()
    effort = str(fm.get("effort", "")).lower()
    name = str(fm.get("name", "")).lower()

    if not model:
        return False, "No model field in frontmatter"
    if not effort:
        return False, "No effort field in frontmatter"

    expected_effort = MODEL_EFFORT_MAP.get(model)
    if expected_effort is None:
        return True, f"Unknown model '{model}' — skipping check"

    if expected_effort == effort:
        return True, f"Model '{model}' matches effort '{effort}'"

    # Allow opus for orchestrators even if effort isn't high
    if model == "opus" and name in ORCHESTRATOR_NAMES:
        return True, f"Opus justified for orchestrator '{name}'"

    # Allow sonnet for security-critical agents even if effort is low
    if model == "sonnet" and "security" in name:
        return True, f"Sonnet justified for security agent '{name}'"

    return False, f"Model '{model}' expects effort '{expected_effort}' but got '{effort}'"


def agent_has_skills(content: str, plugin_root: str = "", **_) -> tuple[bool, str]:
    """Check that preloaded skills in frontmatter actually exist."""
    fm = parse_frontmatter(content)
    skills_raw = fm.get("skills", [])
    if not skills_raw:
        return True, "No preloaded skills (optional)"

    if isinstance(skills_raw, str):
        skills = [s.strip() for s in skills_raw.split(",")]
    else:
        skills = [str(s).strip() for s in skills_raw]

    if not plugin_root:
        return True, f"{len(skills)} preloaded skills (cannot verify — no plugin root)"

    skills_dir = os.path.join(plugin_root, "skills")
    if not os.path.isdir(skills_dir):
        return True, "Cannot locate skills directory"

    existing = set(os.listdir(skills_dir))
    missing = [s for s in skills if s and s not in existing]
    if missing:
        return False, f"Missing preloaded skills: {missing}"
    return True, f"All {len(skills)} preloaded skills exist"


def agent_omit_claudemd(content: str, **_) -> tuple[bool, str]:
    """Check that report-only agents have omitClaudeMd: true.

    Claude Code source reveals read-only agents don't need the CLAUDE.md
    hierarchy (commit/PR/lint guidelines). Adding omitClaudeMd: true reduces
    subagent context overhead.

    Agents that write source code (Edit allowed) NEED CLAUDE.md.
    Agents that only write their own report file (Write allowed, Edit blocked)
    are "report-only writers" and should still have omitClaudeMd: true.
    """
    fm = parse_frontmatter(content)
    name = str(fm.get("name", "")).lower()

    # Orchestrators that spawn subagents need CLAUDE.md
    if name in WRITE_EXEMPT_NAMES:
        if fm.get("omitClaudeMd"):
            return False, f"Agent '{name}' has Write access — should NOT have omitClaudeMd"
        return True, f"Agent '{name}' has Write access — correctly omits omitClaudeMd"

    tools_raw = fm.get("tools", "")
    if isinstance(tools_raw, list):
        tools = [t.strip() for t in tools_raw]
    else:
        tools = [t.strip() for t in str(tools_raw).split(",")]

    disallowed_raw = fm.get("disallowedTools", "")
    if isinstance(disallowed_raw, list):
        disallowed = [t.strip() for t in disallowed_raw]
    else:
        disallowed = [t.strip() for t in str(disallowed_raw).split(",")]

    has_write = "Write" in tools
    edit_blocked = "Edit" in disallowed

    # Source-modifying agents (Edit allowed) need CLAUDE.md
    if has_write and not edit_blocked:
        if fm.get("omitClaudeMd"):
            return False, "Agent can modify source (Write + Edit) — should NOT have omitClaudeMd"
        return True, "Source-modifying agent correctly omits omitClaudeMd"

    # Report-only writer (Write allowed, Edit blocked) or pure read-only:
    # both should have omitClaudeMd: true
    if fm.get("omitClaudeMd") is True:
        if has_write:
            return True, "Report-only writer correctly has omitClaudeMd: true"
        return True, "Read-only agent correctly has omitClaudeMd: true"
    return False, f"Agent '{fm.get('name')}' missing omitClaudeMd: true"


AGENT_MATCHERS = {
    "agent_tools_valid": agent_tools_valid,
    "agent_readonly_enforced": agent_readonly_enforced,
    "agent_bypass_permissions": agent_bypass_permissions,
    "agent_model_appropriate": agent_model_appropriate,
    "agent_has_skills": agent_has_skills,
    "agent_omit_claudemd": agent_omit_claudemd,
}
