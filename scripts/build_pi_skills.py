#!/usr/bin/env python3
"""Build or drift-check the native Pi skills package."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from .build_codex_skills import _differences
from .port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from .port_lib import pi

OUTPUT_DIR = TARGETS_DIR / "pi"


def check() -> int:
    if not OUTPUT_DIR.exists():
        print(f"[pi-skills] missing generated target: {OUTPUT_DIR}", file=sys.stderr)
        return 1
    with tempfile.TemporaryDirectory(prefix="pi-skills-check-") as tmp:
        generated = Path(tmp) / "pi"
        pi.build(SOURCE_PLUGIN_DIR, generated)
        differences = _differences(generated, OUTPUT_DIR)
    if differences:
        print("[pi-skills] generated target has drift:", file=sys.stderr)
        for difference in differences:
            print(f"  - {difference}", file=sys.stderr)
        print("Run `make pi-skills` and commit the result.", file=sys.stderr)
        return 1
    print(f"[pi-skills] OK: {pi.validate(OUTPUT_DIR)} skills")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="scripts.build_pi_skills")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    result = pi.build(SOURCE_PLUGIN_DIR, OUTPUT_DIR)
    print(f"[pi-skills] built {result['skills']} skills in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
