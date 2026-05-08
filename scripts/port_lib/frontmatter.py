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


def parse(text: str) -> Frontmatter:
    """Split a markdown file into (frontmatter dict, body string).

    If the file does not start with `---`, returns Frontmatter(data={}, body=text).
    """
    if not text.startswith(DELIMITER):
        return Frontmatter(data={}, body=text)

    lines = text.splitlines(keepends=True)
    # Find the closing delimiter (first line == "---" after line 0).
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == DELIMITER:
            end_idx = i
            break

    if end_idx is None:
        # Malformed: opener but no closer. Treat entire file as body.
        return Frontmatter(data={}, body=text)

    yaml_block = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])
    data = yaml.safe_load(yaml_block) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Frontmatter must be a mapping, got {type(data).__name__}")
    return Frontmatter(data=data, body=body)


def parse_file(path) -> Frontmatter:
    from pathlib import Path

    return parse(Path(path).read_text(encoding="utf-8"))


def write_file(path, fm: Frontmatter) -> None:
    from pathlib import Path

    Path(path).write_text(fm.dump(), encoding="utf-8")
