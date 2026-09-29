#!/usr/bin/env python3
"""Summarize a `claude plugin eval` trigger run beyond pass/fail.

Reads aggregate-result.json plus each run's trace.jsonl and reports what the
pass/fail table cannot: which skills were actually invoked, plugin load errors
(a disabled plugin scores like a routing miss), hook failures, run errors that
make a verdict unreliable, and stray fires of one skill on another's prompt.

Traces live in the sandbox dirs kept by --keep-temp; --archive copies them into
<results>/traces/ so the sandboxes can be deleted and the run re-analyzed later.

Usage:
    python3 -m lab.plugin_eval.analyze lab/plugin_eval/cases/results/<ts>
    python3 -m lab.plugin_eval.analyze <results> --archive --cleanup --min-recall 0.6

Exit codes: 0 ok, 1 a skill is below --min-recall, 2 plugin failed to load.
"""

import argparse
import json
import os
import re
import shutil
import stat
import sys
from collections import defaultdict

PLUGIN_NAMESPACES = re.compile(r"^(?:phx|ecto|lv):")
TURN_CAP_ERROR = "maximum number of turns"


def results_dir_of(path: str) -> str:
    return path if os.path.isdir(path) else os.path.dirname(path)


def load_aggregate(path: str) -> dict:
    with open(os.path.join(results_dir_of(path), "aggregate-result.json")) as f:
        return json.load(f)


def archived_trace_path(results_dir: str, case_name: str, index: int) -> str:
    return os.path.join(results_dir, "traces", f"{case_name}--{index}.jsonl")


def resolve_trace(results_dir: str, case_name: str, index: int, run: dict) -> str | None:
    archived = archived_trace_path(results_dir, case_name, index)
    if os.path.isfile(archived):
        return archived
    return run.get("tracePath")


def archive_traces(results_dir: str, data: dict) -> int:
    copied = 0
    for case in data.get("cases", []):
        for index, run in enumerate(case.get("arms", {}).get("with", [])):
            source = run.get("tracePath")
            if source and os.path.isfile(source):
                target = archived_trace_path(results_dir, case["name"], index)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copyfile(source, target)
                copied += 1
    return copied


def cleanup_sandboxes(data: dict) -> int:
    """Delete the sealed sandboxes --keep-temp left behind (archive traces first)."""
    removed = 0
    for case in data.get("cases", []):
        for arm in case.get("arms", {}).values():
            for run in arm:
                # tracePath is <tmp>/e-XXXX/out/trace.jsonl; only ever touch that e-XXXX root.
                root = os.path.dirname(os.path.dirname(run.get("tracePath") or ""))
                if not re.fullmatch(r".*/e-[A-Za-z0-9]+", root) or not os.path.isdir(root):
                    continue
                for base, dirs, _ in os.walk(root):
                    for name in dirs:
                        try:
                            os.chmod(os.path.join(base, name), stat.S_IRWXU)
                        except OSError:
                            pass
                os.chmod(root, stat.S_IRWXU)
                shutil.rmtree(root, ignore_errors=True)
                removed += 1
    return removed


def parse_trace(trace_path: str | None) -> dict:
    """Extract skills invoked, tools used, plugin load errors and hook failures."""
    info = {"readable": False, "plugin_errors": [], "skills_invoked": [], "tools": [], "hook_errors": []}
    if not trace_path or not os.path.isfile(trace_path):
        return info
    info["readable"] = True
    with open(trace_path) as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            etype, subtype = event.get("type"), event.get("subtype", "")
            if etype == "system" and subtype == "init":
                info["plugin_errors"] = event.get("plugin_errors") or []
                continue
            if etype == "system" and subtype == "hook_response":
                # exit 2 is a deliberate feedback channel for PostToolUse hooks
                if event.get("outcome") != "success" or event.get("exit_code") not in (0, 2) or event.get("stderr"):
                    stderr = (event.get("stderr") or "")[:240]
                    info["hook_errors"].append(f"{event.get('hook_name')}: exit={event.get('exit_code')} {stderr}")
                continue
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    info["tools"].append(block.get("name"))
                    if block.get("name") == "Skill":
                        info["skills_invoked"].append((block.get("input") or {}).get("skill", "?"))
    return info


def expected_skill(case: dict) -> tuple[str | None, bool]:
    """Return (skill, should_trigger) from the case's `tool_used: Skill` grader."""
    for grader in case.get("graders", []):
        config = grader.get("config") or grader
        if grader.get("type") != "tool_used" or config.get("tool") != "Skill":
            continue
        match = re.search(r"phx:([\w-]+)", config.get("input_match", ""))
        if match:
            return match.group(1), config.get("max") != 0
    return None, True


def summarize(data: dict, results_dir: str) -> dict:
    per_skill = defaultdict(lambda: {"pos": 0, "pos_hit": 0, "neg": 0, "neg_clean": 0, "misroutes": defaultdict(int)})
    summary = {"rows": [], "load_errors": [], "hook_errors": [], "run_errors": [], "unreadable": 0}

    for case in data.get("cases", []):
        skill, should = expected_skill(case)
        for index, run in enumerate(case.get("arms", {}).get("with", [])):
            info = parse_trace(resolve_trace(results_dir, case["name"], index, run))
            summary["unreadable"] += int(not info["readable"])
            invoked = [s.split(":", 1)[1] if PLUGIN_NAMESPACES.match(s) else f"builtin:{s}" for s in info["skills_invoked"]]
            if info["plugin_errors"]:
                summary["load_errors"].append((case["name"], info["plugin_errors"]))
            if info["hook_errors"]:
                summary["hook_errors"].append((case["name"], info["hook_errors"]))
            error = run.get("error") or ""
            # The turn cap is deliberate (routing is decided in the first turns);
            # rate limits, timeouts and auth failures make the verdict unreliable.
            if error and TURN_CAP_ERROR not in error:
                summary["run_errors"].append((case["name"], error))
            hit = skill in invoked if skill else None
            summary["rows"].append({
                "case": case["name"], "skill": skill, "should_trigger": should, "invoked": invoked,
                "hit": hit, "error": run.get("error"), "cost": run.get("costUsd"), "tools": info["tools"],
            })
            if not skill:
                continue
            stats = per_skill[skill]
            if should:
                stats["pos"] += 1
                stats["pos_hit"] += int(hit)
                if not hit:
                    stats["misroutes"][",".join(invoked) or "(none)"] += 1
            else:
                stats["neg"] += 1
                stats["neg_clean"] += int(not hit)

    stray, builtin = defaultdict(list), defaultdict(int)
    for row in summary["rows"]:
        for name in set(row["invoked"]):
            if name.startswith("builtin:"):
                builtin[name[8:]] += 1
            # A negative prompt belongs to some other skill, so only positive
            # prompts can tell us a skill fired where it does not belong.
            elif name != row["skill"] and row["should_trigger"]:
                stray[name].append(row["case"])
    summary["per_skill"] = {k: {**v, "misroutes": dict(v["misroutes"])} for k, v in per_skill.items()}
    summary["stray"] = dict(stray)
    summary["builtin"] = dict(builtin)
    return summary


def recall(stats: dict) -> float:
    return stats["pos_hit"] / stats["pos"] if stats["pos"] else 1.0


def print_report(data: dict, summary: dict, verbose: bool) -> None:
    rows = summary["rows"]
    print(f"runs: {len(rows)}  cost: ${data.get('costUsd', 0):.2f}  duration: {data.get('durationSeconds', 0):.0f}s  "
          f"unreadable traces: {summary['unreadable']}")
    if summary["load_errors"]:
        name, errors = summary["load_errors"][0]
        print(f"\nPLUGIN LOAD ERRORS in {len(summary['load_errors'])} run(s) — results are invalid. {name}: {json.dumps(errors)[:300]}")
    if summary["run_errors"]:
        print(f"\nRUN ERRORS (not the turn cap) in {len(summary['run_errors'])} run(s) — verdicts unreliable:")
        for name, err in summary["run_errors"][:10]:
            print(f"  {name}: {err[:200]}")
    if summary["hook_errors"]:
        print(f"\nHOOK ERRORS in {len(summary['hook_errors'])} run(s):")
        for name, errs in summary["hook_errors"][:5]:
            print(f"  {name}: {errs[0][:300]}")

    per_skill = summary["per_skill"]
    print("\nPER SKILL (recall = positive prompts that invoked it; neg = negative prompts that stayed clean)")
    print(f"{'skill':24} {'recall':>7} {'neg':>6}  misroutes on positive prompts")
    for skill in sorted(per_skill, key=lambda s: (recall(per_skill[s]), s)):
        st = per_skill[skill]
        rec = f"{st['pos_hit']}/{st['pos']}" if st["pos"] else "-"
        neg = f"{st['neg_clean']}/{st['neg']}" if st["neg"] else "-"
        mis = "; ".join(f"{k}×{v}" for k, v in sorted(st["misroutes"].items(), key=lambda kv: -kv[1]))
        print(f"{skill:24} {rec:>7} {neg:>6}  {mis}")

    if summary["stray"]:
        print("\nSTRAY FIRES (skill invoked on another skill's prompt — not always wrong, check overlap)")
        for name, cases in sorted(summary["stray"].items(), key=lambda kv: -len(kv[1])):
            print(f"  {name:22} {len(cases):3}  {', '.join(cases[:6])}")
    if summary["builtin"]:
        print("\nBUILT-IN SKILLS INVOKED: " + ", ".join(f"{k}×{v}" for k, v in sorted(summary["builtin"].items(), key=lambda kv: -kv[1])))

    failures = [r for r in rows if r["hit"] is not None and r["hit"] != r["should_trigger"]]
    shown = rows if verbose else failures
    if shown:
        print(f"\n{'CASES' if verbose else 'FAILED CASES'} ({len(shown)})")
        for r in shown:
            want = "should" if r["should_trigger"] else "should NOT"
            print(f"  {r['case']}: {want} fire {r['skill']}; invoked={r['invoked'] or '-'} tools={r['tools'][:5]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", help="results dir or its aggregate-result.json")
    parser.add_argument("--archive", action="store_true", help="copy traces into <results>/traces/")
    parser.add_argument("--cleanup", action="store_true", help="after archiving, delete the kept sandboxes")
    parser.add_argument("--min-recall", type=float, help="exit 1 if any skill's positive recall is below this")
    parser.add_argument("--json", dest="json_out", help="write the summary as JSON")
    parser.add_argument("--verbose", action="store_true", help="list every case, not just failures")
    args = parser.parse_args()

    results_dir = results_dir_of(args.results)
    data = load_aggregate(args.results)
    if args.archive:
        print(f"archived {archive_traces(results_dir, data)} trace(s) to {os.path.join(results_dir, 'traces')}")
    if args.cleanup:
        if not args.archive:
            parser.error("--cleanup deletes the only copy of each trace; pass --archive too")
        print(f"removed {cleanup_sandboxes(data)} sandbox dir(s)")
    summary = summarize(data, results_dir)
    print_report(data, summary, args.verbose)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(summary, f, indent=2)

    if summary["load_errors"]:
        return 2
    if args.min_recall is not None:
        below = sorted(s for s, st in summary["per_skill"].items() if st["pos"] and recall(st) < args.min_recall)
        if below:
            print(f"\nFAIL: recall below {args.min_recall:.0%}: {', '.join(below)}")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
