# Layer Agent Prompts & Context Supervisor Integration

## How to Spawn Layer Agents

Each layer agent receives the path to its pre-computed JSON file:

```
Agent(
  subagent_type="elixir-xray:{agent-name}",
  prompt="Analyze the pre-computed data at {JSON_PATH}. Write findings to .claude/xray/layers/{layer}.md using the finding schema (YAML frontmatter with id, layer, category, title, severity, effort, automatable, artifact_types, evidence, frequency, confidence). Report ONLY issues found.",
  run_in_background=true,
  mode="bypassPermissions"
)
```

## Context Supervisor Integration

After ALL 6 layer agents complete, spawn the context-supervisor to compress:

```
Agent(
  subagent_type="context-supervisor",
  prompt="""
Compress X-Ray layer findings for synthesis.
Input directory: .claude/xray/layers/
Files to read: git-history.md, pr-reviews.md, code-docs.md, claude-config.md, sessions.md, architecture.md
Output: .claude/xray/layers/summary.md

Rules:
- Preserve ALL finding YAML frontmatter (id, severity, artifact_types)
- Remove verbose descriptions, keep only title + key evidence
- Note cross-layer patterns (same pattern in multiple layers)
- Deduplicate obvious repeats
- Target: < 200 lines total
""",
  mode="bypassPermissions"
)
```

The main context then reads ONLY `summary.md` — never the individual layer files.
This prevents context exhaustion when 6 layers produce 100+ findings.

## Agent ↔ Script Mapping

| Script | Produces | Agent Reads | Agent Writes |
|--------|----------|-------------|-------------|
| analyze-git-history.py | layers/git-history.json | git-history.json | layers/git-history.md |
| analyze-prs.py | layers/pr-reviews.json | pr-reviews.json | layers/pr-reviews.md |
| analyze-code.py | layers/code-docs.json | code-docs.json | layers/code-docs.md |
| analyze-config.sh | layers/claude-config.json | claude-config.json | layers/claude-config.md |
| analyze-sessions.py | layers/sessions/*.json | sessions-summary.json | layers/sessions.md |
| analyze-architecture.sh | layers/architecture.json | architecture.json | layers/architecture.md |

## Session Layer Special Handling

Layer 5 (sessions) is different — it needs ccrider MCP which is **only available
in the main context** (not in subagents).

**CRITICAL**: Do NOT spawn subagents to fetch sessions via ccrider. MCP tools
are not passed to spawned agents. The main context must:

1. Call `mcp__ccrider__list_recent_sessions(limit: 30)` (safe, ~1KB)
2. For each session (sequentially, in main context):
   - Fetch via `mcp__ccrider__get_session_messages(session_id, last_n: 200)`
   - Write result to `layers/sessions/_tmp_{id}.json`
   - Run Python scorer via Bash
   - Delete temp file
3. Run `analyze-sessions.py --mode aggregate` on all scored sessions
4. Session-analyzer agent reads the aggregate JSON

**Max 10 sessions** to avoid context exhaustion (each response is 5-50KB).

This differs from Phoenix plugin's `/session-scan` which uses haiku subagents —
those work because `/session-scan` is a skill with ccrider in the subagent prompt.
X-Ray agents don't have MCP access.
