#!/usr/bin/env python3
"""Analyze PR comments and code review feedback via the gh CLI.

Extracts review themes, friction patterns, and PR size stats from merged
pull requests. Outputs deterministic JSON for downstream agent
interpretation.

Usage:
    python analyze-prs.py
    python analyze-prs.py /path/to/repo --since 2025-09-20 --limit 100
    python analyze-prs.py --output results.json
    python analyze-prs.py --gh-api-fallback --timeout 45
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_BOTS = {
    "dependabot", "dependabot[bot]",
    "github-actions", "github-actions[bot]",
    "renovate", "renovate[bot]",
    "codecov", "codecov[bot]",
    "sonarcloud", "sonarcloud[bot]",
    "netlify", "netlify[bot]",
    "vercel", "vercel[bot]",
    "stale", "stale[bot]",
    "mergify", "mergify[bot]",
    "allcontributors", "allcontributors[bot]",
    "snyk-bot", "greenkeeper[bot]",
    "imgbot", "imgbot[bot]",
    "semantic-release-bot",
    "copilot",
    "linear", "linear[bot]",
    "coderabbitai", "coderabbitai[bot]",
    "greptile-apps", "greptile-apps[bot]",
    "sentry-io", "sentry-io[bot]",
    "claude", "claude[bot]",
}

# Minimum human review comments to fetch full details
MIN_COMMENTS_FOR_DETAIL = 2

# Large PR threshold (additions + deletions)
LARGE_PR_THRESHOLD = 500

# API delay between detail fetches (seconds) to avoid rate limiting
API_DELAY = 0.3

# Retry configuration for transient GitHub API errors
MAX_RETRIES = 3
RETRY_BACKOFFS = [2, 5, 10]  # seconds between retries
RETRYABLE_STATUS_CODES = {"502", "503"}
FATAL_STATUS_CODES = {"401", "404"}

# Duplicate comment threshold — identical text in N+ PRs means bot/template
DUPLICATE_COMMENT_THRESHOLD = 5

# Minimum keyword frequency to count as a review theme
MIN_THEME_FREQUENCY = 3


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _is_retryable_error(stderr_text):
    """Check if a gh CLI error is retryable (transient server error)."""
    lower = stderr_text.lower()
    # Check for HTTP status codes in error messages
    for code in RETRYABLE_STATUS_CODES:
        if code in stderr_text:
            return True
    # Check for timeout / connection indicators
    if any(kw in lower for kw in ("timeout", "timed out", "connection reset",
                                   "bad gateway", "service unavailable",
                                   "server error", "internal error",
                                   "stream error", "received from peer")):
        return True
    return False


def _is_fatal_error(stderr_text):
    """Check if a gh CLI error should NOT be retried."""
    for code in FATAL_STATUS_CODES:
        if code in stderr_text:
            return True
    lower = stderr_text.lower()
    if "not logged in" in lower or "authentication" in lower:
        return True
    if "could not determine base repo" in lower:
        return True
    return False


def run_gh(args, cwd, timeout=60):
    """Run a gh CLI command with retry logic. Returns stdout or None on failure.

    Retries up to MAX_RETRIES times with exponential backoff for transient
    errors (502, 503, timeouts). Fails immediately on 401/404/auth errors.
    """
    cmd = ["gh"] + args
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            print(
                "Error: gh CLI is not installed. Install from https://cli.github.com/",
                file=sys.stderr,
            )
            sys.exit(1)
        except subprocess.TimeoutExpired:
            last_error = f"timeout after {timeout}s"
            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFFS[attempt]
                print(
                    f"Retry {attempt + 1}/{MAX_RETRIES}: gh command timed out, "
                    f"retrying in {backoff}s... ({' '.join(cmd)})",
                    file=sys.stderr,
                )
                time.sleep(backoff)
                continue
            print(
                f"Error: gh command timed out after {MAX_RETRIES} retries: "
                f"{' '.join(cmd)}",
                file=sys.stderr,
            )
            return None

        if result.returncode == 0:
            return result.stdout

        stderr = result.stderr.strip()
        last_error = stderr

        # Fatal errors — fail immediately, no retry
        if _is_fatal_error(stderr):
            if "not logged in" in stderr.lower() or "authentication" in stderr.lower():
                print(
                    "Error: gh is not authenticated. Run `gh auth login` first.",
                    file=sys.stderr,
                )
                sys.exit(1)
            if "could not determine base repo" in stderr.lower():
                print(
                    "Error: not in a GitHub repository or no remote configured.",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(f"Warning: gh command failed (fatal): {stderr}", file=sys.stderr)
            return None

        # Retryable errors — backoff and retry
        if _is_retryable_error(stderr) and attempt < MAX_RETRIES:
            backoff = RETRY_BACKOFFS[attempt]
            print(
                f"Retry {attempt + 1}/{MAX_RETRIES}: {stderr[:120]}... "
                f"retrying in {backoff}s",
                file=sys.stderr,
            )
            time.sleep(backoff)
            continue

        # Non-retryable, non-fatal — give up
        print(f"Warning: gh command failed: {stderr}", file=sys.stderr)
        return None

    # Exhausted all retries
    print(
        f"Error: gh command failed after {MAX_RETRIES} retries: {last_error}",
        file=sys.stderr,
    )
    return None


def check_gh_available(cwd):
    """Verify gh is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            print(
                "Error: gh is not authenticated. Run `gh auth login` first.",
                file=sys.stderr,
            )
            sys.exit(1)
    except FileNotFoundError:
        print(
            "Error: gh CLI is not installed. Install from https://cli.github.com/",
            file=sys.stderr,
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# PR listing and filtering
# ---------------------------------------------------------------------------

def _detect_repo_nwo(cwd):
    """Detect owner/repo from git remote. Returns 'owner/repo' or None."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def list_merged_prs(cwd, limit, timeout=60, gh_api_fallback=False):
    """Fetch merged PRs as a list of dicts.

    When gh_api_fallback is True and `gh pr list` fails, falls back to
    the lower-level `gh api` endpoint which sometimes works when the
    higher-level command doesn't.
    """
    fields = "number,title,createdAt,mergedAt,comments,reviews,additions,deletions,author"
    # The nested comments+reviews query is expensive on large repos and the
    # GitHub GraphQL API 502s on it. Degrade to smaller batches before giving
    # up — 25 recent PRs is far more useful than 0.
    batch_limits = [limit] + [b for b in (50, 25) if b < limit]
    for attempt_limit in batch_limits:
        raw = run_gh(
            ["pr", "list", "--state", "merged", "--limit", str(attempt_limit),
             "--json", fields],
            cwd,
            timeout=timeout,
        )
        if raw:
            try:
                prs = json.loads(raw)
                if attempt_limit < limit:
                    print(
                        f"Note: server rejected larger queries; analyzed "
                        f"{attempt_limit} most recent PRs instead of {limit}.",
                        file=sys.stderr,
                    )
                return prs
            except json.JSONDecodeError:
                print("Error: failed to parse gh pr list JSON output.", file=sys.stderr)
                break  # Parse error won't improve with a smaller batch
        elif attempt_limit != batch_limits[-1]:
            print(
                f"PR listing with limit {attempt_limit} failed; "
                f"trying a smaller batch...",
                file=sys.stderr,
            )

    if not gh_api_fallback:
        return []

    # Fallback: use gh api directly
    print(
        "Trying gh api fallback for PR listing...",
        file=sys.stderr,
    )
    nwo = _detect_repo_nwo(cwd)
    if not nwo:
        print("Error: could not detect owner/repo for API fallback.", file=sys.stderr)
        return []

    # Fetch in pages of 100 (API max) up to limit
    all_prs = []
    page = 1
    per_page = min(limit, 100)
    while len(all_prs) < limit:
        raw = run_gh(
            ["api", f"repos/{nwo}/pulls",
             "-f", "state=closed",
             "-f", f"per_page={per_page}",
             "-f", f"page={page}"],
            cwd,
            timeout=timeout,
        )
        if not raw:
            break
        try:
            page_prs = json.loads(raw)
        except json.JSONDecodeError:
            print("Error: failed to parse gh api fallback JSON.", file=sys.stderr)
            break
        if not page_prs:
            break
        # gh api returns all closed PRs; filter to merged only and normalize
        for pr in page_prs:
            if not pr.get("merged_at"):
                continue
            all_prs.append({
                "number": pr.get("number"),
                "title": pr.get("title", ""),
                "createdAt": pr.get("created_at"),
                "mergedAt": pr.get("merged_at"),
                "comments": pr.get("comments", 0),
                "reviews": pr.get("review_comments", 0),
                "additions": pr.get("additions", 0),
                "deletions": pr.get("deletions", 0),
                "author": pr.get("user", {}).get("login", ""),
            })
            if len(all_prs) >= limit:
                break
        page += 1
        time.sleep(API_DELAY)

    if all_prs:
        print(
            f"Fallback fetched {len(all_prs)} merged PRs via gh api.",
            file=sys.stderr,
        )
    else:
        print("Warning: gh api fallback also returned no PRs.", file=sys.stderr)

    return all_prs


def parse_iso_date(date_str):
    """Parse ISO 8601 date string to datetime. Returns None on failure."""
    if not date_str:
        return None
    try:
        # gh returns RFC 3339 timestamps like "2026-03-20T14:30:00Z"
        date_str = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return None


def filter_prs_by_date(prs, since_date):
    """Keep only PRs created on or after since_date."""
    filtered = []
    for pr in prs:
        created = parse_iso_date(pr.get("createdAt") or pr.get("mergedAt"))
        if created is None:
            continue
        # Make since_date timezone-aware if needed
        if created.tzinfo is not None and since_date.tzinfo is None:
            since_aware = since_date.replace(tzinfo=timezone.utc)
        else:
            since_aware = since_date
        if created >= since_aware:
            filtered.append(pr)
    return filtered


# ---------------------------------------------------------------------------
# Comment extraction and bot filtering
# ---------------------------------------------------------------------------

def count_human_comments(pr):
    """Estimate human comment count from the PR list summary.

    gh returns `comments` (issue-level) and `reviews` as counts or objects
    depending on fields requested. We use the total as an estimate to decide
    whether to fetch details.
    """
    comments_field = pr.get("comments", [])
    reviews_field = pr.get("reviews", [])

    # comments/reviews may be lists (when fetched with detail) or counts
    if isinstance(comments_field, list):
        comment_count = len(comments_field)
    elif isinstance(comments_field, (int, float)):
        comment_count = int(comments_field)
    else:
        comment_count = 0

    if isinstance(reviews_field, list):
        review_count = len(reviews_field)
    elif isinstance(reviews_field, (int, float)):
        review_count = int(reviews_field)
    else:
        review_count = 0

    return comment_count + review_count


def fetch_pr_details(cwd, pr_number, timeout=60):
    """Fetch full comments and reviews for a single PR."""
    raw = run_gh(
        ["pr", "view", str(pr_number),
         "--json", "number,title,comments,reviews"],
        cwd,
        timeout=timeout,
    )
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def is_bot_author(author_info):
    """Check whether a comment/review author is a known bot."""
    if not author_info:
        return False
    # author may be a string or a dict with 'login' key
    if isinstance(author_info, str):
        login = author_info.lower()
    elif isinstance(author_info, dict):
        login = (author_info.get("login") or author_info.get("name") or "").lower()
    else:
        return False
    return login in KNOWN_BOTS or login.endswith("[bot]")


def extract_comment_texts(pr_detail):
    """Extract human (non-bot) comment/review body texts from a PR detail."""
    texts = []

    for comment in pr_detail.get("comments", []):
        if is_bot_author(comment.get("author")):
            continue
        body = (comment.get("body") or "").strip()
        if body:
            texts.append(body)

    for review in pr_detail.get("reviews", []):
        if is_bot_author(review.get("author")):
            continue
        body = (review.get("body") or "").strip()
        if body:
            texts.append(body)

    return texts


def filter_duplicate_comments(all_comment_texts, threshold=DUPLICATE_COMMENT_THRESHOLD):
    """Remove comment texts that appear in too many PRs (likely bot/template).

    Returns (filtered_texts_per_pr_map_is_not_needed, duplicate_count).
    We receive a flat list; instead we count duplicates globally.
    """
    text_counter = Counter(all_comment_texts)
    duplicates = {t for t, c in text_counter.items() if c >= threshold}
    duplicate_count = sum(c for t, c in text_counter.items() if t in duplicates)
    return duplicates, duplicate_count


# ---------------------------------------------------------------------------
# Review theme extraction
# ---------------------------------------------------------------------------

# Keywords and phrases that indicate review feedback themes
THEME_KEYWORDS = {
    "gettext": ["gettext", "i18n", "internationalization", "hardcoded text",
                 "hardcoded string", "translate"],
    "tests": ["test", "tests", "testing", "test coverage", "spec", "untested"],
    "types": ["typespec", "@spec", "dialyzer", "type spec", "@type"],
    "naming": ["naming", "rename", "variable name", "better name", "misleading name"],
    "docs": ["documentation", "docs", "@doc", "@moduledoc", "comment", "docstring"],
    "error_handling": ["error handling", "error case", "rescue", "try/catch",
                       "handle_error", "with clause", "unhappy path"],
    "performance": ["performance", "n+1", "preload", "query", "slow", "optimize",
                     "efficient"],
    "security": ["security", "authorize", "auth", "permission", "sanitize", "escape",
                  "injection"],
    "style": ["format", "formatting", "style", "credo", "lint", "convention"],
    "refactor": ["refactor", "extract", "simplify", "duplication", "dry",
                  "complex", "readability"],
    "validation": ["validation", "validate", "changeset", "required field",
                    "constraint"],
}


def classify_comment_themes(comment_texts, duplicate_texts):
    """Group comments by keyword themes.

    Returns list of theme dicts sorted by count descending.
    """
    theme_prs = defaultdict(set)      # theme -> set of PR numbers
    theme_comments = defaultdict(list) # theme -> sample comment texts
    theme_counts = Counter()

    for pr_number, text in comment_texts:
        if text in duplicate_texts:
            continue
        text_lower = text.lower()
        for theme, keywords in THEME_KEYWORDS.items():
            for kw in keywords:
                if kw in text_lower:
                    theme_counts[theme] += 1
                    theme_prs[theme].add(pr_number)
                    if len(theme_comments[theme]) < 5:
                        # Truncate long comments for the sample
                        sample = text[:200] + ("..." if len(text) > 200 else "")
                        theme_comments[theme].append(sample)
                    break  # One match per theme per comment

    results = []
    for theme, count in theme_counts.most_common():
        if count < MIN_THEME_FREQUENCY:
            continue
        results.append({
            "theme": theme,
            "count": count,
            "prs": sorted(theme_prs[theme]),
            "sample_comments": theme_comments[theme],
        })

    return results


# ---------------------------------------------------------------------------
# Review rounds estimation
# ---------------------------------------------------------------------------

def estimate_review_rounds(pr_detail):
    """Estimate review rounds from the reviews list.

    A 'round' is approximated by counting CHANGES_REQUESTED or COMMENTED
    reviews. APPROVED typically ends a round.
    """
    reviews = pr_detail.get("reviews", [])
    if not reviews:
        return 0

    rounds = 0
    for review in reviews:
        if is_bot_author(review.get("author")):
            continue
        state = (review.get("state") or "").upper()
        if state in ("CHANGES_REQUESTED", "COMMENTED", "DISMISSED"):
            rounds += 1
        elif state == "APPROVED":
            rounds += 1  # The final round

    return max(rounds, 1) if reviews else 0


# ---------------------------------------------------------------------------
# PR size stats
# ---------------------------------------------------------------------------

def compute_size_stats(prs):
    """Compute addition/deletion statistics across PRs."""
    additions = []
    deletions = []
    large_count = 0

    for pr in prs:
        a = pr.get("additions", 0) or 0
        d = pr.get("deletions", 0) or 0
        additions.append(a)
        deletions.append(d)
        if a + d > LARGE_PR_THRESHOLD:
            large_count += 1

    if not additions:
        return {"avg_additions": 0, "avg_deletions": 0, "large_prs": 0}

    return {
        "avg_additions": round(sum(additions) / len(additions)),
        "avg_deletions": round(sum(deletions) / len(deletions)),
        "large_prs": large_count,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze PR comments and code review feedback via gh CLI."
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default=".",
        help="Path to the git repository (default: current directory).",
    )
    parser.add_argument(
        "--since",
        default=None,
        help="ISO date to filter PRs from (default: 6 months ago).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of merged PRs to fetch (default: 100).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON to this file instead of stdout.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds per gh CLI call (default: 30).",
    )
    parser.add_argument(
        "--gh-api-fallback",
        action="store_true",
        default=False,
        help="If gh pr list fails, fall back to gh api repos/.../pulls endpoint.",
    )
    args = parser.parse_args()

    repo_path = os.path.abspath(args.repo_path)

    if not os.path.isdir(repo_path):
        print(f"Error: {repo_path} is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Compute default --since (6 months ago)
    if args.since:
        try:
            since_date = datetime.fromisoformat(args.since)
        except ValueError:
            print(
                f"Error: invalid date format '{args.since}'. Use ISO format: YYYY-MM-DD",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        now = datetime.now()
        month = now.month - 6
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        day = min(now.day, 28)  # Safe for all months
        since_date = datetime(year, month, day)

    check_gh_available(repo_path)

    # Step 1: List merged PRs
    print(f"Fetching up to {args.limit} merged PRs...", file=sys.stderr)
    all_prs = list_merged_prs(
        repo_path, args.limit,
        timeout=args.timeout,
        gh_api_fallback=args.gh_api_fallback,
    )

    if not all_prs:
        result = {
            "total_prs_analyzed": 0,
            "date_range": {"from": None, "to": None},
            "prs_with_reviews": 0,
            "avg_review_rounds": 0,
            "review_themes": [],
            "bot_comments_filtered": 0,
            "high_friction_prs": [],
            "pr_size_stats": {"avg_additions": 0, "avg_deletions": 0, "large_prs": 0},
            "error": "GitHub API unavailable after retries. No merged PRs found.",
        }
        _write_output(result, args.output)
        return

    # Step 2: Filter by date
    prs = filter_prs_by_date(all_prs, since_date)
    print(f"Found {len(prs)} PRs since {since_date.strftime('%Y-%m-%d')}.", file=sys.stderr)

    if not prs:
        result = {
            "total_prs_analyzed": 0,
            "date_range": {
                "from": since_date.strftime("%Y-%m-%d"),
                "to": datetime.now().strftime("%Y-%m-%d"),
            },
            "prs_with_reviews": 0,
            "avg_review_rounds": 0,
            "review_themes": [],
            "bot_comments_filtered": 0,
            "high_friction_prs": [],
            "pr_size_stats": {"avg_additions": 0, "avg_deletions": 0, "large_prs": 0},
            "error": f"No merged PRs found since {since_date.strftime('%Y-%m-%d')}.",
        }
        _write_output(result, args.output)
        return

    # Step 3: Identify PRs needing detailed comment fetch
    prs_needing_detail = [
        pr for pr in prs
        if count_human_comments(pr) >= MIN_COMMENTS_FOR_DETAIL
    ]
    print(
        f"Fetching details for {len(prs_needing_detail)} PRs with 2+ comments...",
        file=sys.stderr,
    )

    # Step 4: Fetch detailed comments
    all_tagged_comments = []     # (pr_number, comment_text)
    all_flat_comments = []       # comment_text (for duplicate detection)
    bot_comment_count = 0
    pr_review_rounds = {}        # pr_number -> rounds
    prs_with_reviews = set()
    pr_human_comment_count = {}  # pr_number -> count of human comments
    # (pr_number, reviewer_login, comment_text) for quote extraction
    pr_comment_details = []

    for i, pr in enumerate(prs_needing_detail):
        pr_number = pr["number"]
        detail = fetch_pr_details(repo_path, pr_number, timeout=args.timeout)
        if detail is None:
            continue

        # Count bot comments for stats
        for comment in detail.get("comments", []):
            if is_bot_author(comment.get("author")):
                bot_comment_count += 1
        for review in detail.get("reviews", []):
            if is_bot_author(review.get("author")):
                bot_comment_count += 1

        human_texts = extract_comment_texts(detail)
        if human_texts:
            prs_with_reviews.add(pr_number)
        pr_human_comment_count[pr_number] = len(human_texts)

        # Collect comment details (reviewer + text) for quote extraction
        for comment in detail.get("comments", []):
            if is_bot_author(comment.get("author")):
                continue
            body = (comment.get("body") or "").strip()
            author = comment.get("author") or {}
            login = (author.get("login") if isinstance(author, dict) else str(author)) or "unknown"
            if body:
                pr_comment_details.append((pr_number, login, body))
        for review in detail.get("reviews", []):
            if is_bot_author(review.get("author")):
                continue
            body = (review.get("body") or "").strip()
            author = review.get("author") or {}
            login = (author.get("login") if isinstance(author, dict) else str(author)) or "unknown"
            if body:
                pr_comment_details.append((pr_number, login, body))

        for text in human_texts:
            all_tagged_comments.append((pr_number, text))
            all_flat_comments.append(text)

        rounds = estimate_review_rounds(detail)
        if rounds > 0:
            pr_review_rounds[pr_number] = rounds

        # Rate limit protection
        if i < len(prs_needing_detail) - 1:
            time.sleep(API_DELAY)

    # Step 5: Filter duplicate comments
    duplicate_texts, dup_count = filter_duplicate_comments(all_flat_comments)
    bot_comment_count += dup_count

    # Step 6: Extract review themes
    review_themes = classify_comment_themes(all_tagged_comments, duplicate_texts)

    # Step 7: Average review rounds
    if pr_review_rounds:
        avg_rounds = round(
            sum(pr_review_rounds.values()) / len(pr_review_rounds), 1
        )
    else:
        avg_rounds = 0

    # Step 8: High friction PRs (most review rounds)
    high_friction = []
    for pr in prs:
        pr_number = pr["number"]
        rounds = pr_review_rounds.get(pr_number, 0)
        if rounds >= 3:
            # Count human comments for this PR
            human_count = len([
                (n, t) for n, t in all_tagged_comments
                if n == pr_number and t not in duplicate_texts
            ])
            high_friction.append({
                "number": pr_number,
                "title": pr.get("title", ""),
                "review_rounds": rounds,
                "human_comments": human_count,
            })
    high_friction.sort(key=lambda x: -x["review_rounds"])
    high_friction = high_friction[:20]  # Top 20

    # Step 9: Extract sample quotes from top 10 most-commented PRs
    top_commented_prs = sorted(
        pr_human_comment_count.items(), key=lambda x: -x[1]
    )[:10]
    top_pr_numbers = {pr_num for pr_num, _ in top_commented_prs}
    sample_quotes = []
    for pr_number, reviewer, text in pr_comment_details:
        if pr_number not in top_pr_numbers:
            continue
        if text in duplicate_texts:
            continue
        if len(text) <= 20:
            continue
        sample_quotes.append({
            "pr": pr_number,
            "reviewer": reviewer,
            "text": text[:200] + ("..." if len(text) > 200 else ""),
        })
        if len(sample_quotes) >= 20:
            break

    # Step 10: PR size stats
    size_stats = compute_size_stats(prs)

    # Step 11: Date range
    pr_dates = []
    for pr in prs:
        dt = parse_iso_date(pr.get("createdAt") or pr.get("mergedAt"))
        if dt:
            pr_dates.append(dt)

    if pr_dates:
        date_range = {
            "from": min(pr_dates).strftime("%Y-%m-%d"),
            "to": max(pr_dates).strftime("%Y-%m-%d"),
        }
    else:
        date_range = {
            "from": since_date.strftime("%Y-%m-%d"),
            "to": datetime.now().strftime("%Y-%m-%d"),
        }

    result = {
        "total_prs_analyzed": len(prs),
        "date_range": date_range,
        "prs_with_reviews": len(prs_with_reviews),
        "avg_review_rounds": avg_rounds,
        "review_themes": review_themes,
        "bot_comments_filtered": bot_comment_count,
        "high_friction_prs": high_friction[:15],
        "pr_size_stats": size_stats,
        "sample_quotes": sample_quotes,
    }

    # Cap sample_comments in review themes
    for theme in result.get("review_themes", []):
        if "sample_comments" in theme:
            theme["sample_comments"] = theme["sample_comments"][:5]
        if "prs" in theme:
            theme["prs"] = theme["prs"][:10]

    _write_output(result, args.output)


def _write_output(result, output_path):
    """Write result JSON to file or stdout."""
    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if output_path:
        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir and not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json + "\n")
        print(f"Output written to {output_path}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
