"""Iron Laws extraction.

Phase 0 source: parse the numbered list under "## Iron Laws Enforcement" in
the project root `CLAUDE.md`. Phase 2D switches the source to
`iron-laws/laws.yaml` (a single canonical YAML file); this module presents
the same `load_laws()` API to callers either way.
"""

from __future__ import annotations

import re

import yaml

from . import CLAUDE_MD, LAWS_YAML

_LAW_LINE_RE = re.compile(r"^\s*(\d+)\.\s+\*\*([^*]+)\*\*\s*-\s*(.+?)\s*$")
_SECTION_HEADER = "## Iron Laws Enforcement"
_TERMINATING_HEADER = "### Violation Response"


def _parse_claude_md(text: str) -> list[dict]:
    """Extract the 22-law numbered list out of CLAUDE.md.

    Returns a list of dicts: ``{"number": int, "title": str, "body": str}``.
    Subsection headers (`### LiveView Iron Laws`) are used to populate
    ``category`` on each law (best-effort, defaults to "general").
    """
    lines = text.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.startswith(_SECTION_HEADER)
        )
    except StopIteration:
        raise ValueError("CLAUDE.md missing '## Iron Laws Enforcement' section")

    try:
        end = next(
            i
            for i, line in enumerate(lines[start:], start=start)
            if line.startswith(_TERMINATING_HEADER)
        )
    except StopIteration:
        end = len(lines)

    laws: list[dict] = []
    current_category = "general"
    for line in lines[start:end]:
        if line.startswith("### "):
            current_category = (
                line.removeprefix("### ").removesuffix(" Iron Laws").strip().lower()
                or "general"
            )
            if "(continued)" in current_category:
                current_category = current_category.replace(" (continued)", "")
            continue

        match = _LAW_LINE_RE.match(line)
        if match:
            number, title, body = match.groups()
            laws.append(
                {
                    "number": int(number),
                    "category": current_category,
                    "title": title.strip(),
                    "body": body.strip(),
                }
            )

    if not laws:
        raise ValueError("Failed to parse any Iron Laws from CLAUDE.md")
    return laws


def _parse_yaml(text: str) -> list[dict]:
    data = yaml.safe_load(text) or {}
    if "laws" not in data:
        raise ValueError("iron-laws/laws.yaml missing top-level `laws:` key")
    return list(data["laws"])


def load_laws() -> list[dict]:
    """Load the canonical Iron Laws.

    Prefers `iron-laws/laws.yaml` when present (Phase 2D), falls back to
    parsing `CLAUDE.md` (Phase 0).
    """
    if LAWS_YAML.exists():
        return _parse_yaml(LAWS_YAML.read_text(encoding="utf-8"))
    return _parse_claude_md(CLAUDE_MD.read_text(encoding="utf-8"))


def render_bullets(laws: list[dict]) -> list[str]:
    """Format laws as `**TITLE** — body` bullet strings."""
    return [f"**{law['title']}** — {law['body']}" for law in laws]
