#!/usr/bin/env python3
"""Build or drift-check the native Codex skills plugin."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from .port_lib import codex
from .port_lib.generated_tree import tree_differences

OUTPUT_DIR = TARGETS_DIR / "codex"

def check() -> int:
    if not OUTPUT_DIR.exists():
        print(f"[codex-skills] missing generated target: {OUTPUT_DIR}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="codex-skills-check-") as tmp:
        generated = Path(tmp) / "codex"
        codex.build(SOURCE_PLUGIN_DIR, generated)
        differences = tree_differences(generated, OUTPUT_DIR)

    if differences:
        print("[codex-skills] generated target has drift:", file=sys.stderr)
        for difference in differences:
            print(f"  - {difference}", file=sys.stderr)
        print("Run `make codex-skills` and commit the result.", file=sys.stderr)
        return 1

    print(f"[codex-skills] OK: {codex.validate(OUTPUT_DIR)} skills")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="scripts.build_codex_skills")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Generate temporarily and fail if targets/codex has drift.",
    )
    args = parser.parse_args()
    if args.check:
        return check()

    result = codex.build(SOURCE_PLUGIN_DIR, OUTPUT_DIR)
    print(f"[codex-skills] built {result['skills']} skills in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
