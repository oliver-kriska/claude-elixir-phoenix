from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from scripts import build_codex_skills
from scripts.build_codex_skills import _differences
from scripts.port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from scripts.port_lib import codex
from scripts.port_lib.frontmatter import parse_file


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(stat.S_IMODE(path.stat().st_mode).to_bytes(2, "big"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _write_skill(
    root: Path,
    directory: str,
    name: str,
    body: str = "# Skill\n",
    description: str = "Use /phx:review for tests.",
) -> Path:
    manifest_dir = root / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_file = manifest_dir / "plugin.json"
    if not manifest_file.exists():
        manifest_file.write_text(
            json.dumps({"name": "fixture", "version": "1.2.3"}),
            encoding="utf-8",
        )
    skill_dir = root / "skills" / directory
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\neffort: high\n---\n\n{body}",
        encoding="utf-8",
    )
    return skill_dir


def test_builds_every_canonical_skill_without_mutating_claude_or_amp(tmp_path) -> None:
    source_before = _tree_hash(SOURCE_PLUGIN_DIR)
    amp_before = _tree_hash(TARGETS_DIR / "amp")
    output = tmp_path / "codex"

    result = codex.build(SOURCE_PLUGIN_DIR, output)
    discovered = codex.discover_skills(SOURCE_PLUGIN_DIR)

    assert result == {"skills": len(discovered)}
    assert len(discovered) == 51
    assert codex.validate(output) == len(discovered)
    assert {item.target_name for item in discovered} == {
        path.parent.name for path in (output / "skills").glob("*/SKILL.md")
    }
    assert _tree_hash(SOURCE_PLUGIN_DIR) == source_before
    assert _tree_hash(TARGETS_DIR / "amp") == amp_before


def test_complete_subtree_is_copied_and_only_markdown_is_transformed(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(
        plugin,
        "source",
        "phx:source",
        "Read `${CLAUDE_SKILL_DIR}/notes/guide.md` and run /phx:source.\n",
    )
    (skill / "notes").mkdir()
    (skill / "notes" / "guide.md").write_text(
        "Use /phx:source and /ecto:n1-check.\n", encoding="utf-8"
    )
    (skill / "notes" / "guide.md").chmod(0o744)
    payload = b"\x00\xff\x10"
    (skill / "assets").mkdir()
    (skill / "assets" / "payload.bin").write_bytes(payload)
    executable = skill / "scripts" / "run.sh"
    executable.parent.mkdir()
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)

    output = tmp_path / "codex"
    codex.build(plugin, output)
    generated = output / "skills" / "phx-source"

    assert (generated / "assets" / "payload.bin").read_bytes() == payload
    assert stat.S_IMODE((generated / "scripts" / "run.sh").stat().st_mode) == 0o755
    assert "$phx-source" in (generated / "SKILL.md").read_text()
    assert "$phx-source" in (generated / "notes" / "guide.md").read_text()
    assert "$ecto-n1-check" in (generated / "notes" / "guide.md").read_text()
    assert stat.S_IMODE((generated / "notes" / "guide.md").stat().st_mode) == 0o744
    assert "notes/guide.md" in (generated / "SKILL.md").read_text()
    assert set(path.relative_to(skill) for path in skill.rglob("*") if path.is_file()) == {
        path.relative_to(generated)
        for path in generated.rglob("*")
        if path.is_file()
    }


def test_frontmatter_and_all_markdown_use_codex_invocation_syntax(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(
        plugin,
        "source",
        "phx:source",
        "Use /phx:review, /lv:assigns, and /ecto:n1-check.\n",
    )
    (skill / "references").mkdir()
    (skill / "references" / "guide.md").write_text(
        "Use /phx:review.\n", encoding="utf-8"
    )

    output = tmp_path / "codex"
    codex.build(plugin, output)
    generated = output / "skills" / "phx-source" / "SKILL.md"
    frontmatter = parse_file(generated)

    assert frontmatter.data == {
        "name": "phx-source",
        "description": "Use $phx-review for tests.",
    }
    all_markdown = "\n".join(
        path.read_text(encoding="utf-8") for path in output.rglob("*.md")
    )
    assert "$phx-review" in all_markdown
    assert "$lv-assigns" in all_markdown
    assert "$ecto-n1-check" in all_markdown
    assert not any(token in all_markdown for token in ("/phx:", "/lv:", "/ecto:"))


def test_rewrites_cross_skill_resources_and_rejects_missing_or_escaping_paths(
    tmp_path,
) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(
        plugin,
        "first",
        "phx:first",
        "Read `${CLAUDE_SKILL_DIR}/../second/references/guide.md`.\n",
    )
    second = _write_skill(plugin, "second", "phx:second")
    (second / "references").mkdir()
    (second / "references" / "guide.md").write_text("Guide\n", encoding="utf-8")

    output = tmp_path / "codex"
    codex.build(plugin, output)
    assert "../phx-second/references/guide.md" in (
        output / "skills" / "phx-first" / "SKILL.md"
    ).read_text()

    missing = tmp_path / "missing"
    broken = _write_skill(
        missing,
        "broken",
        "phx:broken",
        "Read `${CLAUDE_SKILL_DIR}/references/missing.md`.\n",
    )
    with pytest.raises(ValueError, match=str(broken / "SKILL.md")):
        codex.build(missing, tmp_path / "missing-output")

    escaping = tmp_path / "escaping"
    bad = _write_skill(
        escaping,
        "bad",
        "phx:bad",
        "Read `${CLAUDE_SKILL_DIR}/../../secret.md`.\n",
    )
    (escaping / "secret.md").write_text("secret\n", encoding="utf-8")
    with pytest.raises(ValueError, match=str(bad / "SKILL.md")):
        codex.build(escaping, tmp_path / "escaping-output")


def test_normalized_names_are_valid_unique_and_collisions_preserve_target(
    tmp_path,
) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "first", "phx:plan")
    _write_skill(plugin, "second", "phx-plan")
    output = tmp_path / "codex"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")

    with pytest.raises(ValueError, match="collision.*phx-plan"):
        codex.build(plugin, output)

    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_build_rejects_symlinked_resources(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(plugin, "one", "phx:one")
    outside = tmp_path / "outside.txt"
    outside.write_text("must not be packaged\n", encoding="utf-8")
    (skill / "linked.txt").symlink_to(outside)

    with pytest.raises(ValueError, match="linked.txt.*symlinks are not supported"):
        codex.build(plugin, tmp_path / "codex")


def test_projection_is_deterministic_byte_for_byte_and_mode_for_mode(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(plugin, "one", "phx:one")
    script = skill / "run.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o755)
    first = tmp_path / "first"
    second = tmp_path / "second"

    codex.build(plugin, first)
    codex.build(plugin, second)

    assert _tree_hash(first) == _tree_hash(second)
    assert _differences(first, second) == []


def test_drift_comparison_detects_added_removed_and_type_changes(tmp_path) -> None:
    expected = tmp_path / "expected"
    actual = tmp_path / "actual"
    expected.mkdir()
    actual.mkdir()
    (expected / "missing.txt").write_text("missing\n", encoding="utf-8")
    (actual / "extra.txt").write_text("extra\n", encoding="utf-8")
    (expected / "node").write_text("file\n", encoding="utf-8")
    (actual / "node").mkdir()

    assert _differences(expected, actual) == [
        "extra in target: extra.txt",
        "missing in target: missing.txt",
        "type differs: node (file != directory)",
    ]


def test_build_restores_previous_target_when_installation_fails(
    tmp_path, monkeypatch
) -> None:
    plugin = tmp_path / "plugin"
    _write_skill(plugin, "one", "phx:one")
    output = tmp_path / "codex"
    codex.build(plugin, output)
    before = _tree_hash(output)
    original_rename = Path.rename

    def fail_replacement(self, target):
        if self.name == "replacement" and Path(target) == output:
            raise OSError("simulated installation failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_replacement)
    with pytest.raises(OSError, match="simulated installation failure"):
        codex.build(plugin, output)

    assert _tree_hash(output) == before
    assert not list(output.parent.glob(".codex.backup-*"))


def test_drift_check_is_read_only_and_detects_content_and_mode(tmp_path, monkeypatch) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(plugin, "one", "phx:one")
    script = skill / "run.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o755)
    output = tmp_path / "codex"
    codex.build(plugin, output)
    monkeypatch.setattr(build_codex_skills, "SOURCE_PLUGIN_DIR", plugin)
    monkeypatch.setattr(build_codex_skills, "OUTPUT_DIR", output)
    before = _tree_hash(output)

    assert build_codex_skills.check() == 0
    assert _tree_hash(output) == before

    generated_script = output / "skills" / "phx-one" / "run.sh"
    generated_script.chmod(0o644)
    mode_drift = _tree_hash(output)
    assert build_codex_skills.check() == 1
    assert _tree_hash(output) == mode_drift

    generated_script.chmod(0o755)
    skill_file = output / "skills" / "phx-one" / "SKILL.md"
    skill_file.write_text(skill_file.read_text() + "drift\n", encoding="utf-8")
    content_drift = _tree_hash(output)
    assert build_codex_skills.check() == 1
    assert _tree_hash(output) == content_drift


def test_manifests_are_conformant_and_every_declared_path_resolves() -> None:
    root = TARGETS_DIR.parent
    target = TARGETS_DIR / "codex"
    plugin_manifest = json.loads(
        (target / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    canonical_manifest = json.loads(
        (SOURCE_PLUGIN_DIR / ".claude-plugin" / "plugin.json").read_text(
            encoding="utf-8"
        )
    )
    marketplace = json.loads(
        (root / ".agents" / "plugins" / "marketplace.json").read_text(
            encoding="utf-8"
        )
    )

    assert plugin_manifest["skills"] == "./skills/"
    assert plugin_manifest["name"] == canonical_manifest["name"]
    assert plugin_manifest["version"] == canonical_manifest["version"]
    assert "skills" not in plugin_manifest.get("interface", {})
    assert "agents" not in plugin_manifest
    assert "commands" not in plugin_manifest
    assert (target / plugin_manifest["skills"]).is_dir()

    [entry] = marketplace["plugins"]
    assert entry["name"] == plugin_manifest["name"]
    assert entry["source"] == {"source": "local", "path": "./targets/codex"}
    assert (root / entry["source"]["path"]).resolve() == target.resolve()
    assert (root / entry["source"]["path"] / ".codex-plugin/plugin.json").is_file()


def test_repository_hook_is_native_synchronous_and_projects_source(tmp_path) -> None:
    target = TARGETS_DIR / "codex"
    hooks_file = target / "hooks" / "hooks.json"
    hooks = json.loads(hooks_file.read_text(encoding="utf-8"))
    [group] = hooks["hooks"]["PreToolUse"]
    [handler] = group["hooks"]

    assert hooks == codex.CODEX_HOOKS
    assert group["matcher"] == "Bash"
    assert handler["type"] == "command"
    assert handler["command"].startswith('"${PLUGIN_ROOT}/')
    assert "async" not in handler
    assert "if" not in handler

    source = SOURCE_PLUGIN_DIR / "hooks" / "scripts" / codex.CODEX_HOOK_SCRIPT
    generated = target / "hooks" / "scripts" / codex.CODEX_HOOK_SCRIPT
    assert generated.read_text(encoding="utf-8") == source.read_text(
        encoding="utf-8"
    ).replace("Claude Code", "Codex").replace("Claude's", "Codex's")
    assert "outside Codex" in generated.read_text(encoding="utf-8")
    assert "outside Claude Code" not in generated.read_text(encoding="utf-8")
    assert stat.S_IMODE(generated.stat().st_mode) == stat.S_IMODE(source.stat().st_mode)
    assert os.access(generated, os.X_OK)

    plugin_root = tmp_path / "plugin root with spaces"
    shutil.copytree(target / "hooks", plugin_root / "hooks")
    command = handler["command"].replace("${PLUGIN_ROOT}", str(plugin_root))
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "mix.exs").write_text("defmodule Fixture.MixProject do\nend\n")
    blocked = subprocess.run(
        ["/bin/bash", "-lc", command],
        input=json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "mix ecto.reset"}}
        ),
        text=True,
        capture_output=True,
        cwd=fixture,
        check=True,
    )
    output = json.loads(blocked.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert output["hookSpecificOutput"]["permissionDecisionReason"]
    assert output["hookSpecificOutput"]["additionalContext"]

    safe = subprocess.run(
        ["/bin/bash", "-lc", command],
        input=json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "mix test"}}
        ),
        text=True,
        capture_output=True,
        cwd=fixture,
        check=True,
    )
    assert safe.stdout == ""

    installed_script = plugin_root / "hooks" / "scripts" / codex.CODEX_HOOK_SCRIPT
    installed_script.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    installed_script.chmod(0o755)
    failed_open = subprocess.run(
        ["/bin/bash", "-lc", command],
        input=json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "mix ecto.reset"}}
        ),
        text=True,
        capture_output=True,
        cwd=fixture,
        check=True,
    )
    assert failed_open.stdout == ""


def test_flagship_overlays_are_anchored_and_remove_claude_runtime_dependencies() -> None:
    target = TARGETS_DIR / "codex" / "skills"
    investigate = (target / "phx-investigate" / "SKILL.md").read_text()
    review = (target / "phx-review" / "SKILL.md").read_text()
    review_agents = (
        target / "phx-review" / "references" / "agent-spawning.md"
    ).read_text()
    review_requirements = (
        target / "phx-review" / "references" / "requirements-detection.md"
    ).read_text()
    investigate_patterns = (
        target / "phx-investigate" / "references" / "error-patterns.md"
    ).read_text()
    investigate_template = (
        target / "phx-investigate" / "references" / "investigation-template.md"
    ).read_text()

    assert "$phx-investigate" in investigate
    assert "Reproduce Before Fixing" in investigate
    assert "Tidewave is optional" in investigate
    assert "$phx-review" in review
    assert "Review is read-only" in review
    assert "sequential review is fully valid" in review
    assert "optional performance optimization" in review_agents
    assert "Mark `NOT AVAILABLE` and continue" in review_requirements
    assert "generic read-only subagent" in investigate_patterns
    assert "Only when the user explicitly authorizes" in investigate_patterns
    assert "do not write a report file" in investigate_template

    combined = (
        investigate
        + review
        + review_agents
        + review_requirements
        + investigate_patterns
        + investigate_template
    )
    forbidden = (
        "TaskCreate",
        "TaskUpdate",
        "TaskGet",
        "TaskList",
        "AskUserQuestion",
        "subagent_type",
        "$ARGUMENTS",
        "mcp__tidewave__",
        "mcp__linear__",
        "${CODEX_PLUGIN_ROOT}",
    )
    assert not any(token in combined for token in forbidden)


def test_repository_target_has_no_unresolved_claude_tokens() -> None:
    markdown = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (TARGETS_DIR / "codex").rglob("*.md")
    )
    assert not any(
        token in markdown
        for token in (
            "${CLAUDE_SKILL_DIR}",
            "${CLAUDE_PLUGIN_ROOT}",
            "${CODEX_PLUGIN_ROOT}",
            "/phx:",
            "/lv:",
            "/ecto:",
        )
    )


def test_repository_non_markdown_bytes_and_modes_match_canonical_source() -> None:
    output = TARGETS_DIR / "codex" / "skills"
    for skill in codex.discover_skills(SOURCE_PLUGIN_DIR):
        generated = output / skill.target_name
        for source in skill.source_dir.rglob("*"):
            if source.is_dir() or source.name in codex.IGNORED_FILES:
                continue
            target = generated / source.relative_to(skill.source_dir)
            assert target.is_file(), f"missing packaged resource: {target}"
            if source.suffix.lower() != ".md":
                assert target.read_bytes() == source.read_bytes()
                assert stat.S_IMODE(target.stat().st_mode) == stat.S_IMODE(
                    source.stat().st_mode
                )
