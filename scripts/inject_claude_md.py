#!/usr/bin/env python3
"""Regenerate the Iron Laws section in CLAUDE.md from `iron-laws/laws.yaml`.

CLAUDE.md is the canonical Claude Code project instructions file. The Iron
Laws subsection is now generated from the YAML source — edit `iron-laws/laws.yaml`,
then run `make port` (which calls this script) to regenerate the section.

Markers in CLAUDE.md delimit the regenerated block:

    <!-- IRON-LAWS-BEGIN -->
    ...
    <!-- IRON-LAWS-END -->

If markers are missing, the script exits non-zero with a clear error.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
LAWS_YAML = REPO_ROOT / "iron-laws" / "laws.yaml"

BEGIN_MARKER = "<!-- IRON-LAWS-BEGIN -->"
END_MARKER = "<!-- IRON-LAWS-END -->"


# Pretty category headers in render order. Categories not listed here come
# after, in the order they first appear.
CATEGORY_HEADERS = {
    "liveview": "LiveView Iron Laws",
    "ecto": "Ecto Iron Laws",
    "oban": "Oban Iron Laws",
    "security": "Security Iron Laws",
    "otp": "OTP Iron Laws",
    "elixir": "Elixir Iron Laws",
    "verification": "Verification Iron Laws",
}
CATEGORY_ORDER = list(CATEGORY_HEADERS.keys())


def _category_sort_key(law: dict) -> tuple[int, int]:
    cat = law.get("category", "general")
    if cat in CATEGORY_ORDER:
        return (CATEGORY_ORDER.index(cat), law["number"])
    return (len(CATEGORY_ORDER), law["number"])


def _render_section(laws: list[dict]) -> str:
    """Render the laws as a markdown subsection of '## Iron Laws Enforcement'.

    Output starts immediately after BEGIN_MARKER and ends just before END_MARKER.
    Subsections are grouped by category in canonical order; laws stay numbered.
    """
    sorted_laws = sorted(laws, key=_category_sort_key)
    lines: list[str] = []

    current_category: str | None = None
    for law in sorted_laws:
        cat = law.get("category", "general")
        if cat != current_category:
            header = CATEGORY_HEADERS.get(cat, cat.title() + " Iron Laws")
            if lines:
                lines.append("")
            lines.append(f"### {header}")
            lines.append("")
            current_category = cat
        title = law["title"].strip()
        body = law["body"].strip()
        lines.append(f"{law['number']}. **{title}** - {body}")

    return "\n".join(lines)


def render_expected(laws: list[dict] | None = None) -> str:
    """Return what CLAUDE.md SHOULD look like given the YAML.

    Pure: doesn't read or write `CLAUDE.md`. Used by `port.py --check` to
    detect `laws.yaml` ↔ `CLAUDE.md` drift without mutating the working tree.
    """
    if laws is None:
        data = yaml.safe_load(LAWS_YAML.read_text(encoding="utf-8")) or {}
        laws = data.get("laws") or []

    text = CLAUDE_MD.read_text(encoding="utf-8")
    if BEGIN_MARKER not in text or END_MARKER not in text:
        raise RuntimeError(
            f"CLAUDE.md missing markers {BEGIN_MARKER!r} / {END_MARKER!r}"
        )

    rendered = _render_section(laws)
    pre, _, rest = text.partition(BEGIN_MARKER)
    _, _, post = rest.partition(END_MARKER)
    return pre + BEGIN_MARKER + "\n\n" + rendered + "\n\n" + END_MARKER + post


def is_up_to_date() -> bool:
    """True iff `CLAUDE.md`'s Iron Laws section matches the YAML."""
    return CLAUDE_MD.read_text(encoding="utf-8") == render_expected()


def main(check_only: bool = False) -> int:
    try:
        new_text = render_expected()
    except RuntimeError as exc:
        print(f"[inject-claude-md] {exc}", file=sys.stderr)
        return 1

    current = CLAUDE_MD.read_text(encoding="utf-8")
    if new_text == current:
        if not check_only:
            print("[inject-claude-md] CLAUDE.md already up to date.")
        return 0

    if check_only:
        print(
            "[inject-claude-md] CLAUDE.md is OUT OF DATE relative to iron-laws/laws.yaml.\n"
            "  Run `make port` and commit the result.",
            file=sys.stderr,
        )
        return 1

    CLAUDE_MD.write_text(new_text, encoding="utf-8")
    print("[inject-claude-md] regenerated Iron Laws section")
    return 0


if __name__ == "__main__":
    sys.exit(main(check_only="--check" in sys.argv[1:]))
