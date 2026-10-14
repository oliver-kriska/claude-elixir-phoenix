from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / "plugins" / "elixir-phoenix" / "hooks"
HOOK = HOOKS / "scripts" / "block-dangerous-ops.sh"
SHELL_SUITE = HOOKS / "tests" / "block-dangerous-ops_test.sh"


def _decision(command: str, project: Path) -> dict | None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(project),
    }
    # check=True: a deny is JSON on stdout with exit 0, never a non-zero exit.
    result = subprocess.run(
        [str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
        check=True,
    )
    if not result.stdout:
        return None
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    return output


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "mix.exs").write_text("defmodule App.MixProject do\nend\n")
    return tmp_path


def _script(project: Path, *lines: str, name: str = "scripts/smoke.sh") -> Path:
    script = project / name
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("\n".join(["#!/usr/bin/env bash", "set -eu", *lines]) + "\n")
    script.chmod(0o755)
    return script


BEAM_PATTERN_KILLS = [
    "pkill -f phx.server",
    'pkill -f "mix phx.server"',
    "pkill -f 'mix phx.server'",
    "pkill -f beam",
    "pkill beam.smp",
    "pkill -9 -f beam",
    "pkill -f erl",
    "pkill -f erlang",
    "pkill epmd",
    "pkill -f elixir",
    "pkill -f Elixir.MyApp",
    "pkill -f iex",
    "pkill -f mix",
    "killall beam.smp",
    "killall -9 beam.smp",
    "killall epmd",
    "sudo pkill -f beam",
    "/usr/bin/pkill -f beam",
    "cd app && pkill -f phx.server",
    "mix phx.server & sleep 5; pkill -f phx.server",
    "  pkill -f beam",
    "(pkill -f beam)",
    "kill $(pgrep -f beam)",
    "kill -9 $(pgrep -f phx.server)",
    "pgrep -f beam | xargs kill",
    "pgrep beam.smp | xargs -r kill -9",
]


@pytest.mark.parametrize("command", BEAM_PATTERN_KILLS)
def test_beam_pattern_kills_are_denied(project: Path, command: str) -> None:
    output = _decision(command, project)
    assert output is not None, command
    reason = output["permissionDecisionReason"]
    assert reason.startswith("BLOCKED: pattern kill of BEAM processes.")
    assert "by PID" in reason
    assert "pid=$!" in reason
    assert "kill $pid" in reason
    assert "other servers, IEx shells and ElixirLS" in reason
    assert "kill $pid" in output["additionalContext"]


ALLOWED_KILLS = [
    'kill "$pid"',
    "kill $pid",
    "kill -0 123",
    "kill %1",
    "kill -TERM 4242",
    "pkill -P 4242",
    "pkill -f webpack",
    "pkill perl",
    "killall Dock",
    "pgrep -f beam",
    'echo "never pkill -f beam"',
    'git commit -m "stop using pkill -f beam"',
]


@pytest.mark.parametrize("command", ALLOWED_KILLS)
def test_pid_kills_and_unrelated_pattern_kills_are_allowed(
    project: Path, command: str
) -> None:
    assert _decision(command, project) is None


PROD_BUILD_STEPS = [
    "MIX_ENV=prod mix release",
    "MIX_ENV=prod mix release --overwrite",
    "MIX_ENV=prod mix compile",
    "MIX_ENV=prod mix deps.compile",
    "MIX_ENV=prod mix assets.deploy",
    "MIX_ENV=prod mix phx.digest",
    "MIX_ENV=prod mix deps.get --only prod",
    "MIX_ENV=prod mix deps.get --only=prod",
    "MIX_ENV=prod mix do compile, release",
    "MIX_ENV=prod mix do deps.get --only prod + compile + release",
    "MIX_ENV=prod mix compile && mix test",
    "cd app && MIX_ENV=prod mix release",
    "MIX_ENV=prod make release",
]


@pytest.mark.parametrize("command", PROD_BUILD_STEPS)
def test_prod_build_steps_are_allowed(project: Path, command: str) -> None:
    assert _decision(command, project) is None


PROD_DENIED = [
    "MIX_ENV=prod mix ecto.migrate",
    "MIX_ENV=prod mix run priv/repo/seeds.exs",
    "MIX_ENV=prod mix phx.server",
    "MIX_ENV=prod mix",
    "MIX_ENV=prod mix deps.get",
    "MIX_ENV=prod mix test",
    "MIX_ENV=prod iex -S mix",
    "MIX_ENV=prod iex -S mix phx.server",
    "MIX_ENV=prod mix do compile, ecto.migrate",
    "MIX_ENV=prod mix release && MIX_ENV=prod mix ecto.migrate",
]


@pytest.mark.parametrize("command", PROD_DENIED)
def test_prod_steps_outside_the_build_allowlist_are_denied(
    project: Path, command: str
) -> None:
    output = _decision(command, project)
    assert output is not None, command
    reason = output["permissionDecisionReason"]
    assert reason.startswith("BLOCKED: MIX_ENV=prod ")
    assert "allowed only for build steps" in reason
    assert "mix release, mix compile, mix deps.compile" in reason
    assert "mix deps.get --only prod" in reason


def test_prod_deny_names_the_denied_step(project: Path) -> None:
    output = _decision(
        "MIX_ENV=prod mix release && MIX_ENV=prod mix ecto.migrate", project
    )
    assert output is not None
    assert output["permissionDecisionReason"].startswith(
        "BLOCKED: MIX_ENV=prod mix ecto.migrate."
    )
    assert "‘MIX_ENV=prod mix ecto.migrate’" in output["additionalContext"]


@pytest.mark.parametrize(
    "run",
    [
        "bash scripts/smoke.sh",
        "bash -x scripts/smoke.sh",
        "sh scripts/smoke.sh",
        "zsh scripts/smoke.sh",
        "./scripts/smoke.sh",
        "scripts/smoke.sh",
        "source scripts/smoke.sh",
        "mix compile && ./scripts/smoke.sh",
    ],
)
def test_script_running_a_denied_prod_step_is_denied(
    project: Path, run: str
) -> None:
    _script(project, "MIX_ENV=prod mix release", "MIX_ENV=prod mix ecto.migrate")
    output = _decision(run, project)
    assert output is not None, run
    # The script is named the way the command wrote it.
    path = run.split()[-1]
    first_line = output["permissionDecisionReason"].splitlines()[0]
    assert first_line == f"BLOCKED: MIX_ENV=prod mix ecto.migrate in {path}, line 4."
    assert f"in {path}, line 4" in output["additionalContext"]


def test_script_absolute_path_is_scanned(project: Path) -> None:
    script = _script(project, "  MIX_ENV=prod mix phx.server")
    assert _decision(str(script), project) is not None


def test_script_with_a_beam_pattern_kill_is_denied(project: Path) -> None:
    _script(project, "mix phx.server &", "sleep 5", "pkill -f beam")
    output = _decision("bash scripts/smoke.sh", project)
    assert output is not None
    assert output["permissionDecisionReason"].startswith(
        "BLOCKED: pattern kill of BEAM processes in scripts/smoke.sh, line 5."
    )


def test_script_with_only_build_steps_is_allowed(project: Path) -> None:
    _script(
        project,
        "# MIX_ENV=prod mix ecto.migrate runs from the release instead",
        "MIX_ENV=prod mix deps.get --only prod",
        "MIX_ENV=prod mix assets.deploy",
        "MIX_ENV=prod mix release --overwrite",
        'echo "never pkill -f beam"',
        "mix phx.server & pid=$!",
        'kill "$pid"',
    )
    assert _decision("bash scripts/smoke.sh", project) is None
    assert _decision("./scripts/smoke.sh", project) is None


def test_missing_script_is_allowed(project: Path) -> None:
    assert _decision("bash scripts/missing.sh", project) is None
    assert _decision("./scripts/missing.sh", project) is None


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_unreadable_script_is_allowed(project: Path) -> None:
    script = _script(project, "MIX_ENV=prod mix ecto.migrate")
    script.chmod(0)
    try:
        assert _decision("bash scripts/smoke.sh", project) is None
    finally:
        script.chmod(0o644)


def test_relative_script_resolves_against_hook_cwd(tmp_path: Path) -> None:
    (tmp_path / "mix.exs").write_text("")
    app = tmp_path / "app"
    _script(app, "MIX_ENV=prod mix ecto.migrate")
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "bash scripts/smoke.sh"},
        "cwd": str(app),
    }
    result = subprocess.run(
        [str(HOOK)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)},
        check=True,
    )
    output = json.loads(result.stdout)["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "command",
    ["pkill -f beam", "MIX_ENV=prod mix ecto.migrate", "bash scripts/smoke.sh"],
)
def test_new_checks_are_gated_on_mix_exs(tmp_path: Path, command: str) -> None:
    _script(tmp_path, "MIX_ENV=prod mix ecto.migrate", "pkill -f beam")
    assert _decision(command, tmp_path) is None


def test_shell_regression_suite_passes() -> None:
    result = subprocess.run(
        ["bash", str(SHELL_SUITE)], text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-2000:]
