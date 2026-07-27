from __future__ import annotations

import json
import shutil
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
    assert sum(call[0][1:3] == ["plugins", "exec"] for call in calls) == 1
    assert sum(call[0][1:4] == ["skill", "list", "--json"] for call in calls) == 2
    assert sum(call[0][1:3] == ["skill", "remove"] for call in calls) == 51
    assert sum(call[0][1:3] == ["plugins", "exec"] for call in calls) == 1


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
