from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins/rewrite/skills/verify/scripts/fingerprint.py"
)


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.resolve().parent))
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(key, raising=False)


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-C", str(repo), *args],
        check=True, capture_output=True,
    )


def fp(directory: Path, *args: str) -> dict:
    out = subprocess.run(
        [sys.executable, str(SCRIPT), str(directory), "--json", *args],
        check=True, capture_output=True, text=True,
    )
    return json.loads(out.stdout)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    write(root / "lib/app.ex", "defmodule App do\nend\n")
    write(root / ".gitignore", "/ignored/\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    return root


def test_clean_repo_is_head_only(repo: Path) -> None:
    result = fp(repo)

    assert result["mode"] == "git"
    assert len(result["head"]) == 40
    assert result["dirty_files"] == []


def test_already_modified_file_modified_again_changes_fingerprint(repo: Path) -> None:
    write(repo / "lib/app.ex", "defmodule App do\n  def a, do: 1\nend\n")
    first = fp(repo)
    write(repo / "lib/app.ex", "defmodule App do\n  def a, do: 2\nend\n")
    second = fp(repo)

    assert first["dirty_files"] == second["dirty_files"] == ["lib/app.ex"]
    assert first["head"] == second["head"]
    assert first["content_fingerprint"] != second["content_fingerprint"]


def test_untracked_file_counts_individually(repo: Path) -> None:
    clean = fp(repo)
    write(repo / "test/new/a_test.exs", "one")
    added = fp(repo)
    write(repo / "test/new/a_test.exs", "two")
    changed = fp(repo)

    assert added["dirty_files"] == ["test/new/a_test.exs"]
    assert len({clean["content_fingerprint"], added["content_fingerprint"],
                changed["content_fingerprint"]}) == 3


def test_ignored_file_does_not_count(repo: Path) -> None:
    before = fp(repo)
    write(repo / "ignored/out.txt", "generated")

    assert fp(repo) == before


def test_excluded_dirs_do_not_count(repo: Path) -> None:
    before = fp(repo, "--exclude", "cover/")
    write(repo / ".claude/rewrite/verify/02/evidence/run.log", "1 test, 0 failures")
    write(repo / "_build/test/lib/app.beam", "beam")
    write(repo / "deps/jason/mix.exs", "dep")
    write(repo / "cover/index.html", "report")
    after = fp(repo, "--exclude", "cover/")

    assert after == before
    assert fp(repo)["dirty_files"] == ["cover/index.html"]


def test_deleted_tracked_file_counts(repo: Path) -> None:
    before = fp(repo)
    (repo / "lib/app.ex").unlink()
    after = fp(repo)

    assert after["dirty_files"] == ["lib/app.ex"]
    assert after["content_fingerprint"] != before["content_fingerprint"]


def test_new_commit_changes_fingerprint(repo: Path) -> None:
    before = fp(repo)
    write(repo / "lib/b.ex", "b")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "b")
    after = fp(repo)

    assert after["dirty_files"] == []
    assert after["head"] != before["head"]
    assert after["content_fingerprint"] != before["content_fingerprint"]


def test_subdirectory_paths_are_relative(repo: Path) -> None:
    write(repo / "lib/app.ex", "changed")
    write(repo / "README.md", "outside the subdirectory")

    assert fp(repo / "lib")["dirty_files"] == ["app.ex"]


def test_non_git_dir_hashes_every_file(tmp_path: Path) -> None:
    root = tmp_path / "legacy"
    write(root / "app/models/user.rb", "class User; end")
    write(root / "node_modules/x/index.js", "x")
    before = fp(root)
    write(root / "node_modules/x/index.js", "y")
    unchanged = fp(root)
    write(root / "app/models/user.rb", "class User < Base; end")
    after = fp(root)

    assert before["mode"] == "tree"
    assert before["head"] is None
    assert before["file_count"] == 1
    assert unchanged == before
    assert after["content_fingerprint"] != before["content_fingerprint"]


def test_output_is_deterministic_and_never_contains_contents(repo: Path) -> None:
    write(repo / "config/test.secret.exs", "password: hunter2-secret")
    text = subprocess.run(
        [sys.executable, str(SCRIPT), str(repo)], check=True, capture_output=True, text=True,
    ).stdout

    assert fp(repo) == fp(repo)
    assert "hunter2" not in text
    assert "hunter2" not in json.dumps(fp(repo))
    assert "content_fingerprint: " in text


def test_exclude_outside_dir_is_rejected(repo: Path) -> None:
    out = subprocess.run(
        [sys.executable, str(SCRIPT), str(repo), "--exclude", "../other"],
        capture_output=True, text=True,
    )

    assert out.returncode == 2
    assert out.stdout == ""
