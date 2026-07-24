from __future__ import annotations

import hashlib
import stat
from pathlib import Path

import pytest

from scripts import build_amp_skills
from scripts.build_amp_skills import _differences
from scripts.port_lib import SOURCE_PLUGIN_DIR
from scripts.port_lib import amp
from scripts.port_lib.frontmatter import parse_file


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(stat.S_IMODE(path.stat().st_mode).to_bytes(2, "big"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_skill(
    root: Path, directory: str, name: str, body: str = "# Skill\n"
) -> Path:
    skill_dir = root / "skills" / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use for tests.\n---\n\n{body}",
        encoding="utf-8",
    )
    return skill_dir


def test_builds_all_repository_skills_without_mutating_claude_source(tmp_path) -> None:
    before = _tree_hash(SOURCE_PLUGIN_DIR)
    output = tmp_path / "skills"

    result = amp.build(SOURCE_PLUGIN_DIR, output)

    assert result == {"skills": 51}
    assert amp.validate(output) == 51
    assert _tree_hash(SOURCE_PLUGIN_DIR) == before

    for skill_file in output.glob("*/SKILL.md"):
        frontmatter = parse_file(skill_file)
        assert frontmatter.data["name"] == skill_file.parent.name
        assert amp.SKILL_NAME_RE.fullmatch(skill_file.parent.name)

    investigate = (output / "phx-investigate" / "SKILL.md").read_text()
    review = (output / "phx-review" / "SKILL.md").read_text()
    assert "Reproduce Before Fixing" in investigate
    assert "Tidewave is optional" in investigate
    assert "Review is read-only" in review
    assert "sequential review is fully valid" in review
    flagship_text = "\n".join(
        path.read_text(encoding="utf-8")
        for skill in amp.PORTABLE_WORKFLOWS
        for path in sorted((output / skill).rglob("*.md"))
    )
    assert not any(
        token in flagship_text
        for token in (
            "TaskCreate",
            "AskUserQuestion",
            "subagent_type",
            "run_in_background",
            "mcp__tidewave__",
        )
    )


def test_build_copies_complete_subtree_and_transforms_only_markdown(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(
        plugin,
        "source",
        "phx:source",
        "Read `${CLAUDE_SKILL_DIR}/references/guide.md` and run /phx:source.\n",
    )
    references = skill / "references"
    references.mkdir()
    (references / "guide.md").write_text("Use /phx:source.\n", encoding="utf-8")
    (references / "guide.md").chmod(0o744)
    payload = b"\x00\xff\x10"
    (skill / "nested" / "assets").mkdir(parents=True)
    (skill / "nested" / "assets" / "payload.bin").write_bytes(payload)
    executable = skill / "nested" / "run.sh"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)

    output = tmp_path / "output"
    amp.build(plugin, output)

    generated = output / "phx-source"
    assert "references/guide.md" in (generated / "SKILL.md").read_text()
    assert (
        "phx-source"
        in (references := generated / "references" / "guide.md").read_text()
    )
    assert "/phx:source" not in references.read_text()
    assert stat.S_IMODE(references.stat().st_mode) == 0o744
    assert (generated / "nested" / "assets" / "payload.bin").read_bytes() == payload
    assert stat.S_IMODE((generated / "nested" / "run.sh").stat().st_mode) == 0o755


def test_build_rewrites_cross_skill_resources(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    first = _write_skill(
        plugin,
        "first",
        "phx:first",
        "Read `${CLAUDE_SKILL_DIR}/../second/references/guide.md`.\n",
    )
    _ = first
    second = _write_skill(plugin, "second", "phx:second")
    (second / "references").mkdir()
    (second / "references" / "guide.md").write_text("Guide\n", encoding="utf-8")

    output = tmp_path / "output"
    amp.build(plugin, output)

    assert (
        "../phx-second/references/guide.md"
        in (output / "phx-first" / "SKILL.md").read_text()
    )


def test_build_rewrites_verified_bare_resource_paths(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(
        plugin,
        "first",
        "phx:first",
        "Read `../second/references/guide.md` and run "
        "`plugins/elixir-phoenix/skills/second/scripts/run.sh`.\n",
    )
    second = _write_skill(plugin, "second", "phx:second")
    (second / "references").mkdir()
    (second / "references" / "guide.md").write_text("Guide\n", encoding="utf-8")
    (second / "scripts").mkdir()
    (second / "scripts" / "run.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (plugin / "skills" / "first" / "references").mkdir()
    (plugin / "skills" / "first" / "references" / "nested.md").write_text(
        "Read `second/references/guide.md`.\n",
        encoding="utf-8",
    )

    output = tmp_path / "output"
    amp.build(plugin, output)

    generated = (output / "phx-first" / "SKILL.md").read_text()
    assert "../phx-second/references/guide.md" in generated
    assert "../phx-second/scripts/run.sh" in generated
    assert "plugins/elixir-phoenix" not in generated
    nested = (output / "phx-first" / "references" / "nested.md").read_text()
    assert "../../phx-second/references/guide.md" in nested


def test_build_rejects_name_collisions_before_replacing_output(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "first", "phx:plan")
    _write_skill(plugin, "second", "phx-plan")
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")

    with pytest.raises(ValueError, match="collision.*phx-plan"):
        amp.build(plugin, output)

    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_build_reports_missing_resource_with_source_path(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(
        plugin,
        "broken",
        "phx:broken",
        "Read `${CLAUDE_SKILL_DIR}/references/missing.md`.\n",
    )

    with pytest.raises(ValueError, match=str(skill / "SKILL.md")):
        amp.build(plugin, tmp_path / "output")


def test_build_rejects_symlinked_resources_without_replacing_target(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(plugin, "source", "phx:source")
    outside = tmp_path / "outside.txt"
    outside.write_text("private\n", encoding="utf-8")
    (skill / "linked.txt").symlink_to(outside)
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged\n", encoding="utf-8")

    with pytest.raises(ValueError, match="linked.txt.*symlinks are not supported"):
        amp.build(plugin, output)

    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"


def test_amp_projection_is_deterministic(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(plugin, "one", "phx:one")
    (skill / "asset.txt").write_text("asset\n", encoding="utf-8")
    first = tmp_path / "first"
    second = tmp_path / "second"

    amp.build(plugin, first)
    amp.build(plugin, second)

    assert _tree_hash(first) == _tree_hash(second)


def test_drift_comparison_detects_mode_only_changes(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(plugin, "one", "phx:one")
    script = skill / "run.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o755)
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    amp.build(plugin, expected)
    amp.build(plugin, actual)
    (actual / "phx-one" / "run.sh").chmod(0o644)

    assert _differences(expected, actual) == ["mode differs: phx-one/run.sh"]


def test_drift_comparison_detects_file_directory_type_changes(tmp_path) -> None:
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "node").write_text("file\n", encoding="utf-8")
    (actual / "node").mkdir()

    assert _differences(expected, actual) == [
        "type differs: node (file != directory)"
    ]


def test_build_restores_previous_target_when_installation_fails(
    tmp_path,
    monkeypatch,
) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "one", "phx:one")
    output = tmp_path / "output"
    amp.build(plugin, output)
    before = _tree_hash(output)
    original_rename = Path.rename

    def fail_replacement(self, target):
        if self.name == "replacement" and Path(target) == output:
            raise OSError("simulated installation failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_replacement)

    with pytest.raises(OSError, match="simulated installation failure"):
        amp.build(plugin, output)

    assert _tree_hash(output) == before
    assert not list(output.parent.glob(".output.backup-*"))


def test_drift_check_is_read_only(tmp_path, monkeypatch) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "one", "phx:one")
    output = tmp_path / "target" / "skills"
    amp.build(plugin, output)
    before = _tree_hash(output)
    monkeypatch.setattr(build_amp_skills, "SOURCE_PLUGIN_DIR", plugin)
    monkeypatch.setattr(build_amp_skills, "OUTPUT_DIR", output)

    assert build_amp_skills.check() == 0
    assert _tree_hash(output) == before

    skill_file = output / "phx-one" / "SKILL.md"
    skill_file.write_text(skill_file.read_text() + "drift\n", encoding="utf-8")
    drifted = _tree_hash(output)

    assert build_amp_skills.check() == 1
    assert _tree_hash(output) == drifted
