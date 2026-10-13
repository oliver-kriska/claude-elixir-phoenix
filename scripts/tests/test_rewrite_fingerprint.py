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
    # The script drops inherited GIT_* variables, so an empty HOME is what keeps
    # the user's global config (LFS filters, excludesfile) out of its git calls.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.resolve().parent))
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(key, raising=False)


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        # A commit can start detached auto-maintenance, which writes into .git
        # while a test is snapshotting it.
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "maintenance.auto=false",
         "-c", "gc.auto=0", "-C", str(repo), *args],
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


def run_cli(directory: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(directory), "--json", *args],
        capture_output=True, text=True,
    )


@pytest.mark.parametrize(
    "flag, undo",
    [("--assume-unchanged", "--no-assume-unchanged"), ("--skip-worktree", "--no-skip-worktree")],
)
def test_hidden_index_flag_fails_closed(repo: Path, flag: str, undo: str) -> None:
    git(repo, "update-index", flag, "lib/app.ex")
    write(repo / "lib/app.ex", "defmodule App do\n  def a, do: 1\nend\n")

    result = run_cli(repo)

    assert result.returncode == 2
    assert result.stdout == ""
    assert "lib/app.ex" in result.stderr
    assert undo in result.stderr

    git(repo, "update-index", undo, "lib/app.ex")
    assert fp(repo)["dirty_files"] == ["lib/app.ex"]


def test_flagged_path_under_exclude_is_ignored(repo: Path) -> None:
    git(repo, "update-index", "--assume-unchanged", "lib/app.ex")

    assert run_cli(repo).returncode == 2
    assert run_cli(repo, "--exclude", "lib").returncode == 0


def make_repo(root: Path, files: dict[str, str]) -> Path:
    for rel, text in files.items():
        write(root / rel, text)
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    return root


def add_submodule(app: Path, lib: Path, path: str) -> None:
    git(app, "-c", "protocol.file.allow=always", "submodule", "--quiet", "add", str(lib), path)
    git(app, "commit", "-q", "-m", "vendor")


def arm_fsmonitor(tmp_path: Path, probe: str) -> Path:
    app = make_repo(tmp_path / "app", {"lib/app.ex": "a\n"})
    git(app, "config", "core.fsmonitor", probe)
    return app


def arm_clean_filter(driver: str):
    def arm(tmp_path: Path, probe: str) -> Path:
        app = make_repo(tmp_path / "app", {"lib/app.ex": "a\n", ".gitattributes": f"*.ex filter={driver}\n"})
        git(app, "config", f"filter.{driver}.clean", f"{probe} --filter")
        git(app, "config", f"filter.{driver}.required", "true")
        # Same size, new mtime: git re-hashes the file through the clean filter.
        os.utime(app / "lib/app.ex", ns=(0, 0))
        return app
    return arm


def arm_submodule_filter(tmp_path: Path, probe: str) -> Path:
    lib = make_repo(tmp_path / "lib", {"lib.ex": "a\n", ".gitattributes": "*.ex filter=probe\n"})
    app = make_repo(tmp_path / "app", {"lib/app.ex": "a\n"})
    add_submodule(app, lib, "vendored")
    git(app / "vendored", "config", "filter.probe.clean", f"{probe} --filter")
    os.utime(app / "vendored/lib.ex", ns=(0, 0))
    return app


@pytest.mark.parametrize(
    "arm",
    [arm_fsmonitor, arm_clean_filter("probe"), arm_clean_filter("probe=x"), arm_submodule_filter],
    ids=["fsmonitor", "clean-filter", "clean-filter-name-with-equals", "submodule-clean-filter"],
)
def test_git_never_runs_programs_configured_in_dir(tmp_path: Path, arm) -> None:
    sentinel = tmp_path / "probe-ran"
    probe = tmp_path / "probe.sh"
    probe.write_text(f"#!/bin/sh\ntouch '{sentinel}'\n[ \"$1\" = --filter ] && exec cat\nexit 1\n",
                     encoding="utf-8")
    probe.chmod(0o755)
    app = arm(tmp_path, str(probe))

    result = fp(app)

    assert result["mode"] == "git"
    assert not sentinel.exists()
    # The probe is armed: plain git runs it, so the assertion above is not vacuous.
    subprocess.run(["git", "-C", str(app), "diff", "--name-only", "HEAD"],
                   capture_output=True, stdin=subprocess.DEVNULL)
    assert sentinel.exists()


def test_inherited_git_environment_does_not_redirect_identity(
    repo: Path, tmp_path: Path, monkeypatch
) -> None:
    other = make_repo(tmp_path / "other", {"other.ex": "b\n"})
    own = fp(repo)
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    monkeypatch.setenv("GIT_INDEX_FILE", str(other / ".git/index"))
    monkeypatch.setenv("GIT_COMMON_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(other / ".git/objects"))

    assert fp(repo) == own


def test_edit_inside_submodule_work_tree_changes_fingerprint(tmp_path: Path) -> None:
    lib = make_repo(tmp_path / "lib", {"lib.ex": "a\n"})
    app = make_repo(tmp_path / "app", {"lib/app.ex": "a\n"})
    add_submodule(app, lib, "vendored")
    before = fp(app)
    write(app / "vendored/lib.ex", "b\n")
    edited = fp(app)
    write(app / "vendored/new.ex", "c\n")
    added = fp(app)
    left_out = fp(app, "--exclude", "vendored")
    write(app / "vendored/lib.ex", "d\n")

    assert before["submodules"] == ["vendored"]
    assert before["head"] == edited["head"] == added["head"]
    assert len({before["content_fingerprint"], edited["content_fingerprint"],
                added["content_fingerprint"]}) == 3
    assert left_out["submodules"] == []
    assert fp(app, "--exclude", "vendored") == left_out

    git(app / "vendored", "commit", "-q", "-am", "move the submodule commit")
    moved = fp(app)

    assert moved["submodules"] == ["vendored"]
    assert "vendored/lib.ex" in moved["dirty_files"]


def snapshot(root: Path) -> dict[str, tuple]:
    """Bytes, size and mtime of every file and directory under root, .git included."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            path = Path(dirpath, name)
            st = path.lstat()
            data = path.read_bytes() if path.is_file() and not path.is_symlink() else None
            out[str(path.relative_to(root))] = (data, st.st_size, st.st_mtime_ns)
    return out


def test_capture_writes_nothing_in_an_ordinary_repo(repo: Path) -> None:
    write(repo / "lib/staged.ex", "s\n")
    git(repo, "add", "lib/staged.ex")
    write(repo / "lib/untracked.ex", "u\n")
    os.utime(repo / "lib/app.ex", ns=(0, 0))
    before = snapshot(repo)

    result = fp(repo)

    assert snapshot(repo) == before
    assert result["dirty_files"] == ["lib/staged.ex", "lib/untracked.ex"]


def test_split_index_is_hashed_as_a_tree_without_reading_git(tmp_path: Path) -> None:
    app = make_repo(tmp_path / "app", {"lib/app.ex": "a\n", "lib/b.ex": "b\n"})
    git(app, "update-index", "--split-index")
    shared = list((app / ".git").glob("sharedindex.*"))
    for path in shared:
        os.utime(path, ns=(0, 0))
    write(app / "lib/app.ex", "changed\n")
    before = snapshot(app)

    result = fp(app)

    assert shared
    assert snapshot(app) == before
    assert (result["mode"], result["fallback"], result["head"]) == ("tree", "split-index", None)
    assert result["file_count"] == 2
    write(app / "lib/b.ex", "edited\n")
    assert fp(app)["content_fingerprint"] != result["content_fingerprint"]
