from __future__ import annotations

import json
from pathlib import Path

from scripts import generated_target_snapshots as snapshots


def test_snapshot_detects_path_content_and_executable_changes(tmp_path: Path) -> None:
    root = tmp_path / "target"
    root.mkdir()
    script = root / "run.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o644)
    baseline = snapshots.snapshot_tree(root)

    script.write_text("#!/bin/sh\necho changed\n", encoding="utf-8")
    assert snapshots.snapshot_tree(root) != baseline
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o700)
    assert snapshots.snapshot_tree(root) != baseline

    executable = snapshots.snapshot_tree(root)
    script.chmod(0o755)
    assert snapshots.snapshot_tree(root) == executable

    (root / "added.txt").write_text("added\n", encoding="utf-8")
    assert snapshots.snapshot_tree(root) != executable


def test_snapshot_rejects_invalid_target_roots(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    empty = tmp_path / "empty"
    empty.mkdir()
    regular_file = tmp_path / "target-file"
    regular_file.write_text("not a directory\n", encoding="utf-8")
    symlink = tmp_path / "target-link"
    symlink.symlink_to(empty, target_is_directory=True)

    for root in (missing, empty, regular_file, symlink):
        try:
            snapshots.snapshot_tree(root)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected invalid target rejection for {root}")


def test_check_is_read_only_and_detects_drift(tmp_path: Path, monkeypatch) -> None:
    targets = tmp_path / "targets"
    for name in snapshots.TARGET_NAMES:
        target = targets / name
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    snapshot_file = tmp_path / "snapshots.json"
    monkeypatch.setattr(snapshots, "TARGETS_DIR", targets)
    monkeypatch.setattr(snapshots, "SNAPSHOT_FILE", snapshot_file)

    snapshots.update()
    baseline = snapshot_file.read_bytes()
    assert snapshots.check() == 0

    (targets / "codex" / "SKILL.md").write_text("changed\n", encoding="utf-8")
    assert snapshots.check() == 1
    assert snapshot_file.read_bytes() == baseline


def test_repository_snapshots_cover_all_targets() -> None:
    expected = json.loads(snapshots.SNAPSHOT_FILE.read_text(encoding="utf-8"))
    assert expected["format"] == snapshots.FORMAT_VERSION
    assert tuple(expected["targets"]) == tuple(sorted(snapshots.TARGET_NAMES))
