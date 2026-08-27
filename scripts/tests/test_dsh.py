from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest

from scripts import build_dsh_skills
from scripts.port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from scripts.port_lib import dsh
from scripts.port_lib.frontmatter import parse_file
from scripts.port_lib.generated_tree import tree_differences

EXPECTED_SKILLS = 51


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(stat.S_IMODE(mode).to_bytes(2, "big"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_skill(
    root: Path,
    directory: str,
    name: str,
    body: str = "# Skill\n",
    description: str = "Use /phx:review.",
) -> Path:
    manifest_dir = root / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "plugin.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {"name": "fixture", "version": "1.0.0", "keywords": [], "author": {}}
            ),
            encoding="utf-8",
        )
    skill = root / "skills" / directory
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\neffort: high\n---\n\n{body}",
        encoding="utf-8",
    )
    return skill


def test_builds_all_canonical_skills_without_mutating_other_targets(tmp_path) -> None:
    source_before = _tree_hash(SOURCE_PLUGIN_DIR)
    others = {
        name: _tree_hash(TARGETS_DIR / name)
        for name in ("amp", "codex", "pi", "opencode")
    }
    output = tmp_path / "dsh"

    result = dsh.build(SOURCE_PLUGIN_DIR, output)
    discovered = dsh.discover_skills(SOURCE_PLUGIN_DIR)

    assert result == {"skills": len(discovered)}
    assert len(discovered) == EXPECTED_SKILLS
    assert dsh.validate(output) == EXPECTED_SKILLS
    assert {skill.target_name for skill in discovered} == {
        path.parent.name for path in (output / "skills").glob("*/SKILL.md")
    }
    assert _tree_hash(SOURCE_PLUGIN_DIR) == source_before
    for name, before in others.items():
        assert _tree_hash(TARGETS_DIR / name) == before, f"{name} target mutated"


def test_generated_names_satisfy_dsh_kebab_case_discovery() -> None:
    """dsh rejects any skill whose frontmatter name is not kebab-case."""
    skills_root = TARGETS_DIR / "dsh" / "skills"
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        name = parse_file(skill_file).data["name"]
        assert dsh.SKILL_NAME_RE.fullmatch(name), f"{skill_file}: `{name}` not kebab-case"
        assert name == skill_file.parent.name
        assert ":" not in name


def test_generated_descriptions_stay_inside_the_dsh_catalog_bound() -> None:
    """dsh truncates past catalogDescriptionMaxLength instead of erroring."""
    skills_root = TARGETS_DIR / "dsh" / "skills"
    for skill_file in sorted(skills_root.glob("*/SKILL.md")):
        description = parse_file(skill_file).data["description"]
        assert 1 <= len(description.strip()) <= dsh.CATALOG_DESCRIPTION_MAX


def test_validate_rejects_a_description_past_the_catalog_bound(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(
        plugin,
        "source",
        "phx:source",
        description="x" * (dsh.CATALOG_DESCRIPTION_MAX + 1),
    )
    output = tmp_path / "dsh"

    with pytest.raises(ValueError, match="catalog bound"):
        dsh.build(plugin, output)
    assert not output.exists()


def test_validate_rejects_a_nested_skill_dsh_would_never_discover(tmp_path) -> None:
    """dsh discovery is one level deep; a nested SKILL.md is silently invisible."""
    staged = tmp_path / "dsh"
    top = staged / "skills" / "phx-source"
    top.mkdir(parents=True)
    (top / "SKILL.md").write_text(
        "---\nname: phx-source\ndescription: Use it.\n---\n\n# Skill\n",
        encoding="utf-8",
    )
    nested = top / "inner"
    nested.mkdir()
    (nested / "SKILL.md").write_text(
        "---\nname: inner\ndescription: Hidden.\n---\n\n# Nested\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="one level deep"):
        dsh.validate(staged)


def test_command_tokens_use_the_dsh_slash_form(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(
        plugin,
        "source",
        "phx:source",
        "Use /phx:source, /lv:assigns, /ecto:n1-check, and /quick. Keep "
        "../phx-deps-audit/references/guide.md and /tmp/phx-audit-run intact.\n",
        description="Use /phx:review but preserve /tmp/phx:review.",
    )
    output = tmp_path / "dsh"
    dsh.build(plugin, output)
    generated = output / "skills" / "phx-source"
    markdown = "\n".join(path.read_text() for path in generated.rglob("*.md"))

    assert parse_file(generated / "SKILL.md").data == {
        "name": "phx-source",
        "description": "Use /phx-review but preserve /tmp/phx:review.",
    }
    # dsh resolves a whitespace-bounded `/name` token, so the leading slash stays.
    assert "/phx-source" in markdown
    assert "/lv-assigns" in markdown
    assert "/ecto-n1-check" in markdown
    assert "/quick" in markdown
    assert "../phx-deps-audit/references/guide.md" in markdown
    assert "/tmp/phx-audit-run" in markdown
    assert "/tmp/phx:review" in markdown


def test_repository_target_matches_opencode_except_the_runtime_name() -> None:
    """The two Agent Skills targets must not drift apart accidentally."""
    dsh_root = TARGETS_DIR / "dsh" / "skills"
    opencode_root = TARGETS_DIR / "opencode" / "skills"

    assert {p.name for p in dsh_root.iterdir()} == {
        p.name for p in opencode_root.iterdir()
    }
    for generated in sorted(dsh_root.rglob("*")):
        if not generated.is_file():
            continue
        counterpart = opencode_root / generated.relative_to(dsh_root)
        assert counterpart.is_file(), f"{generated}: missing OpenCode counterpart"
        if generated.suffix != ".md":
            assert generated.read_bytes() == counterpart.read_bytes()
            continue
        normalized = generated.read_text(encoding="utf-8").replace(
            "DeepSeek Harness", "OpenCode"
        )
        assert normalized == counterpart.read_text(encoding="utf-8"), (
            f"{generated}: differs from OpenCode beyond the runtime name"
        )


def test_repository_target_carries_no_claude_only_tokens() -> None:
    root = TARGETS_DIR / "dsh"
    assert dsh.validate(root) == EXPECTED_SKILLS
    for markdown in sorted(root.rglob("*.md")):
        text = markdown.read_text(encoding="utf-8")
        for token in ("${CLAUDE_SKILL_DIR}", "${CLAUDE_PLUGIN_ROOT}", "/phx:", "$phx-"):
            assert token not in text, f"{markdown}: leaked `{token}`"


def test_committed_target_has_no_drift(tmp_path) -> None:
    generated = tmp_path / "dsh"
    dsh.build(SOURCE_PLUGIN_DIR, generated)
    assert tree_differences(generated, build_dsh_skills.OUTPUT_DIR) == []


def test_build_is_deterministic_and_leaves_no_scratch_directories(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    dsh.build(SOURCE_PLUGIN_DIR, first)
    dsh.build(SOURCE_PLUGIN_DIR, second)

    assert _tree_hash(first) == _tree_hash(second)
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith(".")] == []


def test_rebuild_over_an_existing_target_replaces_stale_skills(tmp_path) -> None:
    output = tmp_path / "dsh"
    dsh.build(SOURCE_PLUGIN_DIR, output)
    stale = output / "skills" / "phx-stale"
    stale.mkdir()
    (stale / "SKILL.md").write_text(
        "---\nname: phx-stale\ndescription: Gone.\n---\n\n# Stale\n", encoding="utf-8"
    )

    dsh.build(SOURCE_PLUGIN_DIR, output)

    assert not stale.exists()
    assert dsh.validate(output) == EXPECTED_SKILLS


def test_failed_validation_leaves_the_previous_target_in_place(tmp_path) -> None:
    output = tmp_path / "dsh"
    dsh.build(SOURCE_PLUGIN_DIR, output)
    before = _tree_hash(output)

    broken = tmp_path / "broken"
    _write_skill(
        broken, "source", "phx:source", description="y" * (dsh.CATALOG_DESCRIPTION_MAX + 1)
    )
    with pytest.raises(ValueError):
        dsh.build(broken, output)

    assert _tree_hash(output) == before
