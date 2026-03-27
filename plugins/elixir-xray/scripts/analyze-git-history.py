#!/usr/bin/env python3
"""Analyze git commit history for recurring patterns.

Extracts fix patterns, hotspot files, commit conventions, and fix chains
from a git repository. Outputs deterministic JSON for downstream agent
interpretation.

Usage:
    python analyze-git-history.py /path/to/repo
    python analyze-git-history.py /path/to/repo --since "3 months ago"
    python analyze-git-history.py /path/to/repo --output results.json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime


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
        # Some git commands legitimately return empty — only fatal on real errors
        stderr = result.stderr.strip()
        if stderr and "not a git repository" in stderr.lower():
            print(f"Error: {cwd} is not a git repository.", file=sys.stderr)
            sys.exit(1)
        if stderr and result.returncode != 0:
            # Return empty string for non-fatal errors (e.g. no commits in range)
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
# Commit log parsing
# ---------------------------------------------------------------------------

FIELD_SEP = "|||"
LOG_FORMAT = FIELD_SEP.join(["%H", "%h", "%s", "%ai", "%an"])


def parse_commits(repo_path, since):
    """Return list of dicts from `git log`."""
    raw = run_git(
        ["log", f"--since={since}", f"--format={LOG_FORMAT}", "--no-merges"],
        repo_path,
    )
    commits = []
    for line in raw.strip().splitlines():
        if not line:
            continue
        parts = line.split(FIELD_SEP)
        if len(parts) < 5:
            continue
        commits.append({
            "sha": parts[0],
            "short_sha": parts[1],
            "message": parts[2],
            "date": parts[3],
            "author": parts[4],
        })
    return commits


# ---------------------------------------------------------------------------
# Fix pattern extraction
# ---------------------------------------------------------------------------

def extract_fix_patterns(commits, max_sample_messages=5):
    """Group commits containing 'fix' by the keyword following it.

    Uses simple word frequency: the first meaningful word after 'fix' (or
    'fixes', 'fixed') becomes the keyword cluster.
    """
    STOP_WORDS = {
        "a", "an", "the", "for", "in", "of", "to", "and", "on", "up",
        "is", "it", "by", "at", "or", "so", "if", "be", "as", "no",
        "not", "with", "from", "that", "this", "into", "some", "all",
        "bug", "issue", "error", "typo", "broken", "missing",
    }
    fix_re = re.compile(r"\bfix(?:es|ed|ing)?\b", re.IGNORECASE)

    keyword_commits = defaultdict(list)  # keyword -> [commit dict, ...]

    for commit in commits:
        msg = commit["message"]
        match = fix_re.search(msg)
        if not match:
            continue

        # Words after the fix token
        after = msg[match.end():].strip().lower()
        # Strip common prefix punctuation (e.g. "fix: gettext")
        after = re.sub(r"^[:\-\s]+", "", after)
        words = re.findall(r"[a-z_][a-z0-9_]*", after)

        keyword = None
        for w in words:
            if w not in STOP_WORDS and len(w) > 2:
                keyword = w
                break
        if keyword is None:
            keyword = "_general"

        keyword_commits[keyword].append(commit)

    results = []
    for kw, kw_commits in sorted(keyword_commits.items(), key=lambda x: -len(x[1])):
        shas = [c["short_sha"] for c in kw_commits]
        sample = [c["message"] for c in kw_commits[:max_sample_messages]]
        results.append({
            "keyword": kw,
            "count": len(kw_commits),
            "commits": shas,
            "sample_messages": sample,
        })

    return results


# ---------------------------------------------------------------------------
# Hotspot files
# ---------------------------------------------------------------------------

def extract_hotspot_files(repo_path, since, top_n=20):
    """Files changed most frequently in the date range."""
    raw = run_git(
        ["log", f"--since={since}", "--format=", "--name-only", "--no-merges"],
        repo_path,
    )
    file_counter = Counter()
    for line in raw.strip().splitlines():
        line = line.strip()
        if line:
            file_counter[line] += 1

    return [
        {"file": f, "changes": count}
        for f, count in file_counter.most_common(top_n)
    ]


# ---------------------------------------------------------------------------
# Commit conventions
# ---------------------------------------------------------------------------

CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\(.+?\))?!?:\s"
)

# Common external reference patterns (Jira, Linear, GitHub issues, etc.)
REF_PATTERNS = [
    (r"[A-Z]{2,10}-\d+", "JIRA/Linear style"),  # PROJ-123, ENG-456
    (r"#\d+", "GitHub issue"),                     # #123
    (r"GH-\d+", "GitHub explicit"),                # GH-123
]


def analyze_conventions(commits):
    """Detect commit message conventions and external reference patterns."""
    prefix_counter = Counter()
    conventional_count = 0
    ref_pattern_counts = defaultdict(int)
    found_ref_patterns = set()

    for commit in commits:
        msg = commit["message"]

        # Conventional commits
        if CONVENTIONAL_RE.match(msg):
            conventional_count += 1

        # Prefix extraction (word before first colon or space)
        prefix_match = re.match(r"^([a-zA-Z]+)[\s:(\[]", msg)
        if prefix_match:
            prefix = prefix_match.group(1).lower()
            # Only track prefixes that look intentional (not random first words)
            if len(prefix) <= 12:
                prefix_counter[prefix + ":"] += 1

        # External references
        for pattern, label in REF_PATTERNS:
            matches = re.findall(pattern, msg)
            if matches:
                ref_pattern_counts[pattern] += len(matches)
                found_ref_patterns.add(pattern)

    total = len(commits) if commits else 1
    is_conventional = conventional_count / total > 0.5

    # Top prefix patterns (at least 3 occurrences to avoid noise)
    prefix_patterns = [
        {"prefix": p, "count": c}
        for p, c in prefix_counter.most_common(10)
        if c >= 3
    ]

    return {
        "conventional_commits": is_conventional,
        "conventional_commit_ratio": round(conventional_count / total, 2),
        "prefix_patterns": prefix_patterns,
        "has_external_references": bool(found_ref_patterns),
        "reference_patterns": sorted(found_ref_patterns),
    }


# ---------------------------------------------------------------------------
# Time trending for fix patterns
# ---------------------------------------------------------------------------

def _quarter_label(dt):
    """Return a 'YYYY-QN' label for a datetime."""
    return f"{dt.year}-Q{(dt.month - 1) // 3 + 1}"


def _parse_commit_date(date_str):
    """Parse a git commit date string into a datetime."""
    try:
        return datetime.fromisoformat(date_str.strip())
    except (ValueError, TypeError):
        return None


def build_sha_date_map(commits):
    """Build a mapping from short SHA to datetime for all commits."""
    sha_map = {}
    for c in commits:
        dt = _parse_commit_date(c["date"])
        if dt is not None:
            sha_map[c["short_sha"]] = dt
    return sha_map


def compute_trend(dates):
    """Compute trend direction from a list of datetimes.

    Returns 'worsening' if >50% of occurrences are in the recent half
    of the date range, 'improving' if >50% are in the older half,
    'stable' otherwise.
    """
    if len(dates) < 2:
        return "stable"

    sorted_dates = sorted(dates)
    earliest = sorted_dates[0]
    latest = sorted_dates[-1]
    midpoint = earliest + (latest - earliest) / 2

    recent_count = sum(1 for d in sorted_dates if d > midpoint)
    older_count = len(sorted_dates) - recent_count

    total = len(sorted_dates)
    if recent_count / total > 0.5:
        return "worsening"
    elif older_count / total > 0.5:
        return "improving"
    return "stable"


def enrich_fix_patterns_with_trending(fix_patterns, sha_date_map):
    """Add time-trending data to each fix pattern entry in place.

    Adds: first_date, last_date, trend, quarterly_counts.
    """
    for fp in fix_patterns:
        dates = []
        for sha in fp.get("commits", []):
            dt = sha_date_map.get(sha)
            if dt is not None:
                dates.append(dt)

        if not dates:
            fp["first_date"] = None
            fp["last_date"] = None
            fp["trend"] = "stable"
            fp["quarterly_counts"] = {}
            continue

        sorted_dates = sorted(dates)
        fp["first_date"] = sorted_dates[0].strftime("%Y-%m-%d")
        fp["last_date"] = sorted_dates[-1].strftime("%Y-%m-%d")
        fp["trend"] = compute_trend(dates)

        # Build quarterly counts
        qcounts = Counter()
        for dt in dates:
            qcounts[_quarter_label(dt)] += 1
        # Sort by quarter label
        fp["quarterly_counts"] = dict(sorted(qcounts.items()))


# ---------------------------------------------------------------------------
# Fix chains (recurring fixes for the same thing)
# ---------------------------------------------------------------------------

def extract_fix_chains(fix_patterns, min_count=3):
    """Identify keywords that appear in 3+ fix commits (recurring pain)."""
    chains = []
    for fp in fix_patterns:
        if fp["count"] >= min_count and fp["keyword"] != "_general":
            chains.append({
                "pattern": fp["keyword"],
                "count": fp["count"],
                "first_commit": fp["commits"][-1],  # oldest (log is newest-first)
                "last_commit": fp["commits"][0],     # newest
                "sample_messages": fp["sample_messages"],
            })
    return chains


# ---------------------------------------------------------------------------
# Date range
# ---------------------------------------------------------------------------

def compute_date_range(commits):
    """Return ISO date strings for earliest and latest commit."""
    if not commits:
        return {"from": None, "to": None}

    dates = []
    for c in commits:
        # git date format: "2026-03-20 14:30:00 +0100"
        try:
            dt = datetime.fromisoformat(c["date"].strip())
            dates.append(dt)
        except (ValueError, TypeError):
            continue

    if not dates:
        return {"from": None, "to": None}

    return {
        "from": min(dates).strftime("%Y-%m-%d"),
        "to": max(dates).strftime("%Y-%m-%d"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze git commit history for recurring patterns."
    )
    parser.add_argument(
        "repo_path",
        help="Path to the git repository to analyze.",
    )
    parser.add_argument(
        "--since",
        default="6 months ago",
        help='How far back to analyze (default: "6 months ago").',
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

    # Gather data
    commits = parse_commits(repo_path, args.since)

    if not commits:
        result = {
            "total_commits": 0,
            "date_range": {"from": None, "to": None},
            "fix_patterns": [],
            "hotspot_files": [],
            "commit_conventions": {
                "conventional_commits": False,
                "conventional_commit_ratio": 0,
                "prefix_patterns": [],
                "has_external_references": False,
                "reference_patterns": [],
            },
            "fix_chains": [],
            "error": f"No commits found since '{args.since}'.",
        }
    else:
        fix_patterns = extract_fix_patterns(commits)
        sha_date_map = build_sha_date_map(commits)
        enrich_fix_patterns_with_trending(fix_patterns, sha_date_map)
        hotspots = extract_hotspot_files(repo_path, args.since)
        conventions = analyze_conventions(commits)
        fix_chains = extract_fix_chains(fix_patterns)

        # Cap arrays to keep JSON under ~10K tokens for agent consumption
        for fp in fix_patterns:
            fp["commits"] = fp.get("commits", [])[:10]
            fp["sample_messages"] = fp.get("sample_messages", [])[:5]

        result = {
            "total_commits": len(commits),
            "date_range": compute_date_range(commits),
            "fix_patterns": fix_patterns[:30],
            "hotspot_files": hotspots[:30],
            "commit_conventions": conventions,
            "fix_chains": fix_chains[:20],
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
