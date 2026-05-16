#!/usr/bin/env python3
"""Mirror publish driver.

Subtree-splits a target directory and force-pushes it to the per-target
mirror repo. Used at release-tag time by `.github/workflows/publish-mirrors.yml`.

Usage:
    python3 -m scripts.publish --target pi
    python3 -m scripts.publish --target opencode
    python3 -m scripts.publish --target pi --dry-run
    python3 -m scripts.publish --target pi --remote https://github.com/oliver-kriska/pi-elixir-phoenix.git

Codex is *not* a mirror target: Codex installs directly from the source repo
via `codex plugin marketplace add <owner/repo> --ref <ref>` (the repo-root
`.agents/plugins/marketplace.json` points it at the `targets/codex` subtree).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .port_lib import REPO_ROOT

MIRROR_REMOTES = {
    "pi": "https://github.com/oliver-kriska/pi-elixir-phoenix.git",
    "opencode": "https://github.com/oliver-kriska/opencode-elixir-phoenix.git",
}


def _run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}", file=sys.stderr)
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def _subtree_split(target: str) -> str:
    """Run `git subtree split --prefix=targets/<target>` and return the SHA."""
    result = _run(["git", "subtree", "split", f"--prefix=targets/{target}", "HEAD"], cwd=REPO_ROOT)
    sha = result.stdout.strip()
    if not sha:
        raise RuntimeError(f"git subtree split produced empty SHA for {target}")
    return sha


def _publish(target: str, remote: str, branch: str, dry_run: bool) -> int:
    target_dir = REPO_ROOT / "targets" / target
    if not target_dir.exists():
        print(f"[publish] missing {target_dir}", file=sys.stderr)
        return 1

    sha = _subtree_split(target)
    print(f"[publish] {target}: split SHA = {sha}", file=sys.stderr)

    push_cmd = ["git", "push", "--force", remote, f"{sha}:refs/heads/{branch}"]
    if dry_run:
        push_cmd.insert(2, "--dry-run")

    _run(push_cmd, cwd=REPO_ROOT)
    print(f"[publish] {target}: pushed to {remote} ({branch})", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="scripts.publish")
    parser.add_argument(
        "--target",
        choices=list(MIRROR_REMOTES.keys()),
        required=True,
        help="Mirror target. `codex` is not a mirror target.",
    )
    parser.add_argument(
        "--remote",
        help="Override default mirror remote URL (useful for testing).",
    )
    parser.add_argument("--branch", default="main", help="Mirror branch to push to.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    remote = args.remote or MIRROR_REMOTES[args.target]
    return _publish(args.target, remote, args.branch, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
