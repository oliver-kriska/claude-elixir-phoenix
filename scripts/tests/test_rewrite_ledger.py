from __future__ import annotations

import importlib.util
import json
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


def test_complete_table_does_not_mask_an_incomplete_one(rewrite_dir: Path) -> None:
    (rewrite_dir / "ledger.md").write_text(
        "# Ledger\n\n" + HEADER + row("M-01") + row("C-01")
        + "\n## More\n\n| ID | Verdict |\n|----|----|\n| M-02 | KEEP |\n",
        encoding="utf-8",
    )

    errors, warnings = ledger.check(str(rewrite_dir))

    assert "ledger table 2 has no 'impl' column" in errors
    assert "ledger table 2 has no 'evidence' column" in errors
    assert "ledger table 2 has no 'departure' column; accepted risks cannot be recorded" in warnings
    assert not any("table 1" in m for m in errors + warnings)


def test_grouped_analysis_definition_requires_every_alias(rewrite_dir: Path) -> None:
    (rewrite_dir / "analysis/mechanisms.md").write_text(
        "| ID | Mechanism |\n|----|----|\n| M-01, `M-02` | a and b |\n", encoding="utf-8"
    )
    write_ledger(rewrite_dir, row("M-01") + row("C-01"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == ["M-02 (defined in mechanisms.md) is not accounted for in the ledger"]


def test_cli_stats_fails_on_malformed_rows(rewrite_dir: Path, capsys) -> None:
    truncated = row("M-02").rsplit(" not-run | none |", 1)[0] + "\n"
    write_ledger(rewrite_dir, row("M-01", impl="implemented", evidence="pass") + truncated)

    assert ledger.main(["stats", "--rewrite-dir", str(rewrite_dir)]) == 1
    out = capsys.readouterr()
    assert "malformed ledger row (9 cells, header has 11" in out.err
    assert "verified" not in out.out


def test_cli_stats_fails_without_a_ledger_table(rewrite_dir: Path, capsys) -> None:
    (rewrite_dir / "ledger.md").write_text("# Ledger\n\n| ID | Note |\n|----|----|\n| M-01 | x |\n", encoding="utf-8")

    assert ledger.main(["stats", "--rewrite-dir", str(rewrite_dir)]) == 1
    assert "no ledger table" in capsys.readouterr().err


def test_direct_stats_rejects_a_malformed_ledger(rewrite_dir: Path) -> None:
    truncated = row("M-02").rsplit(" not-run | none |", 1)[0] + "\n"
    write_ledger(rewrite_dir, row("M-01", impl="implemented", evidence="pass") + truncated)

    with pytest.raises(ledger.LedgerError) as exc:
        ledger.stats(str(rewrite_dir))

    assert any(e.startswith("malformed ledger row (9 cells") for e in exc.value.errors)


def test_cli_stats_counts_the_snapshot_it_validated(rewrite_dir: Path, capsys, monkeypatch) -> None:
    body = row("M-01", impl="implemented", evidence="pass") + row("M-02", impl="implemented", evidence="fail")
    write_ledger(rewrite_dir, body)
    real_rows = ledger.rows_as_dicts

    def parse_then_truncate(text):
        result = real_rows(text)
        truncated = row("M-02").rsplit(" not-run | none |", 1)[0] + "\n"
        write_ledger(rewrite_dir, row("M-01", impl="implemented", evidence="pass") + truncated)
        return result

    monkeypatch.setattr(ledger, "rows_as_dicts", parse_then_truncate)

    code = ledger.main(["stats", "--rewrite-dir", str(rewrite_dir)])

    assert code == 0
    assert "verified 1 of 2 ledger rows" in capsys.readouterr().out


def test_nonconforming_row_id_fails_check_and_stats(rewrite_dir: Path, capsys) -> None:
    # `R-D4` matched no ID pattern, so its UNDECIDED row vanished and stats reported UNDECIDED 0.
    write_ledger(rewrite_dir, row("M-01") + row("M-02") + row("C-01") + row("R-D4", "UNDECIDED"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert any(e.startswith("malformed ledger row (nonconforming ID R-D4;") for e in errors)
    assert ledger.main(["stats", "--rewrite-dir", str(rewrite_dir)]) == 1
    out = capsys.readouterr()
    assert "nonconforming ID R-D4" in out.err
    assert "UNDECIDED" not in out.out


def test_nonconforming_alias_does_not_hide_a_valid_id(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01") + row("M-02") + row("C-01, R-D5"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert any("nonconforming ID R-D5" in e for e in errors)
    assert "C-01 (defined in contracts.md) is not accounted for in the ledger" in errors


def test_nonconforming_analysis_definition_is_an_error(rewrite_dir: Path) -> None:
    (rewrite_dir / "analysis/runtime.md").write_text(
        "| ID | Component |\n|----|----|\n| R-01 | db |\n| R-J1 | jobs |\n", encoding="utf-8"
    )
    write_ledger(rewrite_dir, row("M-01") + row("M-02") + row("C-01") + row("R-01") + row("R-01a", "DELETE"))

    errors, _ = ledger.check(str(rewrite_dir))

    assert errors == ["runtime.md defines nonconforming ID R-J1; rename it to M-/R-/C- plus two or more digits "
                      "so it is counted"]


SEED = """# Brainstorm: Rewrite slice 07

## Legacy Mechanism → Elixir Decision

| Ledger | Legacy mechanism (anchor) | Purpose | Verdict | Elixir target | Guarantees to keep |
|---|---|---|---|---|---|
| M-04, C-11 | optional auth | anonymous reads | MAP | plug | degrade |

## External Contracts

| Contract | Assertion | Witness the tests must implement |
|---|---|---|
| C-24 | delete is 204 | ExUnit + curl |

## Acceptance Criteria

- [ ] AC-1 (C-24): the delete answers 204 with no body
- [ ] AC-2a (M-04, C-11): each bad-token vector on the list
  reads as anonymous
- [ ] AC-2b (M-04): a valid token reads as that viewer

## Codebase Context

- [ ] AC-99 (C-50): not an acceptance case, outside the section
"""


def test_obligations_lists_each_case_with_its_ledger_ids() -> None:
    cases, errors = ledger.obligations(SEED)
    assert errors == []
    assert [c["id"] for c in cases] == ["AC-1", "AC-2a", "AC-2b"]
    assert cases[1]["cites"] == ["C-11", "M-04"]  # continuation line belongs to its item


def test_obligations_flags_a_table_id_no_case_cites() -> None:
    _, errors = ledger.obligations(SEED.replace("- [ ] AC-1 (C-24):", "- [ ] AC-1 (D-05):"))
    assert errors == ["C-24 (external contracts) is cited by no acceptance case"]


@pytest.mark.parametrize("edit, message", [
    (("- [ ] AC-2b (M-04)", "- [ ] AC-2a (M-04)"), "AC-2a is listed twice"),
    (("- [ ] AC-2b (M-04)", "- [ ] AC-2 (M-04)"), "AC-2 is listed bare and with lettered cases; keep one form"),
    (("- [ ] AC-1 (C-24):", "- [ ] (C-24):"), "acceptance item without an AC-NN id: (C-24): the delete answers 204 with no body"),
])
def test_obligations_errors_make_the_list_unusable(edit, message) -> None:
    _, errors = ledger.obligations(SEED.replace(*edit))
    assert message in errors


def test_obligations_without_the_section_is_an_error() -> None:
    assert ledger.obligations("# Brainstorm\n\n## Summary\n")[1] == ["no `## Acceptance Criteria` section"]


def test_cli_obligations_exit_status(tmp_path: Path, capsys) -> None:
    seed = tmp_path / "interview.md"
    seed.write_text(SEED, encoding="utf-8")
    assert ledger.main(["obligations", "--slice", str(seed)]) == 0
    assert "obligations: 3 acceptance cases" in capsys.readouterr().out
    seed.write_text(SEED.replace("(C-24):", "(D-05):"), encoding="utf-8")
    assert ledger.main(["obligations", "--slice", str(seed)]) == 1
    assert ledger.main(["obligations", "--slice", str(tmp_path / "missing.md")]) == 2


def test_stats_slice_counts_only_the_ids_the_seed_owns(rewrite_dir: Path, tmp_path: Path, capsys) -> None:
    write_ledger(rewrite_dir, row("M-04") + row("C-11") + row("C-24", impl="implemented", evidence="pass") + row("C-50"))
    seed = tmp_path / "interview.md"
    seed.write_text(SEED.replace("## Codebase Context", "## Scope\n\nOut of scope: C-50 belongs to slice 08.\n\n"
                                 "## Codebase Context"), encoding="utf-8")
    assert ledger.main(["stats", "--rewrite-dir", str(rewrite_dir), "--slice", str(seed), "--json"]) == 0
    s = json.loads(capsys.readouterr().out)
    assert s["rows"] == 3 and s["verified"] == 1  # C-50, named in prose and in an item outside the section, is not counted


def test_set_changes_only_impl_and_evidence_cells(rewrite_dir: Path) -> None:
    other = "| M-02 | `a \\| b` | **y** | business | — | MAP | z | — | pending | not-run | none |\n"
    write_ledger(rewrite_dir, row("M-01, C-01") + other)
    before = (rewrite_dir / "ledger.md").read_text(encoding="utf-8")

    code = ledger.main(["set", "--rewrite-dir", str(rewrite_dir), "--ids", "C-01,M-02", "--impl", "implemented", "--evidence", "pass"])

    after = (rewrite_dir / "ledger.md").read_text(encoding="utf-8")
    assert code == 0
    assert after == before.replace("| pending | not-run | none |", "| implemented | pass | none |")
    assert "`a \\| b` | **y**" in after
    assert ledger.check(str(rewrite_dir))[0] == []


def test_set_one_axis_keeps_the_other(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01", impl="implemented") + row("M-02") + row("C-01"))

    assert ledger.main(["set", "--rewrite-dir", str(rewrite_dir), "--ids", "M-01", "--evidence", "pass"]) == 0

    text = (rewrite_dir / "ledger.md").read_text(encoding="utf-8")
    assert "| M-01 | x | y | business | — | REPLACE | z | — | implemented | pass | none |" in text
    assert text.count("| pending | not-run | none |") == 2


def test_set_with_an_unknown_id_writes_nothing(rewrite_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_ledger(rewrite_dir, row("M-01") + row("M-02") + row("C-01"))
    before = (rewrite_dir / "ledger.md").read_text(encoding="utf-8")

    code = ledger.main(["set", "--rewrite-dir", str(rewrite_dir), "--ids", "M-01,C-09", "--impl", "implemented"])

    assert code == 1
    assert "C-09 is not the ID or an alias of any ledger row" in capsys.readouterr().out
    assert (rewrite_dir / "ledger.md").read_text(encoding="utf-8") == before


def test_set_needs_a_state_and_rejects_unknown_values(rewrite_dir: Path) -> None:
    write_ledger(rewrite_dir, row("M-01") + row("M-02") + row("C-01"))

    assert ledger.main(["set", "--rewrite-dir", str(rewrite_dir), "--ids", "M-01"]) == 2
    with pytest.raises(SystemExit):
        ledger.main(["set", "--rewrite-dir", str(rewrite_dir), "--ids", "M-01", "--evidence", "done"])
