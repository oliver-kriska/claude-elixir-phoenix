from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest

from scripts import build_pi_skills
from scripts.port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from scripts.port_lib import pi
from scripts.port_lib.frontmatter import parse_file
from scripts.port_lib.generated_tree import tree_differences


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
    root: Path, directory: str, name: str, body: str = "# Skill\n"
) -> Path:
    manifest_dir = root / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = manifest_dir / "plugin.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps(
                {
                    "name": "fixture",
                    "version": "1.0.0",
                    "keywords": [],
                    "author": {},
                }
            ),
            encoding="utf-8",
        )
    skill = root / "skills" / directory
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Use /phx:review.\neffort: high\n---\n\n{body}",
        encoding="utf-8",
    )
    return skill


def test_builds_all_canonical_skills_without_mutating_other_targets(tmp_path) -> None:
    source_before = _tree_hash(SOURCE_PLUGIN_DIR)
    amp_before = _tree_hash(TARGETS_DIR / "amp")
    codex_before = _tree_hash(TARGETS_DIR / "codex")
    output = tmp_path / "pi"

    result = pi.build(SOURCE_PLUGIN_DIR, output)
    discovered = pi.discover_skills(SOURCE_PLUGIN_DIR)

    assert result == {"skills": len(discovered)}
    assert len(discovered) == 51
    assert pi.validate(output) == 51
    assert {skill.target_name for skill in discovered} == {
        path.parent.name for path in (output / "skills").glob("*/SKILL.md")
    }
    assert _tree_hash(SOURCE_PLUGIN_DIR) == source_before
    assert _tree_hash(TARGETS_DIR / "amp") == amp_before
    assert _tree_hash(TARGETS_DIR / "codex") == codex_before


def test_complete_subtree_bytes_modes_and_pi_syntax(tmp_path) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(
        plugin,
        "source",
        "phx:source",
        "Read `${CLAUDE_SKILL_DIR}/notes/guide.md`; use /phx:source, "
        "/lv:assigns, /ecto:n1-check, and /quick. Keep "
        "../phx-deps-audit/references/guide.md and /tmp/phx-audit-run intact.\n",
    )
    notes = skill / "notes"
    notes.mkdir()
    guide = notes / "guide.md"
    guide.write_text("Use /phx:review.\n", encoding="utf-8")
    guide.chmod(0o744)
    payload = skill / "assets" / "payload.bin"
    payload.parent.mkdir()
    payload.write_bytes(b"\x00\xff\x10")
    script = skill / "scripts" / "run.sh"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o755)

    output = tmp_path / "pi"
    pi.build(plugin, output)
    generated = output / "skills" / "phx-source"
    markdown = "\n".join(path.read_text() for path in generated.rglob("*.md"))

    assert parse_file(generated / "SKILL.md").data == {
        "name": "phx-source",
        "description": "Use /skill:phx-review.",
    }
    assert "/skill:phx-source" in markdown
    assert "/skill:lv-assigns" in markdown
    assert "/skill:ecto-n1-check" in markdown
    assert "/skill:phx-quick" in markdown
    assert "../phx-deps-audit/references/guide.md" in markdown
    assert "/tmp/phx-audit-run" in markdown
    assert "../skill:phx-deps-audit" not in markdown
    assert "/tmp/skill:phx-audit" not in markdown
    assert "notes/guide.md" in markdown
    assert (generated / "assets/payload.bin").read_bytes() == payload.read_bytes()
    assert stat.S_IMODE((generated / "scripts/run.sh").stat().st_mode) == 0o755
    assert stat.S_IMODE((generated / "notes/guide.md").stat().st_mode) == 0o744
    assert {path.relative_to(skill) for path in skill.rglob("*") if path.is_file()} == {
        path.relative_to(generated) for path in generated.rglob("*") if path.is_file()
    }


def test_pi_command_rewrite_requires_complete_tokens() -> None:
    assert pi._rewrite_commands("Use /phx:review and $lv-assigns.") == (
        "Use /skill:phx-review and /skill:lv-assigns."
    )
    for unchanged in (
        "/tmp/phx:review",
        "/tmp/phx-review",
        "/tmp/$phx-review",
        "/phx:Review",
        "/phx:review_more",
        "$phx-review_more",
        "/phx:*extra",
    ):
        assert pi._rewrite_commands(unchanged) == unchanged


def test_rejects_collisions_missing_resources_and_symlinks_without_replacing_target(
    tmp_path,
) -> None:
    collision = tmp_path / "collision"
    _write_skill(collision, "one", "phx:plan")
    _write_skill(collision, "two", "phx-plan")
    output = tmp_path / "pi"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("unchanged", encoding="utf-8")
    with pytest.raises(ValueError, match="collision.*phx-plan"):
        pi.build(collision, output)
    assert sentinel.read_text() == "unchanged"

    missing = tmp_path / "missing"
    _write_skill(
        missing,
        "one",
        "phx:one",
        "Read `${CLAUDE_SKILL_DIR}/references/missing.md`.\n",
    )
    with pytest.raises(ValueError, match="missing referenced resource"):
        pi.build(missing, tmp_path / "missing-output")

    linked = tmp_path / "linked"
    skill = _write_skill(linked, "one", "phx:one")
    outside = tmp_path / "outside"
    outside.write_text("outside", encoding="utf-8")
    (skill / "linked.txt").symlink_to(outside)
    with pytest.raises(ValueError, match="symlinks are not supported"):
        pi.build(linked, tmp_path / "linked-output")


def test_determinism_rollback_and_read_only_drift_detection(
    tmp_path, monkeypatch
) -> None:
    plugin = tmp_path / "plugin"
    skill = _write_skill(plugin, "one", "phx:one")
    script = skill / "run.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o755)
    first = tmp_path / "first"
    second = tmp_path / "second"
    pi.build(plugin, first)
    pi.build(plugin, second)
    assert tree_differences(first, second) == []
    assert _tree_hash(first) == _tree_hash(second)

    before = _tree_hash(first)
    original_rename = Path.rename

    def fail_replacement(self, target):
        if self.name == "replacement" and Path(target) == first:
            raise OSError("simulated installation failure")
        return original_rename(self, target)

    monkeypatch.setattr(Path, "rename", fail_replacement)
    with pytest.raises(OSError, match="simulated installation failure"):
        pi.build(plugin, first)
    assert _tree_hash(first) == before
    monkeypatch.setattr(Path, "rename", original_rename)

    monkeypatch.setattr(build_pi_skills, "SOURCE_PLUGIN_DIR", plugin)
    monkeypatch.setattr(build_pi_skills, "OUTPUT_DIR", first)
    assert build_pi_skills.check() == 0
    script_target = first / "skills/phx-one/run.sh"
    script_target.chmod(0o644)
    drifted = _tree_hash(first)
    assert build_pi_skills.check() == 1
    assert _tree_hash(first) == drifted
    script_target.chmod(0o755)
    (first / "extra.txt").write_text("drift", encoding="utf-8")
    assert build_pi_skills.check() == 1


def test_repository_manifest_resources_and_flagship_overlays() -> None:
    target = TARGETS_DIR / "pi"
    manifest = json.loads((target / "package.json").read_text(encoding="utf-8"))
    repository_manifest = json.loads(
        (TARGETS_DIR.parent / "package.json").read_text(encoding="utf-8")
    )
    assert manifest["pi"] == {"skills": ["./skills"]}
    assert isinstance(manifest["pi"]["skills"], list)
    assert "prompts" not in manifest["pi"]
    assert "extensions" not in manifest["pi"]
    assert "pi-package" in manifest["keywords"]
    assert manifest["name"] == pi.PI_PACKAGE_NAME == "pi-elixir-phoenix"
    assert repository_manifest["pi"] == {"skills": ["./targets/pi/skills"]}
    assert repository_manifest["name"] == manifest["name"]
    assert repository_manifest["version"] == manifest["version"]
    assert repository_manifest["description"] == manifest["description"]
    assert isinstance(repository_manifest["pi"]["skills"], list)
    assert (TARGETS_DIR.parent / repository_manifest["pi"]["skills"][0]).is_dir()
    assert pi.validate(target) == 51

    investigate = (target / "skills/phx-investigate/SKILL.md").read_text()
    review = (target / "skills/phx-review/SKILL.md").read_text()
    assert "/skill:phx-investigate" in investigate
    assert "Reproduce Before Fixing" in investigate
    assert "Tidewave is optional" in investigate
    assert "/skill:phx-review" in review
    assert "Review is read-only" in review
    assert "sequential review is fully valid" in review
    review_tree = "\n".join(
        path.read_text() for path in (target / "skills/phx-review").rglob("*.md")
    )
    assert "Codex subagent" not in review_tree
    assert not any(
        token in investigate + review
        for token in ("TaskCreate", "AskUserQuestion", "subagent_type", "$ARGUMENTS")
    )


def test_repository_plan_work_workflows_are_portable_and_resumable(tmp_path) -> None:
    generated = tmp_path / "pi"
    pi.build(SOURCE_PLUGIN_DIR, generated)
    target = generated / "skills"
    plan = "\n".join(p.read_text() for p in (target / "phx-plan").rglob("*.md"))
    work = "\n".join(p.read_text() for p in (target / "phx-work").rglob("*.md"))
    assert "/skill:phx-plan" in plan
    assert "Research checklist" in plan
    assert "perform the same tracks sequentially" in plan
    assert "/skill:phx-work" in work
    assert "Use the plan file as the portable task list" in work
    assert "execute every task sequentially" in work
    assert "progress.md" in work
    assert "[BLOCKED]" in work
    assert "clears `[BLOCKED]` when starting" in work
    assert "append-only" in work
    assert "**Started**:" in work
    forbidden = (
        "Agent(",
        "subagent_type",
        "TaskCreate",
        "TaskUpdate",
        "TaskGet",
        "TaskList",
        "AskUserQuestion",
        "$ARGUMENTS",
        "mcp__",
        "PostToolUse hook",
        "phoenix-patterns-analyst",
        "ecto-schema-designer",
        "liveview-architect",
        "oban-specialist",
        "otp-advisor",
        "security-analyzer",
        "testing-reviewer",
        "hex-library-researcher",
        "web-researcher",
        "call-tracer",
        "planning-orchestrator",
        "Spawn SPECIALIST",
        "run_in_background",
        "[agent]",
        "Agent annotation",
        "agent routing",
        "project_eval",
        "get_logs",
        "| Hook |",
        "Each hook",
        "/commit",
        "${CLAUDE_SKILL_DIR}",
        "${CLAUDE_PLUGIN_ROOT}",
        "spawning Elixir specialist agents",
        "Spawns Elixir specialist agents",
        "skip to agents",
        "Spawn agents selectively",
        "while agents still running",
        "agent spawning",
        "agent count",
        "Explore agents",
        "execute via subagents",
        "After spawning",
    )
    assert not any(token in plan + work for token in forbidden)


def test_generated_pr_review_and_full_are_portable(tmp_path) -> None:
    generated = tmp_path / "pi"
    pi.build(SOURCE_PLUGIN_DIR, generated)
    pr_review = "\n".join(
        p.read_text() for p in (generated / "skills/phx-pr-review").rglob("*.md")
    )
    full = "\n".join(
        p.read_text() for p in (generated / "skills/phx-full").rglob("*.md")
    )
    assert "/skill:phx-pr-review" in pr_review and "gh auth status" in pr_review
    assert "/skill:phx-full" in full and "read-only review" in full
    assert "Honor user gates" in full
    assert (
        "originalLine" in pr_review
        and "query($threadId: ID!, $endCursor: String)" in pr_review
    )
    assert (
        "comments(first:100, after:$endCursor)" in pr_review
        and "deduplicate by GraphQL `id`" in pr_review
    )
    assert all(f"Gate {gate}" in pr_review for gate in range(1, 5))
    assert "EDIT: NOT APPLICABLE" in pr_review and "`--fix` approves none" in pr_review
    assert "CHANGES_REQUESTED" in pr_review and "Outdated means" in pr_review
    assert "sole state authority" in full and "monotonic `seq`" in full
    assert "next legal phase is VERIFYING" in full and "Completion requires" in full
    assert "COMPOUNDING SKIPPED" in full
    assert not any(
        token in pr_review + full
        for token in ("--codex", "--Pi", "--OpenCode", "/skill:phx-compound")
    )
    assert (
        "specialist agents" not in (generated / "skills/phx-full/SKILL.md").read_text()
    )
    assert (
        "portable sequential plan-work"
        in parse_file(generated / "skills/phx-full/SKILL.md").data["description"]
    )
    assert not any(
        token in pr_review + full
        for token in (
            "Agent(",
            "TaskCreate",
            "AskUserQuestion",
            "mcp__",
            "workflow-orchestrator",
        )
    )


def test_repository_non_markdown_resources_match_canonical_bytes_and_modes() -> None:
    output = TARGETS_DIR / "pi" / "skills"
    for skill in pi.discover_skills(SOURCE_PLUGIN_DIR):
        generated = output / skill.target_name
        for source in skill.source_dir.rglob("*"):
            if source.is_dir() or source.name in pi.IGNORED_FILES:
                continue
            target = generated / source.relative_to(skill.source_dir)
            assert target.is_file(), f"missing packaged resource: {target}"
            if source.suffix.lower() != ".md":
                assert target.read_bytes() == source.read_bytes()
                assert stat.S_IMODE(target.stat().st_mode) == stat.S_IMODE(
                    source.stat().st_mode
                )
