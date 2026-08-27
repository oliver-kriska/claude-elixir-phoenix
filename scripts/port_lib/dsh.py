"""Generate native DeepSeek Harness (dsh) skills from the canonical plugin.

DeepSeek Harness discovers skills through `dsh-skill-filesystem`, which scans
`<projectRoot>/.agents/skills` (and the user-level `~/.agents/skills`) for
single-level `<name>/SKILL.md` bundles. The generated `skills/` tree here is
copied verbatim into one of those roots, so the projection is the Agent Skills
shape already used by the OpenCode target rather than anything dsh-specific.

Two dsh rules the shared validation does not cover:

* Skill names must be kebab-case (`^[a-z0-9]+(?:-[a-z0-9]+)*$`). That is already
  `codex.SKILL_NAME_RE`, so it is reused rather than redeclared.
* `catalogDescriptionMaxLength` defaults to 500 characters and dsh **truncates
  silently** past it instead of failing. `validate()` asserts the tighter bound
  so a future description cannot lose its routing tail without anyone noticing.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from pathlib import Path

from . import codex
from . import opencode
from .frontmatter import Frontmatter, parse_file
from .generated_tree import copy_skill_subtrees
from .skill_transforms import transform_frontmatter

IGNORED_FILES = codex.IGNORED_FILES
SKILL_NAME_RE = codex.SKILL_NAME_RE

# dsh truncates a longer description into the model-facing catalog instead of
# rejecting it, so the ceiling is enforced here where it is still visible.
CATALOG_DESCRIPTION_MAX = 500

_CLAUDE_COMMAND_RE = opencode._CLAUDE_COMMAND_RE
_CLAUDE_NAMESPACE_RE = opencode._CLAUDE_NAMESPACE_RE
_CODEX_COMMAND_RE = opencode._CODEX_COMMAND_RE

_RUNTIME_NAME = "DeepSeek Harness"


def rewrite_commands(text: str, *, reused_overlay: bool = False) -> str:
    """Rewrite command tokens to dsh's `/name` form, leaving paths intact.

    dsh resolves a whitespace-bounded `/name` token naming a user-invocable
    skill anywhere in a user message, so the OpenCode form is already correct.
    """
    return opencode.rewrite_commands(text, reused_overlay=reused_overlay)


def discover_skills(source_plugin_dir: str | Path) -> list[codex.SkillSource]:
    """Discover canonical skills using the shared hardened tree validation."""
    return codex.discover_skills(source_plugin_dir)


def _dsh_overlay(source_file: Path, skill: codex.SkillSource) -> str | None:
    overlay = codex._codex_overlay(source_file, skill)
    if overlay is None:
        return None
    return rewrite_commands(
        overlay.replace("Codex", _RUNTIME_NAME).replace("codex", _RUNTIME_NAME),
        reused_overlay=True,
    )


def _rewrite_resource_paths(
    text: str,
    skill: codex.SkillSource,
    skills: list[codex.SkillSource],
    source_file: Path,
) -> str:
    return codex._rewrite_resource_paths(text, skill, skills, source_file).replace(
        "Claude Code-only hook unavailable in the Codex skills-only plugin",
        f"Claude Code-only hook unavailable in the {_RUNTIME_NAME} skills-only target",
    )


def transform_markdown(
    source_file: Path, skill: codex.SkillSource, skills: list[codex.SkillSource]
) -> str:
    overlay = _dsh_overlay(source_file, skill)
    if source_file == skill.source_dir / "SKILL.md":
        projected = transform_frontmatter(skill.frontmatter.data, "opencode")
        projected["name"] = skill.target_name
        projected["description"] = rewrite_commands(
            skill.frontmatter.data["description"]
        )
        if skill.target_name == "phx-investigate":
            projected["description"] = (
                "Investigate Elixir/Phoenix bugs root-cause first. Reproduce failures, "
                f"cite evidence, and use optional native {_RUNTIME_NAME} subagents only "
                "when useful."
            )
        elif skill.target_name == "phx-review":
            projected["description"] = (
                "Review changed Elixir/Phoenix code read-only. Check requirements, cite "
                "evidence, deduplicate findings, and return a severity-based verdict."
            )
        elif skill.target_name == "phx-full":
            projected["description"] = (
                "Run a portable sequential plan-work-verify-review-compound lifecycle. "
                "Use optional generic workers only when the runtime supports them."
            )
        elif skill.target_name == "phx-freeze":
            projected["description"] = (
                "Apply an advisory edit scope in this session. Use for read-only or "
                "directory-scoped work; no enforcement hook is installed."
            )
        body = overlay if overlay is not None else skill.frontmatter.body
        body = _rewrite_resource_paths(body, skill, skills, source_file)
        return Frontmatter(projected, rewrite_commands(body)).dump()
    text = overlay if overlay is not None else source_file.read_text(encoding="utf-8")
    return rewrite_commands(_rewrite_resource_paths(text, skill, skills, source_file))


def _populate(skills: list[codex.SkillSource], output: Path) -> None:
    copy_skill_subtrees(skills, output / "skills", IGNORED_FILES, transform_markdown)


def validate(output_dir: str | Path) -> int:
    root = Path(output_dir)
    skills_root = root / "skills"
    if not skills_root.is_dir() or any(path.name != "skills" for path in root.iterdir()):
        raise ValueError(f"{root}: DeepSeek Harness target must contain only skills/")
    for generated in sorted(root.rglob("*")):
        if generated.is_symlink() or (not generated.is_dir() and not generated.is_file()):
            raise ValueError(f"{generated}: unsupported generated node")
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        raise ValueError(f"{skills_root}: no generated skills found")

    # dsh's filesystem provider is one level deep: only `<root>/<name>/SKILL.md`
    # and `<root>/<name>.md` are recognised. A nested SKILL.md would be silently
    # invisible, so reject it here instead of shipping a dead skill.
    for nested in sorted(skills_root.rglob("SKILL.md")):
        if nested.parent.parent != skills_root:
            raise ValueError(
                f"{nested}: DeepSeek Harness discovery is one level deep; "
                "nested SKILL.md is never loaded"
            )

    allowed = {"name", "description", "license", "compatibility", "metadata"}
    for skill_file in skill_files:
        fm = parse_file(skill_file)
        name = fm.data.get("name")
        if (
            name != skill_file.parent.name
            or not isinstance(name, str)
            or len(name) > 64
            or not SKILL_NAME_RE.fullmatch(name)
        ):
            raise ValueError(
                f"{skill_file}: invalid or mismatched DeepSeek Harness skill name `{name}`"
            )
        if set(fm.data) - allowed:
            raise ValueError(
                f"{skill_file}: unsupported DeepSeek Harness frontmatter fields"
            )
        description = fm.data.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{skill_file}: invalid DeepSeek Harness skill description")
        if len(description.strip()) > CATALOG_DESCRIPTION_MAX:
            raise ValueError(
                f"{skill_file}: description exceeds the {CATALOG_DESCRIPTION_MAX}-char "
                "dsh catalog bound and would be silently truncated"
            )

    for markdown in sorted(root.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        found = next(
            (
                token
                for token in ("${CLAUDE_SKILL_DIR}", "${CLAUDE_PLUGIN_ROOT}")
                if token in text
            ),
            None,
        )
        if found is None:
            command = _CLAUDE_COMMAND_RE.search(text) or _CLAUDE_NAMESPACE_RE.search(text)
            found = command.group(0) if command else None
        if found is None:
            legacy = _CODEX_COMMAND_RE.search(text)
            found = legacy.group(0) if legacy else None
        if found:
            raise ValueError(
                f"{markdown}: unresolved non-DeepSeek-Harness token `{found}`"
            )

    for flagship in (
        "phx-investigate",
        "phx-review",
        "phx-plan",
        "phx-work",
        "phx-pr-review",
        "phx-full",
        "phx-trace",
        "phx-audit",
        "phx-research",
    ):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((skills_root / flagship).rglob("*.md"))
        )
        forbidden = (
            "Agent(",
            "TaskCreate",
            "TaskUpdate",
            "TaskGet",
            "TaskList",
            "AskUserQuestion",
            "subagent_type",
            "$ARGUMENTS",
            "mcp__tidewave__",
            "mcp__linear__",
            "Claude Task",
            "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH",
        )
        if flagship in {"phx-pr-review", "phx-full"}:
            forbidden += (
                "workflow-orchestrator",
                "parallel-reviewer",
                "planning-orchestrator",
                "run_in_background",
                "Ralph Wiggum",
                "/ralph-loop:",
                "PostToolUse",
                "Claude Code tasks",
                "--codex",
                "--Pi",
                "--OpenCode",
                "/phx-compound",
            )
        if flagship in {"phx-plan", "phx-work"}:
            forbidden += (
                "phoenix-patterns-analyst",
                "ecto-schema-designer",
                "liveview-architect",
                "oban-specialist",
                "otp-advisor",
                "security-analyzer",
                "testing-reviewer",
                "hex-library-researcher",
                "web-researcher",
                "call-tracer",
                "planning-orchestrator",
                "Spawn SPECIALIST",
                "run_in_background",
                "[agent]",
                "Agent annotation",
                "agent routing",
                "project_eval",
                "get_logs",
                "| Hook |",
                "Each hook",
                "/commit",
                "agent spawning",
                "agent count",
                "Explore agents",
                "execute via subagents",
                "After spawning",
            )
        found = next((token for token in forbidden if token in text), None)
        if found:
            raise ValueError(f"{skills_root / flagship}: unavailable API `{found}`")

    codex.validate_portable_workflows(skills_root)
    codex.validate_portable_freeze(skills_root)
    return len(skill_files)


def build(source_plugin_dir: str | Path, output_dir: str | Path) -> dict[str, int]:
    output = Path(output_dir)
    skills = discover_skills(source_plugin_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dsh-skills-", dir=output.parent) as tmp:
        staged = Path(tmp) / "target"
        staged.mkdir()
        _populate(skills, staged)
        count = validate(staged)
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
                        f"failed to install {output} and restore {backup}: {rollback_error}"
                    ) from install_error
            raise
        if backup.exists():
            try:
                shutil.rmtree(backup)
            except OSError as error:
                raise RuntimeError(
                    f"installed {output}, but failed to remove backup {backup}"
                ) from error
    return {"skills": count}
