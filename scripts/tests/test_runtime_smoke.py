from __future__ import annotations

import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

from scripts import runtime_smoke


def _fixture_target(output: Path) -> None:
    for number in range(runtime_smoke.EXPECTED_SKILLS):
        name = (
            "phx-watch-pr"
            if number == 0
            else "phx-deps-audit"
            if number == 1
            else f"skill-{number}"
        )
        skill = output / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Skill\n")
    resource = output / "skills" / runtime_smoke.EXECUTABLE_RESOURCE
    resource.parent.mkdir()
    resource.write_text("#!/bin/sh\n")
    resource.chmod(0o755)
    amp_resource = output / "skills" / runtime_smoke.AMP_EXECUTABLE_RESOURCE
    amp_resource.parent.mkdir()
    amp_resource.write_text("#!/usr/bin/env python3\n")
    amp_resource.chmod(0o755)


def test_amp_uses_native_install_exact_discovery_and_fresh_removal(tmp_path, monkeypatch) -> None:
    canonical = tmp_path / "canonical"
    canonical_resource = canonical / "skills" / runtime_smoke.AMP_SOURCE_EXECUTABLE
    canonical_resource.parent.mkdir(parents=True)
    canonical_resource.write_text("#!/usr/bin/env python3\n")
    canonical_resource.chmod(0o755)

    def build_amp_fixture(_source, output):
        _fixture_target(output)
        for relative in (
            runtime_smoke.amp_port.PLUGIN_TARGET_RELATIVE,
            runtime_smoke.amp_port.WORKFLOW_PLUGIN_RELATIVE_PATH,
        ):
            plugin = output / relative
            plugin.parent.mkdir(parents=True, exist_ok=True)
            plugin.write_text("export default function () {}\n")

    monkeypatch.setattr(runtime_smoke, "SOURCE_PLUGIN_DIR", canonical)
    monkeypatch.setattr(
        runtime_smoke.amp_port,
        "build_target",
        build_amp_fixture,
    )
    monkeypatch.setattr(runtime_smoke, "_executable", lambda name, _env: name)
    for name in (
        "AMP_API_KEY",
        "AMP_ENABLE_TRACING",
        "AMP_HOME",
        "AMP_PWD",
        "AMP_SETTINGS_FILE",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
    ):
        monkeypatch.setenv(name, f"real-{name.lower()}")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/real/config")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs["env"].copy(), kwargs["cwd"]))
        install = tmp_path / "workspace/.agents/skills"
        generated = tmp_path / "generated-target" / "skills"
        if command[-1] == "--version":
            output = "amp test\n"
        elif command[1:3] == ["plugins", "exec"]:
            output = "Plugin loaded\n"
        elif command[1:3] == ["skill", "add"]:
            for skill in generated.iterdir():
                shutil.copytree(skill, install / skill.name, copy_function=shutil.copy2)
            output = "Installed\n"
        elif command[1:3] == ["skill", "remove"]:
            shutil.rmtree(install / command[3])
            output = "Removed\n"
        else:
            records = [
                {
                    "name": path.name,
                    "baseDir": path.resolve().as_uri(),
                }
                for path in install.iterdir()
                if path.is_dir()
            ]
            output = json.dumps({"skills": records, "errors": []})
        return subprocess.CompletedProcess(command, 0, output, "")

    runtime_smoke.smoke_amp(tmp_path, runner)
    assert all(call[1]["HOME"] == str(tmp_path / "home") for call in calls)
    assert all(call[1]["AMP_SETTINGS_FILE"] == str(tmp_path / "settings.json") for call in calls)
    assert all(call[1]["AMP_LOG_FILE"] == str(tmp_path / "amp.log") for call in calls)
    assert all(call[1]["AMP_API_KEY"] == "runtime-smoke-placeholder" for call in calls)
    assert all(call[1]["AMP_URL"] == "http://127.0.0.1:9" for call in calls)
    assert all(call[1]["AMP_SKIP_UPDATE_CHECK"] == "1" for call in calls)
    assert all("AMP_ENABLE_TRACING" not in call[1] for call in calls)
    assert all("AMP_HOME" not in call[1] for call in calls)
    assert all("AMP_PWD" not in call[1] for call in calls)
    assert all("OTEL_EXPORTER_OTLP_ENDPOINT" not in call[1] for call in calls)
    assert all(call[1]["XDG_CONFIG_HOME"] == str(tmp_path / "xdg_config_home") for call in calls)
    assert all(call[2] == tmp_path / "workspace" for call in calls)
    assert sum(call[0][1:3] == ["plugins", "exec"] for call in calls) == 2
    assert sum(call[0][1:4] == ["skill", "list", "--json"] for call in calls) == 2
    assert sum(call[0][1:3] == ["skill", "remove"] for call in calls) == 51
    assert sum(call[0][1:3] == ["plugins", "exec"] for call in calls) == 2


def test_amp_records_require_unique_names_clean_payload_and_path_boundaries(tmp_path) -> None:
    install = tmp_path / "skills"
    expected = install / "phx-review"
    expected.mkdir(parents=True)
    sibling = tmp_path / "skills-other/false"
    sibling.mkdir(parents=True)
    records = [
        {"name": "phx-review", "baseDir": expected.resolve().as_uri()},
        {"name": "false", "baseDir": sibling.resolve().as_uri()},
        {"name": "built-in", "baseDir": "builtin:///skills"},
    ]
    assert runtime_smoke._amp_skill_records(
        {"skills": records, "errors": []}, install
    ) == {"phx-review": expected.resolve()}
    with pytest.raises(RuntimeError, match="duplicate"):
        runtime_smoke._amp_skill_records(
            {"skills": [records[0], records[0]], "errors": []}, install
        )
    with pytest.raises(RuntimeError, match="invalid skill discovery"):
        runtime_smoke._amp_skill_records(
            {"skills": records, "errors": ["broken skill"]}, install
        )
    with pytest.raises(RuntimeError, match="non-local skill URI"):
        runtime_smoke._amp_skill_records(
            {
                "skills": [
                    {"name": "false", "baseDir": "file://remote.example/skills/false"}
                ],
                "errors": [],
            },
            install,
        )
    fallback = {
        "skills": [
            {
                "name": "phx-review",
                "baseDir": (tmp_path / "global/phx-review").resolve().as_uri(),
            }
        ],
        "errors": [],
    }
    assert runtime_smoke._amp_skill_names(fallback) & {"phx-review"} == {
        "phx-review"
    }


def test_resource_snapshot_detects_source_mutation(tmp_path) -> None:
    resource = tmp_path / "watch-pr.sh"
    resource.write_text("#!/bin/sh\n")
    resource.chmod(0o755)
    snapshot = runtime_smoke._resource_snapshot(resource)
    resource.write_text("#!/bin/sh\necho mutated\n")
    with pytest.raises(RuntimeError, match="bytes or mode differ"):
        runtime_smoke._verify_resource_snapshot(resource, snapshot)


def test_codex_uses_isolated_homes_native_install_and_fresh_removal(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_smoke.codex_port, "build", lambda _source, output: _fixture_target(output))
    monkeypatch.setattr(runtime_smoke, "_executable", lambda name, _env: name)
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs["env"].copy(), kwargs["cwd"]))
        if command[-1] == "--version":
            output = "codex-cli test\n"
        elif command[1:3] == ["plugin", "add"]:
            installed = tmp_path / "codex-home/plugins/cache/plugin"
            _fixture_target(installed)
            output = json.dumps({"installedPath": str(installed)})
        elif command[1:3] == ["plugin", "list"]:
            removed = any(call[0][1:3] == ["plugin", "remove"] for call in calls[:-1])
            output = json.dumps(
                {
                    "installed": []
                    if removed
                    else [
                        {
                            "pluginId": "elixir-phoenix@oliver-kriska",
                            "installed": True,
                            "enabled": True,
                        }
                    ]
                }
            )
        elif command[1:3] == ["plugin", "remove"]:
            shutil.rmtree(tmp_path / "codex-home/plugins/cache/plugin")
            output = "{}"
        else:
            output = "{}"
        return subprocess.CompletedProcess(command, 0, output, "")

    runtime_smoke.smoke_codex(tmp_path, runner)
    assert all(call[1]["HOME"] == str(tmp_path / "home") for call in calls)
    assert all(call[1]["CODEX_HOME"] == str(tmp_path / "codex-home") for call in calls)
    assert all(call[1]["HOME"] != str(Path.home()) for call in calls)
    assert all(call[2] == tmp_path / "workspace" for call in calls)
    assert sum(call[0][1:3] == ["plugin", "list"] for call in calls) == 2


def test_opencode_uses_all_isolated_xdg_roots_and_fresh_discovery(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runtime_smoke.opencode_port, "build", lambda _source, output: _fixture_target(output))
    monkeypatch.setattr(runtime_smoke, "_executable", lambda name, _env: name)
    for name in runtime_smoke.OPENCODE_ENV_OVERRIDES:
        monkeypatch.setenv(name, f"/real/{name.lower()}")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs["env"].copy(), kwargs["cwd"]))
        if command[-1] == "--version":
            output = "1.test\n"
        else:
            installed = Path(kwargs["env"]["XDG_CONFIG_HOME"]) / "opencode/skills/elixir-phoenix"
            target = installed / "targets/opencode"
            names = [path.parent.name for path in target.glob("skills/*/SKILL.md")]
            output = json.dumps(
                [{"name": "built-in", "location": "<built-in>"}]
                + (
                    []
                    if not installed.exists()
                    else [
                        {
                            "name": name,
                            "location": str(target / f"skills/{name}/SKILL.md"),
                        }
                        for name in names
                    ]
                )
            )
        return subprocess.CompletedProcess(command, 0, output, "")

    runtime_smoke.smoke_opencode(tmp_path, runner)
    for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        assert all(call[1][name].startswith(str(tmp_path)) for call in calls)
    for name in runtime_smoke.OPENCODE_ENV_OVERRIDES:
        assert all(name not in call[1] for call in calls)
    assert all(call[1]["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1" for call in calls)
    assert all(call[2] == tmp_path / "workspace" for call in calls)
    assert sum(call[0][1:] == ["debug", "skill", "--pure"] for call in calls) == 2


def test_pi_uses_isolated_agent_dir_rpc_discovery_and_fresh_removal(tmp_path, monkeypatch) -> None:
    canonical = tmp_path / "canonical"
    source_resource = canonical / "skills" / runtime_smoke.PI_SOURCE_EXECUTABLE
    source_resource.parent.mkdir(parents=True)
    source_resource.write_text("#!/bin/sh\n")
    source_resource.chmod(0o755)
    monkeypatch.setattr(runtime_smoke, "SOURCE_PLUGIN_DIR", canonical)
    monkeypatch.setattr(runtime_smoke.pi_port, "build", lambda _source, output: _fixture_target(output))
    monkeypatch.setattr(runtime_smoke, "_executable", lambda name, _env: name)
    monkeypatch.setenv("PI_PACKAGE_DIR", "/real/pi-packages")
    calls = []
    removed = False

    def runner(command, **kwargs):
        nonlocal removed
        calls.append((command, kwargs["env"].copy(), kwargs["cwd"], kwargs.get("input")))
        package = tmp_path / "package"
        generated = package / "targets/pi"
        if command[-1] == "--version":
            output = "0.test\n"
        elif command[1] == "list":
            output = "No packages installed.\n" if removed else f"User packages:\n  {package}\n    {package}\n"
        elif command[1] == "remove":
            removed = True
            output = "Removed\n"
        elif command[1:3] == ["--mode", "rpc"]:
            records = [] if removed else [
                {
                    "name": f"skill:{path.parent.name}",
                    "source": "skill",
                    "sourceInfo": {"path": str(path)},
                }
                for path in generated.glob("skills/*/SKILL.md")
            ]
            output = json.dumps(
                {
                    "id": "skills",
                    "type": "response",
                    "command": "get_commands",
                    "success": True,
                    "data": {"commands": records},
                }
            )
        else:
            output = "Installed\n"
        return subprocess.CompletedProcess(command, 0, output, "")

    runtime_smoke.smoke_pi(tmp_path, runner)
    assert all(call[1]["HOME"] == str(tmp_path / "home") for call in calls)
    assert all(call[1]["PI_CODING_AGENT_DIR"] == str(tmp_path / "agent") for call in calls)
    assert all(call[1]["PI_CODING_AGENT_SESSION_DIR"] == str(tmp_path / "sessions") for call in calls)
    assert all(call[1]["PI_OFFLINE"] == "1" for call in calls)
    assert all(call[1]["PI_TELEMETRY"] == "0" for call in calls)
    assert all("PI_PACKAGE_DIR" not in call[1] for call in calls)
    assert all(call[2] == tmp_path / "workspace" for call in calls)
    rpc_calls = [call for call in calls if call[0][1:3] == ["--mode", "rpc"]]
    assert len(rpc_calls) == 2
    assert all(call[3] == '{"id":"skills","type":"get_commands"}\n' for call in rpc_calls)


def test_tree_validation_requires_exact_count_resource_and_executable(tmp_path) -> None:
    target = tmp_path / "target"
    _fixture_target(target)
    runtime_smoke._verify_tree(target / "skills")
    (target / "skills/skill-50/SKILL.md").unlink()
    with pytest.raises(RuntimeError, match="expected 51"):
        runtime_smoke._verify_tree(target / "skills")
    shutil.rmtree(target)
    _fixture_target(target)
    (target / "skills" / runtime_smoke.EXECUTABLE_RESOURCE).chmod(0o644)
    (target / "skills" / runtime_smoke.AMP_EXECUTABLE_RESOURCE).chmod(0o644)
    with pytest.raises(RuntimeError, match="executable resource"):
        runtime_smoke._verify_tree(target / "skills")


def test_opencode_records_require_unique_names_and_path_boundaries(tmp_path) -> None:
    install = tmp_path / "opencode"
    expected = install / "skills/phx-review/SKILL.md"
    expected.parent.mkdir(parents=True)
    expected.write_text("# Skill\n")
    sibling = tmp_path / "opencode-other/skills/false/SKILL.md"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("# False\n")

    records = [
        {"name": "phx-review", "location": str(expected)},
        {"name": "false", "location": str(sibling)},
    ]
    assert runtime_smoke._skill_records(records, install) == {
        "phx-review": expected.resolve()
    }

    with pytest.raises(RuntimeError, match="duplicate"):
        runtime_smoke._skill_records([records[0], records[0]], install)


def test_codex_rejects_disabled_or_off_root_install(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_smoke.codex_port,
        "build",
        lambda _source, output: _fixture_target(output),
    )
    monkeypatch.setattr(runtime_smoke, "_executable", lambda name, _env: name)
    off_root = tmp_path / "outside/plugin"

    def runner(command, **_kwargs):
        if command[-1] == "--version":
            output = "codex-cli test\n"
        elif command[1:3] == ["plugin", "add"]:
            _fixture_target(off_root)
            output = json.dumps({"installedPath": str(off_root)})
        else:
            output = json.dumps(
                {
                    "installed": [
                        {
                            "pluginId": "elixir-phoenix@oliver-kriska",
                            "installed": True,
                            "enabled": False,
                        }
                    ]
                }
            )
        return subprocess.CompletedProcess(command, 0, output, "")

    with pytest.raises(RuntimeError, match="outside isolated CODEX_HOME"):
        runtime_smoke.smoke_codex(tmp_path, runner)


def test_codex_rejects_disabled_plugin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_smoke.codex_port,
        "build",
        lambda _source, output: _fixture_target(output),
    )
    monkeypatch.setattr(runtime_smoke, "_executable", lambda name, _env: name)
    installed = tmp_path / "codex-home/plugins/cache/plugin"

    def runner(command, **_kwargs):
        if command[-1] == "--version":
            output = "codex-cli test\n"
        elif command[1:3] == ["plugin", "add"]:
            _fixture_target(installed)
            output = json.dumps({"installedPath": str(installed)})
        elif command[1:3] == ["plugin", "list"]:
            output = json.dumps(
                {
                    "installed": [
                        {
                            "pluginId": "elixir-phoenix@oliver-kriska",
                            "installed": True,
                            "enabled": False,
                        }
                    ]
                }
            )
        else:
            output = "{}"
        return subprocess.CompletedProcess(command, 0, output, "")

    with pytest.raises(RuntimeError, match="not installed and enabled"):
        runtime_smoke.smoke_codex(tmp_path, runner)


def test_resource_validation_detects_mode_drift(tmp_path) -> None:
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    _fixture_target(source)
    _fixture_target(installed)
    (installed / "skills" / runtime_smoke.EXECUTABLE_RESOURCE).chmod(0o744)

    with pytest.raises(RuntimeError, match="mode differs"):
        runtime_smoke._verify_resource(source / "skills", installed / "skills")


def test_pi_resource_validation_requires_the_expected_executable(tmp_path) -> None:
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source_script = source / runtime_smoke.PI_SOURCE_EXECUTABLE
    source_script.parent.mkdir(parents=True)
    source_script.write_text("#!/bin/sh\n")
    source_script.chmod(0o755)
    decoy = installed / "other/executable.sh"
    decoy.parent.mkdir(parents=True)
    decoy.write_text("#!/bin/sh\n")
    decoy.chmod(0o755)

    with pytest.raises(RuntimeError, match="installed resource is missing"):
        runtime_smoke._verify_resource(
            source,
            installed,
            runtime_smoke.PI_SOURCE_EXECUTABLE,
            runtime_smoke.EXECUTABLE_RESOURCE,
        )


class _FakeProcess:
    """Minimal Popen stand-in for the dsh smoke's spawn seam."""

    def __init__(self, exit_code: int | None = None, dies_after_polls: int | None = None) -> None:
        self._exit_code = exit_code
        self.returncode = exit_code
        self.terminated = False
        self.killed = False
        self._dies_after_polls = dies_after_polls
        self.polls = 0

    def poll(self):
        self.polls += 1
        if (
            self._dies_after_polls is not None
            and self.polls > self._dies_after_polls
            and self._exit_code is None
        ):
            self._exit_code = 1
            self.returncode = 1
        return self._exit_code

    def terminate(self) -> None:
        self.terminated = True
        if self._exit_code is None:
            self._exit_code = -15
            self.returncode = self._exit_code

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


def _dsh_env(tmp_path, monkeypatch, process, responses):
    """Wire the dsh smoke to a fixture target and a scripted RPC transport."""

    def build(_source, output):
        _fixture_target(Path(output))

    monkeypatch.setattr(runtime_smoke.dsh_port, "build", build)
    monkeypatch.setattr(runtime_smoke, "_executable", lambda name, env: f"/fake/{name}")

    calls: list[str] = []

    def fake_rpc(base_url, method, payload):
        calls.append(method)
        outcome = responses.get(method)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(runtime_smoke, "_dsh_rpc", fake_rpc)
    monkeypatch.setattr(runtime_smoke.time, "sleep", lambda _seconds: None)
    return calls


def _dsh_ok_responses(count: int = runtime_smoke.EXPECTED_SKILLS) -> dict:
    names = [
        "phx-watch-pr" if n == 0 else "phx-deps-audit" if n == 1 else f"skill-{n}"
        for n in range(count)
    ]
    return {
        "session.list": {},
        "session.create": {"sessionId": "s-1"},
        "skill.list": {
            "skills": [
                {"name": name, "description": "d", "modelInvocable": True}
                for name in names
            ]
        },
    }


def test_dsh_discovers_every_skill_and_always_stops_the_host(tmp_path, monkeypatch) -> None:
    process = _FakeProcess()
    calls = _dsh_env(tmp_path, monkeypatch, process, _dsh_ok_responses())

    runtime_smoke.smoke_dsh(tmp_path, spawn=lambda *a, **k: process)

    assert calls == ["session.list", "session.create", "skill.list"]
    assert process.terminated


def test_dsh_rejects_a_foreign_listener_answering_for_a_dead_child(tmp_path, monkeypatch) -> None:
    """A squatter on the port must never be mistaken for the spawned host."""
    process = _FakeProcess(exit_code=1)
    _dsh_env(tmp_path, monkeypatch, process, _dsh_ok_responses())

    with pytest.raises(RuntimeError, match="exited early"):
        runtime_smoke.smoke_dsh(tmp_path, spawn=lambda *a, **k: process)


def test_dsh_rejects_a_listener_that_outlives_the_child(tmp_path, monkeypatch) -> None:
    """The child can die between the liveness poll and the probe's reply.

    Something else on the port then answers for it. Without the post-probe
    re-poll the smoke walks straight into `skill.list` and reports PASS on a
    host it never started.
    """
    process = _FakeProcess(dies_after_polls=1)
    calls = _dsh_env(tmp_path, monkeypatch, process, _dsh_ok_responses())

    with pytest.raises(RuntimeError, match="a foreign listener answered"):
        runtime_smoke.smoke_dsh(tmp_path, spawn=lambda *a, **k: process)

    # It must fail on the read-only probe, before creating a session.
    assert calls == ["session.list"]


def test_dsh_reports_missing_skills_rather_than_passing(tmp_path, monkeypatch) -> None:
    process = _FakeProcess()
    responses = _dsh_ok_responses()
    responses["skill.list"] = {"skills": []}
    _dsh_env(tmp_path, monkeypatch, process, responses)

    with pytest.raises(RuntimeError, match="discovered 0 of"):
        runtime_smoke.smoke_dsh(tmp_path, spawn=lambda *a, **k: process)
    assert process.terminated


def test_dsh_rejects_a_skill_that_is_not_model_invocable(tmp_path, monkeypatch) -> None:
    process = _FakeProcess()
    responses = _dsh_ok_responses()
    responses["skill.list"]["skills"][3]["modelInvocable"] = False
    _dsh_env(tmp_path, monkeypatch, process, responses)

    with pytest.raises(RuntimeError, match="not model-invocable"):
        runtime_smoke.smoke_dsh(tmp_path, spawn=lambda *a, **k: process)


def test_dsh_requires_a_session_id(tmp_path, monkeypatch) -> None:
    process = _FakeProcess()
    responses = _dsh_ok_responses()
    responses["session.create"] = {}
    _dsh_env(tmp_path, monkeypatch, process, responses)

    with pytest.raises(RuntimeError, match="no sessionId"):
        runtime_smoke.smoke_dsh(tmp_path, spawn=lambda *a, **k: process)


def test_dsh_rpc_reports_a_reply_carrying_no_result_object() -> None:
    """A top-level error must not surface as `failed: None`."""
    captured: dict = {}

    class _Reply:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(captured["body"]).encode()

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        return _Reply()

    import urllib.request as urllib_request

    original = urllib_request.urlopen
    urllib_request.urlopen = fake_urlopen
    try:
        captured["body"] = {"error": "boom"}
        with pytest.raises(RuntimeError, match="no result object"):
            runtime_smoke._dsh_rpc("http://127.0.0.1:1", "skill.list", {})
        assert captured["url"].endswith("/api/skill.list")

        captured["body"] = {"result": {"ok": False, "error": {"code": "bad-request"}}}
        with pytest.raises(RuntimeError, match="bad-request"):
            runtime_smoke._dsh_rpc("http://127.0.0.1:1", "skill.list", {})
    finally:
        urllib_request.urlopen = original


def test_free_port_returns_an_unbound_loopback_port() -> None:
    """The contract is that the caller can hand the port to a child and bind it."""
    port = runtime_smoke._free_port()
    assert 1024 < port <= 65535

    # The probe socket must be closed, or the spawned host cannot take the port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taker:
        taker.bind(("127.0.0.1", port))
        assert taker.getsockname()[1] == port
