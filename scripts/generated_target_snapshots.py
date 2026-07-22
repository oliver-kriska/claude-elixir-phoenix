#!/usr/bin/env python3
"""Update or verify golden byte-and-mode digests for generated runtime targets."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from pathlib import Path

from .port_lib import REPO_ROOT, TARGETS_DIR

TARGET_NAMES = ("amp", "codex", "pi", "opencode")
SNAPSHOT_FILE = REPO_ROOT / "scripts" / "generated_target_snapshots.json"
FORMAT_VERSION = 1


def snapshot_tree(root: Path) -> dict[str, int | str]:
    """Hash relative paths, kinds, file bytes, and executable mode bits."""
    try:
        root_mode = root.lstat().st_mode
    except FileNotFoundError as error:
        raise ValueError(f"{root}: generated target does not exist") from error
    if stat.S_ISLNK(root_mode) or not stat.S_ISDIR(root_mode):
        raise ValueError(f"{root}: generated target must be a real directory")

    digest = hashlib.sha256()
    entries = 0
    files = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f"{path}: generated symlinks are not supported")
        if stat.S_ISDIR(mode):
            kind = "directory"
            executable = 0
            payload = b""
        elif stat.S_ISREG(mode):
            kind = "file"
            executable = int(bool(mode & stat.S_IXUSR))
            payload = path.read_bytes()
            files += 1
        else:
            raise ValueError(f"{path}: generated special files are not supported")
        record = json.dumps(
            [relative, kind, executable, hashlib.sha256(payload).hexdigest()],
            separators=(",", ":"),
            ensure_ascii=True,
        )
        digest.update(record.encode("utf-8") + b"\n")
        entries += 1
    if files == 0:
        raise ValueError(f"{root}: generated target contains no files")
    return {"sha256": digest.hexdigest(), "entries": entries, "files": files}


def current_snapshots() -> dict:
    return {
        "format": FORMAT_VERSION,
        "targets": {name: snapshot_tree(TARGETS_DIR / name) for name in TARGET_NAMES},
    }


def update() -> None:
    SNAPSHOT_FILE.write_text(
        json.dumps(current_snapshots(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"[generated-snapshots] updated {SNAPSHOT_FILE}")


def check() -> int:
    try:
        expected = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"[generated-snapshots] invalid snapshot: {error}", file=sys.stderr)
        return 1
    try:
        actual = current_snapshots()
    except (OSError, ValueError) as error:
        print(
            f"[generated-snapshots] invalid generated target: {error}", file=sys.stderr
        )
        return 1
    if expected == actual:
        print("[generated-snapshots] OK: Amp, Codex, Pi, OpenCode")
        return 0
    for name in TARGET_NAMES:
        if expected.get("targets", {}).get(name) != actual["targets"][name]:
            print(
                f"[generated-snapshots] {name} digest changed; regenerate the target, "
                "review its diff, then update snapshots",
                file=sys.stderr,
            )
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="scripts.generated_target_snapshots")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    update()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
