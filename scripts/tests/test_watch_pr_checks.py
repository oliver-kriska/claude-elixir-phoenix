"""The check-rollup classifier inside watch-pr.sh.

The jq program is EXTRACTED FROM THE SHIPPED SCRIPT rather than copied here.
A copy would keep passing while the script drifted away from it, which is the
failure this test exists to prevent: the regression it covers was a silent one,
where the watcher simply never emitted an event.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WATCHER = (
    REPO_ROOT
    / "plugins"
    / "elixir-phoenix"
    / "skills"
    / "watch-pr"
    / "scripts"
    / "watch-pr.sh"
)

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None, reason="jq is required by watch-pr.sh itself"
)


def check_program() -> str:
    """The jq source of the `checks` block, read out of watch-pr.sh."""
    match = re.search(
        r"""CHECK=\$\(jq -r '(.*?)' <<<"\$VIEW"\)""",
        WATCHER.read_text(encoding="utf-8"),
        re.S,
    )
    assert match, "the checks block moved — update this extraction"
    return match.group(1)


def classify(rollup: list[dict]) -> str:
    payload = json.dumps({"statusCheckRollup": rollup})
    result = subprocess.run(
        ["jq", "-r", check_program()],
        input=payload,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def check_run(status: str, conclusion: str | None) -> dict:
    return {
        "__typename": "CheckRun",
        "status": status,
        "conclusion": conclusion,
        "name": "Elixir",
    }


def status_context(state: str) -> dict:
    return {"__typename": "StatusContext", "state": state, "context": "CodeRabbit"}


@pytest.mark.parametrize(
    ("label", "rollup", "expected"),
    [
        # StatusContext carries no status/conclusion key at all. Treating its
        # `state` as a CheckRun `status` left passing checks pending forever,
        # so `pending == 0` never held and no check event was ever emitted.
        ("status context passed", [status_context("SUCCESS")], "pending=0 failure=0 total=1"),
        ("status context pending", [status_context("PENDING")], "pending=1 failure=0 total=1"),
        ("status context expected", [status_context("EXPECTED")], "pending=1 failure=0 total=1"),
        ("status context failed", [status_context("FAILURE")], "pending=0 failure=1 total=1"),
        ("status context errored", [status_context("ERROR")], "pending=0 failure=1 total=1"),
        # A cancelled or timed-out run scoring zero failures AND zero pending is
        # worse than a missed event: the watcher reports conclusion "success".
        ("check run cancelled", [check_run("COMPLETED", "CANCELLED")], "pending=0 failure=1 total=1"),
        ("check run timed out", [check_run("COMPLETED", "TIMED_OUT")], "pending=0 failure=1 total=1"),
        ("check run action required", [check_run("COMPLETED", "ACTION_REQUIRED")], "pending=0 failure=1 total=1"),
        ("check run passed", [check_run("COMPLETED", "SUCCESS")], "pending=0 failure=0 total=1"),
        ("check run failed", [check_run("COMPLETED", "FAILURE")], "pending=0 failure=1 total=1"),
        ("check run in progress", [check_run("IN_PROGRESS", None)], "pending=1 failure=0 total=1"),
        ("check run queued", [check_run("QUEUED", None)], "pending=1 failure=0 total=1"),
        # Mixed rollups are the common real shape: Actions plus integrations.
        (
            "one green check run and one pending status context",
            [check_run("COMPLETED", "SUCCESS"), status_context("PENDING")],
            "pending=1 failure=0 total=2",
        ),
        (
            "all green across both shapes",
            [check_run("COMPLETED", "SUCCESS"), status_context("SUCCESS")],
            "pending=0 failure=0 total=2",
        ),
        ("empty rollup", [], "pending=0 failure=0 total=0"),
    ],
)
def test_rollup_classification(label: str, rollup: list[dict], expected: str) -> None:
    assert classify(rollup) == expected, label
