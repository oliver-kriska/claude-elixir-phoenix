#!/usr/bin/env python3
"""Protected-section invariant for the autoresearch loop.

SkillOpt (arXiv 2605.23904) found that a *structural guarantee* preventing fast
edits from overwriting slow lessons is worth ~22 points on SpreadsheetBench.
Their "fast vs slow state" split maps cleanly onto our skills:

  - slow state  = Iron Laws  (hard-won prohibitions; must never erode)
  - fast state  = everything else (patterns, examples, prose the loop tunes)

Without this guard, an optimizer chasing the conciseness dimension can legally
delete or reword an Iron Law, because safety is only a *soft* score penalty and
our anti-thrash rule keeps a mutation when it helps one dimension more than it
hurts another. This module makes Iron Laws **append-only**: the loop may add a
law, but deleting or rewording an existing one forces a REVERT.

The pure function lives here so it is unit-testable; ``checks.sh`` shells out to
``__main__`` and turns a non-empty "removed" set into a hard checks failure.
"""

from __future__ import annotations

import re
import subprocess
import sys

# Matches the Iron Laws H2 heading line (any suffix, e.g. "— Never Violate These")
# and captures the section body up to the next H2 heading or end of file.
_SECTION_RE = re.compile(r"^##\s+Iron Laws[^\n]*\n(.*?)(?=^##\s|\Z)", re.M | re.S)

# A numbered list item: "1. ...", "12. ...". Captures the law text after the prefix.
_ITEM_RE = re.compile(r"^\s*\d+\.\s+(.*\S)\s*$")


def iron_laws(text: str) -> set[str]:
    """Return the set of Iron Law item texts in ``text``.

    The leading ``N. `` number prefix is stripped and whitespace normalized, so
    renumbering (inserting a law in the middle) is NOT treated as erosion — only
    deleting or rewording an existing law changes the set.
    """
    match = _SECTION_RE.search(text)
    if not match:
        return set()
    laws: set[str] = set()
    for line in match.group(1).splitlines():
        item = _ITEM_RE.match(line)
        if item:
            laws.add(" ".join(item.group(1).split()))
    return laws


def removed_iron_laws(head_text: str, new_text: str) -> set[str]:
    """Iron Laws present in ``head_text`` but missing from ``new_text``.

    A non-empty result means the mutation eroded the protected section.
    """
    return iron_laws(head_text) - iron_laws(new_text)


def _git_head_version(path: str) -> str | None:
    """Return the HEAD (last kept) contents of ``path``, or None if untracked."""
    try:
        return subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return None  # New file not yet in HEAD — nothing to protect.


def check_file(path: str) -> set[str]:
    """Compare working-tree ``path`` against HEAD; return eroded Iron Laws."""
    head_text = _git_head_version(path)
    if head_text is None:
        return set()
    with open(path) as f:
        new_text = f.read()
    return removed_iron_laws(head_text, new_text)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: protected_sections.py <skill-file>", file=sys.stderr)
        return 2
    removed = check_file(argv[1])
    if removed:
        sample = sorted(removed)[:2]
        print(f"FAIL: protected Iron Law(s) deleted or reworded: {sample}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
