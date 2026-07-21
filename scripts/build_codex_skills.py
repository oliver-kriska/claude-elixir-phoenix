#!/usr/bin/env python3
"""Build or drift-check the native Codex skills plugin."""

from __future__ import annotations

import argparse
import stat
import sys
import tempfile
from pathlib import Path

from .port_lib import SOURCE_PLUGIN_DIR, TARGETS_DIR
from .port_lib import codex

OUTPUT_DIR = TARGETS_DIR / "codex"


def _differences(expected: Path, actual: Path) -> list[str]:
    def entries(root: Path) -> dict[str, tuple[str, int, Path]]:
        result: dict[str, tuple[str, int, Path]] = {}
        for path in sorted(root.rglob("*")):
            mode = path.lstat().st_mode
            kind = (
                "symlink"
                if stat.S_ISLNK(mode)
                else "directory"
                if stat.S_ISDIR(mode)
                else "file"
                if stat.S_ISREG(mode)
                else "special"
            )
            result[path.relative_to(root).as_posix()] = (
                kind,
                stat.S_IMODE(mode),
                path,
            )
        return result

    expected_entries = entries(expected)
    actual_entries = entries(actual)
    differences: list[str] = []
    for relative in sorted(expected_entries.keys() | actual_entries.keys()):
        if relative not in actual_entries:
            differences.append(f"missing in target: {relative}")
            continue
        if relative not in expected_entries:
            differences.append(f"extra in target: {relative}")
            continue
        expected_kind, expected_mode, expected_path = expected_entries[relative]
        actual_kind, actual_mode, actual_path = actual_entries[relative]
        if expected_kind != actual_kind:
            differences.append(
                f"type differs: {relative} ({expected_kind} != {actual_kind})"
            )
        elif expected_kind == "file" and (
            expected_path.read_bytes() != actual_path.read_bytes()
        ):
            differences.append(f"differs: {relative}")
        elif expected_mode != actual_mode:
            differences.append(f"mode differs: {relative}")
    return differences


def check() -> int:
    if not OUTPUT_DIR.exists():
        print(f"[codex-skills] missing generated target: {OUTPUT_DIR}", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="codex-skills-check-") as tmp:
        generated = Path(tmp) / "codex"
        codex.build(SOURCE_PLUGIN_DIR, generated)
        differences = _differences(generated, OUTPUT_DIR)

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
