from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ENTRIES = {"SKILL.md", "references", "scripts", "priv"}


def test_canonical_skills_ship_only_runtime_content() -> None:
    # Claude Code installs a skill folder as-is and every generated target copies
    # it verbatim, so anything else here lands on users' machines.
    unexpected = sorted(
        entry.relative_to(ROOT).as_posix()
        for skill in ROOT.glob("plugins/*/skills/*")
        if skill.is_dir()
        for entry in skill.iterdir()
        if entry.name not in RUNTIME_ENTRIES and entry.name != ".DS_Store"
    )
    assert not unexpected, (
        "skill folders may only contain SKILL.md, references/, scripts/ and priv/; "
        f"move test harnesses and fixtures under lab/: {unexpected}"
    )
