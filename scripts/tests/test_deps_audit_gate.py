from __future__ import annotations

import fnmatch
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "elixir-phoenix"
GATE = PLUGIN / "hooks" / "scripts" / "deps-audit-gate.sh"
HOOKS_JSON = PLUGIN / "hooks" / "hooks.json"
SMOKE_SUITE = ROOT / "lab" / "deps-audit" / "smoke-test" / "gate-test.sh"
SIDECAR_DOC = PLUGIN / "skills" / "deps-audit" / "references" / "output-renderer.md"


def test_gate_smoke_suite_passes() -> None:
    result = subprocess.run(
        ["bash", str(SMOKE_SUITE)], text=True, capture_output=True, timeout=120
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _gate_if_condition() -> str:
    config = json.loads(HOOKS_JSON.read_text())
    for group in config["hooks"]["PreToolUse"]:
        for hook in group["hooks"]:
            if "deps-audit-gate.sh" in hook["command"]:
                return hook["if"]
    raise AssertionError("deps-audit-gate.sh is not registered as a PreToolUse hook")


def test_gate_trigger_reaches_alias_and_igniter_commands() -> None:
    condition = _gate_if_condition()
    match = re.fullmatch(r"Bash\((.*)\)", condition)
    assert match, condition
    for command in ["mix deps.get", "mix setup", "mix igniter.install foo", "cd app && mix ci"]:
        assert fnmatch.fnmatchcase(command, match.group(1)), (condition, command)


def test_sidecar_fields_the_gate_reads_are_documented() -> None:
    gate = GATE.read_text()
    fields = set(re.findall(r"jq -r '\.([a-z_]+)[^']*' \"\$LAST_RUN\"", gate))
    assert fields, "found no last-run.json reads in the gate"
    doc = SIDECAR_DOC.read_text()
    missing = sorted(field for field in fields if f"`{field}`" not in doc and f'"{field}"' not in doc)
    assert not missing, f"output-renderer.md does not document sidecar fields {missing}"
