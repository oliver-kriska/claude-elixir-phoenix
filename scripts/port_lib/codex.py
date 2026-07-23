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
from .generated_tree import copy_skill_subtrees
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
    copy_skill_subtrees(skills, skills_dir, IGNORED_FILES, _transform_markdown)

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

    for flagship in ("phx-investigate", "phx-review"):
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
