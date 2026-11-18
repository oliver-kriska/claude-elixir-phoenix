from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIFF_CVES = ROOT / "plugins/elixir-phoenix/skills/deps-audit/scripts/diff_cves.py"

CRITICAL_OLD = {
    "pass": False,
    "vulnerabilities": [
        {
            "advisory": {
                "id": "GHSA-decimal-32686",
                "cve": "CVE-2026-32686",
                "title": "Decimal DoS via unbounded exponent",
                "severity": "critical",
            },
            "dependency": {"package": "decimal", "version": "2.3.0"},
        }
    ],
}


def _run(
    tmp_path: Path, old: str | None, new: str | None
) -> tuple[subprocess.CompletedProcess, list[dict]]:
    old_path = tmp_path / "cves_old.json"
    new_path = tmp_path / "cves_new.json"
    out_path = tmp_path / "diff_cves.jsonl"
    if old is not None:
        old_path.write_text(old)
    if new is not None:
        new_path.write_text(new)
    result = subprocess.run(
        [
            sys.executable,
            str(DIFF_CVES),
            "--old",
            str(old_path),
            "--new",
            str(new_path),
            "--out",
            str(out_path),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    rows = []
    if out_path.exists():
        rows = [json.loads(line) for line in out_path.read_text().splitlines() if line]
    return result, rows


def test_truncated_new_scan_fails_the_audit(tmp_path: Path) -> None:
    result, rows = _run(
        tmp_path,
        json.dumps(CRITICAL_OLD),
        '{"pass": false, "vulnerabilities": [{"advis',
    )
    assert result.returncode == 3, result.stderr
    assert not [r for r in rows if r["category"] == "patched"], rows


def test_empty_new_scan_fails_the_audit(tmp_path: Path) -> None:
    result, rows = _run(tmp_path, json.dumps(CRITICAL_OLD), "")
    assert result.returncode == 3, result.stderr
    assert not [r for r in rows if r["category"] == "patched"], rows


def test_new_scan_without_vulnerabilities_list_fails_the_audit(tmp_path: Path) -> None:
    result, rows = _run(
        tmp_path,
        json.dumps(CRITICAL_OLD),
        json.dumps({"error": "could not compile dependency"}),
    )
    assert result.returncode == 3, result.stderr
    assert not [r for r in rows if r["category"] == "patched"], rows


def test_unreadable_old_scan_fails_the_audit(tmp_path: Path) -> None:
    result, rows = _run(tmp_path, "", json.dumps(CRITICAL_OLD))
    assert result.returncode == 3, result.stderr
    assert rows == []


def test_clean_new_scan_still_reports_patched(tmp_path: Path) -> None:
    result, rows = _run(
        tmp_path,
        json.dumps(CRITICAL_OLD),
        json.dumps({"pass": True, "vulnerabilities": []}),
    )
    assert result.returncode == 0, result.stderr
    assert [r["category"] for r in rows] == ["patched"]


def test_missing_old_scan_treats_new_cves_as_introduced(tmp_path: Path) -> None:
    result, rows = _run(tmp_path, None, json.dumps(CRITICAL_OLD))
    assert result.returncode == 0, result.stderr
    assert [(r["category"], r["severity"]) for r in rows] == [("introduced", "block")]
