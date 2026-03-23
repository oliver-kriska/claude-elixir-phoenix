#!/usr/bin/env python3
"""Quality gate ratcheting for Elixir Inspector.

Compares current violation counts against a stored baseline.
Pass: current <= baseline for all categories (no new violations).
Fail: current > baseline for any category (regression detected).
Auto-ratchet: lower baseline when violations are fixed.

Subcommands:
    measure  Scan project, count violations per category, write baseline.json
    check    Compare current state against baseline, output pass/fail

Exit codes:
    0 = pass (no regressions)
    1 = fail (regressions detected)
    2 = error (baseline missing, config error, not an Elixir project)

Usage:
    python quality-gate.py measure /path/to/repo
    python quality-gate.py measure /path/to/repo --baseline custom/path.json
    python quality-gate.py check /path/to/repo
    python quality-gate.py check /path/to/repo --json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
DEFAULT_BASELINE = ".claude/inspector/baseline.json"

# Files that never need their own test file
SKIP_TEST_FILES = frozenset({
    "application.ex",
    "repo.ex",
    "telemetry.ex",
    "mailer.ex",
    "gettext.ex",
    "endpoint.ex",
    "router.ex",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_files(root, ext, subdir=None):
    """Walk root (optionally under subdir) and yield paths ending with ext."""
    base = os.path.join(root, subdir) if subdir else root
    if not os.path.isdir(base):
        return
    for dirpath, _, filenames in os.walk(base):
        for f in filenames:
            if f.endswith(ext):
                yield os.path.join(dirpath, f)


def read_file_safe(path):
    """Read file, return content or empty string on error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (OSError, IOError):
        return ""


def relpath(path, root):
    """Return a relative path, falling back to the absolute path."""
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def has_mix(repo):
    """Check if mix is available and the repo has mix.exs."""
    if not os.path.isfile(os.path.join(repo, "mix.exs")):
        return False
    try:
        result = subprocess.run(
            ["mix", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def load_baseline(path):
    """Load baseline JSON from the given path. Returns None on failure."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_baseline(path, baseline):
    """Save baseline JSON to the given path."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    baseline["updated_at"] = now_iso()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
        f.write("\n")


def now_iso():
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Measurement functions — one per category
# ---------------------------------------------------------------------------

def count_empty_translations(repo):
    """Count empty msgstr entries in PO files under priv/gettext/.

    Returns (count, details_dict).
    """
    priv_dir = os.path.join(repo, "priv")
    if not os.path.isdir(priv_dir):
        return 0, "no priv/ directory"

    po_msgid_re = re.compile(r'msgid\s+"(.+)"')
    total_empty = 0
    per_locale = {}

    for path in find_files(repo, ".po", "priv"):
        content = read_file_safe(path)
        if not content:
            continue

        # Extract locale from path: priv/gettext/LOCALE/LC_MESSAGES/...
        parts = path.split(os.sep)
        locale = "unknown"
        for j, part in enumerate(parts):
            if part == "gettext" and j + 1 < len(parts):
                locale = parts[j + 1]
                break

        entries = re.split(r'\n\n+', content)
        empty_count = 0
        for entry in entries:
            # Skip header entry
            if 'msgid ""' in entry and 'msgstr ""' in entry and "Project-Id-Version" in entry:
                continue
            if po_msgid_re.search(entry):
                msgstr_match = re.search(r'^msgstr\s+"(.*)"', entry, re.MULTILINE)
                if msgstr_match and msgstr_match.group(1) == "":
                    empty_count += 1

        if empty_count > 0:
            per_locale[locale] = per_locale.get(locale, 0) + empty_count
            total_empty += empty_count

    details = ", ".join(f"{loc}: {cnt}" for loc, cnt in sorted(per_locale.items()))
    return total_empty, details if details else "all translations filled"


def count_credo_issues(repo):
    """Run mix credo --strict --format json and count issues.

    Returns (count, details_string) or (-1, reason) if unavailable.
    """
    if not has_mix(repo):
        return -1, "mix not available"

    try:
        result = subprocess.run(
            ["mix", "credo", "--strict", "--format", "json"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        )
        # Credo exits 0 on no issues, non-zero on issues found — both produce JSON
        output = result.stdout.strip()
        if not output:
            return -1, "credo produced no output (not installed?)"

        data = json.loads(output)
        issues = data.get("issues", [])

        # Build breakdown by category
        breakdown = {}
        for issue in issues:
            cat = issue.get("category", "unknown")
            breakdown[cat] = breakdown.get(cat, 0) + 1

        details = ", ".join(f"{cat}: {cnt}" for cat, cnt in sorted(breakdown.items()))
        return len(issues), details if details else "no issues"
    except FileNotFoundError:
        return -1, "mix not found"
    except subprocess.TimeoutExpired:
        return -1, "mix credo timed out"
    except (json.JSONDecodeError, KeyError):
        return -1, "failed to parse credo JSON output"


def count_missing_tests(repo):
    """Count lib/ modules that have no corresponding test file.

    Returns (count, details_string).
    """
    lib_dir = os.path.join(repo, "lib")
    test_dir = os.path.join(repo, "test")

    if not os.path.isdir(lib_dir):
        return 0, "no lib/ directory"

    source_files = []
    for path in find_files(repo, ".ex", "lib"):
        rel = relpath(path, repo)
        source_files.append(rel)

    # Build set of source paths that have corresponding tests
    tested_sources = set()
    if os.path.isdir(test_dir):
        for path in find_files(repo, "_test.exs", "test"):
            rel = relpath(path, repo)
            # Convert test path to source path: test/foo_test.exs -> lib/foo.ex
            src = rel.replace("test/", "lib/", 1).replace("_test.exs", ".ex")
            tested_sources.add(src)

    missing = []
    for sf in source_files:
        basename = os.path.basename(sf)
        if basename in SKIP_TEST_FILES:
            continue
        if sf not in tested_sources:
            missing.append(sf)

    sample = missing[:10]
    details = f"{len(missing)} untested; samples: {', '.join(sample)}" if missing else "all covered"
    return len(missing), details


def count_missing_moduledocs(repo):
    """Count .ex modules in lib/ that lack @moduledoc.

    Returns (count, details_string).
    """
    lib_dir = os.path.join(repo, "lib")
    if not os.path.isdir(lib_dir):
        return 0, "no lib/ directory"

    missing = []
    for path in find_files(repo, ".ex", "lib"):
        content = read_file_safe(path)
        if not content:
            continue
        if re.search(r'defmodule\s', content) and not re.search(r'@moduledoc\s', content):
            missing.append(relpath(path, repo))

    sample = missing[:10]
    details = f"{len(missing)} without @moduledoc; samples: {', '.join(sample)}" if missing else "all documented"
    return len(missing), details


def count_hardcoded_strings(repo):
    """Count quoted strings in .heex files not wrapped in gettext.

    Returns (count, details_string).
    """
    heex_str_re = re.compile(r'"([^"]{3,})"')
    gettext_call_re = re.compile(r'(gettext|dgettext|ngettext|pgettext|Gettext)\s*\(')
    attr_re = re.compile(
        r'(class|id|phx-|type|method|action|href|src|alt|name|value|'
        r'placeholder|for|data-|role|aria-|style|encoding|csrf)=\s*"'
    )

    count = 0
    examples = []

    for path in find_files(repo, ".heex", "lib"):
        content = read_file_safe(path)
        if not content:
            continue
        for i, line in enumerate(content.splitlines(), 1):
            # Skip gettext calls
            if gettext_call_re.search(line):
                continue
            # Skip attribute assignments
            if attr_re.search(line):
                continue
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("<%#") or stripped.startswith("<!--"):
                continue
            for m in heex_str_re.finditer(line):
                text = m.group(1)
                # Filter out non-UI strings
                if (
                    "/" in text
                    or text.startswith(".")
                    or text.startswith("#")
                    or re.match(r'^[a-z_-]+$', text)
                    or re.match(r'^%', text)
                    or len(text.split()) == 0
                ):
                    continue
                count += 1
                if len(examples) < 5:
                    examples.append(f"{relpath(path, repo)}:{i}")

    details = f"{count} found; samples: {', '.join(examples)}" if examples else "none found"
    return count, details


def count_compile_warnings(repo):
    """Run mix compile and count warnings.

    Returns (count, details_string) or (-1, reason) if unavailable.
    """
    if not has_mix(repo):
        return -1, "mix not available"

    try:
        result = subprocess.run(
            ["mix", "compile", "--force", "--warnings-as-errors"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=300,
        )
        # Count warning lines from stderr
        # Elixir compile warnings look like: "warning: ..." or "  lib/foo.ex:10: warning: ..."
        warning_re = re.compile(r'warning:', re.IGNORECASE)
        warnings = []
        for line in result.stderr.splitlines():
            if warning_re.search(line):
                warnings.append(line.strip())

        details = f"{len(warnings)} warnings" if warnings else "clean compile"
        return len(warnings), details
    except FileNotFoundError:
        return -1, "mix not found"
    except subprocess.TimeoutExpired:
        return -1, "mix compile timed out (>5min)"


# ---------------------------------------------------------------------------
# Core: measure all categories
# ---------------------------------------------------------------------------

CATEGORIES = [
    ("empty_translations", count_empty_translations),
    ("credo_issues", count_credo_issues),
    ("missing_tests", count_missing_tests),
    ("missing_moduledocs", count_missing_moduledocs),
    ("hardcoded_strings", count_hardcoded_strings),
    ("compile_warnings", count_compile_warnings),
]


def measure_all(repo):
    """Run all category measurements. Returns dict {name: {count, details}}."""
    results = {}
    for name, fn in CATEGORIES:
        count, details = fn(repo)
        results[name] = {"count": count, "details": details}
    return results


# ---------------------------------------------------------------------------
# Comparison & ratcheting
# ---------------------------------------------------------------------------

def check_regressions(baseline, current):
    """Compare current counts against baseline.

    Returns (regressions, improvements, unchanged, skipped) — each a list.
    """
    regressions = []
    improvements = []
    unchanged = []
    skipped = []

    for category, baseline_data in baseline.get("categories", {}).items():
        baseline_count = baseline_data.get("count", 0)
        current_data = current.get(category)

        if current_data is None or current_data["count"] == -1:
            skipped.append(category)
            continue

        current_count = current_data["count"]
        delta = current_count - baseline_count

        entry = {
            "category": category,
            "baseline": baseline_count,
            "current": current_count,
            "delta": delta,
        }

        if delta > 0:
            regressions.append(entry)
        elif delta < 0:
            improvements.append(entry)
        else:
            unchanged.append(category)

    return regressions, improvements, unchanged, skipped


def auto_ratchet(baseline, current):
    """Lower baseline counts for categories that improved.

    Only ratchets DOWN (tighter), never UP. Records ratchet events in history.
    Returns the modified baseline.
    """
    ts = now_iso()

    for category, baseline_data in baseline.get("categories", {}).items():
        current_data = current.get(category)
        if current_data is None or current_data["count"] == -1:
            continue

        current_count = current_data["count"]
        baseline_count = baseline_data.get("count", 0)

        if current_count < baseline_count:
            baseline.setdefault("history", []).append({
                "date": ts,
                "event": "ratchet_lowered",
                "category": category,
                "old_count": baseline_count,
                "new_count": current_count,
            })
            baseline_data["count"] = current_count
            baseline_data["details"] = current_data.get("details", "")
            baseline_data["last_measured"] = ts

    return baseline


# ---------------------------------------------------------------------------
# Text output formatting
# ---------------------------------------------------------------------------

def format_delta(delta):
    """Format a delta integer with +/- prefix."""
    if delta > 0:
        return f"+{delta}"
    return str(delta)


def print_text_result(regressions, improvements, unchanged, skipped):
    """Print human-readable check results to stdout."""
    if regressions:
        print("FAIL: Quality regressions detected\n")
        for r in regressions:
            print(f"  {r['category']}: {r['baseline']} -> {r['current']} ({format_delta(r['delta'])})")
    else:
        print("PASS: No quality regressions\n")

    if improvements:
        print("\nImprovements (baseline ratcheted down):")
        for i in improvements:
            print(f"  {i['category']}: {i['baseline']} -> {i['current']} ({format_delta(i['delta'])})")

    if unchanged:
        print(f"\nUnchanged: {', '.join(unchanged)}")

    if skipped:
        print(f"\nSkipped (unavailable): {', '.join(skipped)}")


def print_json_result(regressions, improvements, unchanged, skipped):
    """Print JSON check results to stdout."""
    result = {
        "pass": len(regressions) == 0,
        "regressions": regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "skipped": skipped,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_measure(repo, baseline_path):
    """Measure current state and create or update baseline."""
    current = measure_all(repo)
    baseline = load_baseline(baseline_path)
    ts = now_iso()

    if baseline is None:
        # First measurement: create baseline
        baseline = {
            "version": SCHEMA_VERSION,
            "created_at": ts,
            "updated_at": ts,
            "project": os.path.basename(repo),
            "categories": {},
            "history": [],
        }

        measurable = {}
        for name, data in current.items():
            if data["count"] >= 0:
                baseline["categories"][name] = {
                    "count": data["count"],
                    "details": data["details"],
                    "last_measured": ts,
                }
                measurable[name] = data["count"]

        baseline["history"].append({
            "date": ts,
            "event": "baseline_created",
            "totals": measurable,
        })

        save_baseline(baseline_path, baseline)

        print(f"Baseline created at {baseline_path}")
        print(f"Categories measured: {len(baseline['categories'])}")
        for name, data in sorted(baseline["categories"].items()):
            print(f"  {name}: {data['count']}")

    else:
        # Update: auto-ratchet improvements
        old_counts = {
            cat: data["count"]
            for cat, data in baseline.get("categories", {}).items()
        }

        # Add any new categories not in the existing baseline
        for name, data in current.items():
            if data["count"] >= 0 and name not in baseline.get("categories", {}):
                baseline.setdefault("categories", {})[name] = {
                    "count": data["count"],
                    "details": data["details"],
                    "last_measured": ts,
                }
                baseline.setdefault("history", []).append({
                    "date": ts,
                    "event": "category_added",
                    "category": name,
                    "count": data["count"],
                })

        baseline = auto_ratchet(baseline, current)
        save_baseline(baseline_path, baseline)

        print(f"Baseline updated at {baseline_path}")
        for name, data in sorted(baseline.get("categories", {}).items()):
            old = old_counts.get(name)
            current_count = data["count"]
            if old is not None and current_count < old:
                print(f"  {name}: {old} -> {current_count} (ratcheted down)")
            elif old is not None:
                print(f"  {name}: {current_count} (unchanged)")
            else:
                print(f"  {name}: {current_count} (new)")


def cmd_check(repo, baseline_path, output_json):
    """Check current state against baseline. Exit 0=pass, 1=fail, 2=error."""
    baseline = load_baseline(baseline_path)
    if baseline is None:
        print(
            f"Error: no baseline found at {baseline_path}. "
            "Run 'measure' first to create one.",
            file=sys.stderr,
        )
        sys.exit(2)

    current = measure_all(repo)
    regressions, improvements, unchanged, skipped = check_regressions(baseline, current)

    # Auto-ratchet improvements even during check
    baseline = auto_ratchet(baseline, current)
    save_baseline(baseline_path, baseline)

    if output_json:
        print_json_result(regressions, improvements, unchanged, skipped)
    else:
        print_text_result(regressions, improvements, unchanged, skipped)

    if regressions:
        sys.exit(1)
    else:
        sys.exit(0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Quality gate ratcheting for Elixir Inspector",
        epilog="Exit codes: 0=pass, 1=fail (regressions), 2=error",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -- measure --
    measure_parser = subparsers.add_parser(
        "measure",
        help="Scan project, count violations per category, write baseline.json",
    )
    measure_parser.add_argument(
        "repo_path",
        help="Path to the Elixir project root",
    )
    measure_parser.add_argument(
        "--baseline",
        default=None,
        help=f"Path to baseline.json (default: <repo>/{DEFAULT_BASELINE})",
    )

    # -- check --
    check_parser = subparsers.add_parser(
        "check",
        help="Compare current state against baseline, output pass/fail",
    )
    check_parser.add_argument(
        "repo_path",
        help="Path to the Elixir project root",
    )
    check_parser.add_argument(
        "--baseline",
        default=None,
        help=f"Path to baseline.json (default: <repo>/{DEFAULT_BASELINE})",
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output results as JSON instead of text",
    )

    args = parser.parse_args()
    repo = os.path.abspath(args.repo_path)

    if not os.path.isdir(repo):
        print(f"Error: {repo} is not a directory.", file=sys.stderr)
        sys.exit(2)

    # Resolve baseline path
    baseline_path = args.baseline if args.baseline else os.path.join(repo, DEFAULT_BASELINE)
    baseline_path = os.path.abspath(baseline_path)

    if args.command == "measure":
        cmd_measure(repo, baseline_path)
    elif args.command == "check":
        cmd_check(repo, baseline_path, args.output_json)


if __name__ == "__main__":
    main()
