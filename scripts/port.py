#!/usr/bin/env python3
"""Multi-target port driver.

Generates `targets/<agent>/` directories from `plugins/elixir-phoenix/`.

Usage:
    python3 -m scripts.port                       # build all targets
    python3 -m scripts.port --target codex        # build single target
    python3 -m scripts.port --check               # build to a temp dir,
                                                  # diff vs committed targets/,
                                                  # exit 1 on drift
"""

from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
import tempfile
from pathlib import Path

from .port_lib import SOURCE_PLUGIN_DIR as SOURCE_DIR
from .port_lib import TARGETS_DIR, codex, opencode, pi

BUILDERS = {
    "codex": codex.build,
    "pi": pi.build,
    "opencode": opencode.build,
}

CODEX_DESC_BUDGET = 8000  # bytes; spec ceiling 8192, we leave 192-byte margin


def _build_one(target: str, out_dir: Path) -> dict:
    builder = BUILDERS[target]
    return builder(SOURCE_DIR, out_dir)


def _build_all(base_out: Path) -> dict:
    results = {}
    for target in BUILDERS:
        out_dir = base_out / target
        results[target] = _build_one(target, out_dir)
    return results


_DIFF_IGNORE = {".gitkeep", ".DS_Store"}


def _diff_dirs(a: Path, b: Path) -> list[str]:
    """Recursively compare two directories. Return list of differing paths."""
    differences: list[str] = []
    cmp = filecmp.dircmp(a, b, ignore=list(_DIFF_IGNORE))

    def _walk(c: filecmp.dircmp, prefix: str = "") -> None:
        for name in c.left_only:
            differences.append(f"missing in target: {prefix}{name}")
        for name in c.right_only:
            differences.append(f"extra in target: {prefix}{name}")
        for name in c.diff_files:
            differences.append(f"differs: {prefix}{name}")
        # dircmp classifies same_files via a shallow (size+mtime) compare, which
        # can mask a content change when stat signatures happen to match. Re-verify
        # by content so the drift gate is byte-accurate.
        for name in c.same_files:
            if not filecmp.cmp(Path(c.left) / name, Path(c.right) / name, shallow=False):
                differences.append(f"differs: {prefix}{name}")
        for sub_name, sub_cmp in c.subdirs.items():
            _walk(sub_cmp, prefix + sub_name + "/")

    _walk(cmp)
    return differences


def _smoke_validate(target: str, target_dir: Path) -> list[str]:
    """Content checks the drift diff can't catch — vital for non-committed
    Pi/OpenCode targets, which only get a "build succeeded" check otherwise.

    Catches the bug class where output is structurally wrong but the build
    didn't raise: malformed generated frontmatter, or a hook module that
    references runtime files the builder never shipped.
    """
    from .port_lib.frontmatter import parse

    problems: list[str] = []

    # 1. Every generated markdown that declares frontmatter must parse.
    for md in sorted(target_dir.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        try:
            parse(text, source=str(md))
        except Exception as exc:
            rel = md.relative_to(target_dir)
            problems.append(f"{target}: unparseable frontmatter {rel} — {exc}")

    # 2. OpenCode server.ts must only reference scripts that were shipped, and
    #    must not depend on a runtime iron-laws/laws.yaml read (not present in
    #    the release mirror — laws are baked into the module instead).
    server_ts = target_dir / "server.ts"
    if server_ts.exists():
        src = server_ts.read_text(encoding="utf-8")
        for name in sorted(set(re.findall(r"hooks/scripts/([A-Za-z0-9._-]+\.sh)", src))):
            if not (target_dir / "hooks" / "scripts" / name).is_file():
                problems.append(
                    f"{target}: server.ts spawns hooks/scripts/{name} but it was not shipped"
                )
        if "laws.yaml" in src and "readFile" in src:
            problems.append(
                f"{target}: server.ts reads iron-laws/laws.yaml at runtime — bake it instead"
            )
    return problems


# User-managed sidecar files (not generated): preserved by builders and
# seeded into temp dirs during drift check so the temp build sees the same
# overrides as the committed tree.
_USER_CONFIG_FILES = {
    "codex": ["descriptions_short.yaml"],
    "pi": [],
    "opencode": [],
}

# Targets whose generated tree is committed to this repo and must match
# `port.py` output exactly. Codex installs sparsely from `targets/codex/`
# in this repo, so it MUST stay in sync. Pi and OpenCode are generated at
# release time and force-pushed to dedicated mirror repos — they get a
# build-only smoke test instead of a drift check.
_COMMITTED_TARGETS = {"codex"}


def _check_drift(targets_to_check: list[str]) -> int:
    """Build to temp dir, diff against committed `targets/`, exit 1 on drift.

    For non-committed targets (Pi, OpenCode), this only verifies the build
    succeeds without raising — drift can't be measured against a
    non-checked-in tree.

    Also verifies that `CLAUDE.md`'s Iron Laws section is in sync with
    `iron-laws/laws.yaml`. Read-only: does not mutate the working tree.
    """
    from . import inject_claude_md as _icmd

    rc = 0
    if _icmd.main(check_only=True) != 0:
        rc = 1

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        any_drift = bool(rc)
        for target in targets_to_check:
            tmp_target = tmp_path / target
            tmp_target.mkdir(parents=True, exist_ok=True)
            committed = TARGETS_DIR / target

            for sidecar in _USER_CONFIG_FILES.get(target, []):
                src = committed / sidecar
                if src.exists():
                    shutil.copyfile(src, tmp_target / sidecar)

            try:
                _build_one(target, tmp_target)
            except Exception as exc:
                print(
                    f"[port-validate] {target}: BUILD FAILED — {exc}",
                    file=sys.stderr,
                )
                any_drift = True
                continue

            # Content smoke check for every target (drift diff only covers
            # committed targets; this is the only guard Pi/OpenCode get).
            smoke = _smoke_validate(target, tmp_target)
            if smoke:
                any_drift = True
                print(f"[port-validate] SMOKE FAILURES in {target}/:", file=sys.stderr)
                for problem in smoke:
                    print(f"  - {problem}", file=sys.stderr)

            if target not in _COMMITTED_TARGETS:
                status = "build OK" if not smoke else "build FAILED smoke"
                print(f"[port-validate] {target}: {status} (not drift-checked — mirrored at release)")
                continue

            if not committed.exists():
                print(f"[port-validate] target dir missing: {committed}", file=sys.stderr)
                any_drift = True
                continue

            differences = _diff_dirs(tmp_target, committed)
            if differences:
                any_drift = True
                print(f"[port-validate] DRIFT in {target}/:", file=sys.stderr)
                for diff in differences:
                    print(f"  - {diff}", file=sys.stderr)
            else:
                print(f"[port-validate] {target}: OK")

        if any_drift:
            print(
                "\n[port-validate] FAIL — run `make port` and commit the result.",
                file=sys.stderr,
            )
            return 1
    return 0


def _enforce_codex_budget(result: dict) -> int:
    desc_bytes = result.get("description_bytes", 0)
    if desc_bytes > CODEX_DESC_BUDGET:
        print(
            f"[codex] DESCRIPTION BUDGET EXCEEDED: {desc_bytes} > {CODEX_DESC_BUDGET} bytes",
            file=sys.stderr,
        )
        print(
            "[codex] Trim skill descriptions or add `descriptions_short.yaml` mapping.",
            file=sys.stderr,
        )
        return 1
    print(f"[codex] description budget: {desc_bytes}/{CODEX_DESC_BUDGET} bytes ✓")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="scripts.port")
    parser.add_argument(
        "--target",
        choices=list(BUILDERS.keys()),
        action="append",
        help="Target to build (repeatable). Default: all.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build to temp dir; diff vs committed targets/; fail on drift.",
    )
    args = parser.parse_args()

    targets = args.target or list(BUILDERS.keys())

    if args.check:
        return _check_drift(targets)

    rc = 0

    # Regenerate CLAUDE.md's Iron Laws subsection from `iron-laws/laws.yaml`
    # FIRST, so target builds copy the updated CLAUDE.md into their AGENTS.md.
    # Idempotent: prints "already up to date" if no change.
    try:
        from . import inject_claude_md  # type: ignore[attr-defined]

        rc |= inject_claude_md.main()
    except Exception as exc:  # pragma: no cover — regen is best-effort
        print(f"[port] inject-claude-md skipped: {exc}", file=sys.stderr)

    for target in targets:
        out_dir = TARGETS_DIR / target
        out_dir.mkdir(parents=True, exist_ok=True)
        result = _build_one(target, out_dir)
        print(f"[{target}] built: {result}")
        if target == "codex":
            rc |= _enforce_codex_budget(result)

    return rc


if __name__ == "__main__":
    sys.exit(main())
