from __future__ import annotations

import json
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins/rewrite/skills/verify/scripts/evidence.py"
)


@pytest.fixture(autouse=True)
def isolated_git(monkeypatch, tmp_path: Path) -> None:
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
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "maintenance.auto=false",
         "-c", "gc.auto=0", "-C", str(repo), *args],
        check=True, capture_output=True,
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def ev(target: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=target, capture_output=True, text=True)


def committed(root: Path) -> Path:
    write(root / "lib/app.ex", "defmodule App do\nend\n")
    write(root / ".gitignore", "/_build/\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def target(tmp_path: Path) -> Path:
    root = committed(tmp_path / "target")
    source = committed(tmp_path / "legacy")
    assert ev(root, "init", "07", "--source", str(source)).returncode == 0
    return root


EVIDENCE = Path(".claude/rewrite/verify/07/evidence")


def records(target: Path, name: str) -> list[Path]:
    return sorted((target / EVIDENCE).glob(f"*-{name}.md"))


def fields(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- "):
            key, _, value = line[2:].partition(": ")
            out[key] = value
    return out


def test_run_records_exit_identity_and_log(target: Path) -> None:
    r = ev(target, "run", "07", "hello", "--", sys.executable, "-c", "print('6 tests, 0 failures, 1 excluded')")
    assert r.returncode == 0, r.stderr
    [md] = records(target, "hello")
    f = fields(md)
    assert f["exit_status"] == "0" and f["expected_exit"] == "0"
    assert f["identity"] == "fresh"
    assert f["target_before"] == f["target_after"] and "content_fingerprint=" in f["target_before"]
    assert f["source_before"] == f["source_after"]
    assert f["exunit"] == "6 tests, 0 failures, 1 excluded"
    assert (target / f["log"]).read_text(encoding="utf-8").strip() == "6 tests, 0 failures, 1 excluded"


def test_run_returns_the_command_status_and_records_the_expectation(target: Path) -> None:
    r = ev(target, "run", "07", "no-match", "--expect-exit", "1", "--", sys.executable, "-c", "raise SystemExit(1)")
    assert r.returncode == 1
    assert "as expected" in r.stdout
    assert fields(records(target, "no-match")[0])["expected_exit"] == "1"


def test_a_command_that_edits_the_target_is_stale(target: Path) -> None:
    edit = "open('lib/app.ex', 'a').write('# edited\\n')"
    assert ev(target, "run", "07", "edits", "--", sys.executable, "-c", edit).returncode == 0
    assert fields(records(target, "edits")[0])["identity"] == "stale"


def test_missing_command_is_127_and_still_recorded(target: Path) -> None:
    assert ev(target, "run", "07", "nope", "--", "no-such-binary-xyz").returncode == 127
    assert fields(records(target, "nope")[0])["exit_status"] == "127"


def test_uid_placeholder_is_unique_per_record_and_secrets_are_redacted(target: Path) -> None:
    for _ in range(2):
        ev(target, "run", "07", "hurl", "--", "env", "DATABASE_URL=postgres://u:pw@localhost/db",
           "SECRET_KEY_BASE=abc", sys.executable, "-c", "pass", "uid={uid}")
    commands = [fields(p)["command"] for p in records(target, "hurl")]
    assert len(commands) == 2
    assert all("pw@" not in c and "abc" not in c and "<redacted>" in c and "{uid}" not in c for c in commands)
    uids = {c.rsplit("uid=", 1)[1] for c in commands}
    assert len(uids) == 2
    names = fields(records(target, "hurl")[0])["env_names"]
    assert "DATABASE_URL" in names and "SECRET_KEY_BASE" in names


def test_run_without_init_is_an_evidence_error(tmp_path: Path) -> None:
    root = committed(tmp_path / "bare")
    r = ev(root, "run", "07", "x", "--", "true")
    assert r.returncode == 125 and "init" in r.stderr


def test_init_moves_the_previous_run_aside(target: Path, tmp_path: Path) -> None:
    ev(target, "run", "07", "first", "--", "true")
    assert ev(target, "init", "07", "--source", str(tmp_path / "legacy")).returncode == 0
    assert not records(target, "first")
    assert list((target / ".claude/rewrite/verify/07/superseded").glob("*/*-first.md"))


def test_status_lists_missing_outdated_and_unexpected(target: Path) -> None:
    write(target / EVIDENCE / "commands.md",
          "# Commands\n- `compile` — mix compile\n- `rg-ac17` — must find nothing\n- `k6` — smoke\nNot run: bru\n")
    ev(target, "run", "07", "compile", "--", "true")
    ev(target, "run", "07", "rg-ac17", "--", sys.executable, "-c", "raise SystemExit(1)")
    r = ev(target, "status", "07")
    assert r.returncode == 1  # k6 missing
    assert "k6: missing" in r.stdout
    assert "rg-ac17: exit 1 (expected 0), unexpected exit" in r.stdout
    assert "compile: exit 0 (expected 0), fresh, current" in r.stdout
    write(target / "lib/new.ex", "defmodule New do\nend\n")
    assert "compile: exit 0 (expected 0), outdated" in ev(target, "status", "07").stdout


def test_status_passes_when_every_listed_command_has_a_record(target: Path) -> None:
    write(target / EVIDENCE / "commands.md", "- `compile` — mix compile\n")
    ev(target, "run", "07", "compile", "--", "true")
    r = ev(target, "status", "07")
    assert r.returncode == 0, r.stdout
    assert "missing 0" in r.stdout


def fake_release(root: Path) -> Path:
    # Stands in for _build/prod/rel/app/bin/app: records its environment, then stays up.
    script = root / "_build/prod/rel/app/bin/app"
    write(script, "#!/bin/sh\nprintf '%s\\n' \"$RELEASE_DISTRIBUTION\" > \"$(dirname \"$0\")/../dist.txt\"\n"
                  "while :; do sleep 1; done\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def test_port_start_and_stop_own_only_their_process_group(target: Path) -> None:
    release = fake_release(target)
    neighbour = subprocess.Popen(["sleep", "60"])  # a process the port must leave alone
    try:
        r = ev(target, "port", "start", "07", "--release", str(release.relative_to(target)), "--timeout", "10")
        assert r.returncode == 0, r.stderr
        port = json.loads((target / EVIDENCE / "port.json").read_text(encoding="utf-8"))
        pid = port["pid"]
        assert os.getpgid(pid) == pid
        assert (release.parent.parent / "dist.txt").read_text(encoding="utf-8").strip() == "none"
        assert ev(target, "port", "start", "07", "--release", str(release)).returncode == 125  # one port per run
        r = ev(target, "port", "stop", "07")
        assert r.returncode == 0 and "stopped" in r.stdout
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            pytest.fail("the release survived port stop")
        assert neighbour.poll() is None
        assert "already stopped" in ev(target, "port", "stop", "07").stdout
    finally:
        neighbour.send_signal(signal.SIGTERM)
        neighbour.wait()


def test_port_start_reports_a_release_that_exits_early(target: Path) -> None:
    script = target / "_build/prod/rel/app/bin/app"
    write(script, "#!/bin/sh\necho boom\nexit 3\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    r = ev(target, "port", "start", "07", "--release", str(script), "--timeout", "10")
    assert r.returncode == 1 and "exited with 3" in r.stderr


def test_current_prints_both_identities(target: Path) -> None:
    out = ev(target, "current", "07").stdout.splitlines()
    assert out[0].startswith("target ") and "content_fingerprint=" in out[0]
    assert out[1].startswith("source ") and "content_fingerprint=" in out[1]


def test_run_needs_the_command_after_a_double_dash(target: Path) -> None:
    r = ev(target, "run", "07", "compile")
    assert r.returncode == 125 and "after --" in r.stderr
    assert not records(target, "compile")


def test_ev_path_replaces_the_path_an_interpreter_shim_rewrote(target: Path, tmp_path: Path) -> None:
    tools = tmp_path / "tools"
    write(tools / "port-tool", "#!/bin/sh\nprintf 'ev_path=%s\\n' \"${EV_PATH-unset}\"\n")
    (tools / "port-tool").chmod(0o755)
    env = dict(os.environ, PATH="/usr/bin:/bin", EV_PATH=f"{tools}:/usr/bin:/bin")
    r = subprocess.run([sys.executable, str(SCRIPT), "run", "07", "tool", "--", "port-tool"],
                       cwd=target, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    log = fields(records(target, "tool")[0])["log"]
    assert (target / log).read_text(encoding="utf-8").strip() == "ev_path=unset"
