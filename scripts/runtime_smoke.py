#!/usr/bin/env python3
"""Optional, isolated runtime smoke checks for generated skill targets."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

from scripts.port_lib import SOURCE_PLUGIN_DIR
from scripts.port_lib import codex as codex_port
from scripts.port_lib import opencode as opencode_port

EXPECTED_SKILLS = 51
Run = Callable[..., subprocess.CompletedProcess[str]]
EXECUTABLE_RESOURCE = Path("phx-watch-pr/scripts/watch-pr.sh")
OPENCODE_ENV_OVERRIDES = (
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_CONFIG_CONTENT",
    "OPENCODE_TEST_HOME",
)


def _run(
    runner: Run, command: list[str], env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    result = runner(command, env=env, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result


def _json_run(runner: Run, command: list[str], env: dict[str, str], cwd: Path):
    """Parse large runtime JSON via a file (OpenCode truncates piped output)."""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as output:
        result = runner(command, env=env, cwd=cwd, text=True, stdout=output, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError(f"{' '.join(command)} failed: {result.stderr.strip()}")
        if result.stdout:
            output.write(result.stdout)
        output.seek(0)
        return json.load(output)


def _executable(name: str, env: dict[str, str]) -> str:
    executable = shutil.which(name, path=env.get("PATH"))
    if not executable:
        raise RuntimeError(f"{name} is not installed or not on PATH")
    return executable


def _verify_tree(skills: Path) -> None:
    manifests = list(skills.glob("*/SKILL.md"))
    if len(manifests) != EXPECTED_SKILLS:
        raise RuntimeError(f"expected {EXPECTED_SKILLS} skills, found {len(manifests)}")
    resources = [
        path
        for path in skills.rglob("*")
        if path.is_file()
        and path.name != "SKILL.md"
        and "references" not in path.relative_to(skills).parts
    ]
    if not resources:
        raise RuntimeError("no resource outside references/ was retained")
    if not any(stat.S_IMODE(path.stat().st_mode) & 0o111 for path in resources):
        raise RuntimeError("no executable resource retained its mode")


def _verify_resource(source_skills: Path, installed_skills: Path) -> None:
    source = source_skills / EXECUTABLE_RESOURCE
    installed = installed_skills / EXECUTABLE_RESOURCE
    if not installed.is_file():
        raise RuntimeError(f"installed resource is missing: {EXECUTABLE_RESOURCE}")
    if installed.read_bytes() != source.read_bytes():
        raise RuntimeError(f"installed resource bytes differ: {EXECUTABLE_RESOURCE}")
    if stat.S_IMODE(installed.stat().st_mode) != stat.S_IMODE(source.stat().st_mode):
        raise RuntimeError(f"installed resource mode differs: {EXECUTABLE_RESOURCE}")


def _skill_records(records: list[dict], install: Path) -> dict[str, Path]:
    install = install.resolve()
    discovered: dict[str, Path] = {}
    for item in records:
        location = Path(str(item.get("location", ""))).resolve()
        if not location.is_relative_to(install):
            continue
        name = item.get("name")
        if not isinstance(name, str) or name in discovered:
            raise RuntimeError("OpenCode returned duplicate or invalid generated skills")
        discovered[name] = location
    return discovered


def smoke_codex(root: Path, runner: Run = subprocess.run) -> None:
    home, codex_home = root / "home", root / "codex-home"
    workspace = root / "workspace"
    marketplace = root / "marketplace"
    for path in (home, codex_home, workspace, marketplace / ".agents/plugins"):
        path.mkdir(parents=True)
    generated = marketplace / "targets/codex"
    codex_port.build(SOURCE_PLUGIN_DIR, generated)
    shutil.copy2(
        Path(__file__).parents[1] / ".agents/plugins/marketplace.json",
        marketplace / ".agents/plugins/marketplace.json",
    )
    env = os.environ.copy() | {"HOME": str(home), "CODEX_HOME": str(codex_home)}
    executable = _executable("codex", env)
    version = _run(runner, [executable, "--version"], env, workspace).stdout.strip()
    if not version:
        raise RuntimeError("codex returned an empty version")
    _run(runner, [executable, "plugin", "marketplace", "add", str(marketplace), "--json"], env, workspace)
    installed = json.loads(
        _run(runner, [executable, "plugin", "add", "elixir-phoenix@oliver-kriska", "--json"], env, workspace).stdout
    )
    installed_path = Path(installed["installedPath"]).resolve()
    cache_root = (codex_home / "plugins/cache").resolve()
    if not installed_path.is_relative_to(cache_root):
        raise RuntimeError(f"Codex installed outside isolated CODEX_HOME: {installed_path}")
    _verify_tree(installed_path / "skills")
    _verify_resource(generated / "skills", installed_path / "skills")
    listing = json.loads(_run(runner, [executable, "plugin", "list", "--json"], env, workspace).stdout)
    matching = [
        item
        for item in listing["installed"]
        if item.get("pluginId") == "elixir-phoenix@oliver-kriska"
    ]
    if not matching or not matching[0].get("installed") or not matching[0].get("enabled"):
        raise RuntimeError("Codex plugin is not installed and enabled")
    _run(runner, [executable, "plugin", "remove", "elixir-phoenix@oliver-kriska"], env, workspace)
    after = json.loads(_run(runner, [executable, "plugin", "list", "--json"], env, workspace).stdout)
    if any(item.get("pluginId") == "elixir-phoenix@oliver-kriska" for item in after["installed"]):
        raise RuntimeError("Codex rediscovered the removed plugin")
    if installed_path.exists():
        raise RuntimeError(f"Codex left the removed plugin on disk: {installed_path}")
    print(f"[runtime-smoke] Codex {version}: {EXPECTED_SKILLS} skills OK")


def smoke_opencode(root: Path, runner: Run = subprocess.run) -> None:
    roots = {name: root / name.lower() for name in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME")}
    for path in roots.values():
        path.mkdir(parents=True)
    workspace = root / "workspace"
    workspace.mkdir()
    install = roots["XDG_CONFIG_HOME"] / "opencode/skills/elixir-phoenix/targets/opencode"
    opencode_port.build(SOURCE_PLUGIN_DIR, install)
    env = os.environ.copy()
    for name in OPENCODE_ENV_OVERRIDES:
        env.pop(name, None)
    env |= {name: str(path) for name, path in roots.items()}
    env["OPENCODE_DISABLE_PROJECT_CONFIG"] = "1"
    executable = _executable("opencode", env)
    version = _run(runner, [executable, "--version"], env, workspace).stdout.strip()
    if not version:
        raise RuntimeError("opencode returned an empty version")
    _verify_tree(install / "skills")
    discovered = _json_run(
        runner, [executable, "debug", "skill", "--pure"], env, workspace
    )
    expected = {
        path.parent.name: path.resolve() for path in (install / "skills").glob("*/SKILL.md")
    }
    generated = _skill_records(discovered, install)
    if generated != expected:
        raise RuntimeError(
            f"OpenCode discovered {len(generated)} generated skills, "
            f"expected the exact {len(expected)}-skill target"
        )
    shutil.rmtree(roots["XDG_CONFIG_HOME"] / "opencode/skills/elixir-phoenix")
    after = _json_run(
        runner, [executable, "debug", "skill", "--pure"], env, workspace
    )
    remaining = _skill_records(after, install)
    if remaining:
        raise RuntimeError(f"OpenCode rediscovered {len(remaining)} generated skills after removal")
    print(f"[runtime-smoke] OpenCode {version}: {EXPECTED_SKILLS} skills OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", choices=("codex", "opencode"))
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix=f"{args.runtime}-runtime-smoke-") as temporary:
            {"codex": smoke_codex, "opencode": smoke_opencode}[args.runtime](Path(temporary))
    except (KeyError, OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"[runtime-smoke] FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
