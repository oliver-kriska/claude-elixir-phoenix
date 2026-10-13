from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "plugins/rewrite/skills/architect/scripts/ledger.py"
)


def load_ledger():
    spec = importlib.util.spec_from_file_location("rewrite_ledger", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ledger = load_ledger()

HEADER = (
    "| ID | Mechanism (anchor) | Purpose (evidence) | Tags | Guarantees | Verdict "
    "| Elixir target | Contract | Impl | Evidence | Departure |\n"
    "|----|----|----|----|----|----|----|----|----|----|----|\n"
)


def row(ident, verdict="REPLACE", impl="pending", evidence="not-run", departure="none"):
    return f"| {ident} | x | y | business | — | {verdict} | z | — | {impl} | {evidence} | {departure} |\n"


@pytest.fixture
def rewrite_dir(tmp_path: Path) -> Path:
    root = tmp_path / ".claude/rewrite"
    (root / "analysis").mkdir(parents=True)
    (root / "architecture/adr").mkdir(parents=True)
    (root / "analysis/mechanisms.md").write_text(
        "| ID | Mechanism |\n|----|----|\n| M-01 | a |\n| M-02 | b |\n", encoding="utf-8"
    )
    (root / "analysis/contracts.md").write_text(
        "| ID | Surface |\n|----|----|\n| C-01 | wire |\n", encoding="utf-8"
    )
    (root / "architecture/ADR-000-compatibility-bar.md").write_text("# ADR-000\n", encoding="utf-8")
    (root / "architecture/adr/ADR-001-oban.md").write_text("# ADR-001\n", encoding="utf-8")
    return root


def risk(ar, scope, approved="Oliver, 2026-10-09, review thread #4"):
    return (
        f"## {ar} — legacy cookie format kept\n\n- Owner: ops\n- Scope: {scope}\n"
        f"- Rationale: mobile clients\n- Review: after v2 app ships\n- Approved: {approved}\n\n"
    )


def write_ledger(root: Path, body: str) -> None:
    (root / "ledger.md").write_text("# Ledger\n\n" + HEADER + body, encoding="utf-8")


def test_check_passes_when_every_defined_id_is_accounted(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01") + row("M-02", "KEEP→REPLACE") + row("C-01", "SHIM"))

    errors, warnings = ledger.check(str(rewrite_dir))

    assert errors == []
    assert warnings == []


def test_check_reports_missing_ids_bad_values_and_adr_refs(rewrite_dir: Path) -> None:
    write_ledger(
        rewrite_dir,
        row("M-01", verdict="PORT") + row("C-01", impl="done") + "See ADR-007.\n",
    )

    errors, _ = ledger.check(str(rewrite_dir))
    text = "\n".join(errors)

    assert "M-02 (defined in mechanisms.md) is not accounted for" in text
    assert "M-01: verdict 'PORT'" in text
    assert "C-01: implementation 'done'" in text
    assert "ADR-007 referenced" in text


def test_merged_alias_counts_as_accounted(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01, M-02") + row("C-01"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == []


def test_undecided_but_implemented_is_a_warning(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", "UNDECIDED", impl="implemented") + row("M-02") + row("C-01"))

    _, warnings = ledger.check(str(rewrite_dir))

    assert warnings == ["M-01: implemented while its verdict is UNDECIDED"]


def test_departure_must_be_a_recorded_accepted_risk(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", departure="AR-01") + row("M-02", departure="AR-02") + row("C-01", departure="maybe"))
    (rewrite_dir / "verify").mkdir()
    (rewrite_dir / "verify/accepted-risks.md").write_text("# Accepted risks\n\n" + risk("AR-01", "M-01"), encoding="utf-8")

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == [
        "M-02: AR-02 has no section in verify/accepted-risks.md",
        "C-01: departure 'maybe' is neither 'none' nor AR-NN",
    ]


def test_accepted_risk_needs_every_field_and_must_scope_the_row(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", departure="AR-01") + row("M-02", departure="AR-02") + row("C-01"))
    (rewrite_dir / "verify").mkdir()
    (rewrite_dir / "verify/accepted-risks.md").write_text(
        "# Accepted risks\n\n## AR-01 — bare heading\n\n"
        + risk("AR-02", "M-07", approved="TBD"),
        encoding="utf-8",
    )

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == [
        "M-01: AR-01 has no Owner",
        "M-01: AR-01 has no Scope",
        "M-01: AR-01 has no Rationale",
        "M-01: AR-01 has no Review",
        "M-01: AR-01 has no Approved",
        "M-02: AR-02 has no Approved",
        "M-02: AR-02 Scope does not list M-02",
    ]


def test_prose_mention_does_not_account_for_an_id(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", impl="implemented", evidence="pass") + row("C-01") + "\nMissing: M-02\n")

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == ["M-02 (defined in mechanisms.md) is not accounted for in the ledger"]


def test_backticked_id_cell_is_parsed(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01") + row("`M-02`", evidence="fail") + row("C-01"))

    errors, _ = ledger.check(str(rewrite_dir))
    s = ledger.stats(str(rewrite_dir))

    assert errors == []
    assert s["rows"] == 3
    assert s["evidence"]["fail"] == 1


def test_alias_in_two_rows_is_a_duplicate(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01, M-02") + row("M-02") + row("C-01"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == ["M-02 appears in 2 ledger rows"]


def test_truncated_row_and_id_outside_first_cell_fail_closed(rewrite_dir: Path) -> None:
    truncated = row("M-02").rsplit(" not-run | none |", 1)[0] + "\n"
    shifted = "| ~ | M-03 | y | business | — | KEEP | z | — | pending | not-run | none |\n"
    write_ledger(rewrite_dir, row("M-01") + truncated + shifted + row("C-01"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert any(e.startswith("malformed ledger row (9 cells, header has 11") for e in errors)
    assert any(e.startswith("malformed ledger row (no ID in first cell") for e in errors)
    assert "M-02 (defined in mechanisms.md) is not accounted for in the ledger" in errors


def test_empty_departure_cell_is_an_error(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", departure="") + row("M-02") + row("C-01"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == ["M-01: empty departure cell (write 'none' or AR-NN)"]


def test_missing_departure_column_is_a_warning(rewrite_dir: Path) -> None:
    header = HEADER.replace(" Departure |", "").replace("|----|\n", "\n", 1)
    body = "".join(row(i).rsplit(" none |", 1)[0] + "\n" for i in ("M-01", "M-02", "C-01"))
    (rewrite_dir / "ledger.md").write_text("# Ledger\n\n" + header + body, encoding="utf-8")

    errors, warnings = ledger.check(str(rewrite_dir))

    assert errors == []
    assert warnings == ["ledger table has no 'departure' column; accepted risks cannot be recorded"]


def test_stats_keep_retired_and_accepted_risk_out_of_verified(rewrite_dir: Path) -> None:
    write_ledger(
        rewrite_dir,
        row("M-01", impl="implemented", evidence="pass")
        + row("M-02", impl="implemented", evidence="pass", departure="AR-01")
        + row("C-01", "DELETE", impl="retired", evidence="pass"),
    )

    s = ledger.stats(str(rewrite_dir))

    assert s["verified"] == 1
    assert s["denominator"] == 2
    assert s["retired"] == 1
    assert s["accepted_risk"] == 1


def test_stats_scoped_to_slice_ids(rewrite_dir: Path, tmp_path: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", impl="implemented", evidence="pass") + row("M-02") + row("C-01"))
    interview = tmp_path / "interview.md"
    interview.write_text("Ledger rows: M-01, C-01\n", encoding="utf-8")

    code = ledger.main(["stats", "--rewrite-dir", str(rewrite_dir), "--slice", str(interview), "--json"])

    assert code == 0
    assert ledger.stats(str(rewrite_dir), {"M-01", "C-01"})["rows"] == 2


def test_cli_check_exit_codes(rewrite_dir: Path, capsys) -> None:
    write_ledger(rewrite_dir, row("M-01"))
    assert ledger.main(["check", "--rewrite-dir", str(rewrite_dir)]) == 1
    assert "error" in capsys.readouterr().out

    write_ledger(rewrite_dir, row("M-01") + row("M-02") + row("C-01"))
    assert ledger.main(["check", "--rewrite-dir", str(rewrite_dir)]) == 0


def test_realistic_ledger_with_summary_table_suffix_ids_and_escaped_pipes(rewrite_dir: Path) -> None:
    (rewrite_dir / "analysis/contracts.md").write_text(
        "| ID | Surface |\n|----|----|\n| C-01 | wire |\n| C-01a | wire |\n", encoding="utf-8"
    )
    summary = (
        "## UNDECIDED Summary\n\n| ID | Blocking question | Evidence needed |\n|----|----|----|\n"
        "| M-02 | why nightly? | cron owner |\n\n## Mechanisms\n\n"
    )
    piped = row("C-01a", impl="pending").replace("| z |", "| `mode: :optional \\| :required` |")
    (rewrite_dir / "ledger.md").write_text(
        "# Ledger\n\n" + summary + HEADER + row("M-01") + row("M-02", "UNDECIDED") + row("C-01") + piped,
        encoding="utf-8",
    )

    errors, _ = ledger.check(str(rewrite_dir))
    s = ledger.stats(str(rewrite_dir))

    assert errors == []
    assert s["rows"] == 4
    assert s["undecided"] == 1


def test_no_ledger_table_is_an_error_not_a_crash(rewrite_dir: Path) -> None:
    (rewrite_dir / "ledger.md").write_text("# Ledger\n\n| ID | Note |\n|----|----|\n| M-01 | x |\n", encoding="utf-8")

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == ["ledger.md has no ledger table (header starting `| ID |` with a Verdict column)"]


def test_cli_stats_fails_without_a_ledger(tmp_path: Path, capsys) -> None:
    assert ledger.main(["stats", "--rewrite-dir", str(tmp_path)]) == 2
    assert "missing" in capsys.readouterr().out


def test_empty_selection_counts_nothing(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", impl="implemented", evidence="pass") + row("M-02") + row("C-01"))

    assert ledger.stats(str(rewrite_dir), set())["rows"] == 0
    assert ledger.stats(str(rewrite_dir), {"M-01"})["verified"] == 1


def test_cli_slice_unreadable_fails_and_empty_slice_warns(rewrite_dir: Path, tmp_path: Path, capsys) -> None:
    write_ledger(rewrite_dir, row("M-01", impl="implemented", evidence="pass") + row("M-02") + row("C-01"))
    empty = tmp_path / "interview.md"
    empty.write_text("# Slice with no IDs\n", encoding="utf-8")

    assert ledger.main(["stats", "--rewrite-dir", str(rewrite_dir), "--slice", str(tmp_path / "nope.md")]) == 2
    assert "cannot read slice file" in capsys.readouterr().out

    assert ledger.main(["stats", "--rewrite-dir", str(rewrite_dir), "--slice", str(empty)]) == 0
    out = capsys.readouterr()
    assert "verified 0 of 0 ledger rows" in out.out
    assert "matches no ledger rows" in out.err


def test_cli_ids_reports_unknown_ids(rewrite_dir: Path, capsys) -> None:
    write_ledger(rewrite_dir, row("M-01") + row("M-02") + row("C-01"))

    assert ledger.main(["stats", "--rewrite-dir", str(rewrite_dir), "--ids", "M-01,M-99", "--json"]) == 0
    out = capsys.readouterr()
    assert '"unmatched_ids": [\n    "M-99"\n  ]' in out.out
    assert "not in the ledger: M-99" in out.err
