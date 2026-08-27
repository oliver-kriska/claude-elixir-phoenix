#!/usr/bin/env python3
"""Optional, isolated runtime smoke checks for generated skill targets."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from scripts.port_lib import SOURCE_PLUGIN_DIR
from scripts.port_lib import amp as amp_port
from scripts.port_lib import codex as codex_port
from scripts.port_lib import dsh as dsh_port
from scripts.port_lib import opencode as opencode_port
from scripts.port_lib import pi as pi_port

EXPECTED_SKILLS = 51
Run = Callable[..., subprocess.CompletedProcess[str]]
Spawn = Callable[..., "subprocess.Popen[str]"]
EXECUTABLE_RESOURCE = Path("phx-watch-pr/scripts/watch-pr.sh")
PI_SOURCE_EXECUTABLE = Path("watch-pr/scripts/watch-pr.sh")
AMP_EXECUTABLE_RESOURCE = Path("phx-deps-audit/scripts/diff_cves.py")
AMP_SOURCE_EXECUTABLE = Path("deps-audit/scripts/diff_cves.py")
OPENCODE_ENV_OVERRIDES = (
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_CONFIG_CONTENT",
    "OPENCODE_TEST_HOME",
)
PI_ENV_OVERRIDES = ("PI_PACKAGE_DIR",)


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


def _verify_resource(
    source_skills: Path,
    installed_skills: Path,
    source_resource: Path = EXECUTABLE_RESOURCE,
    installed_resource: Path = EXECUTABLE_RESOURCE,
) -> None:
    source = source_skills / source_resource
    installed = installed_skills / installed_resource
    if not installed.is_file():
        raise RuntimeError(f"installed resource is missing: {installed_resource}")
    if installed.read_bytes() != source.read_bytes():
        raise RuntimeError(f"installed resource bytes differ: {installed_resource}")
    if stat.S_IMODE(installed.stat().st_mode) != stat.S_IMODE(source.stat().st_mode):
        raise RuntimeError(f"installed resource mode differs: {installed_resource}")


def _resource_snapshot(path: Path) -> tuple[bytes, int]:
    return path.read_bytes(), stat.S_IMODE(path.stat().st_mode)


def _verify_resource_snapshot(path: Path, expected: tuple[bytes, int]) -> None:
    if not path.is_file():
        raise RuntimeError(f"resource is missing: {path}")
    if _resource_snapshot(path) != expected:
        raise RuntimeError(f"resource bytes or mode differ: {path}")


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


def _amp_skills(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        raise RuntimeError("Amp returned invalid skill discovery data")
    errors = payload.get("errors")
    records = payload.get("skills")
    if not isinstance(errors, list) or errors or not isinstance(records, list):
        raise RuntimeError("Amp returned invalid skill discovery data")
    if not all(isinstance(item, dict) for item in records):
        raise RuntimeError("Amp returned an invalid skill record")
    return records


def _amp_skill_names(payload: dict) -> set[str]:
    names = {item.get("name") for item in _amp_skills(payload)}
    if not all(isinstance(name, str) and name for name in names):
        raise RuntimeError("Amp returned an invalid skill name")
    return names


def _amp_skill_records(payload: dict, install: Path) -> dict[str, Path]:
    records = _amp_skills(payload)
    install = install.resolve()
    discovered: dict[str, Path] = {}
    for item in records:
        base_dir = item.get("baseDir")
        if not isinstance(base_dir, str) or not base_dir.startswith("file://"):
            continue
        parsed = urlparse(base_dir)
        if parsed.netloc not in ("", "localhost"):
            raise RuntimeError(f"Amp returned a non-local skill URI: {base_dir}")
        location = Path(url2pathname(unquote(parsed.path))).resolve()
        if not location.is_relative_to(install):
            continue
        name = item.get("name")
        if not isinstance(name, str) or name in discovered:
            raise RuntimeError("Amp returned duplicate or invalid generated skills")
        discovered[name] = location
    return discovered


def _pi_skill_records(commands: list[dict], install: Path) -> dict[str, Path]:
    install = install.resolve()
    discovered: dict[str, Path] = {}
    for item in commands:
        source_info = item.get("sourceInfo")
        if item.get("source") != "skill" or not isinstance(source_info, dict):
            continue
        location = Path(str(source_info.get("path", ""))).resolve()
        if not location.is_relative_to(install):
            continue
        invocation = item.get("name")
        if not isinstance(invocation, str) or not invocation.startswith("skill:"):
            raise RuntimeError("Pi returned an invalid generated skill command")
        name = invocation.removeprefix("skill:")
        if not name or name in discovered:
            raise RuntimeError("Pi returned duplicate or invalid generated skills")
        discovered[name] = location
    return discovered


def _pi_commands(runner: Run, executable: str, env: dict[str, str], cwd: Path) -> list[dict]:
    command = [executable, "--mode", "rpc", "--no-session", "--no-context-files"]
    result = runner(
        command,
        env=env,
        cwd=cwd,
        text=True,
        capture_output=True,
        input='{"id":"skills","type":"get_commands"}\n',
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    for line in result.stdout.splitlines():
        response = json.loads(line)
        if response.get("id") == "skills" and response.get("command") == "get_commands":
            if not response.get("success"):
                raise RuntimeError("Pi get_commands request failed")
            commands = response.get("data", {}).get("commands")
            if not isinstance(commands, list):
                raise RuntimeError("Pi returned invalid get_commands data")
            return commands
    raise RuntimeError("Pi did not return a get_commands response")


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


def smoke_amp(root: Path, runner: Run = subprocess.run) -> None:
    home, workspace = root / "home", root / "workspace"
    generated = root / "generated-target"
    generated_skills = generated / "skills"
    generated_plugin = generated / amp_port.PLUGIN_TARGET_RELATIVE
    generated_workflow_plugin = generated / amp_port.WORKFLOW_PLUGIN_RELATIVE_PATH
    install = workspace / ".agents/skills"
    xdg_roots = {
        name: root / name.lower()
        for name in (
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
            "XDG_STATE_HOME",
        )
    }
    for path in (home, workspace, install, *xdg_roots.values()):
        path.mkdir(parents=True)
    canonical_resource = SOURCE_PLUGIN_DIR / "skills" / AMP_SOURCE_EXECUTABLE
    canonical_snapshot = _resource_snapshot(canonical_resource)
    amp_port.build_target(SOURCE_PLUGIN_DIR, generated)
    generated_resource = generated_skills / AMP_EXECUTABLE_RESOURCE
    _verify_resource_snapshot(generated_resource, canonical_snapshot)
    settings = root / "settings.json"
    settings.write_text(
        json.dumps(
            {
                "amp.experimental.cli.nativeSecretsStorage.enabled": False,
                "amp.skills.disableClaudeCodeSkills": True,
                "amp.updates.mode": "disabled",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    for name in tuple(env):
        if name.startswith(("AMP_", "OTEL_")):
            env.pop(name)
    env |= {
        "HOME": str(home),
        "AMP_API_KEY": "runtime-smoke-placeholder",
        "AMP_URL": "http://127.0.0.1:9",
        "AMP_SKIP_UPDATE_CHECK": "1",
        "AMP_SETTINGS_FILE": str(settings),
        "AMP_LOG_FILE": str(root / "amp.log"),
        **{name: str(path) for name, path in xdg_roots.items()},
    }
    executable = _executable("amp", env)
    version = _run(runner, [executable, "--version"], env, workspace).stdout.strip()
    if not version:
        raise RuntimeError("amp returned an empty version")
    _run(
        runner,
        [
            executable,
            "plugins",
            "exec",
            str(generated_plugin),
            "session.start",
            "--data",
            '{"thread":{"id":"T-runtime-smoke"}}',
        ],
        env,
        workspace,
    )
    _run(
        runner,
        [
            executable,
            "plugins",
            "exec",
            str(generated_workflow_plugin),
            "agent.start",
            "--data",
            json.dumps(
                {
                    "thread": {"id": "T-00000000-0000-0000-0000-000000000000"},
                    "message": "runtime smoke",
                    "id": "runtime-smoke",
                }
            ),
        ],
        env,
        workspace,
    )
    _run(
        runner,
        [
            executable,
            "skill",
            "add",
            str(generated_skills),
            "--target",
            str(install),
        ],
        env,
        workspace,
    )
    _verify_tree(install)
    _verify_resource_snapshot(generated_resource, canonical_snapshot)
    _verify_resource_snapshot(install / AMP_EXECUTABLE_RESOURCE, canonical_snapshot)
    expected = {
        path.parent.name: (install / path.parent.name).resolve()
        for path in generated_skills.glob("*/SKILL.md")
    }
    discovered = _amp_skill_records(
        json.loads(
            _run(runner, [executable, "skill", "list", "--json"], env, workspace).stdout
        ),
        install,
    )
    if discovered != expected:
        raise RuntimeError(
            f"Amp discovered {len(discovered)} generated skills, "
            f"expected the exact {len(expected)}-skill target"
        )
    for name in sorted(expected):
        _run(
            runner,
            [executable, "skill", "remove", name, "--target", str(install)],
            env,
            workspace,
        )
    after = json.loads(
        _run(runner, [executable, "skill", "list", "--json"], env, workspace).stdout
    )
    remaining = _amp_skill_records(after, install)
    if remaining:
        raise RuntimeError(f"Amp rediscovered {len(remaining)} generated skills after removal")
    fallback_names = _amp_skill_names(after) & expected.keys()
    if fallback_names:
        raise RuntimeError(
            f"Amp discovered removed skill names elsewhere: {sorted(fallback_names)}"
        )
    if any(install.iterdir()):
        raise RuntimeError(f"Amp left removed skills on disk: {install}")
    _verify_tree(generated_skills)
    for plugin in (generated_plugin, generated_workflow_plugin):
        if not plugin.is_file():
            raise RuntimeError(f"Amp generated plugin disappeared: {plugin}")
    _verify_resource_snapshot(generated_resource, canonical_snapshot)
    _verify_resource_snapshot(canonical_resource, canonical_snapshot)
    print(
        f"[runtime-smoke] Amp {version}: {EXPECTED_SKILLS} skills, "
        "elixir-phoenix and phx-watch-pr plugins load OK"
    )


def smoke_pi(root: Path, runner: Run = subprocess.run) -> None:
    home, agent_dir = root / "home", root / "agent"
    workspace, package = root / "workspace", root / "package"
    for path in (home, agent_dir, workspace, package / "targets"):
        path.mkdir(parents=True)
    generated = package / "targets/pi"
    pi_port.build(SOURCE_PLUGIN_DIR, generated)
    shutil.copy2(Path(__file__).parents[1] / "package.json", package / "package.json")
    env = os.environ.copy()
    for name in PI_ENV_OVERRIDES:
        env.pop(name, None)
    env |= {
        "HOME": str(home),
        "PI_CODING_AGENT_DIR": str(agent_dir),
        "PI_CODING_AGENT_SESSION_DIR": str(root / "sessions"),
        "PI_OFFLINE": "1",
        "PI_SKIP_VERSION_CHECK": "1",
        "PI_TELEMETRY": "0",
    }
    executable = _executable("pi", env)
    version = _run(runner, [executable, "--version"], env, workspace).stdout.strip()
    if not version:
        raise RuntimeError("pi returned an empty version")
    source = str(package.resolve())
    _run(runner, [executable, "install", source], env, workspace)
    listing = _run(runner, [executable, "list"], env, workspace).stdout
    if source not in listing:
        raise RuntimeError("Pi did not list the installed package")
    _verify_tree(generated / "skills")
    _verify_resource(
        SOURCE_PLUGIN_DIR / "skills",
        generated / "skills",
        PI_SOURCE_EXECUTABLE,
        EXECUTABLE_RESOURCE,
    )
    expected = {
        path.parent.name: path.resolve()
        for path in (generated / "skills").glob("*/SKILL.md")
    }
    discovered = _pi_skill_records(_pi_commands(runner, executable, env, workspace), generated)
    if discovered != expected:
        raise RuntimeError(
            f"Pi discovered {len(discovered)} generated skills, "
            f"expected the exact {len(expected)}-skill target"
        )
    _run(runner, [executable, "remove", source], env, workspace)
    remaining = _pi_skill_records(_pi_commands(runner, executable, env, workspace), generated)
    if remaining:
        raise RuntimeError(f"Pi rediscovered {len(remaining)} generated skills after removal")
    after = _run(runner, [executable, "list"], env, workspace).stdout
    if source in after:
        raise RuntimeError("Pi still lists the removed package")
    if not package.is_dir():
        raise RuntimeError("Pi removed the local package source")
    _verify_resource(
        SOURCE_PLUGIN_DIR / "skills",
        generated / "skills",
        PI_SOURCE_EXECUTABLE,
        EXECUTABLE_RESOURCE,
    )
    print(f"[runtime-smoke] Pi {version}: {EXPECTED_SKILLS} skills OK")


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


def _dsh_rpc(base_url: str, method: str, payload: dict) -> dict:
    """POST one Typert RPC envelope to the dsh web host's /api bridge.

    Verified against dsh 0.1.1-rc.2: the handler does a two-level parse where
    the URL path equals the method (`POST /api/session.create`), the body is a
    `client-request` full form, and the reply wraps the business value in
    `result: {ok, value}`.
    """
    body = json.dumps(
        {
            "type": "client-request",
            "rpcId": f"smoke-{method}",
            "method": method,
            "payload": payload,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/{method}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        message = json.load(response)
    if not isinstance(message, dict):
        raise RuntimeError(f"{method} returned a non-object reply")
    result = message.get("result")
    if not isinstance(result, dict):
        # A top-level `error` (or any other shape) must not be reported as
        # `failed: None`, which reads like a missing detail rather than a
        # protocol mismatch.
        raise RuntimeError(f"{method} returned no result object: {message}")
    if not result.get("ok"):
        raise RuntimeError(f"{method} failed: {result.get('error')}")
    return result.get("value") or {}


def _free_port() -> int:
    """Reserve an ephemeral loopback port and release it for the child.

    A fixed port lets an unrelated listener — a leftover `dsh web`, the user's
    own session, or a concurrent smoke run — answer the readiness probe, which
    would report PASS without a byte reaching the process this function
    launched.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _dsh_log_tail(log: Path, limit: int = 20) -> str:
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "<no output captured>"
    return "\n".join(lines[-limit:]) or "<no output>"


def _dsh_wait_for_host(
    base_url: str, process: subprocess.Popen, log: Path, timeout: float = 120.0
) -> None:
    deadline = time.monotonic() + timeout
    last = "no response yet"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"dsh web exited early with code {process.returncode}\n"
                f"--- dsh output ---\n{_dsh_log_tail(log)}"
            )
        try:
            # `session.list` is read-only, so probing leaves no stray session.
            _dsh_rpc(base_url, "session.list", {})
        except (urllib.error.URLError, OSError, json.JSONDecodeError, RuntimeError) as error:
            last = str(error)
            time.sleep(1.0)
            continue
        # The child may have died between the poll above and this reply, letting
        # something else on the port answer for it. This check stays outside the
        # `except` above, which swallows RuntimeError for the retry path.
        if process.poll() is not None:
            raise RuntimeError(
                f"a foreign listener answered {base_url}; dsh web exited "
                f"with code {process.returncode}\n"
                f"--- dsh output ---\n{_dsh_log_tail(log)}"
            )
        return
    raise RuntimeError(
        f"dsh web did not answer /api within {timeout:.0f}s: {last}\n"
        f"--- dsh output ---\n{_dsh_log_tail(log)}"
    )


def smoke_dsh(
    root: Path,
    runner: Run = subprocess.run,
    spawn: Spawn = subprocess.Popen,
) -> None:
    """Boot an isolated `dsh web --no-open` and assert it discovers the target.

    dsh exposes no CLI skill introspection, so discovery is verified over the
    loopback RPC bridge. `session.create` and `skill.list` invoke no provider,
    so this needs no API key and no model. `spawn` is the injection seam that
    keeps this function testable, mirroring `runner` in the sibling smokes.
    """
    home = root / "home"
    workspace = root / "workspace"
    for path in (home, workspace):
        path.mkdir(parents=True)
    # dsh resolves the project root as the nearest `.git` ancestor.
    (workspace / ".git").mkdir()
    install = workspace / ".agents" / "skills"
    install.parent.mkdir(parents=True, exist_ok=True)
    dsh_port.build(SOURCE_PLUGIN_DIR, root / "generated")
    shutil.copytree(root / "generated" / "skills", install)
    _verify_tree(install)

    env = os.environ.copy()
    for name in list(env):
        if name.startswith("DSH_") or name.startswith("XDG_"):
            del env[name]
    env |= {
        "HOME": str(home),
        "DSH_HOME": str(home / ".dsh"),
        "DSH_AGENTS_HOME": str(home / ".agents"),
        "DSH_TELEMETRY_DISABLED": "1",
    }
    executable = _executable("dsh", env)
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    log = root / "dsh-web.log"
    # Never leave the child writing into an undrained pipe: a full buffer can
    # wedge it before it listens, and the crash reason is the whole point of
    # the output on the most likely first-run failure.
    with log.open("w", encoding="utf-8") as sink:
        process = spawn(
            [executable, "web", "--no-open", "--host", "127.0.0.1", "--port", str(port)],
            env=env,
            cwd=workspace,
            text=True,
            stdout=sink,
            stderr=subprocess.STDOUT,
        )
        try:
            _dsh_wait_for_host(base_url, process, log)
            session = _dsh_rpc(base_url, "session.create", {"cwd": str(workspace)})
            session_id = session.get("sessionId")
            if not session_id:
                raise RuntimeError("session.create returned no sessionId")
            listed = _dsh_rpc(base_url, "skill.list", {"sessionId": session_id})
            entries = listed.get("skills") or []
            discovered = {
                entry.get("name") for entry in entries if isinstance(entry, dict)
            }
            expected = {path.parent.name for path in install.glob("*/SKILL.md")}
            missing = expected - discovered
            if missing:
                raise RuntimeError(
                    f"dsh discovered {len(discovered & expected)} of {len(expected)} "
                    f"generated skills; missing {sorted(missing)[:5]}"
                )
            unavailable = sorted(
                entry.get("name")
                for entry in entries
                if isinstance(entry, dict)
                and entry.get("name") in expected
                and not entry.get("modelInvocable")
            )
            if unavailable:
                raise RuntimeError(
                    f"generated skills are not model-invocable in dsh: {unavailable[:5]}"
                )
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=20)
    print(f"[runtime-smoke] dsh: {EXPECTED_SKILLS} skills discovered OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime", choices=("amp", "codex", "pi", "opencode", "dsh"))
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix=f"{args.runtime}-runtime-smoke-") as temporary:
            {
                "amp": smoke_amp,
                "codex": smoke_codex,
                "pi": smoke_pi,
                "opencode": smoke_opencode,
                "dsh": smoke_dsh,
            }[args.runtime](Path(temporary))
    except (
        KeyError,
        OSError,
        RuntimeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as error:
        print(f"[runtime-smoke] FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
