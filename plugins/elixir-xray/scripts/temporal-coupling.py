#!/usr/bin/env python3
"""Detect temporal coupling between files via co-change analysis.

Parses git log to find files that frequently change together,
computes Jaccard similarity for each pair, and reports hidden coupling.
Classifies each pair as expected (test companion, same directory) or
unexpected (cross-context, web vs non-web, worker vs LiveView).

Usage:
    python temporal-coupling.py /path/to/repo
    python temporal-coupling.py /path/to/repo --since "6 months ago"
    python temporal-coupling.py /path/to/repo --jaccard-threshold 0.3
    python temporal-coupling.py /path/to/repo --output results.json
"""

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict
from itertools import combinations


# ---------------------------------------------------------------------------
# Git helpers (reuse pattern from analyze-git-history.py)
# ---------------------------------------------------------------------------

def run_git(args, cwd):
    """Run a git command and return stdout."""
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=120
        )
    except FileNotFoundError:
        print("Error: git is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(
            f"Error: git command timed out: {' '.join(cmd)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr and "not a git repository" in stderr.lower():
            print(f"Error: {cwd} is not a git repository.", file=sys.stderr)
            sys.exit(1)
        # Non-fatal: return empty string (e.g. no commits in range)
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
# Core algorithm
# ---------------------------------------------------------------------------

def parse_commit_file_map(repo_path, since, max_files_per_commit):
    """Parse git log into {commit_hash: set_of_files}.

    Uses --name-only with a delimiter format to separate commits.
    Skips commits that touch more than *max_files_per_commit* tracked
    files (mega-commits from refactors, renames, etc.).
    """
    raw = run_git(
        [
            "log",
            f"--since={since}",
            "--pretty=format:__COMMIT__%H",
            "--name-only",
            "--no-merges",
        ],
        repo_path,
    )

    commit_files = {}  # sha -> set of files
    current_sha = None

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("__COMMIT__"):
            current_sha = line[len("__COMMIT__"):]
            commit_files[current_sha] = set()
        elif current_sha is not None:
            # Only track Elixir/Phoenix file types to reduce noise
            if line.endswith((".ex", ".exs", ".heex", ".eex", ".sface")):
                commit_files[current_sha].add(line)

    # Drop mega-commits (refactors, bulk renames) that would explode pairs
    commit_files = {
        sha: files
        for sha, files in commit_files.items()
        if 0 < len(files) <= max_files_per_commit
    }

    return commit_files


def build_cochange_matrix(commit_files, min_cochanges):
    """Build co-change counts for file pairs.

    For each commit, every pair of files in that commit gets +1.
    Only tracks files that appear in >= *min_cochanges* commits total
    to reduce pair explosion.

    Returns:
        file_commit_count: {file: number_of_commits_touching_it}
        pair_count: {(file_a, file_b): number_of_commits_with_both}
        pair_commits: {(file_a, file_b): [short_sha, ...]} (max 5 examples)
    """
    # Step 1: Count per-file frequency
    file_commit_count = defaultdict(int)
    for files in commit_files.values():
        for f in files:
            file_commit_count[f] += 1

    # Step 2: Filter to files with >= min_cochanges
    frequent_files = {
        f for f, c in file_commit_count.items() if c >= min_cochanges
    }

    # Step 3: Count co-changes
    pair_count = defaultdict(int)
    pair_commits = defaultdict(list)

    for sha, files in commit_files.items():
        relevant = sorted(files & frequent_files)
        for a, b in combinations(relevant, 2):
            pair = (a, b)
            pair_count[pair] += 1
            if len(pair_commits[pair]) < 5:
                pair_commits[pair].append(sha[:8])

    return dict(file_commit_count), dict(pair_count), dict(pair_commits)


def compute_jaccard_scores(file_commit_count, pair_count, threshold):
    """Compute Jaccard index for each file pair.

    Jaccard(A, B) = |commits_with_both| / |commits_with_A_or_B|
                  = pair_count / (count_A + count_B - pair_count)

    Returns list of pairs with score >= *threshold*, sorted descending.
    """
    results = []

    for (file_a, file_b), both_count in pair_count.items():
        count_a = file_commit_count.get(file_a, 0)
        count_b = file_commit_count.get(file_b, 0)
        union = count_a + count_b - both_count

        if union == 0:
            continue

        jaccard = both_count / union

        if jaccard >= threshold:
            results.append(
                {
                    "file_a": file_a,
                    "file_b": file_b,
                    "jaccard_score": round(jaccard, 3),
                    "cochanges": both_count,
                    "changes_a": count_a,
                    "changes_b": count_b,
                }
            )

    results.sort(key=lambda x: x["jaccard_score"], reverse=True)
    return results


def classify_coupling(pair):
    """Classify whether a coupling is expected or unexpected.

    Expected couplings (lower signal):
    - module.ex + module_test.exs  (test companion)
    - files in the same directory   (same context module)
    - schema + migration file

    Unexpected couplings (high signal):
    - Two different contexts changing together
    - Web + non-web boundary crossing
    - Worker + LiveView changing together
    """
    a, b = pair["file_a"], pair["file_b"]

    # Test companion: lib/x.ex <-> test/x_test.exs
    if a.replace("lib/", "test/").replace(".ex", "_test.exs") == b:
        return "expected_test_companion"
    if b.replace("lib/", "test/").replace(".ex", "_test.exs") == a:
        return "expected_test_companion"

    # Same directory (same context module)
    dir_a = os.path.dirname(a)
    dir_b = os.path.dirname(b)
    if dir_a and dir_b and dir_a == dir_b:
        return "expected_same_directory"

    # Schema + migration
    if ("migrations" in a and "schema" in b) or (
        "migrations" in b and "schema" in a
    ):
        return "expected_schema_migration"

    # Different Phoenix contexts (lib/app/context_a/... + lib/app/context_b/...)
    parts_a = a.split("/")
    parts_b = b.split("/")
    if (
        len(parts_a) >= 3
        and len(parts_b) >= 3
        and parts_a[0] == "lib"
        and parts_b[0] == "lib"
        and parts_a[1] == parts_b[1]  # Same app
        and parts_a[2] != parts_b[2]  # Different context
    ):
        return "unexpected_cross_context"

    # Web + non-web boundary
    if ("_web" in a and "_web" not in b) or ("_web" in b and "_web" not in a):
        return "unexpected_web_nonweb"

    # Worker + LiveView
    if ("worker" in a.lower() and "live" in b.lower()) or (
        "worker" in b.lower() and "live" in a.lower()
    ):
        return "unexpected_worker_liveview"

    return "unclear"


def handle_renames(repo_path, since):
    """Build a rename map from git log --diff-filter=R.

    Unifies old_name -> new_name so co-change analysis doesn't split a
    renamed file into two separate entries.

    Returns: {old_path: new_path}
    """
    raw = run_git(
        [
            "log",
            f"--since={since}",
            "--diff-filter=R",
            "--name-status",
            "--pretty=format:",
            "--no-merges",
        ],
        repo_path,
    )
    rename_map = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: R100\told_path\tnew_path
        parts = line.split("\t")
        if len(parts) >= 3 and parts[0].startswith("R"):
            old_path = parts[1]
            new_path = parts[2]
            rename_map[old_path] = new_path
    return rename_map


def apply_renames(commit_files, rename_map):
    """Replace old file names with current names in commit_files.

    Follows rename chains (A -> B -> C) with cycle detection.
    Modifies *commit_files* in place.
    """
    for sha, files in commit_files.items():
        updated = set()
        for f in files:
            resolved = f
            seen = set()
            while resolved in rename_map and resolved not in seen:
                seen.add(resolved)
                resolved = rename_map[resolved]
            updated.add(resolved)
        commit_files[sha] = updated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Detect temporal coupling via co-change analysis.",
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
        "--min-cochanges",
        type=int,
        default=3,
        help="Minimum commits per file to include in analysis (default: 3).",
    )
    parser.add_argument(
        "--jaccard-threshold",
        type=float,
        default=0.3,
        help="Minimum Jaccard score to report a pair (default: 0.3).",
    )
    parser.add_argument(
        "--max-files-per-commit",
        type=int,
        default=50,
        help="Skip commits touching more files than this (default: 50).",
    )
    parser.add_argument(
        "--max-pairs",
        type=int,
        default=50,
        help="Maximum number of coupled pairs to report (default: 50).",
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

    # Step 1: Parse git log into commit -> files mapping
    commit_files = parse_commit_file_map(
        repo_path, args.since, args.max_files_per_commit
    )

    if not commit_files:
        result = {
            "total_commits_analyzed": 0,
            "total_files_tracked": 0,
            "total_pairs_above_threshold": 0,
            "unexpected_couplings": 0,
            "expected_couplings": 0,
            "coupled_pairs": [],
            "error": f"No commits found since '{args.since}'.",
        }
        output_json = json.dumps(result, indent=2, ensure_ascii=False)
        if args.output:
            _write_output(args.output, output_json)
        else:
            print(output_json)
        return

    # Step 2: Handle renames so old->new paths unify
    rename_map = handle_renames(repo_path, args.since)
    if rename_map:
        apply_renames(commit_files, rename_map)

    # Step 3: Build co-change matrix
    file_counts, pair_counts, pair_examples = build_cochange_matrix(
        commit_files, min_cochanges=args.min_cochanges
    )

    # Step 4: Compute Jaccard scores
    coupled_pairs = compute_jaccard_scores(
        file_counts, pair_counts, threshold=args.jaccard_threshold
    )

    # Step 5: Classify and enrich each pair
    for pair in coupled_pairs:
        pair["coupling_type"] = classify_coupling(pair)
        pair_key = (pair["file_a"], pair["file_b"])
        pair["example_commits"] = pair_examples.get(pair_key, [])

    # Step 6: Trim to max_pairs
    coupled_pairs = coupled_pairs[: args.max_pairs]

    # Summary stats
    unexpected = [
        p for p in coupled_pairs if p["coupling_type"].startswith("unexpected")
    ]
    expected = [
        p for p in coupled_pairs if p["coupling_type"].startswith("expected")
    ]

    # Cap to keep JSON under ~10K tokens for agent consumption
    for pair in coupled_pairs:
        if "example_commits" in pair:
            pair["example_commits"] = pair["example_commits"][:5]

    result = {
        "total_commits_analyzed": len(commit_files),
        "total_files_tracked": len(file_counts),
        "total_pairs_above_threshold": len(coupled_pairs),
        "unexpected_couplings": len(unexpected),
        "expected_couplings": len(expected),
        "coupled_pairs": coupled_pairs[:50],
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        _write_output(args.output, output_json)
    else:
        print(output_json)


def _write_output(path, content):
    """Write content to *path*, creating parent directories as needed."""
    output_dir = os.path.dirname(os.path.abspath(path))
    if output_dir and not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    print(f"Output written to {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
