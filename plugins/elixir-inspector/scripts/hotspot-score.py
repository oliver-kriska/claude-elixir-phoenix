#!/usr/bin/env python3
"""Compute composite hotspot risk scores for an Elixir/Phoenix project.

Implements the Tornhill-style composite hotspot algorithm combining four
signals — change frequency, complexity proxy, bug ratio, and trend — into
a single normalised risk score per file.

Usage:
    python hotspot-score.py /path/to/repo
    python hotspot-score.py /path/to/repo --since "3 months ago"
    python hotspot-score.py /path/to/repo --top-n 50 --output hotspots.json
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directories and patterns to skip (generated/vendor/build artefacts)
SKIP_PATTERNS = (
    "vendor/",
    "deps/",
    "_build/",
    "priv/static/assets/",
    ".elixir_ls/",
    "node_modules/",
)

# File extensions to analyse
ELIXIR_EXTENSIONS = (".ex", ".exs", ".heex", ".eex", ".sface")

# Commit-message patterns that signal a bug fix
FIX_RE = re.compile(
    r"\b(fix|bug|patch|error|hotfix|revert|broken|crash)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run_git(args, cwd):
    """Run a git command and return stdout. Raises on failure."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        print("Error: git is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(f"Error: git command timed out: {' '.join(cmd)}", file=sys.stderr)
        sys.exit(1)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr and "not a git repository" in stderr.lower():
            print(f"Error: {cwd} is not a git repository.", file=sys.stderr)
            sys.exit(1)
        if stderr and result.returncode != 0:
            return ""
    return result.stdout


def is_git_repo(path):
    """Check whether *path* is inside a git work tree."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# File filtering
# ---------------------------------------------------------------------------

def should_skip(filepath):
    """Return True if *filepath* should be excluded from analysis."""
    for pattern in SKIP_PATTERNS:
        if filepath.startswith(pattern) or f"/{pattern}" in filepath:
            return True
    return False


def is_elixir_file(filepath):
    """Return True if *filepath* has an Elixir-family extension."""
    return filepath.endswith(ELIXIR_EXTENSIONS)


# ---------------------------------------------------------------------------
# Component A: Change Frequency (log-normalised, 0-1)
# ---------------------------------------------------------------------------

def compute_change_frequency(file_commit_count):
    """Normalise file change counts to 0-1 via log scaling.

    A file changed in 100 commits shouldn't score 5x a file changed 20 times;
    the relationship is logarithmic.  Formula: log(1+count) / log(1+max_count).
    """
    if not file_commit_count:
        return {}

    max_count = max(file_commit_count.values())
    if max_count == 0:
        return {f: 0.0 for f in file_commit_count}

    log_max = math.log(1 + max_count)
    return {
        f: round(math.log(1 + count) / log_max, 3)
        for f, count in file_commit_count.items()
    }


# ---------------------------------------------------------------------------
# Component B: Complexity Proxy (0-1)
# ---------------------------------------------------------------------------

def compute_complexity_proxy(repo_path, files):
    """Estimate complexity from line count + max indentation depth.

    True cyclomatic complexity requires AST parsing (expensive). This proxy
    correlates strongly with real complexity for Elixir:
      complexity = 0.6 * normalised_lines + 0.4 * normalised_max_depth

    Weight rationale: deep nesting is disproportionately risky, but raw size
    still drives maintenance burden.
    """
    metrics = {}

    for filepath in files:
        full_path = os.path.join(repo_path, filepath)
        if not os.path.isfile(full_path):
            continue

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except (OSError, IOError):
            continue

        line_count = len(lines)
        max_indent = 0
        non_empty = 0

        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            non_empty += 1
            indent = len(line) - len(stripped)
            # Convert to indent levels (2-space Elixir convention)
            indent_level = indent // 2
            max_indent = max(max_indent, indent_level)

        metrics[filepath] = {
            "lines": line_count,
            "max_indent_level": max_indent,
        }

    if not metrics:
        return {}

    # Normalise each sub-component to 0-1 (log for lines, linear for depth)
    max_lines = max(m["lines"] for m in metrics.values()) or 1
    max_depth = max(m["max_indent_level"] for m in metrics.values()) or 1

    scores = {}
    for filepath, m in metrics.items():
        line_score = math.log(1 + m["lines"]) / math.log(1 + max_lines)
        depth_score = m["max_indent_level"] / max_depth
        scores[filepath] = round(0.6 * line_score + 0.4 * depth_score, 3)

    return scores


# ---------------------------------------------------------------------------
# Component C: Bug Ratio (0-1)
# ---------------------------------------------------------------------------

def compute_bug_ratio(repo_path, since, file_commit_count):
    """For each file, fraction of its changes that are bug fixes.

    A file changed 20 times with 15 fixes has bug_ratio=0.75.  Detection:
    commit message contains fix/bug/patch/error/hotfix/revert/broken/crash.
    """
    raw = run_git(
        [
            "log",
            f"--since={since}",
            "--pretty=format:__COMMIT__%H|||%s",
            "--name-only",
            "--no-merges",
        ],
        repo_path,
    )

    file_fix_count = defaultdict(int)
    # Also track which fix commits touch each file (for example_fix_commits)
    file_fix_commits = defaultdict(list)
    current_is_fix = False
    current_msg = ""
    current_sha = ""

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("__COMMIT__"):
            payload = line[len("__COMMIT__"):]
            parts = payload.split("|||", 1)
            current_sha = parts[0] if parts else ""
            current_msg = parts[1] if len(parts) > 1 else ""
            current_is_fix = bool(FIX_RE.search(current_msg))
        elif current_is_fix and is_elixir_file(line) and not should_skip(line):
            file_fix_count[line] += 1
            file_fix_commits[line].append({
                "sha": current_sha[:8],
                "message": current_msg[:120],
            })

    bug_ratios = {}
    for filepath, total in file_commit_count.items():
        if total == 0:
            continue
        fixes = file_fix_count.get(filepath, 0)
        bug_ratios[filepath] = round(fixes / total, 3)

    return bug_ratios, dict(file_fix_commits)


# ---------------------------------------------------------------------------
# Component D: Trend Multiplier (0.5-2.0)
# ---------------------------------------------------------------------------

def compute_trend_multiplier(repo_path, since):
    """Determine whether a file is worsening or improving.

    Split the time range in half and compare change counts between the recent
    and older halves.

    Multipliers:
      > 2x recent  → 2.0 (worsening fast)
      1.5-2x       → 1.5 (worsening)
      0.7-1.5x     → 1.0 (stable)
      0.3-0.7x     → 0.7 (improving)
      < 0.3x       → 0.5 (improving fast)
    """
    raw = run_git(
        [
            "log",
            f"--since={since}",
            "--pretty=format:__COMMIT__%H|||%aI",
            "--name-only",
            "--no-merges",
        ],
        repo_path,
    )

    file_dates = defaultdict(list)
    current_date = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("__COMMIT__"):
            date_str = line.split("|||", 1)[1] if "|||" in line else ""
            try:
                current_date = datetime.fromisoformat(date_str.strip())
            except (ValueError, TypeError):
                current_date = None
        elif current_date and is_elixir_file(line) and not should_skip(line):
            file_dates[line].append(current_date)

    multipliers = {}
    for filepath, dates in file_dates.items():
        if len(dates) < 2:
            multipliers[filepath] = 1.0
            continue

        sorted_dates = sorted(dates)
        midpoint = sorted_dates[0] + (sorted_dates[-1] - sorted_dates[0]) / 2

        recent = sum(1 for d in sorted_dates if d > midpoint)
        older = len(sorted_dates) - recent

        if older == 0:
            ratio = 3.0  # All changes are recent
        else:
            ratio = recent / older

        if ratio > 2.0:
            multipliers[filepath] = 2.0
        elif ratio > 1.5:
            multipliers[filepath] = 1.5
        elif ratio > 0.7:
            multipliers[filepath] = 1.0
        elif ratio > 0.3:
            multipliers[filepath] = 0.7
        else:
            multipliers[filepath] = 0.5

    return multipliers


# ---------------------------------------------------------------------------
# Trend label helper
# ---------------------------------------------------------------------------

def trend_label(multiplier):
    """Map a numeric trend multiplier to a human-readable label."""
    if multiplier > 1.0:
        return "worsening"
    elif multiplier < 1.0:
        return "improving"
    return "stable"


# ---------------------------------------------------------------------------
# Min-max normalisation helper
# ---------------------------------------------------------------------------

def min_max_normalise(scores):
    """Normalise a dict of {key: float} to 0-1 via min-max scaling."""
    if not scores:
        return {}
    vals = scores.values()
    lo = min(vals)
    hi = max(vals)
    spread = hi - lo
    if spread == 0:
        return {k: 0.5 for k in scores}
    return {k: round((v - lo) / spread, 3) for k, v in scores.items()}


# ---------------------------------------------------------------------------
# Composite Hotspot Score
# ---------------------------------------------------------------------------

ALPHA = 0.5  # weight for complexity in the Tornhill formula
BETA = 0.5   # weight for churn (change frequency) in the Tornhill formula


def compute_hotspot_scores(repo_path, since, top_n=30):
    """Compute composite risk scores for all Elixir files.

    Tornhill-style composite:
        risk_score = normalize(freq) * (alpha * normalize(complexity)
                     + beta * normalize(churn)) * (1 + bug_ratio)
                     * trend_multiplier

    The (1 + bug_ratio) term makes bug history an amplifier — a file with
    zero bug fixes still carries risk from its complexity and churn.  Final
    scores are normalised to 0-1 where 1.0 = highest risk.
    """

    # -- Step 1: Collect file → commit count -----------------------------------
    raw = run_git(
        ["log", f"--since={since}", "--format=", "--name-only", "--no-merges"],
        repo_path,
    )

    file_commit_count = defaultdict(int)
    for line in raw.splitlines():
        line = line.strip()
        if line and is_elixir_file(line) and not should_skip(line):
            file_commit_count[line] += 1

    if not file_commit_count:
        return {"total_files_analyzed": 0, "hotspots": []}

    fcc = dict(file_commit_count)

    # -- Step 2: Compute each component ----------------------------------------
    freq_scores = compute_change_frequency(fcc)
    complexity_scores = compute_complexity_proxy(repo_path, fcc.keys())
    bug_ratios, fix_commits_map = compute_bug_ratio(repo_path, since, fcc)
    trend_multipliers = compute_trend_multiplier(repo_path, since)

    # -- Step 3: Normalise components to 0-1 (min-max) -------------------------
    norm_freq = min_max_normalise(freq_scores)
    norm_complexity = min_max_normalise(complexity_scores)

    # -- Step 4: Composite score -----------------------------------------------
    raw_scores = {}
    for filepath in fcc:
        freq = norm_freq.get(filepath, 0)
        complexity = norm_complexity.get(filepath, 0.5)  # mid-range default
        bug = bug_ratios.get(filepath, 0)
        trend = trend_multipliers.get(filepath, 1.0)

        # Tornhill composite: freq * (alpha*complexity + beta*churn) * (1+bug) * trend
        # Here churn IS freq (change frequency serves double duty as the churn metric)
        raw_score = freq * (ALPHA * complexity + BETA * freq) * (1 + bug) * trend
        raw_scores[filepath] = raw_score

    # -- Step 5: Normalise final scores to 0-1 ---------------------------------
    max_score = max(raw_scores.values()) if raw_scores else 1
    if max_score == 0:
        max_score = 1

    results = []
    for filepath, raw_score in raw_scores.items():
        normalised = round(raw_score / max_score, 3)
        trend_mult = trend_multipliers.get(filepath, 1.0)

        # Pick up to 3 example fix commits for this file
        example_fixes = fix_commits_map.get(filepath, [])[:3]

        results.append({
            "file": filepath,
            "risk_score": normalised,
            "change_frequency": freq_scores.get(filepath, 0),
            "complexity": complexity_scores.get(filepath, 0),
            "bug_ratio": bug_ratios.get(filepath, 0),
            "trend": trend_mult,
            "trend_label": trend_label(trend_mult),
            "change_count": fcc[filepath],
            "example_fix_commits": example_fixes[:3],
        })

    results.sort(key=lambda x: x["risk_score"], reverse=True)

    return {
        "total_files_analyzed": len(fcc),
        "hotspots": results[:top_n],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compute composite hotspot risk scores for an Elixir/Phoenix project."
    )
    parser.add_argument(
        "repo_path",
        help="Path to the git repository to analyse.",
    )
    parser.add_argument(
        "--since",
        default="6 months ago",
        help='How far back to analyse (default: "6 months ago").',
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Number of top hotspots to return (default: 30).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON to this file instead of stdout.",
    )
    args = parser.parse_args()

    repo_path = os.path.abspath(args.repo_path)

    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a directory.", file=sys.stderr)
        sys.exit(1)

    if not is_git_repo(repo_path):
        print(f"Error: {repo_path} is not a git repository.", file=sys.stderr)
        sys.exit(1)

    scores = compute_hotspot_scores(repo_path, args.since, args.top_n)

    result = {
        "repo": repo_path,
        "since": args.since,
        "top_n": args.top_n,
        **scores,
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        output_dir = os.path.dirname(os.path.abspath(args.output))
        if output_dir and not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json + "\n")
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
