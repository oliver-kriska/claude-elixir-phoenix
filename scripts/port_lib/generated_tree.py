"""Shared filesystem projection for generated skill subtrees."""

from __future__ import annotations

import shutil
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
