"""Generate Amp-compatible Agent Skills from the Claude Code source plugin."""

from __future__ import annotations

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
    "[Claude Code-only hook unavailable in the Amp skills-only target: {path}]"
)


@dataclass(frozen=True)
class SkillSource:
    source_dir: Path
    source_name: str
    target_name: str
    frontmatter: Frontmatter


def discover_skills(source_plugin_dir: str | Path) -> list[SkillSource]:
    """Read all canonical skills and reject invalid or colliding target names."""
    plugin_dir = Path(source_plugin_dir)
    skills_dir = plugin_dir / "skills"
    discovered: list[SkillSource] = []
    names: dict[str, Path] = {}

    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        frontmatter = parse_file(skill_file)
        source_name = frontmatter.data.get("name")
        if not isinstance(source_name, str) or not source_name:
            raise ValueError(f"{skill_file}: missing string frontmatter field `name`")

        description = frontmatter.data.get("description")
        if not isinstance(description, str) or not description:
            raise ValueError(
                f"{skill_file}: missing string frontmatter field `description`"
            )

        target_name = normalize_skill_name(source_name)
        if len(target_name) > 64 or not SKILL_NAME_RE.fullmatch(target_name):
            raise ValueError(
                f"{skill_file}: normalized Amp skill name `{target_name}` is invalid"
            )

        if target_name in names:
            raise ValueError(
                f"{skill_file}: normalized Amp skill name collision `{target_name}` "
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
    """Map a canonical resource path to its generated relative location."""
    by_source_dir = {skill.source_dir.resolve(): skill for skill in skills}
    resolved = source_path.resolve()

    owner = next(
        (
            skill
            for source_dir, skill in by_source_dir.items()
            if resolved == source_dir or source_dir in resolved.parents
        ),
        None,
    )
    if owner is None:
        raise ValueError(
            f"{current.source_dir / 'SKILL.md'}: resource escapes canonical skills: "
            f"{source_path}"
        )

    relative_resource = resolved.relative_to(owner.source_dir.resolve())
    generated_resource = Path(owner.target_name) / relative_resource
    generated_current = Path(current.target_name)
    return Path(os.path.relpath(generated_resource, generated_current)).as_posix()


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
            raise ValueError(
                f"{source_file}: missing referenced resource {source_path}"
            )
        return _target_relative_path(source_path, current, skills)

    def replace_plugin_root(match: re.Match[str]) -> str:
        raw_path = match.group(1)
        if raw_path.startswith("hooks/"):
            return CLAUDE_HOOK_UNAVAILABLE.format(path=raw_path)

        source_path = plugin_dir / raw_path
        if not source_path.exists():
            raise ValueError(
                f"{source_file}: missing referenced resource {source_path}"
            )
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


def _transform_markdown(
    source_file: Path,
    current: SkillSource,
    skills: list[SkillSource],
) -> str:
    if source_file.name == "SKILL.md" and source_file.parent == current.source_dir:
        projected = transform_frontmatter(current.frontmatter.data, "amp")
        body = _rewrite_resource_paths(
            current.frontmatter.body,
            current,
            skills,
            source_file,
        )
        body = rewrite_slash_commands(body, "amp")
        return Frontmatter(projected, body).dump()

    text = source_file.read_text(encoding="utf-8")
    text = _rewrite_resource_paths(text, current, skills, source_file)
    return rewrite_slash_commands(text, "amp")


def _populate(skills: list[SkillSource], output_dir: Path) -> None:
    for skill in skills:
        target_skill = output_dir / skill.target_name
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
            else:
                shutil.copy2(source_file, destination)


def validate(output_dir: str | Path) -> int:
    """Validate a generated Amp skills directory and return its skill count."""
    root = Path(output_dir)
    skill_files = sorted(root.glob("*/SKILL.md"))
    if not skill_files:
        raise ValueError(f"{root}: no generated skills found")

    for skill_file in skill_files:
        frontmatter = parse_file(skill_file)
        name = frontmatter.data.get("name")
        if name != skill_file.parent.name:
            raise ValueError(
                f"{skill_file}: frontmatter name `{name}` does not match directory"
            )
        if set(frontmatter.data) - {
            "name",
            "description",
            "license",
            "compatibility",
            "metadata",
        }:
            raise ValueError(f"{skill_file}: unsupported Amp frontmatter fields")
        if (
            not isinstance(name, str)
            or len(name) > 64
            or not SKILL_NAME_RE.fullmatch(name)
        ):
            raise ValueError(f"{skill_file}: invalid Amp skill name `{name}`")
        description = frontmatter.data.get("description")
        if not isinstance(description, str) or not 1 <= len(description) <= 1024:
            raise ValueError(f"{skill_file}: invalid Amp skill description")

    for markdown in sorted(root.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        unresolved = (
            "${CLAUDE_SKILL_DIR}",
            "${CLAUDE_PLUGIN_ROOT}",
            "/phx:",
            "/lv:",
            "/ecto:",
        )
        found = next((token for token in unresolved if token in text), None)
        if found:
            raise ValueError(f"{markdown}: unresolved Claude token `{found}`")

    return len(skill_files)


def build(source_plugin_dir: str | Path, output_dir: str | Path) -> dict[str, int]:
    """Replace output_dir with a validated projection, rolling back on failure."""
    source = Path(source_plugin_dir)
    output = Path(output_dir)
    skills = discover_skills(source)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".amp-skills-", dir=output.parent) as tmp:
        staged = Path(tmp) / "skills"
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
        except Exception:
            if backup.exists() and not output.exists():
                backup.rename(output)
            raise
        if backup.exists():
            shutil.rmtree(backup)

    return {"skills": count}
