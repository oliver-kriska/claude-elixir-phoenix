#!/usr/bin/env python3
"""Content identity of a directory, for rewrite verification evidence.

In a git work tree the identity is HEAD plus the bytes of every dirty file:
tracked files changed in the work tree or the index (`git ls-files -m`,
`git diff-index --cached --name-only HEAD`) and untracked files that are not
ignored (`git ls-files -o --exclude-standard`). Each submodule's work tree is hashed as plain files
(everything but `.git`, ignored files included), so edits inside it count
without running git under the submodule's config. Outside git, when DIR
itself is ignored, or when the index is stored split (`sharedindex.*`; git
bumps its mtime on every read), every file under DIR is hashed instead and
the output names the fallback. Each file is read in full,
in chunks, whatever its size. Git runs with hooks, fsmonitor and filter
drivers disabled, so a capture never executes a program the checkout names.

Paths are relative to DIR. An exclude is a DIR-relative path prefix and adds
to the defaults (verification output and build trees). Two captures taken
with the same excludes are equal only when HEAD and the content of every
counted file are equal.

Only paths and digests are printed, never file contents or environment
values. Stdlib only; reads files, never writes them. Exit 2 means the
identity could not be established, including when tracked files carry
assume-unchanged or skip-worktree flags (git hides their edits); the flags are
reported, never cleared.

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
SPLIT_INDEX = "split-index"


class IdentityError(Exception):
    pass


# Config a checkout can carry that makes read-only git commands run programs:
# an fsmonitor hook, any hook, signature checks (gpg.program) and the transport
# a partial clone uses to fetch missing objects (core.sshCommand, helpers).
GIT_SAFE_CONFIG = ("core.fsmonitor=false", f"core.hooksPath={os.devnull}", "log.showSignature=false",
                   "protocol.allow=never")


def git(directory, *args, options=()):
    # Inherited GIT_* variables can point git at another repository (GIT_DIR,
    # GIT_COMMON_DIR, GIT_INDEX_FILE, ...) or inject config. Optional locks off:
    # read commands must not refresh the index of a legacy checkout.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") or k == "GIT_CEILING_DIRECTORIES"}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", FINGERPRINT_GIT_EMPTY="")
    cmd = ["git", *(arg for item in GIT_SAFE_CONFIG for arg in ("-c", item)), *options, "-C", directory, *args]
    try:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, env=env, check=False)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def split_index(directory):
    """True when the index is stored split (`sharedindex.*` beside it).

    Every git command that reads a split index bumps the shared file's mtime,
    whatever the locks or config, so the index must not be read at all.
    Leftover shared files from an earlier split also count: a false positive
    only costs the whole-tree fallback. rev-parse reads no index.
    """
    out = git(directory, "rev-parse", "--git-dir", "--git-common-dir")
    for gitdir in os.fsdecode(out or b"").splitlines():
        try:
            names = os.listdir(os.path.join(directory, gitdir))
        except OSError:
            continue
        if any(name.startswith("sharedindex.") for name in names):
            return True
    return False


def blank_filters(directory):
    """Global options that disable every configured filter driver.

    Commands that compare the work tree (`ls-files -m`, `diff HEAD`) re-hash
    stat-dirty and racily clean files through clean/process filters, which run
    whatever command the config names. `-c` splits at the first "=", so a
    driver name containing one needs --config-env (git 2.31+).
    """
    names = set()
    for entry in (git(directory, "config", "-z", "--get-regexp", r"^filter\.") or b"").split(b"\0"):
        key = os.fsdecode(entry.split(b"\n", 1)[0])
        names.add(key[len("filter."):key.rfind(".")])
    options = []
    for name in sorted(n for n in names if n):
        for var in ("clean", "process", "required"):
            key = f"filter.{name}.{var}"
            options += [f"--config-env={key}=FINGERPRINT_GIT_EMPTY"] if "=" in name else ["-c", f"{key}="]
    return options


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


def check_index_flags(root, excludes):
    # Git skips assume-unchanged and skip-worktree files when listing changes,
    # so an edit to one would leave the identity unchanged. In `ls-files -v`
    # those show as a lowercase tag (assume-unchanged) or `S` (skip-worktree).
    tagged = git(root, "ls-files", "-v", "-z")
    if tagged is None:
        raise IdentityError(f"git could not list index flags in {root}")
    flagged = []
    for entry in tagged.split(b"\0"):
        tag, rel = entry[:1], os.fsdecode(entry[2:])
        if (tag.islower() or tag == b"S") and not excluded(rel, excludes):
            flagged.append(rel)
    if flagged:
        shown = ", ".join(flagged[:5]) + (", ..." if len(flagged) > 5 else "")
        raise IdentityError(
            f"{len(flagged)} tracked file(s) carry an assume-unchanged or skip-worktree "
            f"flag, so edits to them are invisible to git: {shown}. Clear the flags "
            "with `git update-index --no-assume-unchanged --no-skip-worktree <path>`"
            " or exclude the paths with --exclude."
        )


def git_identity(root, excludes):
    inside = git(root, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.strip() != b"true":
        return None
    if split_index(root):
        return SPLIT_INDEX
    if git(root, "check-ignore", "-q", ".") is not None:
        return None
    check_index_flags(root, excludes)
    head_out = git(root, "rev-parse", "--verify", "-q", "HEAD")
    head = head_out.decode().strip() if head_out else None
    options = blank_filters(root)
    listed = git(root, "ls-files", "-z", "-m", "-o", "--exclude-standard", options=options)
    if head:
        # Index against HEAD only; `ls-files -m` covers the work tree. Porcelain
        # `git diff` rewrites the index when it refreshes stat data, even with
        # optional locks off, and runs git inside dirty submodules.
        changed = git(root, "diff-index", "--cached", "--name-only", "--relative", "--no-renames", "-z", "HEAD")
    else:
        # Unborn HEAD: every tracked file is new content.
        changed = git(root, "ls-files", "-z", "-c")
    staged = git(root, "ls-files", "-z", "-s")
    if listed is None or changed is None or staged is None:
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
    # Git compares a submodule by commit only, so edits inside its work tree
    # would be invisible: hash those files directly instead of asking git.
    gitlinks = {os.fsdecode(e.partition(b"\t")[2]) for e in staged.split(b"\0") if e.startswith(b"160000 ")}
    submodules, tree_files = [], {}
    for rel in sorted(gitlinks):
        full = os.path.join(root, rel)
        if excluded(rel, excludes) or not os.path.isdir(full) or os.path.islink(full):
            continue
        submodules.append(rel)
        if rel not in paths:
            walk(root, rel, excludes, tree_files)
    return head, files, submodules, tree_files


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
    fallback = found if found == SPLIT_INDEX else None
    if found and not fallback:
        mode, (head, dirty, submodules, tree_files) = "git", found
        files = {**dirty, **tree_files}
    else:
        mode, head, dirty, submodules, files = "tree", None, None, None, {}
        walk(root, "", excludes, files)
    return {
        "path": root,
        "mode": mode,
        "fallback": fallback,
        "head": head,
        "dirty_files": sorted(dirty) if mode == "git" else None,
        "submodules": submodules,
        "file_count": len(files),
        "excludes": excludes,
        "content_fingerprint": fingerprint(mode, head, excludes, files),
    }


def format_text(r):
    counted = [f"files: {r['file_count']}"]
    if r["mode"] == "git":
        counted = [f"dirty_files: {len(r['dirty_files'])}"]
        if r["submodules"]:
            counted.append(f"submodules: {', '.join(r['submodules'])} (work trees hashed as plain files)")
    return "\n".join([
        f"path: {r['path']}",
        f"mode: {r['mode']}" + (f" ({r['fallback']} fallback: git index not read)" if r["fallback"] else ""),
        f"head: {r['head'] or 'none'}",
        *counted,
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
