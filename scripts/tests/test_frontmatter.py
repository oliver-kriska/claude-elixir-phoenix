from __future__ import annotations

import pytest

from scripts.port_lib.frontmatter import Frontmatter, parse, parse_file, write_file


def test_parse_round_trips_frontmatter_and_body() -> None:
    text = """---
name: phx:plan
description: "Plán with unicode"
paths:
  - "**/*.ex"
---
# Plan

Body text.
"""

    parsed = parse(text)

    assert parsed.data == {
        "name": "phx:plan",
        "description": "Plán with unicode",
        "paths": ["**/*.ex"],
    }
    assert parsed.body == "# Plan\n\nBody text.\n"
    assert parse(parsed.dump()) == parsed


def test_parse_preserves_markdown_without_frontmatter() -> None:
    text = "# Plain Markdown\n\nNo metadata.\n"

    assert parse(text) == Frontmatter(data={}, body=text)
    assert parse(text).dump() == text


def test_parse_reports_source_for_missing_closer() -> None:
    with pytest.raises(ValueError, match=r"skill/SKILL\.md: malformed frontmatter"):
        parse("---\nname: broken\n", source="skill/SKILL.md")


@pytest.mark.parametrize(
    "yaml_value",
    ["- one\n- two", "plain scalar", "false", "0", "[]", '""'],
)
def test_parse_rejects_non_mapping_frontmatter(yaml_value: str) -> None:
    text = f"---\n{yaml_value}\n---\nBody\n"

    with pytest.raises(ValueError, match="frontmatter must be a mapping"):
        parse(text)


@pytest.mark.parametrize("opener", ["----", "---suffix", "--- "])
def test_parse_requires_exact_opening_delimiter(opener: str) -> None:
    text = f"{opener}\nordinary Markdown\n---\n"

    assert parse(text) == Frontmatter(data={}, body=text)


def test_parse_rejects_duplicate_keys_with_source() -> None:
    text = "---\nname: first\nname: second\n---\nBody\n"

    with pytest.raises(
        ValueError,
        match=r"(?s)skill/SKILL\.md: invalid YAML.*duplicate key",
    ):
        parse(text, source="skill/SKILL.md")


def test_parse_file_and_write_file(tmp_path) -> None:
    source = tmp_path / "source.md"
    output = tmp_path / "output.md"
    source.write_text("---\nname: testing\n---\n# Body\n", encoding="utf-8")

    parsed = parse_file(source)
    write_file(output, parsed)

    assert output.read_text(encoding="utf-8") == parsed.dump()
