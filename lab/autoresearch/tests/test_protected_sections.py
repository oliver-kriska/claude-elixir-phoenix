"""Tests for the protected-section (Iron Laws append-only) invariant."""

import os
import sys

# protected_sections.py lives in scripts/ and is normally run as __main__,
# so make it importable without turning scripts/ into a package.
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

import protected_sections as ps  # noqa: E402


HEAD = """\
---
name: security
---

# Security

## Iron Laws — Never Violate These

1. **VALIDATE AT BOUNDARIES** — Never trust client input
2. **NEVER INTERPOLATE USER INPUT** — Use Ecto's `^` operator
3. **NO String.to_atom WITH USER INPUT** — Atom exhaustion DoS

## Quick Patterns

Some prose here.
"""


def test_iron_laws_extracts_items():
    laws = ps.iron_laws(HEAD)
    assert len(laws) == 3
    assert "**VALIDATE AT BOUNDARIES** — Never trust client input" in laws


def test_iron_laws_empty_when_no_section():
    assert ps.iron_laws("# Skill\n\nNo laws here.\n") == set()


def test_iron_laws_stops_at_next_h2():
    # "Some prose here." lives under Quick Patterns, not Iron Laws.
    assert all("prose" not in law for law in ps.iron_laws(HEAD))


def test_append_is_allowed():
    new = HEAD.replace(
        "3. **NO String.to_atom WITH USER INPUT** — Atom exhaustion DoS\n",
        "3. **NO String.to_atom WITH USER INPUT** — Atom exhaustion DoS\n"
        "4. **ESCAPE BY DEFAULT** — Never use `raw/1` with untrusted content\n",
    )
    assert ps.removed_iron_laws(HEAD, new) == set()


def test_renumber_is_allowed():
    # Insert a law in the middle; existing law texts survive, only prefixes shift.
    new = HEAD.replace(
        "2. **NEVER INTERPOLATE USER INPUT** — Use Ecto's `^` operator\n",
        "2. **NEW MIDDLE LAW** — inserted here\n"
        "3. **NEVER INTERPOLATE USER INPUT** — Use Ecto's `^` operator\n",
    )
    assert ps.removed_iron_laws(HEAD, new) == set()


def test_deletion_is_rejected():
    new = HEAD.replace(
        "2. **NEVER INTERPOLATE USER INPUT** — Use Ecto's `^` operator\n", ""
    )
    removed = ps.removed_iron_laws(HEAD, new)
    assert removed == {"**NEVER INTERPOLATE USER INPUT** — Use Ecto's `^` operator"}


def test_rewording_is_rejected():
    new = HEAD.replace(
        "2. **NEVER INTERPOLATE USER INPUT** — Use Ecto's `^` operator",
        "2. **INTERPOLATION OK SOMETIMES** — relax the rule",
    )
    assert len(ps.removed_iron_laws(HEAD, new)) == 1


def test_check_file_skips_untracked(monkeypatch, tmp_path):
    # File not in HEAD → nothing to protect → no erosion reported.
    monkeypatch.setattr(ps, "_git_head_version", lambda path: None)
    f = tmp_path / "SKILL.md"
    f.write_text("# new skill\n")
    assert ps.check_file(str(f)) == set()


def test_main_returns_nonzero_on_erosion(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(ps, "_git_head_version", lambda path: HEAD)
    f = tmp_path / "SKILL.md"
    f.write_text(HEAD.replace("1. **VALIDATE AT BOUNDARIES** — Never trust client input\n", ""))
    rc = ps.main(["protected_sections.py", str(f)])
    assert rc == 1
    assert "FAIL: protected Iron Law" in capsys.readouterr().out


def test_main_returns_zero_when_intact(monkeypatch, tmp_path):
    monkeypatch.setattr(ps, "_git_head_version", lambda path: HEAD)
    f = tmp_path / "SKILL.md"
    f.write_text(HEAD)
    assert ps.main(["protected_sections.py", str(f)]) == 0
