from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WATCH_PR = ROOT / "plugins" / "elixir-phoenix" / "skills" / "watch-pr" / "scripts" / "watch-pr.sh"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="watch-pr.sh needs jq")


def check_run(status: str, conclusion: str = "") -> dict:
    return {"__typename": "CheckRun", "status": status, "conclusion": conclusion, "name": "ci"}


def status_context(state: str) -> dict:
    # StatusContext has no `status` or `conclusion` key at all.
    return {"__typename": "StatusContext", "state": state, "context": "ci/external"}


def check_events(tmp_path: Path, rollup: list[dict]) -> list[dict]:
    """Run one watcher poll against a closed PR and return its `check` events."""
    view = {
        "state": "CLOSED",
        "mergedAt": None,
        "reviews": [],
        "comments": [],
        "statusCheckRollup": rollup,
        "updatedAt": "2026-09-21T00:00:00Z",
    }
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_gh = bin_dir / "gh"
    fake_gh.write_text(f"#!/bin/sh\ncat <<'JSON'\n{json.dumps(view)}\nJSON\n", encoding="utf-8")
    fake_gh.chmod(0o755)

    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "WATCH_DELTA_FILE": str(tmp_path / "delta.jsonl"),
    }
    result = subprocess.run(
        ["bash", str(WATCH_PR), "1", "checks"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert events[-1]["kind"] == "pr_closed", events
    return [event for event in events if event["kind"] == "check"]


@pytest.mark.parametrize(
    ("rollup", "expected"),
    [
        pytest.param([status_context("SUCCESS")], "success", id="status-context-success"),
        pytest.param([status_context("FAILURE")], "failure", id="status-context-failure"),
        pytest.param([status_context("ERROR")], "failure", id="status-context-error"),
        pytest.param([status_context("PENDING")], None, id="status-context-pending"),
        pytest.param([status_context("EXPECTED")], None, id="status-context-expected"),
        pytest.param([check_run("COMPLETED", "SUCCESS")], "success", id="check-run-success"),
        pytest.param([check_run("COMPLETED", "SKIPPED")], "success", id="check-run-skipped"),
        pytest.param([check_run("COMPLETED", "NEUTRAL")], "success", id="check-run-neutral"),
        pytest.param([check_run("COMPLETED", "FAILURE")], "failure", id="check-run-failure"),
        pytest.param([check_run("COMPLETED", "CANCELLED")], "failure", id="check-run-cancelled"),
        pytest.param([check_run("COMPLETED", "TIMED_OUT")], "failure", id="check-run-timed-out"),
        pytest.param([check_run("COMPLETED", "STARTUP_FAILURE")], "failure", id="check-run-startup-failure"),
        pytest.param([check_run("COMPLETED", "ACTION_REQUIRED")], "failure", id="check-run-action-required"),
        pytest.param([check_run("COMPLETED", "STALE")], "failure", id="check-run-stale"),
        pytest.param([check_run("IN_PROGRESS")], None, id="check-run-in-progress"),
        pytest.param([check_run("QUEUED")], None, id="check-run-queued"),
        pytest.param(
            [check_run("COMPLETED", "SUCCESS")] * 8 + [status_context("SUCCESS")] * 2,
            "success",
            id="all-green-mixed-rollup",
        ),
        pytest.param(
            [check_run("COMPLETED", "SUCCESS"), status_context("PENDING")],
            None,
            id="mixed-rollup-still-pending",
        ),
        pytest.param(
            [check_run("COMPLETED", "SUCCESS"), status_context("FAILURE")],
            "failure",
            id="mixed-rollup-status-context-fails",
        ),
    ],
)
def test_check_event_classifies_both_rollup_shapes(
    tmp_path: Path, rollup: list[dict], expected: str | None
) -> None:
    events = check_events(tmp_path, rollup)
    if expected is None:
        assert events == []
    else:
        assert [event["conclusion"] for event in events] == [expected]
