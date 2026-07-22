"""Shared filesystem projection for generated skill subtrees."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path
from typing import Callable, Protocol, TypeVar


class SkillTreeSource(Protocol):
    source_dir: Path
    target_name: str


Skill = TypeVar("Skill", bound=SkillTreeSource)


def copy_skill_subtrees(
    skills: list[Skill],
    output_dir: Path,
    ignored_files: set[str],
    transform_markdown: Callable[[Path, Skill, list[Skill]], str],
    *,
    preserve_markdown_mode: bool = True,
) -> None:
    """Project complete skill trees while transforming Markdown only."""
    for skill in skills:
        target_skill = output_dir / skill.target_name
        for source_file in sorted(skill.source_dir.rglob("*")):
            if source_file.is_dir() or source_file.name in ignored_files:
                continue

            destination = target_skill / source_file.relative_to(skill.source_dir)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source_file.suffix.lower() == ".md":
                destination.write_text(
                    transform_markdown(source_file, skill, skills),
                    encoding="utf-8",
                )
                if preserve_markdown_mode:
                    destination.chmod(source_file.stat().st_mode & 0o7777)
            else:
                shutil.copy2(source_file, destination)


def tree_differences(expected: Path, actual: Path) -> list[str]:
    """Compare generated trees by path, node type, bytes, and mode."""

    def entries(root: Path) -> dict[str, tuple[str, int, Path]]:
        result: dict[str, tuple[str, int, Path]] = {}
        for path in sorted(root.rglob("*")):
            mode = path.lstat().st_mode
            kind = (
                "symlink"
                if stat.S_ISLNK(mode)
                else "directory"
                if stat.S_ISDIR(mode)
                else "file"
                if stat.S_ISREG(mode)
                else "special"
            )
            result[path.relative_to(root).as_posix()] = (
                kind,
                stat.S_IMODE(mode),
                path,
            )
        return result

    expected_entries = entries(expected)
    actual_entries = entries(actual)
    differences: list[str] = []
    for relative in sorted(expected_entries.keys() | actual_entries.keys()):
        if relative not in actual_entries:
            differences.append(f"missing in target: {relative}")
            continue
        if relative not in expected_entries:
            differences.append(f"extra in target: {relative}")
            continue
        expected_kind, expected_mode, expected_path = expected_entries[relative]
        actual_kind, actual_mode, actual_path = actual_entries[relative]
        if expected_kind != actual_kind:
            differences.append(
                f"type differs: {relative} ({expected_kind} != {actual_kind})"
            )
        elif expected_kind == "file" and (
            expected_path.read_bytes() != actual_path.read_bytes()
        ):
            differences.append(f"differs: {relative}")
        elif expected_mode != actual_mode:
            differences.append(f"mode differs: {relative}")
    return differences
