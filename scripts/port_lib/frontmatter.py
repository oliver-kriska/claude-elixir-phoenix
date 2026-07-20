"""Read and write YAML frontmatter without changing Markdown bodies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DELIMITER = "---"


@dataclass
class Frontmatter:
    data: dict
    body: str

    def dump(self) -> str:
        """Serialize frontmatter and body back to a complete file."""
        if not self.data:
            return self.body

        head = yaml.safe_dump(
            self.data,
            sort_keys=False,
            allow_unicode=True,
        ).rstrip()
        return f"{DELIMITER}\n{head}\n{DELIMITER}\n{self.body}"


def parse(text: str, source: str | None = None) -> Frontmatter:
    """Split Markdown into a frontmatter mapping and unchanged body."""
    if not text.startswith(DELIMITER):
        return Frontmatter(data={}, body=text)

    lines = text.splitlines(keepends=True)
    end_idx = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == DELIMITER:
            end_idx = index
            break

    prefix = f"{source}: " if source else ""
    if end_idx is None:
        raise ValueError(f"{prefix}malformed frontmatter — opener `---` without closer")

    yaml_block = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])
    data = yaml.safe_load(yaml_block) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"{prefix}frontmatter must be a mapping, got {type(data).__name__}"
        )

    return Frontmatter(data=data, body=body)


def parse_file(path: str | Path) -> Frontmatter:
    file_path = Path(path)
    return parse(file_path.read_text(encoding="utf-8"), source=str(file_path))


def write_file(path: str | Path, frontmatter: Frontmatter) -> None:
    Path(path).write_text(frontmatter.dump(), encoding="utf-8")
