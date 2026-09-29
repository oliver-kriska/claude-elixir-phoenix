#!/usr/bin/env python3
"""Summarize a `claude plugin eval` output-quality run (lab/plugin_eval/quality/).

The CLI table shows one score per case. This adds what decides whether a case
measures the plugin at all: each grader's pass rate in the with-plugin and
no-plugin arms. A grader that passes both arms equally is not measuring the
plugin, however high the case score is.

It also reports what makes a verdict unreliable: plugin load errors (a disabled
plugin scores like the baseline), run errors (rate limits, timeouts, turn cap),
and permission denials. `.claude/` is a protected directory in eval runs, so
plan and review artifacts written there are denied even with Write granted.

Usage:
    python3 -m lab.plugin_eval.quality lab/plugin_eval/quality/results/<ts>
    python3 -m lab.plugin_eval.quality <results> --archive --cleanup --json <results>/summary.json

Exit codes: 0 ok, 2 plugin failed to load in a with-plugin run.
"""

import argparse
import json
import os
import shutil
import sys

from lab.plugin_eval.analyze import cleanup_sandboxes, load_aggregate, results_dir_of

ARMS = ("with", "without")


def archived_trace_path(results_dir: str, case_name: str, arm: str, index: int) -> str:
    return os.path.join(results_dir, "traces", f"{case_name}--{arm}--{index}.jsonl")


def resolve_trace(results_dir: str, case_name: str, arm: str, index: int, run: dict) -> str | None:
    archived = archived_trace_path(results_dir, case_name, arm, index)
    return archived if os.path.isfile(archived) else run.get("tracePath")


def archive_traces(results_dir: str, data: dict) -> int:
    copied = 0
    for case in data.get("cases", []):
        for arm in ARMS:
            for index, run in enumerate(case.get("arms", {}).get(arm, [])):
                source = run.get("tracePath")
                if source and os.path.isfile(source):
                    target = archived_trace_path(results_dir, case["name"], arm, index)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    shutil.copyfile(source, target)
                    copied += 1
    return copied


def parse_trace(trace_path: str | None) -> dict:
    """Plugins loaded, plugin load errors, and denied tool calls (with the path they targeted)."""
    info = {"readable": False, "plugins": [], "plugin_errors": [], "denied": []}
    if not trace_path or not os.path.isfile(trace_path):
        return info
    info["readable"] = True
    inputs = {}
    with open(trace_path) as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "system" and event.get("subtype") == "init":
                info["plugins"] = [p.get("name") for p in event.get("plugins") or []]
                info["plugin_errors"] = event.get("plugin_errors") or []
            elif event.get("type") == "system" and event.get("subtype") == "permission_denied":
                target = inputs.get(event.get("tool_use_id"), {})
                detail = target.get("file_path") or target.get("command") or ""
                info["denied"].append(f"{event.get('tool_name')} {detail}".strip())
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    inputs[block.get("id")] = block.get("input") or {}
    return info


def run_cost(run: dict) -> float:
    return (run.get("costUsd") or 0) + (run.get("judgeCostUsd") or 0)


def verdict(with_rate: float | None, without_rate: float | None) -> str:
    """How a grader behaves across arms: does it measure what the plugin adds?"""
    if with_rate is None:
        return "not scored"
    if without_rate is None:
        return "with-only"
    if with_rate > without_rate:
        return "plugin +"
    if with_rate < without_rate:
        return "plugin -"
    if with_rate == 1:
        return "both pass"
    if with_rate == 0:
        return "both fail"
    return "tie"


def summarize(data: dict, results_dir: str) -> dict:
    summary = {"cases": [], "load_errors": [], "run_errors": [], "denied": [], "unreadable": 0}
    for case in data.get("cases", []):
        arms = case.get("arms", {})
        aggregates = case.get("aggregates") or {}
        graders = {}
        row = {
            "case": case["name"],
            "with": aggregates.get("score"),
            "without": aggregates.get("scoreWithout"),
            "delta": aggregates.get("delta"),
            "runs": {arm: len(arms.get(arm, [])) for arm in ARMS},
            "cost": round(sum(run_cost(r) for arm in ARMS for r in arms.get(arm, [])), 4),
            "graders": graders,
        }
        for arm in ARMS:
            for index, run in enumerate(arms.get(arm, [])):
                info = parse_trace(resolve_trace(results_dir, case["name"], arm, index, run))
                summary["unreadable"] += int(not info["readable"])
                if arm == "with" and info["readable"] and (info["plugin_errors"] or "phx" not in info["plugins"]):
                    summary["load_errors"].append((case["name"], info["plugin_errors"] or "phx not loaded"))
                if run.get("error"):
                    summary["run_errors"].append((case["name"], arm, run["error"]))
                for denied in info["denied"]:
                    summary["denied"].append((case["name"], arm, denied))
                for result in run.get("graders", []):
                    stats = graders.setdefault(result["name"], {"with": [0, 0], "without": [0, 0], "scored": True})
                    stats["scored"] = stats["scored"] and result.get("scored", True)
                    stats[arm][0] += int(bool(result.get("passed")))
                    stats[arm][1] += 1
        for name, stats in graders.items():
            rates = {arm: (stats[arm][0] / stats[arm][1] if stats[arm][1] else None) for arm in ARMS}
            stats["verdict"] = verdict(rates["with"], rates["without"]) if stats["scored"] else "indicator"
        summary["cases"].append(row)
    return summary


def fmt(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "-"
    return f"{value:+.2f}" if signed else f"{value:.2f}"


def print_report(data: dict, summary: dict) -> None:
    print(f"cost: ${data.get('costUsd', 0):.2f}  duration: {data.get('durationSeconds', 0):.0f}s  "
          f"unreadable traces: {summary['unreadable']}")
    if summary["load_errors"]:
        name, errors = summary["load_errors"][0]
        print(f"\nPLUGIN LOAD ERRORS in {len(summary['load_errors'])} run(s) — with-arm scores are invalid. "
              f"{name}: {json.dumps(errors)[:300]}")
    if summary["run_errors"]:
        print(f"\nRUN ERRORS in {len(summary['run_errors'])} run(s) — graded on partial output:")
        for name, arm, err in summary["run_errors"][:10]:
            print(f"  {name} [{arm}]: {err[:200]}")
    if summary["denied"]:
        print(f"\nPERMISSION DENIALS ({len(summary['denied'])}):")
        for name, arm, denied in summary["denied"][:12]:
            print(f"  {name} [{arm}]: {denied[:160]}")

    print(f"\n{'CASE':26} {'WITH':>5} {'W/OUT':>6} {'Δ':>6} {'RUNS':>5} {'COST':>7}")
    for row in summary["cases"]:
        runs = f"{row['runs']['with']}+{row['runs']['without']}"
        print(f"{row['case']:26} {fmt(row['with']):>5} {fmt(row['without']):>6} {fmt(row['delta'], True):>6} "
              f"{runs:>5} ${row['cost']:>6.2f}")
    deltas = [row["delta"] for row in summary["cases"] if row["delta"] is not None]
    if deltas:
        print(f"{'mean':26} {'':>5} {'':>6} {sum(deltas) / len(deltas):>+6.2f}")

    print("\nGRADERS (passed/runs per arm; 'plugin +' = discriminates in the plugin's favour)")
    for row in summary["cases"]:
        print(f"  {row['case']}")
        for name, stats in sorted(row["graders"].items()):
            w, wo = stats["with"], stats["without"]
            without = f"{wo[0]}/{wo[1]}" if wo[1] else "-"
            print(f"    {name:30} {w[0]}/{w[1]:<3} {without:>5}  {stats['verdict']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", help="results dir or its aggregate-result.json")
    parser.add_argument("--archive", action="store_true", help="copy both arms' traces into <results>/traces/")
    parser.add_argument("--cleanup", action="store_true", help="after archiving, delete the kept sandboxes")
    parser.add_argument("--json", dest="json_out", help="write the summary as JSON")
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
    print_report(data, summary)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(summary, f, indent=2)
    return 2 if summary["load_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
