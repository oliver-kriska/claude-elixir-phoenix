#!/usr/bin/env python3
"""Build or drift-check the Amp Agent Skills projection."""

from __future__ import annotations

import argparse
import filecmp
import sys
import tempfile
from pathlib import Path

from .port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from .port_lib import amp

OUTPUT_DIR = TARGETS_DIR / "amp" / "skills"


def _differences(expected: Path, actual: Path) -> list[str]:
    differences: list[str] = []
    comparison = filecmp.dircmp(expected, actual)

    def walk(current: filecmp.dircmp, prefix: str = "") -> None:
        differences.extend(
            f"missing in target: {prefix}{name}" for name in current.left_only
        )
        differences.extend(
            f"extra in target: {prefix}{name}" for name in current.right_only
        )
        for name in current.common_files:
            left = Path(current.left) / name
            right = Path(current.right) / name
            if not filecmp.cmp(left, right, shallow=False):
                differences.append(f"differs: {prefix}{name}")
        for name, child in current.subdirs.items():
            walk(child, f"{prefix}{name}/")

    walk(comparison)
    return differences


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
