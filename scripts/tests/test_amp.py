from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
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


def _write_amp_plugin(root: Path) -> None:
    source = SOURCE_PLUGIN_DIR / amp.PLUGIN_SOURCE_RELATIVE
    target = root / amp.PLUGIN_SOURCE_RELATIVE
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


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


def test_builds_complete_target_with_public_workflow_commands(tmp_path) -> None:
    output = tmp_path / "amp"

    result = amp.build_target(SOURCE_PLUGIN_DIR, output)

    assert result == {"skills": 51, "commands": 45, "plugins": 1}
    skills = amp.discover_skills(SOURCE_PLUGIN_DIR)
    specialists = amp.discover_specialists(SOURCE_PLUGIN_DIR)
    commands = amp.workflow_commands(skills)
    assert len(commands) == 40
    assert [specialist.key for specialist in specialists] == [
        "elixir",
        "ecto",
        "liveview",
        "security",
        "testing",
    ]
    assert amp.validate(output / "skills") == 51
    assert (
        amp.validate_plugin(output / amp.PLUGIN_RELATIVE_PATH, skills, specialists)
        == 45
    )

    by_skill = {command.skill_name: command for command in commands}
    assert (by_skill["phx-investigate"].category, by_skill["phx-investigate"].title) == (
        "phx",
        "investigate",
    )
    assert (by_skill["ecto-n1-check"].category, by_skill["ecto-n1-check"].title) == (
        "ecto",
        "n1-check",
    )
    assert (by_skill["lv-assigns"].category, by_skill["lv-assigns"].title) == (
        "lv",
        "assigns",
    )
    assert by_skill["phx-full"].argument_hint == "<feature description>"
    assert "security" not in by_skill
    assert "testing" not in by_skill

    plugin = (output / amp.PLUGIN_RELATIVE_PATH).read_text(encoding="utf-8")
    assert plugin.startswith(f"// Distribution: {amp.PLUGIN_DISTRIBUTION_URL}\n")
    assert "@amp-plugin" not in plugin
    assert "elixir-phoenix-${workflow.skillName}" in plugin
    assert "amp.on('agent.start'" in plugin
    assert "amp.activeThread.current?.id === event.thread.id" in plugin
    assert "function parentDirectories(path: string)" in plugin
    assert "...projectDirectories.map" in plugin
    assert "statSync(candidate).isFile()" in plugin
    assert "].join('\\n')" in plugin
    assert "].join('\n')" not in plugin
    assert "amp skill list" not in plugin
    assert "--codex" not in plugin
    assert "amp.createAgent" in plugin
    assert "tools: ['Read', 'finder']" in plugin
    assert "Promise.allSettled" in plugin
    assert "parentThreadID" in plugin
    assert "executor: 'local'" in plugin
    assert "name: 'elixir_phoenix_parallel_review'" in plugin
    assert "name: 'elixir_phoenix_parallel_investigate'" in plugin
    assert "amp.on('tool.call'" in plugin
    assert "amp.helpers.filesModifiedByToolCall(event)" in plugin
    assert "amp.on('agent.end'" in plugin
    assert "action: 'continue'" in plugin
    assert "amp.experimental" not in plugin

    review = (output / "skills" / "phx-review" / "SKILL.md").read_text()
    investigate = (output / "skills" / "phx-investigate" / "SKILL.md").read_text()
    assert "elixir_phoenix_parallel_review" in review
    assert "elixir_phoenix_parallel_investigate" in investigate


def test_generated_plugin_runtime_policies_with_bun(tmp_path) -> None:
    bun = shutil.which("bun")
    if not bun:
        pytest.skip("Bun is required for the generated Amp plugin behavior harness")

    output = tmp_path / "amp"
    workspace = tmp_path / "workspace"
    home = tmp_path / "home"
    home.mkdir()
    amp.build_target(SOURCE_PLUGIN_DIR, output)
    shutil.copytree(output / "skills", workspace / ".agents" / "skills")

    result = subprocess.run(
        [
            bun,
            "run",
            str(Path(__file__).with_name("amp_plugin_harness.ts")),
            str(output / amp.PLUGIN_RELATIVE_PATH),
            str(workspace),
        ],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Amp plugin behavior harness passed" in result.stdout


def test_projects_five_canonical_agents_to_enforced_read_only_prompts() -> None:
    specialists = amp.discover_specialists(SOURCE_PLUGIN_DIR)

    assert len(specialists) == 5
    for specialist in specialists:
        assert "Your only tools are\n`Read` and `finder`" in specialist.instructions
        assert "Never modify source" in specialist.instructions
        assert "Save Findings File First" not in specialist.instructions
        assert "call `Write`" not in specialist.instructions
        assert "Write audit to" not in specialist.instructions
        assert "Write review to" not in specialist.instructions


def test_missing_required_canonical_specialist_fails_before_replacing_target(
    tmp_path,
) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "one", "phx:one")
    agents = plugin / "agents"
    agents.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged\n", encoding="utf-8")

    with pytest.raises(ValueError, match="required Amp specialist source is missing"):
        amp.build_target(plugin, output)

    assert sentinel.read_text(encoding="utf-8") == "unchanged\n"


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


def test_build_rejects_palette_collisions_before_replacing_output(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "first", "foo")
    _write_skill(plugin, "second", "phx:foo")
    output = tmp_path / "output"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")

    with pytest.raises(ValueError, match="palette label collision `phx: foo`"):
        amp.build_target(plugin, output)

    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_workflow_command_rejects_reserved_clear_id(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "clear", "clear-pending-workflow")

    with pytest.raises(ValueError, match="command ID is reserved"):
        amp.workflow_commands(amp.discover_skills(plugin))


def test_workflow_command_rejects_native_palette_label(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "specialist", "phx:specialist")

    with pytest.raises(ValueError, match="phx: specialist.*reserved"):
        amp.workflow_commands(amp.discover_skills(plugin))


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


def test_complete_target_generates_native_watch_plugin_and_overlay(tmp_path) -> None:
    output = tmp_path / "amp"

    result = amp.build_target(SOURCE_PLUGIN_DIR, output)

    assert result == {"skills": 51, "plugins": 1}
    assert amp.validate_plugin(
        output / amp.PLUGIN_TARGET_RELATIVE,
        SOURCE_PLUGIN_DIR,
    ) == 1
    watch = (output / "skills/phx-watch-pr/SKILL.md").read_text(encoding="utf-8")
    assert "elixir_phoenix_watch_pr" in watch
    assert "keep-alive lease" in watch
    assert "Never merge or deploy" in watch
    assert "gh pr checks {n} --watch" not in watch
    assert not (output / "skills/phx-watch-pr/scripts/watch-pr.sh").exists()


def test_complete_amp_target_is_deterministic(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    amp.build_target(SOURCE_PLUGIN_DIR, first)
    amp.build_target(SOURCE_PLUGIN_DIR, second)

    assert _tree_hash(first) == _tree_hash(second)


def test_native_watch_plugin_lifecycle_harness(tmp_path) -> None:
    output = tmp_path / "amp"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    amp.build_target(SOURCE_PLUGIN_DIR, output)

    result = subprocess.run(
        [
            "npx",
            "tsx",
            "scripts/tests/amp_watch_pr_harness.mts",
            str(output / amp.PLUGIN_TARGET_RELATIVE),
            str(workspace),
        ],
        cwd=Path(__file__).parents[2],
        text=True,
        capture_output=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "Amp phx-watch-pr lifecycle harness passed" in result.stdout


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
    _write_amp_plugin(plugin)
    output = tmp_path / "target"
    amp.build_target(plugin, output)
    before = _tree_hash(output)
    monkeypatch.setattr(build_amp_skills, "SOURCE_PLUGIN_DIR", plugin)
    monkeypatch.setattr(build_amp_skills, "OUTPUT_DIR", output)

    assert build_amp_skills.check() == 0
    assert _tree_hash(output) == before

    skill_file = output / "skills" / "phx-one" / "SKILL.md"
    skill_file.write_text(skill_file.read_text() + "drift\n", encoding="utf-8")
    drifted = _tree_hash(output)

    assert build_amp_skills.check() == 1
    assert _tree_hash(output) == drifted
