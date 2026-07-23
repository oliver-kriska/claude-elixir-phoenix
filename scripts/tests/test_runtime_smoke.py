from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import runtime_smoke


def _fixture_target(output: Path) -> None:
    for number in range(runtime_smoke.EXPECTED_SKILLS):
        name = "phx-watch-pr" if number == 0 else f"skill-{number}"
        skill = output / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Skill\n")
    resource = output / "skills" / runtime_smoke.EXECUTABLE_RESOURCE
    resource.parent.mkdir()
    resource.write_text("#!/bin/sh\n")
    resource.chmod(0o755)


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
