"""Generate a native Codex skills plugin from the Claude Code source plugin."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .frontmatter import Frontmatter, parse_file
from .skill_transforms import (
    normalize_skill_name,
    rewrite_slash_commands,
    transform_frontmatter,
)

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SKILL_DIR_TOKEN_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/([A-Za-z0-9_./<>-]+)")
PLUGIN_ROOT_TOKEN_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
BARE_SIBLING_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])\.\./([a-z0-9-]+)/([A-Za-z0-9_./<>-]+)"
)
CANONICAL_SKILL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])plugins/elixir-phoenix/skills/"
    r"([a-z0-9-]+)/([A-Za-z0-9_./<>-]+)"
)
BARE_SKILL_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./:-])([a-z0-9-]+)/([A-Za-z0-9_./<>-]+)"
)
IGNORED_FILES = {".DS_Store"}
CLAUDE_HOOK_UNAVAILABLE = (
    "[Claude Code-only hook unavailable in the Codex skills-only plugin: {path}]"
)
CODEX_DESCRIPTION = (
    "Generated Elixir, Phoenix, LiveView, Ecto, Oban, testing, and security "
    "skills for Codex"
)


def _assert_ordered_markers(
    source: str, markers: tuple[str, ...], source_file: Path
) -> None:
    """Require each canonical marker exactly once and in the declared order."""
    positions: list[int] = []
    for marker in markers:
        if source.count(marker) != 1:
            raise ValueError(
                f"{source_file}: expected canonical marker exactly once: {marker}"
            )
        positions.append(source.index(marker))
    if positions != sorted(positions):
        raise ValueError(f"{source_file}: canonical marker order changed")

INVESTIGATE_BODY = """# Investigate Bug

Investigate Elixir/Phoenix bugs root-cause first. Reproduce or establish the
failing behavior before recommending a fix, and cite concrete paths and lines.

## Usage

```text
$phx-investigate Users can't log in after password reset
$phx-investigate FunctionClauseError in UserController.show
$phx-investigate Complex auth bug --parallel
```

Treat the text after the skill name as the bug description. `--parallel` asks
for independent investigation tracks when native Codex subagent tooling is
available; it is an optimization, never a requirement.

## Iron Laws

1. **Read the error literally first** — extract the exception, message, failing
   assertion, and first relevant application frame before theorizing.
2. **Check the obvious before going deep** — compile errors, missing migrations,
   atom/string mismatches, nil values, stale servers, and changeset errors explain
   many failures.
3. **Reproduce before proposing a fix** — run the smallest relevant test or
   controlled command and record its output. If reproduction is impossible,
   state exactly what evidence establishes the failure instead.
4. **Confirm the root cause with evidence** — distinguish the observed failure,
   the causal code path, and the proposed correction.
5. **Do not edit while investigating unless the user asks for a fix** — the
   investigation result is evidence and a recommendation, not an implicit patch.

## Workflow

### 1. Consult Existing Evidence

Search `.claude/solutions/`, recent diffs, tests, logs, and the literal error.
Do not block if `.claude/solutions/` does not exist.

### 2. Capture Runtime Context When Available

Tidewave is optional. If its tools are configured, use them for logs, source
locations, safe queries, or hypothesis checks. Otherwise use repository files,
`mix` commands, and local logs. Never fail or ask the user to install Tidewave
merely to continue an investigation.

### 3. Run Sanity Checks

Choose focused checks that fit the report, such as:

```bash
mix compile --warnings-as-errors
mix test test/path_test.exs --trace
```

Do not run migrations or other state-changing commands unless they are necessary,
safe for the fixture, and authorized by the user.

### 4. Reproduce Before Fixing

Capture the exact command, failure, and relevant output. Read
`references/error-patterns.md`, then inspect only the code needed to trace the
failure from entry point to cause.

### 5. Check the Obvious

Check saved files, atom/string keys, preload state, pattern matches, nil values,
return values, server restarts, and changeset errors. For silent LiveView form
failures, inspect `{:error, changeset}` and rendered validation errors before JS.

### 6. Trace and Test the Hypothesis

Use targeted searches, source reads, tests, or non-mutating diagnostics. Only add
temporary source diagnostics if the user explicitly authorizes edits, and remove
them before reporting. Cite `path:line` evidence for both the failing behavior
and the causal code.

If native Codex subagents are available and the bug genuinely spans independent
areas, delegate read-only tracks by concern. Otherwise perform the same tracks
sequentially in this session. Do not require named custom agents.

### 7. Report

Use `references/investigation-template.md`. Include:

- reproduction or evidence establishing the failure;
- root cause, not merely the symptom;
- relevant paths and lines;
- confidence and any unverified assumptions;
- the smallest safe fix or next diagnostic step.

Route follow-up work with `$phx-quick`, `$phx-plan`, or `$phx-compound` when
appropriate. Do not invoke another skill unless the user asks you to continue.

## References

- `references/error-patterns.md` — common errors and checklist
- `references/investigation-template.md` — output format
- `references/debug-commands.md` — debug commands and common fixes
"""

REVIEW_BODY = """# Review Elixir/Phoenix Code

Perform an evidence-based, read-only review of changed code. Find and explain
issues; do not edit files, create tasks, or fix findings.

## Usage

```text
$phx-review
$phx-review test
$phx-review security
$phx-review .claude/plans/auth/plan.md
$phx-review --no-requirements
```

Treat the text after the skill name as a focus area, issue identifier, or path to
a plan/specification.

## Iron Laws

1. **Review is read-only** — inspect and report; never modify the worktree.
2. **Scope to changed code** — distinguish new defects from pre-existing issues.
3. **Every finding needs evidence** — cite a path and line, explain impact, and
   describe the concrete failure mode.
4. **Check requirements when available** — unmet requirements affect the verdict.
5. **Deduplicate and prioritize** — one root cause is one finding, with the
   highest justified severity.
6. **Do not require custom agents, hooks, MCP, or unavailable task APIs** — use
   optional runtime capabilities only when present.

## Workflow

### 1. Establish Scope

Determine the merge base or user-specified base, then inspect:

```bash
git status --short
git diff --name-only <base>...HEAD
git diff --stat <base>...HEAD
git diff <base>...HEAD -- <changed-files>
```

Do not assume `HEAD~5` is the correct base. Include uncommitted changes when the
user asks to review the current worktree. Record the chosen scope in the result.

### 2. Load Requirements

Unless `--no-requirements` is set, look for an explicit plan/spec path, current
conversation requirements, a branch or commit issue identifier, or the latest
relevant plan. Use available integrations or `gh issue view` when configured;
otherwise mark requirements `NOT AVAILABLE` and continue.

Read `references/requirements-detection.md` for detection order. Never let a
missing Linear, GitHub, hook, or MCP integration block code review.

### 3. Review by Concern

Select only concerns relevant to the diff:

- Elixir/Phoenix correctness and idioms;
- Ecto queries, changesets, transactions, migrations, and N+1 risks;
- LiveView lifecycle, reconnect, forms, streams, and assigns;
- authentication, authorization, secrets, and input handling;
- Oban idempotency, retries, uniqueness, and transaction boundaries;
- tests, regressions, and verification gaps;
- deployment/runtime configuration when those files changed.

Native Codex subagents may run independent read-only concern tracks in parallel.
Use generic subagents with the complete diff scope and return findings to this
session; do not depend on separately installed named agents. If subagents are
unavailable or unnecessary, run every selected concern sequentially here. A
sequential review is fully valid.

### 4. Verify Findings

For each candidate:

1. Confirm it is in changed code or label it `PRE-EXISTING`.
2. Trace the actual runtime or data-flow consequence.
3. Check nearby tests and requirements.
4. Remove style-only noise and speculative concerns.
5. Merge duplicates under the clearest root cause.

Run targeted read-only verification when it materially changes confidence. Do
not alter files or suppress failures. If a check cannot run, report that clearly.

### 5. Report a Verdict

Return one verdict:

- `PASS`
- `PASS WITH WARNINGS`
- `REQUIRES CHANGES`
- `BLOCKED`

List findings in descending severity as `BLOCKER`, `WARNING`, or `SUGGESTION`.
Each finding must include `path:line`, evidence, impact, and the smallest
appropriate correction. Add requirements coverage before findings; any `UNMET`
requirement requires `REQUIRES CHANGES`.

If there are no findings, say so explicitly and list residual risks or checks not
run. Stop after presenting the review. Suggest `$phx-triage`, `$phx-plan`, or
`$phx-compound` as optional next steps without invoking them automatically.

## References

- `references/requirements-detection.md` — requirements source and coverage rules
- `references/agent-spawning.md` — Codex concern selection and optional parallelism
"""

REVIEW_AGENT_REFERENCE = """# Codex Review Execution Reference

`$phx-review` works without separately installed custom agents. Native Codex
subagents are an optional performance optimization, not a correctness dependency.

## Concern Selection

| Concern | Select when |
|---|---|
| Elixir/Phoenix | Always |
| Security | Auth, session, password, token, upload, or input code changed |
| Testing | Tests changed, public behavior changed, or regression coverage is absent |
| Ecto/LiveView | Relevant schemas, queries, migrations, LiveViews, or components changed |
| Oban | Worker or queue code changed |
| Deployment | Dockerfile, release, `fly.toml`, or runtime configuration changed |
| Requirements | A plan, specification, or issue is available |

## Parallel Mode

When native subagent tooling is available, delegate independent concerns to
generic read-only workers. Give each worker the same base ref, changed-file list,
requirements context, and instruction to return evidence-backed findings with
`path:line` citations. Keep one worker per concern and deduplicate in the parent.

When subagents are unavailable, expensive, or unnecessary, review the same
concerns sequentially in the current session. Never treat a sequential run as a
failed review and never require plugin-root agent definitions or Claude task APIs.

## Output Contract

Return findings to the current session. Do not write files unless the user asks
for a persisted report. The review remains read-only and ends after the verdict.
"""

REVIEW_REQUIREMENTS_REFERENCE = """# Requirements Detection

Use this order and stop at the first usable source:

| Priority | Source | Detection | Fetch |
|---|---|---|---|
| 1 | Explicit path | User input ends in `.md` and the file exists | Read the file |
| 2 | Explicit issue ID | Input matches `^[A-Z]+-\\d+$` or `^#?\\d+$` | Available Linear integration or `gh issue view` |
| 3 | Conversation context | Requirements already appear in the session | Reuse them |
| 4 | Branch name | Branch contains an issue-like identifier | Available integration or `gh` |
| 5 | Commit subjects | Recent subjects contain an identifier | Available integration or `gh` |
| 6 | Latest plan | Relevant `.claude/plans/*/plan.md` exists | Read the file |
| 7 | None | No source found | Mark `NOT AVAILABLE` and continue |

Never let a missing Linear, GitHub, MCP, hook, or network integration block the
review. Record the selected requirements source and any fetch failure. Do not
silently substitute guessed requirements.

## Coverage Output

For each acceptance criterion, report `MET`, `PARTIAL`, `UNMET`, or `UNCLEAR`
with changed-file evidence. Put requirements coverage before code-quality
findings. Any `UNMET` criterion requires a `REQUIRES CHANGES` verdict; `PARTIAL`
without `UNMET` downgrades `PASS` to `PASS WITH WARNINGS`.
"""


def _replace_anchored(source: str, old: str, new: str, source_file: Path) -> str:
    """Replace one canonical block, failing loudly when its structure drifts."""
    if source.count(old) != 1:
        raise ValueError(f"{source_file}: portable plan/work overlay anchor changed")
    return source.replace(old, new)


def _replace_section(
    source: str, start_heading: str, end_heading: str, replacement: str, source_file: Path
) -> str:
    """Replace one bounded section and reject missing, duplicate, or reordered headings."""
    if source.count(start_heading) != 1 or source.count(end_heading) != 1:
        raise ValueError(f"{source_file}: portable plan/work section anchor changed")
    start = source.index(start_heading)
    end = source.index(end_heading)
    if start >= end:
        raise ValueError(f"{source_file}: portable plan/work heading order changed")
    return source[:start] + replacement + source[end:]


def _replace_tail(source: str, heading: str, replacement: str, source_file: Path) -> str:
    """Replace from one unique heading through end-of-file."""
    if source.count(heading) != 1:
        raise ValueError(f"{source_file}: portable plan/work tail anchor changed")
    return source[: source.index(heading)] + replacement


def _portable_plan_work_overlay(
    source_file: Path, current: "SkillSource"
) -> str | None:
    """Remove executable Claude-only dependencies from plan/work workflows."""
    relative = source_file.relative_to(current.source_dir).as_posix()
    if current.target_name not in {"phx-plan", "phx-work"}:
        return None

    source = (
        current.frontmatter.body
        if relative == "SKILL.md"
        else source_file.read_text(encoding="utf-8")
    )

    if current.target_name == "phx-plan" and relative == "SKILL.md":
        required = ("# Plan Elixir/Phoenix Feature", "## Workflow", "## CRITICAL: After Writing the Plan")
        if not all(marker in source for marker in required):
            raise ValueError(f"{source_file}: portable plan overlay anchors changed")
        source = _replace_anchored(
            source,
            "Plan a feature by spawning Elixir specialist agents, then output\nstructured plan with checkboxes.",
            "Plan a feature by researching the relevant Elixir/Phoenix concerns, then\noutput a structured plan with checkboxes.",
            source_file,
        )
        source = _replace_anchored(
            source,
            "1. Spawns Elixir specialist agents for research",
            "1. Covers relevant concerns through resumable research tracks",
            source_file,
        )
        source = _replace_anchored(
            source,
            '- `$ARGUMENTS` = Feature description, review file, or existing plan',
            "- Text after the skill name = feature description, review file, or existing plan",
            source_file,
        )
        source = _replace_anchored(source, """4. **Runtime context** (Tidewave) — Gather live schemas, routes,
   and warnings before spawning agents (direct path only — the
   research orchestrator gathers its own)
5. **Spawn research** — Selective, based on need. **0–2 agents**:
   spawn directly in parallel. **3+ agents** (broad multi-context
   feature): spawn ONE `planning-orchestrator` to run and compress
   the fan-out, then read only its digest and
   `summaries/consolidated.md`. Create a Claude Code task per spawn:
   `TaskCreate({subject: "{Agent} research", activeForm: "Researching..."})`,
   mark `in_progress` on spawn, `completed` when done
6. **Wait for ALL agents** — Do NOT proceed until all return
   "completed". NEVER write plan while any agent is still running""", """4. **Create research state** — Before research, create
   `.claude/plans/{slug}/scratchpad.md` with a concern-track checklist
5. **Gather optional runtime context** — Only when Tidewave tools are independently
   configured and exposed; otherwise inspect source, routes, schemas, and tests
6. **Research selectively** — Cover only relevant concerns. Native generic
   subagents may run independent tracks in parallel, but they are optional.
   Without them, run every selected track sequentially in this session and
   save evidence under `.claude/plans/{slug}/research/`
7. **Finish ALL research tracks** — Maintain the scratchpad checklist,
   marking each selected track `[x]` only after its evidence is captured.
   NEVER write the plan while any selected track remains unchecked""", source_file)
        source = _replace_anchored(
            source,
            "1. **Gather context** — File path (skip to agents), brainstorm",
            "1. **Gather context** — File path (skip to research), brainstorm",
            source_file,
        )
        source = _replace_anchored(source, "7. **Breadboard** (LiveView) — System map for multi-page features\n8. **Completeness check**", "8. **Breadboard** (LiveView) — Produce the system map from collected evidence\n9. **Completeness check**", source_file)
        source = _replace_anchored(source, "9. **Split decision**", "10. **Split decision**", source_file)
        source = _replace_anchored(source, "10. **Generate plan**", "11. **Generate plan**", source_file)
        source = _replace_anchored(source, "    Also create `plans/{slug}/scratchpad.md` for decisions and dead-ends", "    Reuse `.claude/plans/{slug}/scratchpad.md` for decisions and dead-ends", source_file)
        source = _replace_anchored(source, "11. **Self-check**", "12. **Self-check**", source_file)
        source = _replace_anchored(source, "12. **Present and ask**", "13. **Present and ask**", source_file)
        source = _replace_section(source, "### --existing Mode (Deepening)", "## Iron Laws", """### --existing Mode (Deepening)

Enhance an existing plan without relying on named agents:

1. Load the plan and create or update `.claude/plans/{slug}/scratchpad.md`
2. Identify thin sections and add a checklist of relevant concern tracks
3. Complete every track in this session, sequentially by default; generic workers
   are optional only for independent tracks and must write evidence under
   `.claude/plans/{slug}/research/`
4. Produce breadboarding and infrastructure notes directly from the gathered
   evidence, independent of whether workers were used
5. Add implementation detail, resolve spikes, and strengthen verification
6. Present a diff summary; never delete or silently rewrite existing tasks

""", source_file)
        source = _replace_anchored(
            source,
            "2. Use `AskUserQuestion` with options:",
            "2. Ask the user a normal conversational question with these options:",
            source_file,
        )
        source = _replace_anchored(source, "6. **Do NOT spawn hex-library-researcher for existing deps**", "6. **Do NOT run a library-selection track for existing dependencies**", source_file)
        source = _replace_anchored(
            source,
            "3. **Spawn agents selectively** — Only relevant, not all",
            "3. **Select research tracks narrowly** — Only relevant concerns, not all",
            source_file,
        )
        source = _replace_anchored(
            source,
            "4. **NEVER write plan while agents still running**",
            "4. **NEVER write the plan while selected research tracks remain incomplete**",
            source_file,
        )

    elif current.target_name == "phx-plan" and relative == "references/planning-workflow.md":
        required = ("## Agent Spawning", "## Waiting for Agents", "## Presenting the Plan")
        if not all(marker in source for marker in required):
            raise ValueError(f"{source_file}: portable planning reference anchors changed")
        portable = """## Research Tracks

Select only the concerns the feature needs. Use the canonical selection table
below as concern expertise, not as a requirement for installed named agents.

- `quick`: existing-project-patterns track
- `standard`: patterns plus 1-2 relevant concern tracks
- `deep`: patterns plus all relevant concern and external-research tracks

Native generic subagents are an optional optimization. Give each one a focused
scope and require it to write evidence to `.claude/plans/{slug}/research/`.
When subagents are unavailable, perform the same tracks sequentially in this
session using repository search, dependency documentation, web research when
needed, and optional Tidewave tools when independently configured.

Before any research, create `.claude/plans/{slug}/scratchpad.md` and track progress there:

```markdown
## Research checklist
- [x] Existing project patterns — research/patterns.md
- [ ] Ecto/data design
- [ ] LiveView interaction design
```

Do not generate the plan until every selected track is `[x]`. If a track fails,
record the failure and complete it in the current session instead of dropping
its coverage. Preserve source paths, line evidence, alternatives, and confidence.

## Concern Selection

| Condition | Research concern |
|---|---|
| Always | Existing project patterns and context boundaries |
| NEW library not in `mix.exs` | Hex/library evaluation |
| UI, form, live, real-time | LiveView architecture |
| Database, schema, table | Ecto/data design |
| Job, worker, async, queue | Oban behavior |
| GenServer, process, state | OTP design |
| Auth, permission, secrets | Security |
| Unfamiliar technology | Primary docs and web evidence |
| Function signature changes | Call-site tracing |

Do not research an existing dependency as if selecting a new library. Inspect
its installed source/docs or optional runtime docs instead.

## Completing Research

Wait for every optional subagent to finish, collect its output, and complete any
missing or failed track sequentially. The checklist, research files, and
scratchpad make this state resumable without a runtime task API. Breadboarding
and infrastructure output are synthesized from this evidence, not delegated to
or made conditional on any named worker.

"""
        source = _replace_section(source, "## Agent Spawning", "## Infrastructure Knowledge Persistence", portable, source_file)
        source = _replace_anchored(
            source,
            "Check `$ARGUMENTS` for a path containing `interview.md`",
            "Check the text after the skill name for a path containing `interview.md`",
            source_file,
        )
        source = _replace_anchored(source, "Use interview content as input for agent spawning (depth detection still applies)", "Use interview content for concern-track selection (depth detection still applies)", source_file)
        source = _replace_anchored(source, "**Depth determines agent count AND plan detail:**", "**Depth determines research track counts, concerns, and plan detail:**", source_file)
        source = _replace_anchored(source, "| Depth      | Agents             | Clarification           | Plan Detail", "| Depth      | Research tracks / concerns | Clarification           | Plan Detail", source_file)
        source = _replace_anchored(source, "| `quick`    | 1 (patterns only)", "| `quick`    | 1 pattern track", source_file)
        source = _replace_anchored(source, "| `standard` | 2-3 specialists", "| `standard` | 2-3 concern tracks", source_file)
        source = _replace_anchored(source, "| `deep`     | 4+ (full research)", "| `deep`     | 4+ full research tracks", source_file)
        source = _replace_anchored(source, "When Explore agents discover **project infrastructure**", "When completed research discovers **project infrastructure**", source_file)
        source = _replace_anchored(
            source,
            "Then use `AskUserQuestion`:",
            "Then ask the user a normal conversational question:",
            source_file,
        )
        source = _replace_anchored(source, "Do NOT use subagent_type names", "Do NOT use runtime worker names", source_file)
        source = _replace_anchored(source, "If liveview-architect was spawned, its report should include\naffordance tables. Use these to build a system map.", "Synthesize affordance tables and the system map from the completed research-track evidence.", source_file)
        source = _replace_tail(source, "## Deepening an Existing Plan (--existing mode)", """## Deepening an Existing Plan (--existing mode)

1. Load the existing plan and create or update its scratchpad checklist
2. Select thin sections as concern tracks; complete them sequentially in the
   current session by default
3. Optionally use native generic workers only for independent tracks, with
   bounded prompts and `.claude/plans/{slug}/research/{topic}.md` output
4. Synthesize breadboarding and infrastructure notes from the gathered evidence
5. Add detail and verification without deleting or silently changing tasks
6. Present a diff summary and stop for user review

Deepening is useful for unfamiliar code, external integrations, security-sensitive
work, and unresolved spikes. Preserve existing scope and decisions.
""", source_file)

    elif current.target_name == "phx-plan" and relative == "references/agent-selection.md":
        _assert_ordered_markers(
            source,
            (
                "# Agent Selection Guidelines",
                "## When to Spawn Which Agents",
                "## When to Spawn hex-library-researcher",
                "## When to Spawn web-researcher",
                "## When to Spawn call-tracer",
                "## When to Ask Clarifying Questions",
            ),
            source_file,
        )
        source = """# Concern Track Selection

Select research by feature concerns, not named agents.

| Feature type | Required concern tracks |
|---|---|
| CRUD or data-heavy | Existing patterns, Ecto/data design |
| Interactive or real-time UI | Existing patterns, LiveView architecture |
| External integration | Existing patterns, OTP boundaries; library evaluation only for a new dependency |
| Background processing | Existing patterns, Oban behavior, OTP supervision |
| Authentication/permissions | Existing patterns, security and negative paths |
| Refactoring/signature changes | Existing patterns, call-site tracing |

Run selected tracks sequentially in the current session by default. Native
generic workers are optional only for independent tracks.

## Dependency Research

Evaluate libraries only when adding a dependency absent from `mix.exs` or
comparing replacements. For an existing dependency, inspect `deps/{library}`
and its installed/version-matched documentation. Optional Tidewave dependency
documentation tools may be used only when independently configured and exposed.

## External Research

Use primary documentation and focused web research for unfamiliar technology,
known issues, or infrastructure questions. Capture URLs, findings, alternatives,
and confidence in `.claude/plans/{slug}/research/`.

## Clarification

Ask at most three focused questions when scope, integration points, performance,
or competing valid approaches cannot be resolved from repository evidence.
"""

    elif current.target_name == "phx-plan" and relative == "references/plan-template.md":
        source = _replace_anchored(source, "Include when the liveview-architect produced a breadboard.", "Include for multi-page LiveView work after synthesizing the research evidence.", source_file)
        source = _replace_section(source, "## Task Agent Annotations", "## Files to Follow as Patterns", """## Concern Annotations

Annotations are portable concern and verification labels, not worker identities:

| Annotation | Concern |
|---|---|
| `[ecto]` | Schemas, migrations, queries |
| `[liveview]` | LiveView, real-time UI, PubSub |
| `[oban]` | Background jobs and workers |
| `[otp]` | Processes and supervision |
| `[security]` | Authentication, authorization, tokens |
| `[test]` | Tests, mocks, factories |
| `[direct]` | General implementation and wiring |

""", source_file)

    elif current.target_name == "phx-work" and relative == "SKILL.md":
        required = ("# Work", "## Step 3: Load, Create Task List, and Resume", "## Step 5: Completion")
        if not all(marker in source for marker in required):
            raise ValueError(f"{source_file}: portable work overlay anchors changed")
        portable = """**Use the plan file as the portable task list.** For every unchecked item,
preserve its `- [ ] [Pn-Tm]` row and ordering. At the start of a task, set its
phase to `[IN_PROGRESS]` and append a `Started:` entry to
`.claude/plans/{slug}/progress.md`. Mark the plan checkbox `[x]` only after
verification passes, then append the completion evidence to `progress.md`.

Dependencies remain explicit in phase order: do not start a later phase while
an earlier phase has unchecked non-blocked tasks. This checklist is the progress
UI, durable state, and resume mechanism; no runtime task API is required.

"""
        source = _replace_section(
            source,
            "**Create Claude Code tasks**",
            "With `--from P2-T3`",
            portable,
            source_file,
        )
        source = _replace_anchored(source, '1. **Start task**: `TaskUpdate({taskId, status: "in_progress"})`', "1. **Start task**: mark its phase `[IN_PROGRESS]` and log the start in `.claude/plans/{slug}/progress.md`", source_file)
        source = _replace_anchored(source,
            "2. **Route** by `[agent]` annotation (see `${CLAUDE_SKILL_DIR}/references/execution-guide.md`)",
            "2. **Apply concern guidance** from the annotation and its required verification (see `${CLAUDE_SKILL_DIR}/references/execution-guide.md`); it never selects a named worker",
            source_file,
        )
        source = _replace_anchored(
            source,
            "3. **Plan checkboxes ARE the state** -- `[x]` = done, `[ ]` = pending.\n   No separate JSON state files. Resume by reading the plan.",
            "3. **Plan checkboxes ARE the state** -- `[x]` = done; `[ ]` = pending\n   unless the row is visibly tagged `[BLOCKED]`. No separate JSON state files.\n   Resume by reading the plan.",
            source_file,
        )
        source = _replace_anchored(source,
            "5. **Complete task**: Mark checkbox `[x]` on pass, **append\n   implementation note** inline, AND\n   `TaskUpdate({taskId, status: \"completed\"})`. Example:",
            "5. **Complete task**: Mark checkbox `[x]` on pass, **append\n   implementation note** inline, and log verification evidence in `progress.md`. Example:",
            source_file,
        )
        source = _replace_anchored(source, "**Parallel groups**: Tasks under `### Parallel:` header spawn\nas background subagents.", "**Parallel groups**: Tasks under `### Parallel:` may use native generic workers only when independent; otherwise execute them sequentially in the current session.", source_file)
        source = _replace_anchored(
            source,
            "for spawning pattern, prompt template, and checkpoint flow.",
            "for the optional-worker pattern, sequential fallback, and checkpoint flow.",
            source_file,
        )
        source = _replace_anchored(source, "  (format is checked by PostToolUse hook automatically)", "  and `mix format --check-formatted <changed_files>`", source_file)
        source = _replace_anchored(source, "- Per-feature (Tidewave): behavioral smoke test via `project_eval`\n  (create record, fetch, verify -- see execution-guide.md)", "- Per-feature: when Tidewave tools are independently configured and exposed, use a behavioral runtime smoke test; otherwise run a focused repository test and a local/manual smoke check (see execution-guide.md)", source_file)
        source = _replace_anchored(source, "The PostToolUse hook checks formatting but does NOT modify files —\nrun `mix format` explicitly during verification or before committing.", "No hook is assumed. Run `mix format` explicitly during verification and\n`mix format --check-formatted <changed_files>` before completing each task.", source_file)
        source = _replace_anchored(source, "Summarize results with `AskUserQuestion`:", "Summarize results, then ask the user a normal conversational question:", source_file)
        source = _replace_anchored(source, "3. **Commit changes** (`/commit`), 4. **Continue manually**.", "3. **Create a git commit** with the platform's native git workflow, 4. **Continue manually**.", source_file)
        source = _replace_anchored(source, "Execute each unchecked task (`- [ ] [Pn-Tm][agent] Description`):", "Execute each unchecked task (`- [ ] [Pn-Tm][concern] Description`):", source_file)
        source = _replace_anchored(source, "Find first unchecked task by `[Pn-Tm]` ID.", "Select the first unchecked task not tagged `[BLOCKED]`. Stop if an unresolved\n`[BLOCKED]` task precedes it unless `--skip-blockers` is explicit.\n`--skip-blockers` skips only tagged blocked rows; `--from <blocked-id>`\nexplicitly retries that row and clears `[BLOCKED]` when starting.", source_file)
        source = _replace_anchored(source, "6. **On failure**: retry up to 3 times, then create BLOCKER\n   and write DEAD-END to scratchpad (see error-recovery.md)", "6. **On failure**: retry up to 3 times, then keep the row unchecked and\n   append `[BLOCKED]`, optionally mark its phase `[BLOCKED]`, record the\n   blocker in `progress.md`, write a DEAD-END to scratchpad, and stop by\n   default. Continue only when `--skip-blockers` was explicitly supplied", source_file)

    elif current.target_name == "phx-work" and relative == "references/execution-guide.md":
        required = ("## Task Routing", "## Parallel Task Execution", "## Checkpoint Pattern")
        if not all(marker in source for marker in required):
            raise ValueError(f"{source_file}: portable execution reference anchors changed")
        portable = """### Execution Pattern

Native generic subagents are optional for tasks that are independent and touch
different files. Give each worker the full task text, locations, constraints,
and verification contract, and wait for all workers before checkpointing.
Do not require annotation-named custom agents.

If native subagents are unavailable, execute every task sequentially in plan
order in this session. This fallback is complete: apply the same domain guidance,
verification, checkbox update, implementation note, and progress-log entry for
each task. Never skip a task because parallel execution is unavailable.

"""
        source = _replace_section(source, "### Spawning Pattern", "### Waiting and Checkpoint", portable, source_file)
        source = _replace_anchored(source, "Tasks under `### Parallel:` header execute via subagents:", "Tasks under `### Parallel:` are eligible for optional generic workers or sequential execution:", source_file)
        source = _replace_anchored(source, "After spawning, wait for ALL agents to complete, then run phase checkpoint:", "If optional workers were used, wait for all of them; otherwise, after the sequential tasks complete, run the phase checkpoint:", source_file)
        source = _replace_section(source, "## Task Routing", "## Parallel Task Execution", """## Concern Guidance

Annotations such as `[ecto]`, `[liveview]`, `[oban]`, `[otp]`, `[security]`,
`[test]`, and `[direct]` describe implementation concerns and required checks.
They are not custom-agent identities and never route work to a named worker.
Execute in the current session by default. A native generic worker is optional
only for an independent task with disjoint files and a complete verification
contract.

| Annotation | Guidance and required verification |
|---|---|
| `[ecto]` | Ecto safety; migrate/rollback as applicable plus focused tests |
| `[liveview]` | LiveView lifecycle/security; focused LiveView test plus local/manual UI smoke |
| `[oban]` | Idempotency and args; worker test plus enqueue behavior check |
| `[otp]` | Supervision/concurrency; focused process tests |
| `[security]` | Authorization/input handling; negative-path tests and audit |
| `[test]` | Test quality; run the named focused test |
| `[direct]` | General implementation; format and compile plus affected test |

Legacy unannotated tasks use their subject matter to select the same concern
guidance, never a worker identity. Security requirements take priority.

""", source_file)
        source = _replace_anchored(source, "[Task Routing](#task-routing)", "[Concern Guidance](#concern-guidance)", source_file)
        source = _replace_anchored(source,
            "When Tidewave is available, also call\n`mcp__tidewave__get_logs level: :error` after code changes",
            "When Tidewave is independently configured, optionally inspect error-level runtime logs after code changes",
            source_file,
        )
        source = _replace_section(source, "### Per-Feature Behavioral Smoke Test (Tidewave)", "### After ALL Phases (Final Gate)", """### Per-Feature Behavioral Smoke Test

Use Tidewave runtime tools only when they are independently configured and
exposed in the current environment. If available, exercise the main behavior
and inspect errors without persisting test data. Tidewave is optional, never a
completion prerequisite.

Without Tidewave, run all applicable fallbacks:

1. `mix test test/path/to/affected_test.exs`
2. Exercise the public repository/context function in a local test or `mix run`
3. For UI work, start the app locally and perform a manual browser smoke check;
   if that is impossible, record the unverified manual step explicitly

""", source_file)
        source = _replace_anchored(source,
            "2. **Complete Claude Code task**: `TaskUpdate({taskId, status: \"completed\"})`\n   This updates the live progress indicator visible in the UI.",
            "2. **Log completion**: Append the task ID, changed files, and verification result to `progress.md`.",
            source_file,
        )
        source = _replace_anchored(source,
            "5. **Start next task**: `TaskUpdate({nextTaskId, status: \"in_progress\"})`\n   then move to next unchecked task",
            "5. **Start next task**: Log its start, then select the next unchecked\n   non-`[BLOCKED]` task. Stop if an unresolved blocker precedes it unless\n   `--skip-blockers` was explicitly supplied",
            source_file,
        )
        source = _replace_anchored(source, "4. **Log progress**: Append to `.claude/plans/{feature}/progress.md`\n", "", source_file)
        source = _replace_tail(
            source,
            "### Escalate to BLOCKER",
            """### Escalate to BLOCKER

After 3 failures, keep the plan row unchecked, append `[BLOCKED]`, and
optionally mark its phase `[BLOCKED]`. Append the attempts and error evidence to
`.claude/plans/{slug}/progress.md`, write the dead end to `scratchpad.md`, and
stop by default. Continue to later work only with explicit `--skip-blockers`.

```markdown
- [ ] [P2-T3][ecto] [BLOCKED] Implement register_user/1

## BLOCKER: P2-T3
**Attempts**: 3
**Error history**: {commands and first actionable failures}
**Suggested next action**: {evidence-based recommendation}
```

Retry this task explicitly with the native `phx-work` invocation and
`--from P2-T3`; clear `[BLOCKED]` when starting that retry.
""",
            source_file,
        )

    elif current.target_name == "phx-work" and relative == "references/file-formats.md":
        source = _replace_anchored(source, "**Task format**: `- [ ] [Pn-Tm][agent] Description`", "**Task format**: `- [ ] [Pn-Tm][concern] Description`", source_file)
        source = _replace_anchored(source, "- `[agent]`: Agent annotation (for routing)", "- `[concern]`: Guidance and verification annotation; never a worker identity", source_file)
        source = _replace_anchored(source, "## Phase 1: {Phase Name} [COMPLETED|IN_PROGRESS|PENDING]", "## Phase 1: {Phase Name} [COMPLETED|IN_PROGRESS|PENDING|BLOCKED]", source_file)
        source = _replace_anchored(source, "- [ ] [P1-T3][direct] Another pending task", "- [ ] [P1-T3][direct] [BLOCKED] Blocked task (remains unchecked)", source_file)
        source = _replace_anchored(source, "**Task format**: `- [ ] [Pn-Tm][concern] Description`", "**Task format**: `- [ ] [Pn-Tm][concern] Description`; blocked tasks use `- [ ] [Pn-Tm][concern] [BLOCKED] Description`", source_file)
        source = _replace_anchored(source, "**Notes**: {any observations}", "**Started**: {date and time task execution began}\n**Notes**: {any observations}\n\nProgress evidence is append-only: never rewrite or delete prior Started, PASS, FAIL, retry, or blocker records.", source_file)

    elif current.target_name == "phx-work" and relative == "references/error-recovery.md":
        source = _replace_anchored(source, "4. **After 3 retries**: Log blocker, skip task, continue", "4. **After 3 retries**: Mark the blocker in both plan and progress, write the scratchpad DEAD-END, and stop. Skip and continue only with explicit `--skip-blockers`", source_file)
        source = _replace_anchored(source, "## BLOCKER: Task could not be completed", "## BLOCKER: P2-T3 — Task could not be completed", source_file)
        source = _replace_anchored(source, "**Task ID**: P2-T3", "**Plan task**: `- [ ] [P2-T3][ecto] BLOCKED — Implement register_user/1`", source_file)
        source = _replace_anchored(source, "`- [ ] [P2-T3][ecto] BLOCKED — Implement register_user/1`", "`- [ ] [P2-T3][ecto] [BLOCKED] Implement register_user/1`", source_file)
        source = _replace_anchored(source, "## Recovery After BLOCKER", "By default, return control after recording this state. Only `--skip-blockers` may advance to a later task.\n\n## Recovery After BLOCKER", source_file)

    elif current.target_name == "phx-work" and relative == "references/resume-strategies.md":
        source = _replace_anchored(source, "- `[ ]` = pending", "- `[ ]` = pending; `[ ] ... [BLOCKED] ...` = blocked and still incomplete", source_file)
        source = _replace_anchored(source, "- Phase status `[COMPLETED|IN_PROGRESS|PENDING]` tracks phase progress", "- Phase status `[COMPLETED|IN_PROGRESS|PENDING|BLOCKED]` tracks phase progress", source_file)
        source = _replace_anchored(source, "- BLOCKERs in progress file track failed tasks", "- `[BLOCKED]` on the plan row is authoritative; progress records preserve blocker evidence", source_file)
        source = _replace_anchored(source, "/phx:work  # Find most recent IN_PROGRESS plan, resume from first [ ]", "/phx:work  # Resume at first unchecked non-[BLOCKED] task; stop if an earlier blocker exists", source_file)
        source = _replace_anchored(source, "Skips directly to P2-T3 regardless of earlier unchecked tasks.", "Targets P2-T3 regardless of earlier unchecked tasks. If it is `[BLOCKED]`, this explicitly retries it and clears the tag when starting.", source_file)
        source = _replace_anchored(source, "Continues past tasks that previously failed with BLOCKER status.", "Skips rows visibly tagged `[BLOCKED]`; it does not infer blockers from prose or progress history.", source_file)
        source = _replace_anchored(source, "No state file to parse. Just find first `[ ]` and continue.", "No state file to parse. Select the first unchecked row not tagged `[BLOCKED]`, but stop when an unresolved blocker precedes it unless `--skip-blockers` was supplied.", source_file)
        source = _replace_anchored(
            source,
            "- All tasks before the target should be `[x]` in plan\n- If earlier tasks are unchecked, warn and ask user:",
            "- Tasks before the target must be `[x]`, or visibly `[BLOCKED]` when\n  `--skip-blockers` was explicitly supplied\n- If another earlier task is unchecked, warn and ask the user:",
            source_file,
        )

    elif current.target_name == "phx-work" and relative == "references/harness-patterns.md":
        source = _replace_section(source, "## Action Verification Pattern", "## Anti-Pattern: Unstructured Retry Loop", """## Action Verification Pattern

Portable targets assume no lifecycle hooks. Verify actions explicitly after
each edit and use command output as feedback:

```bash
mix format --check-formatted <changed_files>
mix compile --warnings-as-errors
mix test <affected_test_files>
mix credo --strict
```

For auth/security changes, also search the changed files for unsafe atom
creation and untrusted raw HTML, then run negative-path authorization tests.
For repeated failures, capture the exact command and first error in the
scratchpad before trying a different approach.

The loop is: edit, run the explicit command, read its concrete failure, fix the
root cause, and rerun the same command. Do not rely on implicit automation.

""", source_file)

    else:
        return None

    return source


@dataclass(frozen=True)
class SkillSource:
    source_dir: Path
    source_name: str
    target_name: str
    frontmatter: Frontmatter


def _plugin_manifest(source_plugin_dir: str | Path) -> dict:
    source_file = Path(source_plugin_dir) / ".claude-plugin" / "plugin.json"
    try:
        source = json.loads(source_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{source_file}: invalid or missing source manifest") from error

    name = source.get("name")
    version = source.get("version")
    if not isinstance(name, str) or not name:
        raise ValueError(f"{source_file}: missing string field `name`")
    if not isinstance(version, str) or not version:
        raise ValueError(f"{source_file}: missing string field `version`")

    return {
        "name": name,
        "version": version,
        "description": CODEX_DESCRIPTION,
        "skills": "./skills/",
        "interface": {
            "displayName": "Elixir/Phoenix Skills",
            "shortDescription": "Generated Elixir and Phoenix development workflows",
        },
    }


def discover_skills(source_plugin_dir: str | Path) -> list[SkillSource]:
    """Read all canonical skills and reject invalid or colliding target names."""
    skills_dir = Path(source_plugin_dir) / "skills"
    if skills_dir.is_symlink() or not skills_dir.is_dir():
        raise ValueError(f"{skills_dir}: canonical skills must be a real directory")
    for source_path in sorted(skills_dir.rglob("*")):
        if source_path.is_symlink():
            raise ValueError(f"{source_path}: symlinks are not supported in skills")
        if not source_path.is_dir() and not source_path.is_file():
            raise ValueError(f"{source_path}: special files are not supported in skills")

    discovered: list[SkillSource] = []
    names: dict[str, Path] = {}

    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        frontmatter = parse_file(skill_file)
        source_name = frontmatter.data.get("name")
        description = frontmatter.data.get("description")
        if not isinstance(source_name, str) or not source_name:
            raise ValueError(f"{skill_file}: missing string frontmatter field `name`")
        if not isinstance(description, str) or not description:
            raise ValueError(
                f"{skill_file}: missing string frontmatter field `description`"
            )

        target_name = normalize_skill_name(source_name)
        if len(target_name) > 64 or not SKILL_NAME_RE.fullmatch(target_name):
            raise ValueError(
                f"{skill_file}: normalized Codex skill name `{target_name}` is invalid"
            )
        if target_name in names:
            raise ValueError(
                f"{skill_file}: normalized Codex skill name collision `{target_name}` "
                f"with {names[target_name]}"
            )

        names[target_name] = skill_file
        discovered.append(
            SkillSource(
                source_dir=skill_file.parent,
                source_name=source_name,
                target_name=target_name,
                frontmatter=frontmatter,
            )
        )

    if not discovered:
        raise ValueError(f"{skills_dir}: no */SKILL.md files found")
    return discovered


def _target_relative_path(
    source_path: Path,
    current: SkillSource,
    skills: list[SkillSource],
) -> str:
    resolved = source_path.resolve()
    owner = next(
        (
            skill
            for skill in skills
            if resolved == skill.source_dir.resolve()
            or skill.source_dir.resolve() in resolved.parents
        ),
        None,
    )
    if owner is None:
        raise ValueError(
            f"{current.source_dir / 'SKILL.md'}: resource escapes canonical skills: "
            f"{source_path}"
        )

    generated_resource = (
        Path(owner.target_name) / resolved.relative_to(owner.source_dir.resolve())
    )
    return Path(
        os.path.relpath(generated_resource, Path(current.target_name))
    ).as_posix()


def _rewrite_resource_paths(
    text: str,
    current: SkillSource,
    skills: list[SkillSource],
    source_file: Path,
) -> str:
    plugin_dir = current.source_dir.parent.parent

    def replace_skill_dir(match: re.Match[str]) -> str:
        raw_path = match.group(1)
        if "<" in raw_path or ">" in raw_path:
            return raw_path
        source_path = current.source_dir / raw_path
        if not source_path.exists():
            raise ValueError(f"{source_file}: missing referenced resource {source_path}")
        return _target_relative_path(source_path, current, skills)

    def replace_plugin_root(match: re.Match[str]) -> str:
        raw_path = match.group(1)
        if raw_path.startswith("hooks/"):
            return CLAUDE_HOOK_UNAVAILABLE.format(path=raw_path)
        source_path = plugin_dir / raw_path
        if not source_path.exists():
            raise ValueError(f"{source_file}: missing referenced resource {source_path}")
        if not raw_path.startswith("skills/"):
            raise ValueError(
                f"{source_file}: unsupported CLAUDE_PLUGIN_ROOT resource {source_path}"
            )
        return _target_relative_path(source_path, current, skills)

    def replace_bare_sibling(match: re.Match[str]) -> str:
        source_path = current.source_dir.parent / match.group(1) / match.group(2)
        if "<" in match.group(0) or ">" in match.group(0) or not source_path.exists():
            return match.group(0)
        return _target_relative_path(source_path, current, skills)

    def replace_canonical_skill_path(match: re.Match[str]) -> str:
        source_path = current.source_dir.parent / match.group(1) / match.group(2)
        if "<" in match.group(0) or ">" in match.group(0) or not source_path.exists():
            return match.group(0)
        return _target_relative_path(source_path, current, skills)

    def replace_bare_skill_path(match: re.Match[str]) -> str:
        source_skill = current.source_dir.parent / match.group(1)
        source_path = source_skill / match.group(2)
        if (
            "<" in match.group(0)
            or ">" in match.group(0)
            or not (source_skill / "SKILL.md").is_file()
            or not source_path.exists()
        ):
            return match.group(0)
        return _target_relative_path(source_path, current, skills)

    text = SKILL_DIR_TOKEN_RE.sub(replace_skill_dir, text)
    text = PLUGIN_ROOT_TOKEN_RE.sub(replace_plugin_root, text)
    text = BARE_SIBLING_PATH_RE.sub(replace_bare_sibling, text)
    text = CANONICAL_SKILL_PATH_RE.sub(replace_canonical_skill_path, text)
    return BARE_SKILL_PATH_RE.sub(replace_bare_skill_path, text)


def _codex_overlay(source_file: Path, current: SkillSource) -> str | None:
    portable_workflow = _portable_plan_work_overlay(source_file, current)
    if portable_workflow is not None:
        return portable_workflow

    if source_file == current.source_dir / "SKILL.md":
        body = current.frontmatter.body
        if current.target_name == "phx-investigate":
            required = ("# Investigate Bug", "## Investigation Workflow", "## References")
            if not all(marker in body for marker in required):
                raise ValueError(
                    f"{source_file}: Codex investigate overlay anchors changed"
                )
            return INVESTIGATE_BODY
        if current.target_name == "phx-review":
            required = ("# Review Elixir/Phoenix Code", "## Workflow", "## Iron Laws")
            if not all(marker in body for marker in required):
                raise ValueError(f"{source_file}: Codex review overlay anchors changed")
            return REVIEW_BODY

    if (
        current.target_name == "phx-review"
        and source_file.relative_to(current.source_dir).as_posix()
        == "references/agent-spawning.md"
    ):
        source = source_file.read_text(encoding="utf-8")
        required = ("# Review Agent Spawning Reference", "## Agent Selection Table")
        if not all(marker in source for marker in required):
            raise ValueError(f"{source_file}: Codex review reference anchors changed")
        return REVIEW_AGENT_REFERENCE

    relative = source_file.relative_to(current.source_dir).as_posix()
    if current.target_name == "phx-review" and relative == (
        "references/requirements-detection.md"
    ):
        source = source_file.read_text(encoding="utf-8")
        if "# Requirements Detection Reference" not in source:
            raise ValueError(f"{source_file}: Codex requirements anchors changed")
        return REVIEW_REQUIREMENTS_REFERENCE

    if current.target_name == "phx-investigate" and relative == (
        "references/error-patterns.md"
    ):
        source = source_file.read_text(encoding="utf-8")
        marker = "Spawn `deep-bug-investigator` agent to systematically check:"
        if marker not in source:
            raise ValueError(f"{source_file}: Codex error-pattern anchors changed")
        transformed = source.replace(
            marker,
            "Check systematically, or delegate to a generic read-only subagent if "
            "native Codex subagent tooling is available:",
        )
        diagnostic_marker = "## IO.inspect Everything\n\n```elixir"
        if diagnostic_marker not in transformed:
            raise ValueError(f"{source_file}: Codex diagnostic anchors changed")
        transformed = transformed.replace(
            diagnostic_marker,
            "## Temporary Diagnostics\n\nOnly when the user explicitly authorizes "
            "temporary source edits, add and later remove diagnostics such as:\n\n```elixir",
        )
        stuck_marker = """## When Stuck

1. `IO.inspect(binding(), label: "all variables")`
2. Add `require IEx; IEx.pry` and step through
3. Check if code is even being reached (add `IO.puts "HERE"`)
4. Compare working vs broken path"""
        if stuck_marker not in transformed:
            raise ValueError(f"{source_file}: Codex stuck-check anchors changed")
        return transformed.replace(
            stuck_marker,
            """## When Stuck

1. Inspect values through failing test output or an available safe runtime eval
2. Run a focused IEx expression without modifying source files
3. Trace reachability through existing logs or tests; source edits require approval
4. Compare the working and broken paths""",
        )

    if current.target_name == "phx-investigate" and relative == (
        "references/investigation-template.md"
    ):
        source = source_file.read_text(encoding="utf-8")
        marker = "# Bug Investigation: $ARGUMENTS"
        write_marker = "Create `.claude/plans/{slug}/research/investigation.md`:"
        if marker not in source or write_marker not in source:
            raise ValueError(f"{source_file}: Codex investigation anchors changed")
        return source.replace(
            write_marker,
            "Return this structure in the current session; do not write a report file "
            "unless the user explicitly asks for one:",
        ).replace(marker, "# Bug Investigation: <bug description>")
    return None


def _transform_markdown(
    source_file: Path,
    current: SkillSource,
    skills: list[SkillSource],
) -> str:
    overlay = _codex_overlay(source_file, current)
    if source_file == current.source_dir / "SKILL.md":
        projected = transform_frontmatter(current.frontmatter.data, "codex")
        if current.target_name == "phx-investigate":
            projected["description"] = (
                "Investigate Elixir/Phoenix bugs root-cause first. Reproduce failures, "
                "cite evidence, and use optional Codex subagents only when useful."
            )
        elif current.target_name == "phx-review":
            projected["description"] = (
                "Review changed Elixir/Phoenix code read-only. Check requirements, "
                "cite evidence, deduplicate findings, and return a severity-based verdict."
            )
        body = overlay if overlay is not None else current.frontmatter.body
        body = _rewrite_resource_paths(body, current, skills, source_file)
        body = rewrite_slash_commands(body, "codex")
        return Frontmatter(projected, body).dump()

    text = overlay if overlay is not None else source_file.read_text(encoding="utf-8")
    text = _rewrite_resource_paths(text, current, skills, source_file)
    return rewrite_slash_commands(text, "codex")


def _populate(skills: list[SkillSource], output_dir: Path, manifest: dict) -> None:
    skills_dir = output_dir / "skills"
    for skill in skills:
        target_skill = skills_dir / skill.target_name
        for source_file in sorted(skill.source_dir.rglob("*")):
            if source_file.is_dir() or source_file.name in IGNORED_FILES:
                continue
            destination = target_skill / source_file.relative_to(skill.source_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source_file.suffix.lower() == ".md":
                destination.write_text(
                    _transform_markdown(source_file, skill, skills),
                    encoding="utf-8",
                )
                destination.chmod(source_file.stat().st_mode & 0o7777)
            else:
                shutil.copy2(source_file, destination)

    manifest_dir = output_dir / ".codex-plugin"
    manifest_dir.mkdir(parents=True)
    manifest_file = manifest_dir / "plugin.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_file.chmod(0o644)


def validate(output_dir: str | Path, expected_manifest: dict | None = None) -> int:
    """Validate a generated Codex plugin and return its skill count."""
    root = Path(output_dir)
    manifest_file = root / ".codex-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{manifest_file}: invalid or missing plugin manifest") from error

    if expected_manifest is not None and manifest != expected_manifest:
        raise ValueError(f"{manifest_file}: unexpected Codex plugin manifest")
    for field in ("name", "version", "description"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise ValueError(f"{manifest_file}: invalid or missing field `{field}`")
    if "agents" in manifest or "commands" in manifest:
        raise ValueError(f"{manifest_file}: unsupported Codex manifest field")

    skills_path = manifest.get("skills")
    if not isinstance(skills_path, str) or not skills_path.startswith("./"):
        raise ValueError(f"{manifest_file}: invalid skills path")
    skills_root = root / skills_path
    if not skills_root.is_dir():
        raise ValueError(f"{manifest_file}: skills path does not resolve")

    for generated_path in sorted(root.rglob("*")):
        if generated_path.is_symlink():
            raise ValueError(f"{generated_path}: generated symlinks are not supported")
        if not generated_path.is_dir() and not generated_path.is_file():
            raise ValueError(f"{generated_path}: generated special file is not supported")

    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        raise ValueError(f"{skills_root}: no generated skills found")

    allowed_fields = {"name", "description", "license", "compatibility", "metadata"}
    for skill_file in skill_files:
        frontmatter = parse_file(skill_file)
        name = frontmatter.data.get("name")
        if name != skill_file.parent.name:
            raise ValueError(
                f"{skill_file}: frontmatter name `{name}` does not match directory"
            )
        if set(frontmatter.data) - allowed_fields:
            raise ValueError(f"{skill_file}: unsupported Codex frontmatter fields")
        if not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name):
            raise ValueError(f"{skill_file}: invalid Codex skill name `{name}`")
        description = frontmatter.data.get("description")
        if not isinstance(description, str) or not 1 <= len(description) <= 1024:
            raise ValueError(f"{skill_file}: invalid Codex skill description")

    unresolved = (
        "${CLAUDE_SKILL_DIR}",
        "${CLAUDE_PLUGIN_ROOT}",
        "${CODEX_PLUGIN_ROOT}",
        "/phx:",
        "/lv:",
        "/ecto:",
    )
    for markdown in sorted(root.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        found = next((token for token in unresolved if token in text), None)
        if found:
            raise ValueError(f"{markdown}: unresolved Claude token `{found}`")

    for flagship in ("phx-investigate", "phx-review", "phx-plan", "phx-work"):
        flagship_root = skills_root / flagship
        if not flagship_root.is_dir():
            continue
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(flagship_root.rglob("*.md"))
        )
        forbidden = (
            "TaskCreate",
            "TaskUpdate",
            "TaskGet",
            "TaskList",
            "AskUserQuestion",
            "subagent_type",
            "$ARGUMENTS",
            "mcp__tidewave__",
            "mcp__linear__",
        )
        if flagship in {"phx-plan", "phx-work"}:
            forbidden += (
                "phoenix-patterns-analyst", "ecto-schema-designer",
                "liveview-architect", "oban-specialist", "otp-advisor",
                "security-analyzer", "testing-reviewer", "hex-library-researcher",
                "web-researcher", "call-tracer", "planning-orchestrator",
                "Spawn SPECIALIST", "run_in_background", "[agent]",
                "Agent annotation", "agent routing", "project_eval", "get_logs",
                "| Hook |", "Each hook", "/commit",
                "agent spawning", "agent count", "Explore agents",
                "execute via subagents", "After spawning",
            )
        found = next((token for token in forbidden if token in text), None)
        if found:
            raise ValueError(f"{flagship_root}: unavailable API `{found}`")

    return len(skill_files)


def build(source_plugin_dir: str | Path, output_dir: str | Path) -> dict[str, int]:
    """Replace output_dir with a validated plugin, rolling back on failure."""
    output = Path(output_dir)
    skills = discover_skills(source_plugin_dir)
    manifest = _plugin_manifest(source_plugin_dir)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".codex-plugin-", dir=output.parent) as tmp:
        staged = Path(tmp) / "target"
        staged.mkdir()
        _populate(skills, staged, manifest)
        count = validate(staged, manifest)

        replacement = Path(tmp) / "replacement"
        staged.rename(replacement)
        backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
        if output.exists():
            output.rename(backup)
        try:
            replacement.rename(output)
        except BaseException as install_error:
            if backup.exists() and not output.exists():
                try:
                    backup.rename(output)
                except BaseException as rollback_error:
                    raise RuntimeError(
                        f"failed to install {output} and failed to restore backup "
                        f"{backup}: {rollback_error}"
                    ) from install_error
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)

    return {"skills": count}
