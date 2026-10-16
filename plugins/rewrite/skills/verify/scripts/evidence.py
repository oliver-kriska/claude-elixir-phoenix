#!/usr/bin/env python3
"""Evidence records for /rewrite:verify, written the same way on every run.

Run from the target root. Records live in .claude/rewrite/verify/SLICE/evidence/.

init SLICE --source DIR [--exclude REL ...]
    Start a run. Moves earlier files in the evidence directory to
    ../superseded/{ts}/ and writes run.json with the source path and the
    exclude list that every capture in this run uses.
run SLICE NAME [--cwd DIR] [--expect-exit N] [--timeout S] -- CMD ...
    Captures target (the current directory) and source identity, runs CMD
    without a shell, captures both again and writes {ts}-NAME.md and
    {ts}-NAME.log. `{uid}` in an argument becomes a value unique to this
    record. Values of secret-like NAME=value arguments are redacted in the
    record. Exits with CMD's status (124 timeout, 127 not found).
port start SLICE --release BIN [--ready-url URL] [--timeout S]
    Starts `BIN start` with RELEASE_DISTRIBUTION=none (no epmd outlives it) in
    a new process group, writes port.pid and port.json, and waits until the
    URL answers with any HTTP status.
port stop SLICE
    Stops only that process group: SIGTERM, then SIGKILL after 20 s. Never
    matches processes by name.
current SLICE
    Target and source identity now, for the auditors' CURRENT_IDENTITY.
status SLICE
    Each `- `NAME`` line of commands.md against its newest record: missing,
    incomplete (an identity capture failed), stale (identity moved during the
    command), outdated (the tree moved since), or the exit status against the
    expected one. Exit 1 when a name is missing or incomplete.

EV_PATH, when set, replaces PATH for the script and every command it runs.
A version-manager shim on python3 (mise, asdf, pyenv) rewrites PATH for its
child from that directory's tool config, so a command can resolve other
binaries than the caller's shell did; `ev` passes the shell's PATH this way.

Stdlib only. Identity comes from fingerprint.py beside this file. Exit 125
means the evidence itself could not be written or read.
"""

import argparse
import datetime
import importlib.util
import json
import os
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_ERROR = 125
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
LISTED_RE = re.compile(r"^\s*[-*]\s+`([A-Za-z0-9][A-Za-z0-9._-]*)`")
RECORD_RE = re.compile(r"^(\d{8}T\d{6}Z)(?:\.(\d+))?-(.+)\.md$")
SENSITIVE_RE = re.compile(r"^(DATABASE_URL|AWS_.*|.*(SECRET|TOKEN|KEY|PASSWORD|PASS|PWD|CREDENTIAL).*)$", re.I)
# The app-facing names a record lists; the rest of the inherited environment is the caller's, not the run's.
ENV_NAME_RE = re.compile(r"^(DATABASE_URL|MIX_ENV|PORT|PHX_HOST|PHX_SERVER|SECRET_KEY_BASE|RELEASE_.*)$")
EXUNIT_RE = re.compile(r"((?:\d+ doctests?, )?(?:\d+ propert(?:y|ies), )?\d+ tests?, \d+ failures?"
                       r"(?:, \d+ invalid)?(?:, \d+ excluded)?(?:, \d+ skipped)?)")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
STOP_GRACE = 20


class EvidenceError(Exception):
    pass


def load_fingerprint():
    spec = importlib.util.spec_from_file_location("rewrite_fingerprint", os.path.join(HERE, "fingerprint.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FP = load_fingerprint()


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp(t):
    return t.strftime("%Y%m%dT%H%M%SZ")


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def evidence_dir(slice_id):
    if not NAME_RE.match(slice_id):
        raise EvidenceError(f"bad slice id: {slice_id!r}")
    return os.path.join(".claude", "rewrite", "verify", slice_id, "evidence")


def read_run(ev):
    path = os.path.join(ev, "run.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise EvidenceError(f"no {path}: run `evidence.py init SLICE --source DIR` first") from None
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"cannot read {path}: {exc}") from None


def capture(directory, excludes):
    try:
        r = FP.identity(directory, excludes)
    except FP.IdentityError as exc:
        return None, f"capture failed: {exc}"
    return r, f"mode={r['mode']} head={r['head'] or 'none'} content_fingerprint={r['content_fingerprint']}"


def same(a, b):
    return a is not None and b is not None and all(a[k] == b[k] for k in ("mode", "head", "content_fingerprint"))


def redact(arg):
    name, sep, _ = arg.partition("=")
    if sep and SENSITIVE_RE.match(name.lstrip("-")):
        return f"{name}=<redacted>"
    return arg


def env_names(cmd):
    names = {k for k in os.environ if ENV_NAME_RE.match(k)}
    if cmd and os.path.basename(cmd[0]) == "env":
        names |= {a.partition("=")[0] for a in cmd[1:] if "=" in a and not a.startswith("-")}
    return ", ".join(sorted(names)) or "none"


def exunit_summary(log_path):
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            found = EXUNIT_RE.findall(ANSI_RE.sub("", fh.read()))
    except OSError:
        return "log unreadable"
    return found[-1] if found else "none in log"


def unique_paths(ev, name, t):
    base = stamp(t)
    for n in range(1, 1000):
        ts = base if n == 1 else f"{base}.{n}"
        md = os.path.join(ev, f"{ts}-{name}.md")
        if not os.path.exists(md):
            return ts, md, os.path.join(ev, f"{ts}-{name}.log")
    raise EvidenceError(f"too many records named {name} in one second")


def cmd_init(args):
    ev = evidence_dir(args.slice)
    if not os.path.isdir(args.source):
        raise EvidenceError(f"source is not a directory: {args.source}")
    old = read_port(ev) if os.path.isdir(ev) else None
    if old and not old.get("stopped_at") and alive(old["pid"]):
        raise EvidenceError(f"the last run's port is still up (pid {old['pid']}): `evidence.py port stop {args.slice}`")
    t = now()
    if os.path.isdir(ev) and os.listdir(ev):
        dest = os.path.join(os.path.dirname(ev), "superseded", stamp(t))
        os.makedirs(dest, exist_ok=True)
        for entry in sorted(os.listdir(ev)):
            shutil.move(os.path.join(ev, entry), os.path.join(dest, entry))
        print(f"moved earlier evidence to {dest}")
    os.makedirs(ev, exist_ok=True)
    run = {"started_at": iso(t), "source": os.path.realpath(args.source),
           "excludes": FP.normalize_excludes([*FP.DEFAULT_EXCLUDES, *args.exclude])}
    with open(os.path.join(ev, "run.json"), "w", encoding="utf-8") as fh:
        json.dump(run, fh, indent=2)
    print(f"run started {run['started_at']}: {ev}; write {ev}/commands.md next")
    return 0


def cmd_run(args):
    if not NAME_RE.match(args.name):
        raise EvidenceError(f"bad record name: {args.name!r} (letters, digits, . _ -)")
    cmd = args.cmd
    if not cmd:
        raise EvidenceError("put the command after --: `evidence.py run SLICE NAME [options] -- CMD ...`")
    ev = evidence_dir(args.slice)
    run = read_run(ev)
    excludes = run["excludes"]
    started = now()
    ts, md, log = unique_paths(ev, args.name, started)
    uid = f"{int(time.time())}{secrets.token_hex(3)}"
    cmd = [a.replace("{uid}", uid) for a in cmd]
    tb, tb_text = capture(".", excludes)
    sb, sb_text = capture(run["source"], excludes)
    try:
        with open(log, "wb") as out:
            try:
                status = subprocess.run(cmd, cwd=args.cwd, stdin=subprocess.DEVNULL, stdout=out,
                                        stderr=subprocess.STDOUT, timeout=args.timeout or None).returncode
            except FileNotFoundError as exc:
                out.write(f"evidence.py: {exc}\n".encode())
                status = 127
            except subprocess.TimeoutExpired:
                out.write(f"evidence.py: timed out after {args.timeout} s\n".encode())
                status = 124
    except OSError as exc:
        raise EvidenceError(f"cannot write {log}: {exc}") from None
    finished = now()
    ta, ta_text = capture(".", excludes)
    sa, sa_text = capture(run["source"], excludes)
    fresh = same(tb, ta) and same(sb, sa)
    lines = [
        f"# {ts}-{args.name}",
        "",
        f"- command: `{shlex.join(redact(a) for a in cmd)}`",
        f"- cwd: {os.path.abspath(args.cwd or '.')}",
        f"- exit_status: {status}",
        f"- expected_exit: {args.expect_exit}",
        f"- started_at: {iso(started)}",
        f"- finished_at: {iso(finished)}",
        f"- target_before: {tb_text}",
        f"- target_after: {ta_text}",
        f"- source_before: {sb_text}",
        f"- source_after: {sa_text}",
        f"- excludes: {', '.join(excludes)}",
        f"- identity: {'fresh' if fresh else 'stale'}",
        f"- env_names: {env_names(cmd)} (values never recorded)",
        f"- exunit: {exunit_summary(log)}",
        f"- log: {log}",
        "",
    ]
    try:
        with open(md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    except OSError as exc:
        raise EvidenceError(f"cannot write {md}: {exc}") from None
    verdict = "as expected" if status == args.expect_exit else f"expected {args.expect_exit}"
    print(f"{args.name}: exit {status} ({verdict}), identity {'fresh' if fresh else 'stale'}, record {md}")
    return status


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def command_of(pid):
    try:
        return subprocess.run(["ps", "-ww", "-o", "command=", "-p", str(pid)], capture_output=True, text=True).stdout
    except OSError:
        return ""


def ours(pid, release):
    # The release leads the process group it was started in, and its command line names the release root.
    try:
        if os.getpgid(pid) != pid:
            return False
    except ProcessLookupError:
        return False
    root = os.path.dirname(os.path.dirname(release))
    command = command_of(pid)
    return root in command or os.path.realpath(root) in command


def read_port(ev):
    path = os.path.join(ev, "port.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"cannot read {path}: {exc}") from None


def write_port(ev, port):
    with open(os.path.join(ev, "port.json"), "w", encoding="utf-8") as fh:
        json.dump(port, fh, indent=2)


def stop_group(pid):
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return "already gone"
    deadline = time.monotonic() + STOP_GRACE
    while time.monotonic() < deadline:
        if not alive(pid):
            return "stopped"
        time.sleep(0.25)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return "stopped"
    return f"killed after {STOP_GRACE} s"


def ready(url):
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def port_start(args):
    ev = evidence_dir(args.slice)
    read_run(ev)
    old = read_port(ev)
    if old and not old.get("stopped_at") and alive(old["pid"]):
        raise EvidenceError(f"a port from this run is still up (pid {old['pid']}): `evidence.py port stop {args.slice}`")
    release = os.path.abspath(args.release)
    if not os.access(release, os.X_OK):
        raise EvidenceError(f"not an executable release script: {args.release}")
    t = now()
    log = os.path.join(ev, f"{stamp(t)}-server.log")
    env = dict(os.environ, RELEASE_DISTRIBUTION="none")
    with open(log, "wb") as out:
        proc = subprocess.Popen([release, "start"], stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
    port = {"pid": proc.pid, "release": release, "started_at": iso(t), "log": log, "ready_url": args.ready_url}
    write_port(ev, port)
    with open(os.path.join(ev, "port.pid"), "w", encoding="utf-8") as fh:
        fh.write(f"{proc.pid}\n")
    begun = time.monotonic()
    while time.monotonic() - begun < args.timeout:
        code = proc.poll()
        if code is not None:
            port["stopped_at"] = iso(now())
            write_port(ev, port)
            print(f"port exited with {code} before it was ready; see {log}", file=sys.stderr)
            return 1
        if ready(args.ready_url) if args.ready_url else time.monotonic() - begun >= 2:
            print(f"port up: pid {proc.pid} (own process group, RELEASE_DISTRIBUTION=none), log {log}")
            return 0
        time.sleep(0.5)
    result = stop_group(proc.pid)
    port["stopped_at"] = iso(now())
    write_port(ev, port)
    print(f"port not ready after {args.timeout} s ({result}); see {log}", file=sys.stderr)
    return 1


def port_stop(args):
    ev = evidence_dir(args.slice)
    port = read_port(ev)
    if not port:
        raise EvidenceError(f"no port.json in {ev}: nothing this run started")
    pid = port["pid"]
    if port.get("stopped_at") or not alive(pid):
        result = "already stopped"
    elif not ours(pid, port["release"]):
        raise EvidenceError(f"pid {pid} is no longer the release this run started; stopped nothing, check it by hand")
    else:
        result = stop_group(pid)
    port["stopped_at"] = iso(now())
    write_port(ev, port)
    print(f"port pid {pid}: {result}")
    return 0


def current(run):
    _, target = capture(".", run["excludes"])
    _, source = capture(run["source"], run["excludes"])
    return target, source


def cmd_current(args):
    run = read_run(evidence_dir(args.slice))
    target, source = current(run)
    print(f"target {os.path.abspath('.')}: {target}")
    print(f"source {run['source']}: {source}")
    return 0


def fields(path):
    out = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            key, sep, value = line[2:].partition(": ") if line.startswith("- ") else ("", "", "")
            if sep:
                out[key] = value.strip()
    return out


def newest_records(ev):
    found = {}
    for entry in os.listdir(ev):
        m = RECORD_RE.match(entry)
        if m:
            key = (m.group(1), int(m.group(2) or 1))
            if m.group(3) not in found or key > found[m.group(3)][0]:
                found[m.group(3)] = (key, os.path.join(ev, entry))
    return {name: path for name, (_, path) in found.items()}


def cmd_status(args):
    ev = evidence_dir(args.slice)
    run = read_run(ev)
    listed_path = os.path.join(ev, "commands.md")
    try:
        with open(listed_path, encoding="utf-8") as fh:
            listed = list(dict.fromkeys(m.group(1) for m in map(LISTED_RE.match, fh) if m))
    except FileNotFoundError:
        print(f"missing {listed_path}: write the run list first", file=sys.stderr)
        return 1
    records = newest_records(ev)
    target_now, source_now = current(run)
    counts = {"missing": 0, "incomplete": 0, "stale": 0, "outdated": 0, "unexpected exit": 0}
    for name in listed:
        if name not in records:
            counts["missing"] += 1
            print(f"{name}: missing")
            continue
        f = fields(records[name])
        notes = []
        if any(f.get(k, "capture failed").startswith("capture failed") for k in
               ("target_before", "target_after", "source_before", "source_after")):
            notes.append("incomplete")
        elif f.get("identity") != "fresh":
            notes.append("stale")
        elif f.get("target_after") != target_now or f.get("source_after") != source_now:
            notes.append("outdated")
        if f.get("exit_status") != f.get("expected_exit", "0"):
            notes.append("unexpected exit")
        for n in notes:
            counts[n] += 1
        state = ", ".join(notes) or "fresh, current"
        print(f"{name}: exit {f.get('exit_status')} (expected {f.get('expected_exit', '0')}), {state} — "
              f"{os.path.basename(records[name])}")
    for name in sorted(set(records) - set(listed)):
        print(f"{name}: recorded but not in commands.md")
    print("; ".join(f"{k} {v}" for k, v in counts.items()) + f" of {len(listed)} listed")
    return 1 if counts["missing"] or counts["incomplete"] or not listed else 0


def main(argv=None):
    if os.environ.get("EV_PATH"):
        os.environ["PATH"] = os.environ.pop("EV_PATH")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init")
    p.add_argument("slice")
    p.add_argument("--source", required=True)
    p.add_argument("--exclude", action="append", default=[], metavar="REL")
    p = sub.add_parser("run")
    p.add_argument("slice")
    p.add_argument("name")
    p.add_argument("--cwd")
    p.add_argument("--expect-exit", type=int, default=0)
    p.add_argument("--timeout", type=int, default=0)
    p = sub.add_parser("port")
    p.add_argument("action", choices=["start", "stop"])
    p.add_argument("slice")
    p.add_argument("--release")
    p.add_argument("--ready-url")
    p.add_argument("--timeout", type=int, default=60)
    for name in ("current", "status"):
        sub.add_parser(name).add_argument("slice")
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = []
    if "--" in argv:
        cut = argv.index("--")
        argv, cmd = argv[:cut], argv[cut + 1:]
    args = ap.parse_args(argv)
    args.cmd = cmd
    try:
        if args.command == "init":
            return cmd_init(args)
        if args.command == "run":
            return cmd_run(args)
        if args.command == "port":
            if args.action == "start" and not args.release:
                ap.error("port start needs --release")
            return port_start(args) if args.action == "start" else port_stop(args)
        return cmd_current(args) if args.command == "current" else cmd_status(args)
    except EvidenceError as exc:
        print(f"evidence: {exc}", file=sys.stderr)
        return EVIDENCE_ERROR


if __name__ == "__main__":
    sys.exit(main())
