"""Generate native OpenCode 1.17.2 skills from the canonical plugin."""

from __future__ import annotations

import re
import shutil
import tempfile
import uuid
from pathlib import Path

from . import codex
from .frontmatter import Frontmatter, parse_file
from .skill_transforms import transform_frontmatter

IGNORED_FILES = codex.IGNORED_FILES
SKILL_NAME_RE = codex.SKILL_NAME_RE
_CLAUDE_COMMAND_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])/(phx|lv|ecto):([a-z][a-z0-9-]*)(?![A-Za-z0-9_:-])"
)
_CLAUDE_NAMESPACE_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])/(phx|lv|ecto):"
    r"(?:\*(?![A-Za-z0-9_:-])|(?![A-Za-z0-9_*:-]))"
)
_CODEX_COMMAND_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])\$(phx|lv|ecto)-([a-z][a-z0-9-]*)(?![A-Za-z0-9_:-])"
)


def rewrite_commands(text: str, *, reused_overlay: bool = False) -> str:
    """Rewrite only command tokens, leaving filesystem/resource paths intact."""
    text = _CLAUDE_COMMAND_RE.sub(r"/\1-\2", text)
    text = _CLAUDE_NAMESPACE_RE.sub(r"/\1-*", text)
    if reused_overlay:
        text = _CODEX_COMMAND_RE.sub(r"/\1-\2", text)
    return text


def discover_skills(source_plugin_dir: str | Path) -> list[codex.SkillSource]:
    """Discover canonical skills using the shared hardened tree validation."""
    return codex.discover_skills(source_plugin_dir)


def _opencode_overlay(source_file: Path, skill: codex.SkillSource) -> str | None:
    overlay = codex._codex_overlay(source_file, skill)
    if overlay is None:
        return None
    return rewrite_commands(
        overlay.replace("Codex", "OpenCode").replace("codex", "OpenCode"),
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
        "Claude Code-only hook unavailable in the OpenCode skills-only target",
    )


def transform_markdown(
    source_file: Path, skill: codex.SkillSource, skills: list[codex.SkillSource]
) -> str:
    overlay = _opencode_overlay(source_file, skill)
    if source_file == skill.source_dir / "SKILL.md":
        projected = transform_frontmatter(skill.frontmatter.data, "opencode")
        projected["description"] = rewrite_commands(
            skill.frontmatter.data["description"]
        )
        if skill.target_name == "phx-investigate":
            projected["description"] = (
                "Investigate Elixir/Phoenix bugs root-cause first. Reproduce failures, cite evidence, and use optional native OpenCode subagents only when useful."
            )
        elif skill.target_name == "phx-review":
            projected["description"] = (
                "Review changed Elixir/Phoenix code read-only. Check requirements, cite evidence, deduplicate findings, and return a severity-based verdict."
            )
        body = overlay if overlay is not None else skill.frontmatter.body
        body = _rewrite_resource_paths(body, skill, skills, source_file)
        return Frontmatter(projected, rewrite_commands(body)).dump()
    text = overlay if overlay is not None else source_file.read_text(encoding="utf-8")
    return rewrite_commands(_rewrite_resource_paths(text, skill, skills, source_file))


def _populate(skills: list[codex.SkillSource], output: Path) -> None:
    for skill in skills:
        target_skill = output / "skills" / skill.target_name
        for source_file in sorted(skill.source_dir.rglob("*")):
            if source_file.is_dir() or source_file.name in IGNORED_FILES:
                continue
            destination = target_skill / source_file.relative_to(skill.source_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source_file.suffix.lower() == ".md":
                destination.write_text(
                    transform_markdown(source_file, skill, skills), encoding="utf-8"
                )
                destination.chmod(source_file.stat().st_mode & 0o7777)
            else:
                shutil.copy2(source_file, destination)


def validate(output_dir: str | Path) -> int:
    root = Path(output_dir)
    skills_root = root / "skills"
    if not skills_root.is_dir() or any(
        path.name != "skills" for path in root.iterdir()
    ):
        raise ValueError(f"{root}: OpenCode target must contain only skills/")
    for generated in sorted(root.rglob("*")):
        if generated.is_symlink() or (
            not generated.is_dir() and not generated.is_file()
        ):
            raise ValueError(f"{generated}: unsupported generated node")
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        raise ValueError(f"{skills_root}: no generated skills found")
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
                f"{skill_file}: invalid or mismatched OpenCode skill name `{name}`"
            )
        if set(fm.data) - allowed:
            raise ValueError(f"{skill_file}: unsupported OpenCode frontmatter fields")
        description = fm.data.get("description")
        if (
            not isinstance(description, str)
            or not 1 <= len(description.strip()) <= 1024
        ):
            raise ValueError(f"{skill_file}: invalid OpenCode skill description")
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
            command = _CLAUDE_COMMAND_RE.search(text) or _CLAUDE_NAMESPACE_RE.search(
                text
            )
            found = command.group(0) if command else None
        if found:
            raise ValueError(f"{markdown}: unresolved non-OpenCode token `{found}`")
    for flagship in ("phx-investigate", "phx-review", "phx-plan", "phx-work"):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((skills_root / flagship).rglob("*.md"))
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
            "Claude Task",
        )
        if flagship in {"phx-plan", "phx-work"}:
            forbidden += (
                "phoenix-patterns-analyst", "ecto-schema-designer", "liveview-architect",
                "oban-specialist", "otp-advisor", "security-analyzer", "testing-reviewer",
                "hex-library-researcher", "web-researcher", "call-tracer",
                "planning-orchestrator", "Spawn SPECIALIST", "run_in_background",
                "[agent]", "Agent annotation", "agent routing", "project_eval",
                "get_logs", "| Hook |", "Each hook", "/commit",
                "agent spawning", "agent count", "Explore agents",
                "execute via subagents", "After spawning",
            )
        found = next((token for token in forbidden if token in text), None)
        if found:
            raise ValueError(f"{skills_root / flagship}: unavailable API `{found}`")
    return len(skill_files)


def build(source_plugin_dir: str | Path, output_dir: str | Path) -> dict[str, int]:
    output = Path(output_dir)
    skills = discover_skills(source_plugin_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".opencode-skills-", dir=output.parent
    ) as tmp:
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
