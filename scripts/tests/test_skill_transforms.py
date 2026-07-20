from __future__ import annotations

import pytest

from scripts.port_lib.skill_transforms import (
    inline_iron_laws,
    normalize_skill_name,
    port_references,
    rewrite_reference_paths,
    rewrite_slash_commands,
    transform_frontmatter,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("phx:plan", "phx-plan"),
        ("lv:assigns", "lv-assigns"),
        ("ecto:n1-check", "ecto-n1-check"),
        ("liveview-patterns", "liveview-patterns"),
        ("", ""),
    ],
)
def test_normalize_skill_name(source: str, expected: str) -> None:
    assert normalize_skill_name(source) == expected


def test_claude_frontmatter_is_preserved() -> None:
    data = {
        "name": "phx:plan",
        "description": "Use after /phx:review.",
        "effort": "high",
        "paths": ["**/*.ex"],
    }

    transformed = transform_frontmatter(data, "claude")

    assert transformed == data
    assert transformed is not data


@pytest.mark.parametrize("target", ["codex", "pi", "opencode"])
def test_non_claude_frontmatter_preserves_extensions_in_metadata(target: str) -> None:
    data = {
        "name": "phx:plan",
        "description": "Use after /phx:review.",
        "effort": "high",
        "paths": ["**/*.ex"],
    }

    transformed = transform_frontmatter(data, target)

    assert transformed["name"] == "phx-plan"
    assert transformed["metadata"] == {
        "effort": "high",
        "paths": ["**/*.ex"],
    }
    assert "/phx:review" not in transformed["description"]


def test_transform_frontmatter_rejects_unknown_target() -> None:
    with pytest.raises(ValueError, match="Unknown target: other"):
        transform_frontmatter({"name": "testing"}, "other")


def test_reference_paths_are_relative_outside_claude() -> None:
    body = "Read `${CLAUDE_SKILL_DIR}/references/nested/example.md`."

    assert rewrite_reference_paths(body, "codex") == (
        "Read `references/nested/example.md`."
    )
    assert rewrite_reference_paths(body, "claude") == body


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        ("claude", "Run /phx:plan, /lv:assigns, and /ecto:n1-check."),
        ("codex", "Run phx-plan, lv-assigns, and ecto-n1-check."),
        ("pi", "Run /phx-plan, /lv-assigns, and /ecto-n1-check."),
        ("opencode", "Run /phx-plan, /lv-assigns, and /ecto-n1-check."),
    ],
)
def test_rewrite_slash_commands(target: str, expected: str) -> None:
    body = "Run /phx:plan, /lv:assigns, and /ecto:n1-check."

    assert rewrite_slash_commands(body, target) == expected


def test_rewrite_slash_commands_rejects_unknown_target() -> None:
    with pytest.raises(ValueError, match="Unknown target: other"):
        rewrite_slash_commands("Run /phx:plan.", "other")


def test_port_references_transforms_markdown_and_preserves_binary(tmp_path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "guide.md").write_text(
        "Use /phx:review and read ${CLAUDE_SKILL_DIR}/references/details.md.\n",
        encoding="utf-8",
    )
    payload = b"\x00\x01\xff"
    (source / "asset.bin").write_bytes(payload)

    port_references(source, destination, "codex")

    assert (destination / "guide.md").read_text(encoding="utf-8") == (
        "Use phx-review and read references/details.md.\n"
    )
    assert (destination / "asset.bin").read_bytes() == payload


def test_inline_iron_laws_is_idempotent() -> None:
    body = "# Skill\n\nInstructions.\n"
    laws = ["Do one thing", "Do another thing"]

    once = inline_iron_laws(body, laws, "codex")
    twice = inline_iron_laws(once, laws, "codex")

    assert twice == once
    assert once.count("## Iron Laws (Inlined)") == 1
    assert "- Do one thing" in once


def test_inline_iron_laws_preserves_claude_body() -> None:
    body = "# Skill\n"

    assert inline_iron_laws(body, ["Law"], "claude") == body
