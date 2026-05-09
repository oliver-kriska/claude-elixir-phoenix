"""YAML frontmatter helpers for SKILL.md / agent .md files.

The convention used by this plugin (and the broader agentskills.io spec):

    ---
    name: phx:plan
    description: ...
    ---
    # Body markdown...

This module reads/writes that delimited block without rewriting the body.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

DELIMITER = "---"


@dataclass
class Frontmatter:
    data: dict
    body: str

    def dump(self) -> str:
        """Serialize back to a complete file string."""
        if not self.data:
            return self.body
        head = yaml.safe_dump(self.data, sort_keys=False, allow_unicode=True).rstrip()
        return f"{DELIMITER}\n{head}\n{DELIMITER}\n{self.body}"


def parse(text: str, source: str | None = None) -> Frontmatter:
    """Split a markdown file into (frontmatter dict, body string).

    If the file does not start with `---`, returns Frontmatter(data={}, body=text).

    If the file starts with `---` but has no closing delimiter, raises
    `ValueError` with the source path (when provided) — silently treating
    malformed files as bodyless caused confusing `KeyError`s downstream.
    """
    if not text.startswith(DELIMITER):
        return Frontmatter(data={}, body=text)

    lines = text.splitlines(keepends=True)
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == DELIMITER:
            end_idx = i
            break

    if end_idx is None:
        prefix = f"{source}: " if source else ""
        raise ValueError(
            f"{prefix}malformed frontmatter — opener `---` without closer"
        )

    yaml_block = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])
    data = yaml.safe_load(yaml_block) or {}
    if not isinstance(data, dict):
        prefix = f"{source}: " if source else ""
        raise ValueError(
            f"{prefix}frontmatter must be a mapping, got {type(data).__name__}"
        )
    return Frontmatter(data=data, body=body)


def parse_file(path) -> Frontmatter:
    from pathlib import Path

    p = Path(path)
    return parse(p.read_text(encoding="utf-8"), source=str(p))


def write_file(path, fm: Frontmatter) -> None:
    from pathlib import Path

    Path(path).write_text(fm.dump(), encoding="utf-8")
