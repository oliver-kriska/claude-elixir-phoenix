"""Generate a native Pi skills package from the Claude Code source plugin."""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from . import codex
from .frontmatter import Frontmatter, parse_file
from .skill_transforms import rewrite_slash_commands, transform_frontmatter

IGNORED_FILES = codex.IGNORED_FILES
SKILL_NAME_RE = codex.SKILL_NAME_RE
PI_DESCRIPTION = (
    "Generated Elixir, Phoenix, LiveView, Ecto, Oban, testing, and security "
    "skills for Pi"
)
_CODEX_COMMAND_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])\$(phx|lv|ecto)-"
    r"([a-z][a-z0-9-]*)(?![A-Za-z0-9_:-])"
)
_QUICK_COMMAND_RE = re.compile(r"(?<![A-Za-z0-9_./-])/quick(?=\s|$|[,.)])")


def _rewrite_commands(text: str) -> str:
    text = rewrite_slash_commands(text, "pi")
    text = _CODEX_COMMAND_RE.sub(r"/skill:\1-\2", text)
    text = _QUICK_COMMAND_RE.sub("/skill:phx-quick", text)
    return text.replace(
        "— Scans session JSONL files, finds uncovered Bash commands, classifies risk, "
        "and recommends",
        "— Scans session JSONL files, finds uncovered Bash commands,\n"
        "classifies risk, and recommends",
    )


def _package_manifest(source_plugin_dir: str | Path) -> dict:
    source_file = Path(source_plugin_dir) / ".claude-plugin" / "plugin.json"
    try:
        source = json.loads(source_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{source_file}: invalid or missing source manifest") from error

    for field in ("name", "version"):
        if not isinstance(source.get(field), str) or not source[field]:
            raise ValueError(f"{source_file}: missing string field `{field}`")

    return {
        "name": f"pi-{source['name']}",
        "version": source["version"],
        "description": PI_DESCRIPTION,
        "keywords": [*source.get("keywords", []), "pi-package"],
        "author": source.get("author", {}),
        "homepage": source.get("homepage"),
        "repository": source.get("repository"),
        "engines": {"node": ">=22.19.0"},
        "pi": {"skills": ["./skills"]},
    }


def discover_skills(source_plugin_dir: str | Path) -> list[codex.SkillSource]:
    return codex.discover_skills(source_plugin_dir)


def _pi_overlay(source_file: Path, skill: codex.SkillSource) -> str | None:
    overlay = codex._codex_overlay(source_file, skill)
    if overlay is None:
        return None
    return _rewrite_commands(overlay.replace("Codex", "Pi"))


def _rewrite_resource_paths(
    text: str,
    skill: codex.SkillSource,
    skills: list[codex.SkillSource],
    source_file: Path,
) -> str:
    return codex._rewrite_resource_paths(text, skill, skills, source_file).replace(
        "Claude Code-only hook unavailable in the Codex skills-only plugin",
        "Claude Code-only hook unavailable in the Pi skills-only package",
    )


def _transform_markdown(
    source_file: Path,
    skill: codex.SkillSource,
    skills: list[codex.SkillSource],
) -> str:
    overlay = _pi_overlay(source_file, skill)
    if source_file == skill.source_dir / "SKILL.md":
        projected = transform_frontmatter(skill.frontmatter.data, "pi")
        projected["description"] = _rewrite_commands(projected["description"])
        if skill.target_name == "phx-investigate":
            projected["description"] = (
                "Investigate Elixir/Phoenix bugs root-cause first. Reproduce failures, "
                "cite evidence, and use optional Pi subagents only when useful."
            )
        elif skill.target_name == "phx-review":
            projected["description"] = (
                "Review changed Elixir/Phoenix code read-only. Check requirements, "
                "cite evidence, deduplicate findings, and return a severity-based verdict."
            )
        body = overlay if overlay is not None else skill.frontmatter.body
        body = _rewrite_resource_paths(body, skill, skills, source_file)
        return Frontmatter(projected, _rewrite_commands(body)).dump()

    text = overlay if overlay is not None else source_file.read_text(encoding="utf-8")
    text = _rewrite_resource_paths(text, skill, skills, source_file)
    return _rewrite_commands(text)


def _populate(skills: list[codex.SkillSource], output: Path, manifest: dict) -> None:
    for skill in skills:
        target_skill = output / "skills" / skill.target_name
        for source_file in sorted(skill.source_dir.rglob("*")):
            if source_file.is_dir() or source_file.name in IGNORED_FILES:
                continue
            destination = target_skill / source_file.relative_to(skill.source_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source_file.suffix.lower() == ".md":
                destination.write_text(
                    _transform_markdown(source_file, skill, skills), encoding="utf-8"
                )
                destination.chmod(source_file.stat().st_mode & 0o7777)
            else:
                shutil.copy2(source_file, destination)

    manifest_file = output / "package.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest_file.chmod(0o644)


def validate(output_dir: str | Path, expected_manifest: dict | None = None) -> int:
    root = Path(output_dir)
    manifest_file = root / "package.json"
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"{manifest_file}: invalid or missing Pi package manifest") from error
    if expected_manifest is not None and manifest != expected_manifest:
        raise ValueError(f"{manifest_file}: unexpected Pi package manifest")
    if manifest.get("keywords", []).count("pi-package") != 1:
        raise ValueError(f"{manifest_file}: missing `pi-package` keyword")
    pi_manifest = manifest.get("pi")
    if pi_manifest != {"skills": ["./skills"]}:
        raise ValueError(f"{manifest_file}: Pi baseline must declare only a skills array")

    skills_root = root / "skills"
    if not skills_root.is_dir():
        raise ValueError(f"{manifest_file}: skills path does not resolve")
    for generated in sorted(root.rglob("*")):
        if generated.is_symlink() or (not generated.is_dir() and not generated.is_file()):
            raise ValueError(f"{generated}: unsupported generated node")

    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        raise ValueError(f"{skills_root}: no generated skills found")
    allowed_fields = {"name", "description", "license", "compatibility", "metadata"}
    for skill_file in skill_files:
        frontmatter = parse_file(skill_file)
        name = frontmatter.data.get("name")
        if name != skill_file.parent.name or not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name):
            raise ValueError(f"{skill_file}: invalid or mismatched Pi skill name `{name}`")
        if set(frontmatter.data) - allowed_fields:
            raise ValueError(f"{skill_file}: unsupported Pi frontmatter fields")
        description = frontmatter.data.get("description")
        if (
            not isinstance(description, str)
            or not 1 <= len(description.strip()) <= 1024
        ):
            raise ValueError(f"{skill_file}: invalid Pi skill description")

    unresolved = (
        "${CLAUDE_SKILL_DIR}",
        "${CLAUDE_PLUGIN_ROOT}",
        "/phx:",
        "/lv:",
        "/ecto:",
        "$phx-",
        "$lv-",
        "$ecto-",
        "/quick",
    )
    for markdown in sorted(root.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        found = next((token for token in unresolved if token in text), None)
        if found:
            raise ValueError(f"{markdown}: unresolved non-Pi token `{found}`")

    for flagship in ("phx-investigate", "phx-review"):
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((skills_root / flagship).rglob("*.md"))
        )
        forbidden = (
            "TaskCreate", "TaskUpdate", "TaskGet", "TaskList", "AskUserQuestion",
            "subagent_type", "$ARGUMENTS", "mcp__tidewave__", "mcp__linear__",
        )
        found = next((token for token in forbidden if token in text), None)
        if found:
            raise ValueError(f"{skills_root / flagship}: unavailable API `{found}`")
    return len(skill_files)


def build(source_plugin_dir: str | Path, output_dir: str | Path) -> dict[str, int]:
    output = Path(output_dir)
    skills = discover_skills(source_plugin_dir)
    manifest = _package_manifest(source_plugin_dir)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".pi-package-", dir=output.parent) as tmp:
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
                        f"failed to install {output} and restore {backup}: {rollback_error}"
                    ) from install_error
            raise
        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
    return {"skills": count}
