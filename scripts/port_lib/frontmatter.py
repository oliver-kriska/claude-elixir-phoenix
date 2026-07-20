"""Read and write YAML frontmatter without changing Markdown bodies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode
from yaml.resolver import BaseResolver

DELIMITER = "---"


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: MappingNode,
    deep: bool = False,
) -> dict:
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


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
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != DELIMITER:
        return Frontmatter(data={}, body=text)

    end_idx = None
    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == DELIMITER:
            end_idx = index
            break

    prefix = f"{source}: " if source else ""
    if end_idx is None:
        raise ValueError(f"{prefix}malformed frontmatter — opener `---` without closer")

    yaml_block = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])
    try:
        data = yaml.load(yaml_block, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise ValueError(f"{prefix}invalid YAML frontmatter — {exc}") from exc
    if data is None:
        data = {}
    elif not isinstance(data, dict):
        raise ValueError(
            f"{prefix}frontmatter must be a mapping, got {type(data).__name__}"
        )

    return Frontmatter(data=data, body=body)


def parse_file(path: str | Path) -> Frontmatter:
    file_path = Path(path)
    return parse(file_path.read_text(encoding="utf-8"), source=str(file_path))


def write_file(path: str | Path, frontmatter: Frontmatter) -> None:
    Path(path).write_text(frontmatter.dump(), encoding="utf-8")
