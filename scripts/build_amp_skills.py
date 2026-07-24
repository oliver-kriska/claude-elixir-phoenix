#!/usr/bin/env python3
"""Build or drift-check the Amp Agent Skills projection."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from .port_lib import amp
from .port_lib.generated_tree import tree_differences

OUTPUT_DIR = TARGETS_DIR / "amp" / "skills"


def _differences(expected: Path, actual: Path) -> list[str]:
    return tree_differences(expected, actual)


def check() -> int:
    if not OUTPUT_DIR.exists():
        print(f"[amp-skills] missing generated target: {OUTPUT_DIR}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="amp-skills-check-") as tmp:
        generated = Path(tmp) / "skills"
        amp.build(SOURCE_PLUGIN_DIR, generated)
        differences = _differences(generated, OUTPUT_DIR)

    if differences:
        print("[amp-skills] generated target has drift:", file=sys.stderr)
        for difference in differences:
            print(f"  - {difference}", file=sys.stderr)
        print("Run `make amp-skills` and commit the result.", file=sys.stderr)
        return 1

    print(f"[amp-skills] OK: {amp.validate(OUTPUT_DIR)} skills")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="scripts.build_amp_skills")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Generate in a temporary directory and fail if targets/amp has drift.",
    )
    args = parser.parse_args()

    if args.check:
        return check()

    result = amp.build(SOURCE_PLUGIN_DIR, OUTPUT_DIR)
    print(f"[amp-skills] built {result['skills']} skills in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
