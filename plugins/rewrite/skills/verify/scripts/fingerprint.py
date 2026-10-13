#!/usr/bin/env python3
"""Content identity of a directory, for rewrite verification evidence.

In a git work tree the identity is HEAD plus the bytes of every dirty file:
tracked files changed since HEAD (`git ls-files -m`, `git diff --name-only
HEAD`) and untracked files that are not ignored (`git ls-files -o
--exclude-standard`). Outside git, or when DIR itself is ignored, every file
under DIR is hashed. Each file is read in full, in chunks, whatever its size.

Paths are relative to DIR. An exclude is a DIR-relative path prefix and adds
to the defaults (verification output and build trees). Two captures taken
with the same excludes are equal only when HEAD and the content of every
counted file are equal.

Only paths and digests are printed, never file contents or environment
values. Stdlib only; reads files, never writes them. Exit 2 means the
identity could not be established.

Usage:
    python3 fingerprint.py DIR [--exclude REL ...] [--json]
"""

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys

DEFAULT_EXCLUDES = (".claude/rewrite/verify/", "_build/", "deps/", "node_modules/")
CHUNK = 1 << 20


class IdentityError(Exception):
    pass


def git(directory, *args):
    # No optional locks: read commands must not refresh the index of a legacy
    # checkout. Inherited repository overrides would point git at another tree.
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    try:
        proc = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", directory, *args],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, check=False,
        )
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def normalize_excludes(raw):
    out = set()
    for item in raw:
        rel = item.replace(os.sep, "/")
        while rel.startswith("./"):
            rel = rel[2:]
        rel = rel.rstrip("/")
        if not rel or item.startswith("/") or ".." in rel.split("/"):
            raise IdentityError(f"exclude must be a path inside DIR: {item}")
        out.add(rel)
    return sorted(out)


def excluded(rel, excludes):
    return any(rel == e or rel.startswith(e + "/") for e in excludes)


def file_digest(path):
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return "deleted"
    except OSError as exc:
        raise IdentityError(f"cannot stat {path}: {exc.strerror}") from None
    if stat.S_ISLNK(st.st_mode):
        return "symlink:" + hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
    if not stat.S_ISREG(st.st_mode):
        return f"special:{stat.S_IFMT(st.st_mode):o}"
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        return "deleted"
    except OSError as exc:
        raise IdentityError(f"cannot read {path}: {exc.strerror}") from None
    h = hashlib.sha256()
    with os.fdopen(fd, "rb") as fh:
        st = os.fstat(fh.fileno())
        if not stat.S_ISREG(st.st_mode):
            return f"special:{stat.S_IFMT(st.st_mode):o}"
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    mode = "x" if st.st_mode & 0o111 else "-"
    return f"file:{mode}:{h.hexdigest()}"


def walk(root, start, excludes, files):
    stack = [start]
    while stack:
        rel = stack.pop()
        try:
            with os.scandir(os.path.join(root, rel) if rel else root) as it:
                entries = list(it)
        except OSError as exc:
            raise IdentityError(f"cannot list {rel or root}: {exc.strerror}") from None
        for entry in entries:
            child = f"{rel}/{entry.name}" if rel else entry.name
            if entry.name == ".git" or excluded(child, excludes):
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append(child)
            else:
                files[child] = file_digest(entry.path)


def git_identity(root, excludes):
    inside = git(root, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.strip() != b"true":
        return None
    if git(root, "check-ignore", "-q", ".") is not None:
        return None
    head_out = git(root, "rev-parse", "--verify", "-q", "HEAD")
    head = head_out.decode().strip() if head_out else None
    listed = git(root, "ls-files", "-z", "-m", "-o", "--exclude-standard")
    if head:
        changed = git(root, "diff", "--name-only", "--relative", "--no-renames",
                      "--ignore-submodules=none", "-z", "HEAD")
    else:
        # Unborn HEAD: every tracked file is new content.
        changed = git(root, "ls-files", "-z", "-c")
    if listed is None or changed is None:
        raise IdentityError(f"git could not list changes in {root}")
    paths = {os.fsdecode(p).rstrip("/") for p in (listed + b"\0" + changed).split(b"\0") if p}
    files = {}
    for rel in sorted(paths):
        if excluded(rel, excludes):
            continue
        full = os.path.join(root, rel)
        if os.path.isdir(full) and not os.path.islink(full):
            walk(root, rel, excludes, files)
        else:
            files[rel] = file_digest(full)
    return head, files


def fingerprint(mode, head, excludes, files):
    h = hashlib.sha256()
    h.update(json.dumps([mode, head, excludes]).encode() + b"\n")
    for rel in sorted(files):
        h.update(os.fsencode(rel) + b"\0" + files[rel].encode() + b"\0")
    return h.hexdigest()


def identity(directory, extra_excludes=()):
    excludes = normalize_excludes([*DEFAULT_EXCLUDES, *extra_excludes])
    root = os.path.realpath(directory)
    if not os.path.isdir(root):
        raise IdentityError(f"not a directory: {directory}")
    found = git_identity(root, excludes)
    if found:
        mode, (head, files) = "git", found
    else:
        mode, head, files = "tree", None, {}
        walk(root, "", excludes, files)
    return {
        "path": root,
        "mode": mode,
        "head": head,
        "dirty_files": sorted(files) if mode == "git" else None,
        "file_count": len(files),
        "excludes": excludes,
        "content_fingerprint": fingerprint(mode, head, excludes, files),
    }


def format_text(r):
    counted = f"dirty_files: {r['file_count']}" if r["mode"] == "git" else f"files: {r['file_count']}"
    return "\n".join([
        f"path: {r['path']}",
        f"mode: {r['mode']}",
        f"head: {r['head'] or 'none'}",
        counted,
        "excludes: " + ", ".join(r["excludes"]),
        f"content_fingerprint: {r['content_fingerprint']}",
    ])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dir")
    ap.add_argument("--exclude", action="append", default=[], metavar="REL",
                    help="DIR-relative path prefix to leave out (repeatable, adds to the defaults)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        result = identity(args.dir, args.exclude)
    except IdentityError as exc:
        print(f"fingerprint: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else format_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
