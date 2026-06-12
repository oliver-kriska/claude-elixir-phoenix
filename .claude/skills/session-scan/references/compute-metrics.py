#!/usr/bin/env python3
"""
Session Analytics v2 — Compute deterministic metrics from Claude Code sessions.

Reads ccrider message JSON and computes friction scores, fingerprints, plugin
opportunity scores, tool bigrams, file hotspots, and session chaining.

Usage:
    # Single session (outputs JSON to stdout)
    python3 compute-metrics.py <messages.json> --session-id ID --project NAME

    # Batch mode (appends to metrics.jsonl)
    python3 compute-metrics.py --batch <manifest.json>

    # Trends mode (computes windowed aggregates)
    python3 compute-metrics.py --trends <metrics.jsonl> [--memory MEMORY.md]

    # Backfill from v1 extracts
    python3 compute-metrics.py --backfill <extracts-dir/>
"""

import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone


# ─── Friction Score Weights ───────────────────────────────────────────────────

FRICTION_WEIGHTS = {
    "error_tool_ratio": 2.0,
    "retry_loops": 3.0,
    "user_corrections": 2.5,
    "approach_changes": 2.0,
    "context_compactions": 1.5,
    "interrupted_requests": 1.0,
}

# Sigmoid normalization: score = 1 / (1 + e^(-k*(raw - midpoint)))
FRICTION_SIGMOID_K = 3.0
FRICTION_SIGMOID_MIDPOINT = 1.5

# ─── Fingerprint Rules ───────────────────────────────────────────────────────

CORRECTION_PATTERNS = re.compile(
    r"\b(no[,.]?\s|wrong|instead|actually|that'?s not|not what I|"
    r"I meant|I said|please don'?t|stop|undo|revert)\b",
    re.IGNORECASE,
)

FINGERPRINT_KEYWORDS = {
    "bug-fix": re.compile(
        r"\b(fix|bug|broken|error|issue|crash|fail|debug|wrong)\b", re.IGNORECASE
    ),
    "feature": re.compile(
        r"\b(add|implement|build|create|new feature|scaffold)\b", re.IGNORECASE
    ),
    "exploration": re.compile(
        r"\b(explore|understand|how does|what is|explain|look at)\b", re.IGNORECASE
    ),
    "maintenance": re.compile(
        r"\b(deps?|update|upgrade|bump|version|migrate)\b", re.IGNORECASE
    ),
    "review": re.compile(
        r"\b(review|PR|pull request|code review|feedback)\b", re.IGNORECASE
    ),
    "refactoring": re.compile(
        r"\b(refactor|extract|rename|move|reorganize|clean ?up)\b", re.IGNORECASE
    ),
}

# ─── Plugin Opportunity Signals ───────────────────────────────────────────────

PHX_COMMAND_RE = re.compile(r"/phx:\w+")
SKILL_COMMAND_RE = re.compile(r"/(?:phx|ecto|lv):[a-z][a-z0-9_-]*")

# ─── Model Context Windows ────────────────────────────────────────────────────
# Inspired by badlogic / earendil-works/pi session-context-stats.mjs
# (https://github.com/earendil-works/pi/blob/main/scripts/session-context-stats.mjs)

MODEL_CONTEXT_WINDOWS = {
    "claude-opus-4-7": 200_000,
    "claude-opus-4-7[1m]": 1_000_000,
    "claude-opus-4-6": 200_000,
    "claude-opus-4-6[1m]": 1_000_000,
    "claude-sonnet-4-6": 200_000,
    "claude-sonnet-4-6[1m]": 1_000_000,
    "claude-sonnet-4-5": 200_000,
    "claude-haiku-4-5": 200_000,
    "claude-haiku-4-5-20251001": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
}


def get_context_window(model):
    """Look up context window for a model, with fuzzy matching."""
    if not model:
        return None
    if model in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[model]
    base = re.sub(r"\[1m\]$", "", model)
    if base in MODEL_CONTEXT_WINDOWS:
        return MODEL_CONTEXT_WINDOWS[base]
    for known, ctx in MODEL_CONTEXT_WINDOWS.items():
        if known in model:
            return ctx
    return None


def sigmoid(raw):
    """Apply sigmoid normalization to raw friction score."""
    return 1.0 / (1.0 + math.exp(-FRICTION_SIGMOID_K * (raw - FRICTION_SIGMOID_MIDPOINT)))


# ─── Message Parsing ─────────────────────────────────────────────────────────


def parse_messages(data):
    """Parse ccrider message JSON into structured lists.

    Accepts either:
    - A list of message objects (ccrider format)
    - A dict with a 'messages' key containing the list
    """
    if isinstance(data, dict):
        messages = data.get("messages", [])
    elif isinstance(data, list):
        messages = data
    else:
        return []
    return messages


def _get_role(msg):
    """Get message role, supporting both API format (role) and ccrider format (type)."""
    return msg.get("role", msg.get("type", msg.get("message", {}).get("role", "")))


def _get_content(msg):
    """Get message content, supporting both API and ccrider formats."""
    return msg.get("content", msg.get("message", {}).get("content", ""))


# Tool name detection from assistant text (ccrider doesn't preserve tool_use blocks)
TOOL_MENTION_RE = re.compile(
    r"\b(Read|Edit|Write|Bash|Grep|Glob|Task|NotebookEdit|WebFetch|WebSearch"
    r"|mcp__tidewave\w*)\b"
)
BASH_CMD_RE = re.compile(r"(?:^|\n)\s*(?:\$|>)\s*(mix\s|git\s|npm\s|python3?\s|cd\s|rm\s)")


def extract_tool_calls(messages):
    """Extract ordered list of tool calls from messages.

    For API format: extracts structured tool_use blocks.
    For ccrider format: infers tool names from assistant message text patterns.
    """
    tools = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = _get_content(msg)
        role = _get_role(msg)

        # API format: structured content blocks
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tools.append(block)

        # ccrider format: infer tools from assistant text
        elif isinstance(content, str) and role == "assistant":
            mentioned = TOOL_MENTION_RE.findall(content)
            for name in mentioned:
                tools.append({"name": name, "input": {}})
            # Detect bash commands in text
            if BASH_CMD_RE.search(content):
                tools.append({"name": "Bash", "input": {}})

    return tools


def extract_user_messages(messages):
    """Extract user message texts."""
    user_msgs = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = _get_role(msg)
        if role != "user":
            continue
        content = _get_content(msg)
        if isinstance(content, str):
            if not content.startswith("<system-reminder>") and not content.startswith(
                "<local-command-caveat>"
            ) and not content.startswith("<local-command-stdout>") and len(content) > 5:
                user_msgs.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    if not text.startswith("<system-reminder>") and not text.startswith(
                        "<command-name>"
                    ):
                        if len(text) > 5:
                            user_msgs.append(text)
    return user_msgs


def extract_errors(messages):
    """Extract tool errors from messages."""
    errors = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        content = _get_content(msg)
        role = _get_role(msg)

        # API format: structured error blocks
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "tool_result" and block.get("is_error"):
                        err = block.get("content", "")
                        if isinstance(err, str) and len(err) > 5:
                            errors.append(err[:200])

        # ccrider format: detect error patterns in assistant text
        elif isinstance(content, str) and role == "assistant":
            if re.search(r"\b(error|Error|ERROR|failed|Failed|FAILED)\b", content):
                if re.search(r"\b(compilation|compile|test|credo|format)\s+(error|fail)", content, re.I):
                    errors.append(content[:200])
    return errors


def extract_timestamps(messages):
    """Extract timestamps from messages."""
    timestamps = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        ts = msg.get("timestamp")
        if ts:
            timestamps.append(ts)
    return timestamps


def extract_token_usage(messages):
    """Extract per-turn token usage and model info.

    Works on raw Claude Code JSONL entries (which have `message.usage` blocks
    with cache_creation/cache_read breakdown). Returns None for ccrider-extracted
    data without usage info.

    Total prompt tokens per turn = input_tokens + cache_creation + cache_read.
    Compaction is inferred when prompt tokens drop >40% between consecutive turns.

    Extended fields (2026-05-23): cache TTL split (ephemeral_5m vs ephemeral_1h),
    per-turn hit rate array, cache decay events (TTL expiry vs compaction),
    per-model token breakdown, first-turn baseline.
    """
    turns = []
    models = []

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        inner = msg.get("message")
        if not isinstance(inner, dict):
            continue
        usage = inner.get("usage")
        if not isinstance(usage, dict):
            continue

        input_tokens = usage.get("input_tokens", 0) or 0
        cache_creation = usage.get("cache_creation_input_tokens", 0) or 0
        cache_read = usage.get("cache_read_input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        prompt_tokens = input_tokens + cache_creation + cache_read

        # Cache TTL split (1h extended vs default 5m). Absent in older sessions.
        cc_detail = usage.get("cache_creation") or {}
        cache_create_5m = cc_detail.get("ephemeral_5m_input_tokens", 0) or 0
        cache_create_1h = cc_detail.get("ephemeral_1h_input_tokens", 0) or 0

        # Per-turn hit rate: cached portion of incoming context this turn.
        denom = input_tokens + cache_creation + cache_read
        hit_rate = round(cache_read / denom, 4) if denom else 0.0

        model = inner.get("model")
        if model:
            models.append(model)

        turns.append({
            "model": model,
            "prompt_tokens": prompt_tokens,
            "input_tokens": input_tokens,
            "cache_creation_tokens": cache_creation,
            "cache_creation_5m": cache_create_5m,
            "cache_creation_1h": cache_create_1h,
            "cache_read_tokens": cache_read,
            "output_tokens": output_tokens,
            "hit_rate": hit_rate,
        })

    if not turns:
        return None

    prompt_seq = [t["prompt_tokens"] for t in turns]
    cache_read_seq = [t["cache_read_tokens"] for t in turns]
    cache_create_seq = [t["cache_creation_tokens"] for t in turns]
    max_prompt = max(prompt_seq)

    # Compaction events: prompt drops >40% (existing logic).
    compaction_events = 0
    compaction_turns = set()
    pre_compaction_max = max_prompt
    for i in range(1, len(prompt_seq)):
        if prompt_seq[i - 1] > 10_000 and prompt_seq[i] < prompt_seq[i - 1] * 0.6:
            if compaction_events == 0:
                pre_compaction_max = max(prompt_seq[:i])
            compaction_events += 1
            compaction_turns.add(i)

    # Cache decay events: cache_read drops >50% from prior turn AND not a
    # compaction AND prior turn had meaningful cache. Indicates TTL expiry.
    cache_decay_events = []
    for i in range(1, len(cache_read_seq)):
        prev_cr = cache_read_seq[i - 1]
        curr_cr = cache_read_seq[i]
        if prev_cr < 10_000 or i in compaction_turns:
            continue
        if curr_cr < prev_cr * 0.5:
            cache_decay_events.append({
                "turn_index": i,
                "prev_cache_read": prev_cr,
                "cache_read": curr_cr,
                "drop_pct": round((prev_cr - curr_cr) / prev_cr * 100, 1),
                "cache_creation_this_turn": cache_create_seq[i],
            })

    # Per-model breakdown: input/output/cache split by model (investigates
    # Sonnet/Haiku underuse vs Opus hypothesis from LinkedIn thread).
    model_breakdown = {}
    for t in turns:
        m = t["model"] or "unknown"
        b = model_breakdown.setdefault(m, {
            "turns": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        })
        b["turns"] += 1
        b["input_tokens"] += t["input_tokens"]
        b["output_tokens"] += t["output_tokens"]
        b["cache_creation_tokens"] += t["cache_creation_tokens"]
        b["cache_read_tokens"] += t["cache_read_tokens"]

    primary_model = Counter(models).most_common(1)[0][0] if models else None
    ctx_window = get_context_window(primary_model)
    max_ctx_pct = round(max_prompt / ctx_window * 100, 1) if ctx_window else None
    pre_compaction_ctx_pct = (
        round(pre_compaction_max / ctx_window * 100, 1) if ctx_window else None
    )

    total_input = sum(t["input_tokens"] for t in turns)
    total_output = sum(t["output_tokens"] for t in turns)
    total_cache_create = sum(t["cache_creation_tokens"] for t in turns)
    total_cache_create_5m = sum(t["cache_creation_5m"] for t in turns)
    total_cache_create_1h = sum(t["cache_creation_1h"] for t in turns)
    total_cache_read = sum(t["cache_read_tokens"] for t in turns)
    total_billable = total_input + total_cache_create + total_cache_read + total_output
    overall_hit_rate = (
        round(total_cache_read / total_billable, 4) if total_billable else 0.0
    )
    pct_1h_writes = (
        round(total_cache_create_1h / total_cache_create * 100, 1)
        if total_cache_create else None
    )

    # First-turn baseline = system prompt + tool defs + CLAUDE.md + memory.
    first_turn_baseline = turns[0]["cache_creation_tokens"] if turns else 0

    return {
        "primary_model": primary_model,
        "models_used": sorted(set(models)),
        "context_window": ctx_window,
        "turn_count_with_tokens": len(turns),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_creation_tokens": total_cache_create,
        "total_cache_creation_5m_tokens": total_cache_create_5m,
        "total_cache_creation_1h_tokens": total_cache_create_1h,
        "pct_1h_cache_writes": pct_1h_writes,
        "total_cache_read_tokens": total_cache_read,
        "overall_cache_hit_rate": overall_hit_rate,
        "per_turn_cache_hit_rates": [t["hit_rate"] for t in turns],
        "max_prompt_tokens": max_prompt,
        "max_ctx_pct": max_ctx_pct,
        "pre_compaction_max_tokens": pre_compaction_max,
        "pre_compaction_ctx_pct": pre_compaction_ctx_pct,
        "compaction_events_inferred": compaction_events,
        "cache_decay_events": cache_decay_events,
        "first_turn_baseline_tokens": first_turn_baseline,
        "model_breakdown": model_breakdown,
    }


# ─── Metric Computation ──────────────────────────────────────────────────────


def compute_friction(tool_calls, user_msgs, errors, messages):
    """Compute friction score (0.0-1.0) with signal breakdown."""
    tool_count = len(tool_calls)

    # Error-tool ratio
    error_count = len(errors)
    error_tool_ratio = error_count / max(tool_count, 1)

    # Retry loops: same command 3+ times with failures between
    retry_loops = 0
    bash_cmds = []
    for tc in tool_calls:
        name = tc.get("name", "")
        inp = tc.get("input", {})
        if name == "Bash":
            bash_cmds.append(inp.get("command", ""))
    # Detect consecutive similar commands
    window = []
    for cmd in bash_cmds:
        normalized = cmd.strip().split()[0] if cmd.strip() else ""
        if window and window[-1] == normalized:
            window.append(normalized)
        else:
            if len(window) >= 3:
                retry_loops += 1
            window = [normalized]
    if len(window) >= 3:
        retry_loops += 1

    # User corrections
    user_corrections = 0
    for text in user_msgs:
        if CORRECTION_PATTERNS.search(text[:500]):
            user_corrections += 1

    # Approach changes: detect tool pattern shifts (edit-heavy -> read-heavy)
    approach_changes = 0
    if len(tool_calls) >= 10:
        chunk_size = max(len(tool_calls) // 4, 5)
        chunks = [
            tool_calls[i : i + chunk_size]
            for i in range(0, len(tool_calls), chunk_size)
        ]
        prev_dominant = None
        for chunk in chunks:
            counts = Counter(tc.get("name", "") for tc in chunk)
            dominant = counts.most_common(1)[0][0] if counts else None
            if prev_dominant and dominant and prev_dominant != dominant:
                approach_changes += 1
            prev_dominant = dominant

    # Context compactions
    context_compactions = 0
    for msg in messages:
        content = _get_content(msg)
        if isinstance(content, str) and "context compaction" in content.lower():
            context_compactions += 1
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    if "context compaction" in block.get("text", "").lower():
                        context_compactions += 1

    # Interrupted requests
    interrupted_requests = 0
    for msg in messages:
        content = _get_content(msg)
        if isinstance(content, str):
            if "[Request interrupted by user]" in content:
                interrupted_requests += 1
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    if "[Request interrupted by user]" in block.get("text", ""):
                        interrupted_requests += 1

    signals = {
        "error_tool_ratio": round(error_tool_ratio, 3),
        "retry_loops": retry_loops,
        "user_corrections": user_corrections,
        "approach_changes": approach_changes,
        "context_compactions": context_compactions,
        "interrupted_requests": interrupted_requests,
    }

    # Weighted sum
    raw = sum(
        signals[k] * FRICTION_WEIGHTS[k]
        for k in FRICTION_WEIGHTS
    )

    score = round(sigmoid(raw), 3)
    return score, signals


def compute_fingerprint(user_msgs, tool_calls, files_edited):
    """Classify session type with confidence."""
    scores = defaultdict(float)

    user_text = " ".join(user_msgs[:10])  # First 10 messages for intent

    for fp_type, pattern in FINGERPRINT_KEYWORDS.items():
        matches = pattern.findall(user_text)
        scores[fp_type] += len(matches) * 2.0

    # Tool profile signals
    tool_names = [tc.get("name", "") for tc in tool_calls]
    tool_counts = Counter(tool_names)
    total = max(len(tool_names), 1)

    read_pct = (tool_counts.get("Read", 0) + tool_counts.get("Grep", 0) + tool_counts.get("Glob", 0)) / total
    edit_pct = (tool_counts.get("Edit", 0) + tool_counts.get("Write", 0)) / total
    bash_pct = tool_counts.get("Bash", 0) / total

    if read_pct > 0.5 and edit_pct < 0.1:
        scores["exploration"] += 3.0
    if edit_pct > 0.3:
        scores["feature"] += 2.0
    if bash_pct > 0.3:
        scores["bug-fix"] += 2.0
    if len(files_edited) > 10:
        scores["refactoring"] += 2.0
    if len(files_edited) > 5:
        scores["feature"] += 1.0

    # Tidewave signals
    tidewave_count = sum(1 for n in tool_names if n.startswith("mcp__tidewave"))
    if tidewave_count > 0:
        scores["bug-fix"] += 1.5

    # Mix deps signals
    bash_cmds = [tc.get("input", {}).get("command", "") for tc in tool_calls if tc.get("name") == "Bash"]
    deps_cmds = [c for c in bash_cmds if "mix deps" in c or "mix hex" in c]
    if deps_cmds:
        scores["maintenance"] += 3.0

    # gh pr signals
    pr_cmds = [c for c in bash_cmds if "gh pr" in c or "gh issue" in c]
    if pr_cmds:
        scores["review"] += 3.0

    if not scores:
        return "unknown", 0.0

    best = max(scores, key=scores.get)
    total_score = sum(scores.values())
    confidence = round(scores[best] / max(total_score, 1), 2)

    return best, confidence


def compute_plugin_opportunity(user_msgs, tool_calls, phx_commands):
    """Compute plugin opportunity score (0.0-1.0)."""
    could_use = []

    tool_names = [tc.get("name", "") for tc in tool_calls]
    tool_count = len(tool_names)
    bash_cmds = [tc.get("input", {}).get("command", "") for tc in tool_calls if tc.get("name") == "Bash"]

    # Retry loops suggest /phx:investigate
    consecutive = 0
    for i in range(1, len(bash_cmds)):
        if bash_cmds[i].split()[0:2] == bash_cmds[i - 1].split()[0:2] if bash_cmds[i].strip() else False:
            consecutive += 1
            if consecutive >= 2:
                could_use.append("investigate")
                break
        else:
            consecutive = 0

    # Many tools without plan suggest /phx:plan
    if tool_count > 50 and "plan" not in phx_commands:
        could_use.append("plan")

    # Multiple mix test runs suggest /phx:verify
    test_runs = sum(1 for c in bash_cmds if "mix test" in c or "mix compile" in c)
    if test_runs >= 3 and "verify" not in phx_commands:
        could_use.append("verify")

    # PR commands suggest /phx:pr-review
    pr_cmds = sum(1 for c in bash_cmds if "gh pr" in c)
    if pr_cmds >= 2 and "pr-review" not in phx_commands:
        could_use.append("pr-review")

    # Many edits without review suggest /phx:review
    edit_count = sum(1 for n in tool_names if n in ("Edit", "Write"))
    if edit_count > 10 and "review" not in phx_commands:
        could_use.append("review")

    score = min(len(could_use) * 0.2, 1.0)
    return round(score, 2), could_use


def compute_tool_profile(tool_calls):
    """Compute tool usage percentages."""
    names = [tc.get("name", "") for tc in tool_calls]
    total = max(len(names), 1)
    counts = Counter(names)

    read_count = counts.get("Read", 0) + counts.get("Glob", 0)
    edit_count = counts.get("Edit", 0) + counts.get("Write", 0)
    bash_count = counts.get("Bash", 0)
    grep_count = counts.get("Grep", 0)
    tidewave_count = sum(v for k, v in counts.items() if k.startswith("mcp__tidewave"))
    other_count = total - read_count - edit_count - bash_count - grep_count - tidewave_count

    return {
        "read_pct": round(read_count / total * 100, 1),
        "edit_pct": round(edit_count / total * 100, 1),
        "bash_pct": round(bash_count / total * 100, 1),
        "grep_pct": round(grep_count / total * 100, 1),
        "tidewave_pct": round(tidewave_count / total * 100, 1),
        "other_pct": round(max(other_count, 0) / total * 100, 1),
    }


def compute_tool_bigrams(tool_calls, top_n=15):
    """Extract top tool sequence pairs."""
    names = [tc.get("name", "") for tc in tool_calls]
    bigrams = Counter()
    for i in range(len(names) - 1):
        pair = f"{names[i]}->{names[i+1]}"
        bigrams[pair] += 1
    return dict(bigrams.most_common(top_n))


def compute_file_hotspots(tool_calls, top_n=10):
    """Count reads/edits per file path."""
    hotspots = defaultdict(lambda: {"reads": 0, "edits": 0})
    for tc in tool_calls:
        name = tc.get("name", "")
        inp = tc.get("input", {})
        fp = inp.get("file_path", "")
        if not fp:
            continue
        if name in ("Read", "Glob"):
            hotspots[fp]["reads"] += 1
        elif name in ("Edit", "Write"):
            hotspots[fp]["edits"] += 1

    ranked = sorted(
        hotspots.items(),
        key=lambda x: x[1]["reads"] + x[1]["edits"],
        reverse=True,
    )[:top_n]

    return [{"path": p, **counts} for p, counts in ranked]


def compute_duration(timestamps):
    """Compute session duration in minutes from timestamps."""
    if len(timestamps) < 2:
        return None
    try:
        first, last = timestamps[0], timestamps[-1]
        if isinstance(first, str) and isinstance(last, str):
            t1 = datetime.fromisoformat(first.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(last.replace("Z", "+00:00"))
            return round((t2 - t1).total_seconds() / 60, 1)
        elif isinstance(first, (int, float)) and isinstance(last, (int, float)):
            return round((last - first) / 60000, 1)
    except (ValueError, TypeError):
        pass
    return None


def categorize_files(files):
    """Categorize files by type (preserved from v1 extract-session.py)."""
    categories = Counter()
    for fp in files:
        if "_live.ex" in fp or "_live/" in fp:
            categories["liveview"] += 1
        elif "_test.exs" in fp:
            categories["test"] += 1
        elif "/migrations/" in fp:
            categories["migration"] += 1
        elif "_worker.ex" in fp or "/workers/" in fp:
            categories["oban_worker"] += 1
        elif "/contexts/" in fp or (fp.endswith(".ex") and "/lib/" in fp):
            categories["context_or_module"] += 1
        elif fp.endswith(".heex"):
            categories["template"] += 1
        elif "router.ex" in fp:
            categories["router"] += 1
        elif fp.endswith(".js") or fp.endswith(".ts"):
            categories["javascript"] += 1
        elif fp.endswith(".css"):
            categories["css"] += 1
        else:
            categories["other"] += 1
    return dict(categories)


# ─── Skill Effectiveness ─────────────────────────────────────────────────────


def _locate_skill_invocations(user_msgs, all_messages):
    """Find skill invocations and their position in the message stream.

    Returns list of {skill, msg_index, user_msg_index} for each invocation.
    """
    invocations = []
    user_idx = 0
    for i, msg in enumerate(all_messages):
        if not isinstance(msg, dict):
            continue
        role = _get_role(msg)
        content = _get_content(msg)
        if role != "user":
            continue
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            user_idx += 1
            continue

        if text.startswith("Base directory for this skill:"):
            user_idx += 1
            continue

        cmds = SKILL_COMMAND_RE.findall(text)
        for cmd in cmds:
            if "{" in cmd or "<" in cmd:
                continue
            invocations.append({
                "skill": cmd,
                "msg_index": i,
                "user_msg_index": user_idx,
            })
        user_idx += 1
    return invocations


def compute_skill_effectiveness(user_msgs, tool_calls, errors, messages):
    """Compute per-skill effectiveness signals.

    For each skill invocation, measures what happened before and after:
    - Pre/post error rates
    - Post-skill edit count (did the skill lead to action?)
    - Post-skill test runs (did the user verify?)
    - Whether user corrections followed (skill didn't help)
    - Time-to-action (how quickly edits followed)

    Returns dict keyed by skill command name.
    """
    invocations = _locate_skill_invocations(user_msgs, messages)
    if not invocations:
        return {}

    # Build tool call index: map message index -> tool calls in that range
    total_msgs = len(messages)

    # Extract tool_calls with message positions
    tool_positions = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        content = _get_content(msg)
        role = _get_role(msg)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_positions.append({"msg_index": i, "tc": block})
        elif isinstance(content, str) and role == "assistant":
            mentioned = TOOL_MENTION_RE.findall(content)
            for name in mentioned:
                tool_positions.append({
                    "msg_index": i,
                    "tc": {"name": name, "input": {}},
                })

    results = {}
    for inv in invocations:
        skill = inv["skill"]
        msg_idx = inv["msg_index"]

        # Collect tools after this skill invocation
        post_tools = [tp for tp in tool_positions if tp["msg_index"] > msg_idx]

        # Window: next 50 tool calls after invocation (or until next skill)
        next_skill_idx = total_msgs
        for other in invocations:
            if other["msg_index"] > msg_idx:
                next_skill_idx = min(next_skill_idx, other["msg_index"])
                break
        window_tools = [tp for tp in post_tools if tp["msg_index"] < next_skill_idx][:50]

        # Count post-skill signals
        post_edits = sum(
            1 for tp in window_tools if tp["tc"].get("name") in ("Edit", "Write")
        )
        post_reads = sum(
            1 for tp in window_tools if tp["tc"].get("name") in ("Read", "Grep", "Glob")
        )
        # For API-format: check input.command; for ccrider-format: check surrounding text
        post_test_runs = 0
        for tp in window_tools:
            if tp["tc"].get("name") != "Bash":
                continue
            cmd = tp["tc"].get("input", {}).get("command", "")
            if cmd and "mix test" in cmd:
                post_test_runs += 1
            elif not cmd:
                # ccrider-format: tool input is empty, check assistant text at this position
                mi = tp["msg_index"]
                if mi < len(messages) and isinstance(messages[mi], dict):
                    text = _get_content(messages[mi])
                    if isinstance(text, str) and "mix test" in text:
                        post_test_runs += 1

        # Post-skill errors (from messages in the window)
        window_msgs = [
            m for j, m in enumerate(messages)
            if isinstance(m, dict)
            and j > msg_idx
            and j < next_skill_idx
        ]
        post_errors = len(extract_errors(window_msgs))

        # Post-skill user corrections
        post_corrections = 0
        for m in window_msgs:
            content = _get_content(m)
            role = _get_role(m)
            if role == "user" and isinstance(content, str):
                if CORRECTION_PATTERNS.search(content[:500]):
                    post_corrections += 1

        # Led to action: skill resulted in edits or test runs
        led_to_action = post_edits > 0 or post_test_runs > 0

        # Outcome heuristic
        if post_errors == 0 and post_corrections == 0 and led_to_action:
            outcome = "effective"
        elif post_corrections > 0 or post_errors > 3:
            outcome = "friction"
        elif not led_to_action:
            outcome = "no_action"
        else:
            outcome = "mixed"

        # Store per-skill (aggregate if same skill invoked multiple times)
        if skill not in results:
            results[skill] = {
                "invocation_count": 0,
                "total_post_edits": 0,
                "total_post_reads": 0,
                "total_post_test_runs": 0,
                "total_post_errors": 0,
                "total_post_corrections": 0,
                "led_to_action_count": 0,
                "outcomes": [],
            }

        r = results[skill]
        r["invocation_count"] += 1
        r["total_post_edits"] += post_edits
        r["total_post_reads"] += post_reads
        r["total_post_test_runs"] += post_test_runs
        r["total_post_errors"] += post_errors
        r["total_post_corrections"] += post_corrections
        if led_to_action:
            r["led_to_action_count"] += 1
        r["outcomes"].append(outcome)

    # Compute summary metrics per skill
    for skill, r in results.items():
        n = r["invocation_count"]
        r["action_rate"] = round(r["led_to_action_count"] / max(n, 1), 2)
        r["avg_post_errors"] = round(r["total_post_errors"] / max(n, 1), 2)
        r["avg_post_corrections"] = round(r["total_post_corrections"] / max(n, 1), 2)
        # Dominant outcome
        outcome_counts = Counter(r["outcomes"])
        r["dominant_outcome"] = outcome_counts.most_common(1)[0][0] if outcome_counts else "unknown"

    return results


# ─── Main Metric Pipeline ────────────────────────────────────────────────────


def compute_session_metrics(data, session_id, project, date=None):
    """Compute all metrics for a single session."""
    messages = parse_messages(data)
    tool_calls = extract_tool_calls(messages)
    user_msgs = extract_user_messages(messages)
    errors = extract_errors(messages)
    timestamps = extract_timestamps(messages)

    # Extract files edited/read
    files_edited = set()
    files_read = set()
    for tc in tool_calls:
        name = tc.get("name", "")
        fp = tc.get("input", {}).get("file_path", "")
        if not fp:
            continue
        if name in ("Edit", "Write"):
            files_edited.add(fp)
        elif name == "Read":
            files_read.add(fp)

    # Extract phx commands from user messages
    phx_commands = []
    for text in user_msgs:
        if not text.startswith("Base directory for this skill:"):
            cmds = PHX_COMMAND_RE.findall(text)
            cmds = [c for c in cmds if "{" not in c and "<" not in c]
            phx_commands.extend(cmds)

    # Tidewave detection
    tool_names = [tc.get("name", "") for tc in tool_calls]
    tidewave_available = any(n.startswith("mcp__tidewave") for n in tool_names)
    tidewave_used = tidewave_available  # If calls exist, it was used

    friction_score, friction_signals = compute_friction(
        tool_calls, user_msgs, errors, messages
    )
    fingerprint, fp_confidence = compute_fingerprint(
        user_msgs, tool_calls, list(files_edited)
    )
    opportunity_score, could_use = compute_plugin_opportunity(
        user_msgs, tool_calls, [c.replace("/phx:", "") for c in phx_commands]
    )
    tool_profile = compute_tool_profile(tool_calls)
    bigrams = compute_tool_bigrams(tool_calls)
    hotspots = compute_file_hotspots(tool_calls)
    duration = compute_duration(timestamps)
    skill_effectiveness = compute_skill_effectiveness(
        user_msgs, tool_calls, errors, messages
    )
    token_usage = extract_token_usage(messages)

    # Tier 2 eligibility
    tier2_reasons = []
    if friction_score > 0.35:
        tier2_reasons.append("friction > 0.35")
    if opportunity_score > 0.5:
        tier2_reasons.append("opportunity > 0.5")
    if phx_commands:
        tier2_reasons.append("plugin commands used")
    if len(user_msgs) > 50:
        tier2_reasons.append("message_count > 50")
    if token_usage and (token_usage.get("max_ctx_pct") or 0) >= 90:
        tier2_reasons.append("max_ctx_pct >= 90")
    tier2_eligible = len(tier2_reasons) > 0

    return {
        "session_id": session_id,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "project": project,
        "date": date or (timestamps[0][:10] if timestamps and isinstance(timestamps[0], str) else None),
        "duration_minutes": duration,
        "message_count": len(user_msgs),
        "tool_count": len(tool_calls),
        "fingerprint": fingerprint,
        "fingerprint_confidence": fp_confidence,
        "friction_score": friction_score,
        "friction_signals": friction_signals,
        "plugin_opportunity_score": opportunity_score,
        "plugin_signals": {
            "phx_commands_used": list(set(phx_commands)),
            "could_use": could_use,
            "tidewave_available": tidewave_available,
            "tidewave_used": tidewave_used,
        },
        "tool_profile": tool_profile,
        "tool_bigrams": bigrams,
        "file_hotspots": hotspots,
        "file_categories": categorize_files(list(files_edited)),
        "skill_effectiveness": skill_effectiveness,
        "token_usage": token_usage,
        "session_chain": {"previous_session_id": None, "chain_length": 1},
        "tier2_eligible": tier2_eligible,
        "tier2_reason": " AND ".join(tier2_reasons) if tier2_reasons else None,
        "tier2_completed": False,
    }


# ─── Backfill from v1 Extracts ───────────────────────────────────────────────


def backfill_from_v1(extract_path):
    """Compute v2 metrics from a v1 extract JSON file.

    v1 extracts have tool_usage, user_messages, phx_commands, errors, etc.
    Some v2 signals (user corrections, approach changes) are approximated.
    """
    with open(extract_path) as f:
        v1 = json.load(f)

    session_id = v1.get("session_id", os.path.basename(extract_path).replace(".json", ""))
    project = v1.get("project", "unknown")
    tool_usage = v1.get("tool_usage", {})
    total_tools = sum(tool_usage.values())

    # Approximate friction from available v1 data
    error_count = len(v1.get("errors", []))
    error_tool_ratio = round(error_count / max(total_tools, 1), 3)

    # User corrections approximation from user messages
    user_msgs = v1.get("user_messages", [])
    user_corrections = sum(
        1 for text in user_msgs if CORRECTION_PATTERNS.search(text[:500])
    )

    friction_signals = {
        "error_tool_ratio": error_tool_ratio,
        "retry_loops": 0,  # Can't reliably detect from v1 extracts
        "user_corrections": user_corrections,
        "approach_changes": 0,
        "context_compactions": 0,
        "interrupted_requests": 0,
    }
    raw = sum(friction_signals[k] * FRICTION_WEIGHTS[k] for k in FRICTION_WEIGHTS)
    friction_score = round(sigmoid(raw), 3)

    # Fingerprint from v1 data
    user_text = " ".join(user_msgs[:10])
    scores = defaultdict(float)
    for fp_type, pattern in FINGERPRINT_KEYWORDS.items():
        matches = pattern.findall(user_text)
        scores[fp_type] += len(matches) * 2.0

    # Tool profile from v1 tool_usage
    read_count = tool_usage.get("Read", 0) + tool_usage.get("Glob", 0)
    edit_count = tool_usage.get("Edit", 0) + tool_usage.get("Write", 0)
    bash_count = tool_usage.get("Bash", 0)
    grep_count = tool_usage.get("Grep", 0)
    tidewave_count = sum(v for k, v in tool_usage.items() if k.startswith("mcp__tidewave"))

    if read_count / max(total_tools, 1) > 0.5 and edit_count / max(total_tools, 1) < 0.1:
        scores["exploration"] += 3.0
    if edit_count / max(total_tools, 1) > 0.3:
        scores["feature"] += 2.0
    if bash_count / max(total_tools, 1) > 0.3:
        scores["bug-fix"] += 2.0

    best = max(scores, key=scores.get) if scores else "unknown"
    total_score = sum(scores.values())
    fp_confidence = round(scores.get(best, 0) / max(total_score, 1), 2) if scores else 0.0

    # Plugin opportunity from v1 phx_commands
    phx_commands = v1.get("phx_commands", [])
    could_use = []
    if total_tools > 50 and not phx_commands:
        could_use.append("plan")
    mix_cmds = v1.get("mix_commands", [])
    test_runs = sum(1 for c in mix_cmds if "mix test" in c or "mix compile" in c)
    if test_runs >= 3:
        could_use.append("verify")

    opportunity_score = min(len(could_use) * 0.2, 1.0)

    other_count = max(total_tools - read_count - edit_count - bash_count - grep_count - tidewave_count, 0)

    return {
        "session_id": session_id,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "backfilled": True,
        "project": project,
        "date": None,
        "duration_minutes": v1.get("duration_minutes"),
        "message_count": v1.get("user_message_count", len(user_msgs)),
        "tool_count": total_tools,
        "fingerprint": best,
        "fingerprint_confidence": fp_confidence,
        "friction_score": friction_score,
        "friction_signals": friction_signals,
        "plugin_opportunity_score": round(opportunity_score, 2),
        "plugin_signals": {
            "phx_commands_used": phx_commands,
            "could_use": could_use,
            "tidewave_available": bool(v1.get("tidewave_usage")),
            "tidewave_used": bool(v1.get("tidewave_usage")),
        },
        "tool_profile": {
            "read_pct": round(read_count / max(total_tools, 1) * 100, 1),
            "edit_pct": round(edit_count / max(total_tools, 1) * 100, 1),
            "bash_pct": round(bash_count / max(total_tools, 1) * 100, 1),
            "grep_pct": round(grep_count / max(total_tools, 1) * 100, 1),
            "tidewave_pct": round(tidewave_count / max(total_tools, 1) * 100, 1),
            "other_pct": round(other_count / max(total_tools, 1) * 100, 1),
        },
        "tool_bigrams": {},
        "file_hotspots": [],
        "file_categories": v1.get("file_categories", {}),
        "skill_effectiveness": {},
        "token_usage": None,
        "session_chain": {"previous_session_id": None, "chain_length": 1},
        "tier2_eligible": friction_score > 0.35 or opportunity_score > 0.5,
        "tier2_reason": None,
        "tier2_completed": False,
    }


# ─── Raw JSONL Token/Context Scanner ─────────────────────────────────────────
# Inspired by badlogic / earendil-works/pi session-context-stats.mjs.
# PI's script focuses purely on context-window economics; this mode brings
# the same per-day / per-model / threshold-bucket view to our pipeline.


def scan_raw_jsonl(jsonl_dir, since_dt=None):
    """Scan raw Claude Code JSONL session files for token/context metrics.

    Returns list of per-session summaries. Skips files without `message.usage`
    blocks (e.g. legacy or non-assistant traffic only).
    """
    results = []
    if not os.path.isdir(jsonl_dir):
        return results

    for fname in sorted(os.listdir(jsonl_dir)):
        if not fname.endswith(".jsonl"):
            continue
        fpath = os.path.join(jsonl_dir, fname)
        if since_dt:
            try:
                mtime = datetime.fromtimestamp(
                    os.path.getmtime(fpath), tz=timezone.utc
                )
                if mtime < since_dt:
                    continue
            except OSError:
                continue

        messages = []
        first_ts = None
        last_ts = None
        try:
            with open(fpath, errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    messages.append(e)
                    ts = e.get("timestamp")
                    if isinstance(ts, str):
                        if first_ts is None:
                            first_ts = ts
                        last_ts = ts
        except OSError:
            continue

        if not messages:
            continue

        usage = extract_token_usage(messages)
        if not usage:
            continue

        duration = None
        if first_ts and last_ts:
            try:
                t1 = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                duration = round((t2 - t1).total_seconds() / 60, 1)
            except (ValueError, TypeError):
                pass

        sid = fname.replace(".jsonl", "")
        results.append({
            "session_id": sid,
            "date": first_ts[:10] if isinstance(first_ts, str) else None,
            "duration_minutes": duration,
            "turns": usage["turn_count_with_tokens"],
            "primary_model": usage["primary_model"],
            "models_used": usage["models_used"],
            "context_window": usage["context_window"],
            "max_prompt_tokens": usage["max_prompt_tokens"],
            "max_ctx_pct": usage["max_ctx_pct"],
            "pre_compaction_max_tokens": usage["pre_compaction_max_tokens"],
            "pre_compaction_ctx_pct": usage["pre_compaction_ctx_pct"],
            "compaction_events": usage["compaction_events_inferred"],
            "total_input_tokens": usage["total_input_tokens"],
            "total_output_tokens": usage["total_output_tokens"],
            "total_cache_creation_tokens": usage["total_cache_creation_tokens"],
            "total_cache_read_tokens": usage["total_cache_read_tokens"],
        })
    return results


def _median(values):
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def aggregate_ctx_scan(sessions):
    """Compute totals + per-day + per-model aggregates from scan_raw_jsonl output."""
    if not sessions:
        return {"count": 0, "totals": {}, "by_day": {}, "by_model": {}}

    def _agg(group):
        ctx_pcts = [s["max_ctx_pct"] for s in group if s["max_ctx_pct"] is not None]
        pre_pcts = [
            s["pre_compaction_ctx_pct"]
            for s in group
            if s["pre_compaction_ctx_pct"] is not None
        ]
        durations = [s["duration_minutes"] for s in group if s["duration_minutes"]]
        return {
            "count": len(group),
            "avg_turns": round(sum(s["turns"] for s in group) / len(group), 1),
            "avg_duration_min": round(sum(durations) / len(durations), 1) if durations else None,
            "avg_max_tokens": round(sum(s["max_prompt_tokens"] for s in group) / len(group)),
            "med_max_ctx_pct": round(_median(ctx_pcts), 1) if ctx_pcts else None,
            "avg_max_ctx_pct": round(sum(ctx_pcts) / len(ctx_pcts), 1) if ctx_pcts else None,
            "med_pre_compact_ctx_pct": round(_median(pre_pcts), 1) if pre_pcts else None,
            "over_80_pct_count": sum(1 for p in ctx_pcts if p >= 80),
            "over_90_pct_count": sum(1 for p in ctx_pcts if p >= 90),
            "over_100_pct_count": sum(1 for p in ctx_pcts if p >= 100),
            "compaction_rate_pct": round(
                sum(1 for s in group if s["compaction_events"] > 0) / len(group) * 100, 1
            ),
        }

    by_day = defaultdict(list)
    by_model = defaultdict(list)
    for s in sessions:
        if s["date"]:
            by_day[s["date"]].append(s)
        if s["primary_model"]:
            by_model[s["primary_model"]].append(s)

    return {
        "count": len(sessions),
        "totals": _agg(sessions),
        "by_day": {d: _agg(g) for d, g in sorted(by_day.items())},
        "by_model": {m: _agg(g) for m, g in sorted(by_model.items())},
    }


# ─── ASCII / HTML Rendering ──────────────────────────────────────────────────
# Bar-chart styling and HTML preformatted-text layout follow PI's
# session-context-stats.mjs report (badlogic / earendil-works/pi).


def render_ascii_bar(value, max_value, width=40):
    """Render a horizontal bar using full/empty block characters."""
    if value is None or max_value is None or max_value <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, value / max_value))
    filled = round(ratio * width)
    return "█" * filled + "░" * (width - filled)


def render_ctx_scan_text(scan_result):
    """Render scan_raw_jsonl + aggregate result as plain-text report."""
    lines = []
    t = scan_result["totals"]
    if not t:
        return "No sessions with token usage found."

    lines.append("─── Totals " + "─" * 60)
    lines.append(
        f"  sessions: {t['count']}   avg_turns: {t['avg_turns']}   "
        f"avg_duration: {t['avg_duration_min'] or '-'} min"
    )
    lines.append(
        f"  avg_max_tokens: {t['avg_max_tokens']:,}   "
        f"med_max_ctx: {t['med_max_ctx_pct']}%   "
        f"med_pre_compact: {t['med_pre_compact_ctx_pct']}%"
    )
    lines.append(
        f"  >=80%: {t['over_80_pct_count']}   >=90%: {t['over_90_pct_count']}   "
        f">=100%: {t['over_100_pct_count']}   compaction_rate: {t['compaction_rate_pct']}%"
    )
    lines.append(
        "  ctx usage: " + render_ascii_bar(t["med_max_ctx_pct"] or 0, 100)
        + f"  {t['med_max_ctx_pct'] or 0}%"
    )

    lines.append("")
    lines.append("─── By Day " + "─" * 60)
    lines.append(
        f"  {'date':<12} {'n':>4} {'turns':>6} {'maxTok':>9} "
        f"{'medCtx%':>8} {'>=90':>5}   bar"
    )
    for d, g in scan_result["by_day"].items():
        bar = render_ascii_bar(g["med_max_ctx_pct"] or 0, 100)
        lines.append(
            f"  {d:<12} {g['count']:>4} {g['avg_turns']:>6} "
            f"{g['avg_max_tokens']:>9,} {(g['med_max_ctx_pct'] or 0):>7}% "
            f"{g['over_90_pct_count']:>5}   {bar}"
        )

    lines.append("")
    lines.append("─── By Model " + "─" * 58)
    lines.append(
        f"  {'model':<35} {'n':>4} {'turns':>6} {'maxTok':>9} "
        f"{'medCtx%':>8} {'>=90':>5}   bar"
    )
    for m, g in scan_result["by_model"].items():
        bar = render_ascii_bar(g["med_max_ctx_pct"] or 0, 100)
        lines.append(
            f"  {m:<35} {g['count']:>4} {g['avg_turns']:>6} "
            f"{g['avg_max_tokens']:>9,} {(g['med_max_ctx_pct'] or 0):>7}% "
            f"{g['over_90_pct_count']:>5}   {bar}"
        )

    return "\n".join(lines)


def render_trends_text(trends_result):
    """Render compute_trends() output as plain-text report with bars."""
    lines = []
    lines.append(f"Total sessions: {trends_result.get('total_sessions', 0)}")
    lines.append(f"Computed at: {trends_result.get('computed_at', '-')}")
    lines.append("")

    windows = trends_result.get("windows", {})
    lines.append("─── Window Comparison " + "─" * 50)
    lines.append(
        f"  {'metric':<28} {'7d':>8} {'30d':>8} {'all':>8}"
    )
    rows = [
        ("sessions", "count"),
        ("avg friction", "avg_friction"),
        ("max friction", "max_friction"),
        ("avg opportunity", "avg_opportunity"),
        ("tier2 eligible %", "tier2_eligible_pct"),
        ("plugin adoption %", "plugin_adoption_rate"),
    ]
    for label, key in rows:
        v7 = windows.get("7d", {}).get(key, "-")
        v30 = windows.get("30d", {}).get(key, "-")
        vall = windows.get("all", {}).get(key, "-")
        lines.append(f"  {label:<28} {str(v7):>8} {str(v30):>8} {str(vall):>8}")

    # Friction bar (all-time vs 30d vs 7d)
    lines.append("")
    lines.append("─── Friction trend (avg, 0–1 scale) " + "─" * 35)
    for w in ("all", "30d", "7d"):
        v = windows.get(w, {}).get("avg_friction", 0) or 0
        lines.append(f"  {w:<5} {render_ascii_bar(v, 1.0)}  {v}")

    # Fingerprints
    lines.append("")
    lines.append("─── Fingerprint Distribution (all-time) " + "─" * 32)
    fps = windows.get("all", {}).get("fingerprint_distribution", {})
    fp_max = max(fps.values()) if fps else 1
    for fp, n in fps.items():
        lines.append(f"  {fp:<14} {render_ascii_bar(n, fp_max)}  {n}")

    # Per-model token aggregates (if any entries had token_usage)
    by_model = trends_result.get("by_model", {})
    if by_model:
        lines.append("")
        lines.append("─── By Model (token usage) " + "─" * 45)
        lines.append(
            f"  {'model':<35} {'n':>4} {'medCtx%':>8} {'>=90':>5}   bar"
        )
        for m, g in by_model.items():
            bar = render_ascii_bar(g.get("med_max_ctx_pct") or 0, 100)
            lines.append(
                f"  {m:<35} {g['count']:>4} "
                f"{(g.get('med_max_ctx_pct') or 0):>7}% "
                f"{g.get('over_90_pct_count', 0):>5}   {bar}"
            )

    mc = trends_result.get("memory_comparison")
    if mc:
        lines.append("")
        lines.append("─── MEMORY.md Comparison " + "─" * 47)
        for k, v in mc.items():
            lines.append(f"  {k:<32} {v}")

    return "\n".join(lines)


def render_html_report(title, body_text, generated_at):
    """Wrap pre-formatted body text in a minimal HTML page."""
    safe_body = (
        body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">\n"
        f"<title>{title}</title>\n"
        "<style>\n"
        "  body { font: 13px/1.5 ui-monospace, \"SF Mono\", Menlo, monospace;\n"
        "         background: #f7f7f7; color: #222; margin: 0; padding: 24px; }\n"
        "  h1 { font-size: 18px; margin: 0 0 4px; }\n"
        "  .meta { color: #666; font-size: 12px; margin-bottom: 16px; }\n"
        "  pre { background: white; padding: 16px; border: 1px solid #ddd;\n"
        "        border-radius: 4px; overflow-x: auto; }\n"
        "  .footer { margin-top: 12px; font-size: 11px; color: #888; }\n"
        "  a { color: #555; }\n"
        "</style></head><body>\n"
        f"<h1>{title}</h1>\n"
        f"<div class=\"meta\">Generated {generated_at}</div>\n"
        f"<pre>{safe_body}</pre>\n"
        "<div class=\"footer\">Bar-chart layout inspired by "
        "<a href=\"https://github.com/earendil-works/pi/blob/main/scripts/session-context-stats.mjs\">"
        "badlogic / earendil-works/pi session-context-stats.mjs</a>.</div>\n"
        "</body></html>\n"
    )


# ─── Trends Computation ──────────────────────────────────────────────────────


def compute_trends(metrics_path, memory_path=None, project_filter=None):
    """Compute windowed aggregates from metrics.jsonl."""
    entries = []
    with open(metrics_path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    if project_filter:
                        proj = entry.get("project", "")
                        if project_filter.lower() not in proj.lower():
                            continue
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue

    if not entries:
        return {"error": "No metrics found", "total_sessions": 0}

    now = datetime.now(timezone.utc)
    windows = {
        "7d": now - timedelta(days=7),
        "30d": now - timedelta(days=30),
        "all": datetime(2000, 1, 1, tzinfo=timezone.utc),
    }

    def parse_date(entry):
        d = entry.get("date") or entry.get("scanned_at", "")
        if not d:
            return None
        try:
            dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            try:
                return datetime.strptime(d[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                return None

    trends = {}
    for window_name, cutoff in windows.items():
        window_entries = [
            e for e in entries if (parse_date(e) or datetime(2000, 1, 1, tzinfo=timezone.utc)) >= cutoff
        ]
        if not window_entries:
            trends[window_name] = {"count": 0}
            continue

        frictions = [e.get("friction_score") or 0 for e in window_entries]
        opportunities = [e.get("plugin_opportunity_score") or 0 for e in window_entries]
        fingerprints = Counter(e.get("fingerprint", "unknown") for e in window_entries)
        tier2_count = sum(1 for e in window_entries if e.get("tier2_eligible"))
        phx_users = sum(1 for e in window_entries if e.get("plugin_signals", {}).get("phx_commands_used"))
        backfilled = sum(1 for e in window_entries if e.get("backfilled"))

        trends[window_name] = {
            "count": len(window_entries),
            "backfilled_count": backfilled,
            "avg_friction": round(sum(frictions) / len(frictions), 3),
            "max_friction": round(max(frictions), 3),
            "avg_opportunity": round(sum(opportunities) / len(opportunities), 3),
            "fingerprint_distribution": dict(fingerprints.most_common()),
            "tier2_eligible_count": tier2_count,
            "tier2_eligible_pct": round(tier2_count / len(window_entries) * 100, 1),
            "plugin_adoption_rate": round(phx_users / len(window_entries) * 100, 1),
        }

    # Memory comparison (if provided)
    memory_comparison = None
    if memory_path and os.path.exists(memory_path):
        with open(memory_path) as f:
            memory_text = f.read()
        memory_comparison = {
            "plugin_adoption_memory": "8-12%" if "8-12%" in memory_text else "unknown",
            "plugin_adoption_measured": f"{trends.get('all', {}).get('plugin_adoption_rate', 0)}%",
        }

    # Per-model aggregates (only entries with token_usage have model info)
    by_model = defaultdict(list)
    for e in entries:
        tu = e.get("token_usage") or {}
        model = tu.get("primary_model")
        if not model:
            continue
        by_model[model].append({
            "max_ctx_pct": tu.get("max_ctx_pct"),
            "max_prompt_tokens": tu.get("max_prompt_tokens", 0),
            "compaction_events": tu.get("compaction_events_inferred", 0),
            "friction_score": e.get("friction_score") or 0,
            "plugin_opportunity_score": e.get("plugin_opportunity_score") or 0,
        })

    by_model_summary = {}
    for model, group in by_model.items():
        ctx_pcts = [g["max_ctx_pct"] for g in group if g["max_ctx_pct"] is not None]
        by_model_summary[model] = {
            "count": len(group),
            "avg_friction": round(sum(g["friction_score"] for g in group) / len(group), 3),
            "avg_opportunity": round(
                sum(g["plugin_opportunity_score"] for g in group) / len(group), 3
            ),
            "med_max_ctx_pct": round(_median(ctx_pcts), 1) if ctx_pcts else None,
            "avg_max_tokens": round(sum(g["max_prompt_tokens"] for g in group) / len(group)),
            "over_90_pct_count": sum(1 for p in ctx_pcts if p >= 90),
            "compaction_rate_pct": round(
                sum(1 for g in group if g["compaction_events"] > 0) / len(group) * 100, 1
            ),
        }

    return {
        "computed_at": now.isoformat(),
        "total_sessions": len(entries),
        "windows": trends,
        "by_model": by_model_summary,
        "memory_comparison": memory_comparison,
    }


# ─── Batch Mode ──────────────────────────────────────────────────────────────


def run_batch(manifest_path):
    """Process multiple sessions from a manifest file.

    Manifest format: JSON array of {session_id, project, messages_path}
    Appends results to metrics.jsonl in the same directory.
    """
    with open(manifest_path) as f:
        manifest = json.load(f)

    output_dir = os.path.dirname(manifest_path) or "."
    metrics_path = os.path.join(output_dir, "metrics.jsonl")

    results = []
    for i, entry in enumerate(manifest):
        sid = entry["session_id"]
        project = entry.get("project", "unknown")
        msg_path = entry["messages_path"]

        print(f"[{i+1}/{len(manifest)}] {project}/{sid[:12]}... ", end="", flush=True)

        try:
            with open(msg_path) as f:
                data = json.load(f)
            metrics = compute_session_metrics(data, sid, project)
            results.append(metrics)

            with open(metrics_path, "a") as f:
                f.write(json.dumps(metrics) + "\n")

            print(f"OK (friction={metrics['friction_score']}, fp={metrics['fingerprint']})")
        except Exception as e:
            print(f"ERROR: {e}")

    print(f"\nDone: {len(results)} sessions processed -> {metrics_path}")
    return results


# ─── CLI ──────────────────────────────────────────────────────────────────────


def print_usage():
    print("Usage:")
    print("  python3 compute-metrics.py <messages.json> --session-id ID --project NAME")
    print("  python3 compute-metrics.py --batch <manifest.json>")
    print("  python3 compute-metrics.py --trends <metrics.jsonl> [--memory MEMORY.md]")
    print("                              [--project NAME] [--html OUTPUT.html]")
    print("  python3 compute-metrics.py --scan-jsonl <jsonl-dir> [--since YYYY-MM-DD]")
    print("                              [--html OUTPUT.html]")
    print("  python3 compute-metrics.py --backfill <extracts-dir/>")
    print("  python3 compute-metrics.py --help")


if __name__ == "__main__":
    if len(sys.argv) < 2 or "--help" in sys.argv:
        print_usage()
        sys.exit(0)

    mode = sys.argv[1]

    if mode == "--batch":
        if len(sys.argv) < 3:
            print("Error: --batch requires manifest path")
            sys.exit(1)
        run_batch(sys.argv[2])

    elif mode == "--trends":
        if len(sys.argv) < 3:
            print("Error: --trends requires metrics.jsonl path")
            sys.exit(1)
        memory_path = None
        if "--memory" in sys.argv:
            idx = sys.argv.index("--memory")
            if idx + 1 < len(sys.argv):
                memory_path = sys.argv[idx + 1]
        project_filter = None
        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                project_filter = sys.argv[idx + 1]
        html_path = None
        if "--html" in sys.argv:
            idx = sys.argv.index("--html")
            if idx + 1 < len(sys.argv):
                html_path = sys.argv[idx + 1]
        result = compute_trends(sys.argv[2], memory_path, project_filter)
        if html_path:
            text = render_trends_text(result)
            html = render_html_report(
                "Session Trends", text, result.get("computed_at", "")
            )
            with open(html_path, "w") as f:
                f.write(html)
            print(f"Wrote HTML report: {html_path}")
        else:
            print(json.dumps(result, indent=2))

    elif mode == "--scan-jsonl":
        if len(sys.argv) < 3:
            print("Error: --scan-jsonl requires a JSONL directory")
            sys.exit(1)
        jsonl_dir = sys.argv[2]
        since_dt = None
        if "--since" in sys.argv:
            idx = sys.argv.index("--since")
            if idx + 1 < len(sys.argv):
                try:
                    since_dt = datetime.fromisoformat(
                        sys.argv[idx + 1]
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    print(f"Error: --since must be ISO date (YYYY-MM-DD), got {sys.argv[idx + 1]}")
                    sys.exit(1)
        html_path = None
        if "--html" in sys.argv:
            idx = sys.argv.index("--html")
            if idx + 1 < len(sys.argv):
                html_path = sys.argv[idx + 1]

        sessions = scan_raw_jsonl(jsonl_dir, since_dt)
        agg = aggregate_ctx_scan(sessions)
        result = {
            "scanned_dir": os.path.abspath(jsonl_dir),
            "since": since_dt.isoformat() if since_dt else None,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            **agg,
            "sessions": sessions,
        }
        if html_path:
            text = render_ctx_scan_text(agg)
            html = render_html_report(
                "Session Context Stats", text, result["computed_at"]
            )
            with open(html_path, "w") as f:
                f.write(html)
            print(f"Wrote HTML report: {html_path} ({len(sessions)} sessions)")
        else:
            print(json.dumps(result, indent=2, default=str))

    elif mode == "--backfill":
        if len(sys.argv) < 3:
            print("Error: --backfill requires extracts directory")
            sys.exit(1)
        extracts_dir = sys.argv[2]
        if not os.path.isdir(extracts_dir):
            print(f"Error: {extracts_dir} is not a directory")
            sys.exit(1)

        metrics_path = os.environ.get(
            "METRICS_PATH",
            os.path.join(os.path.dirname(extracts_dir), "session-metrics", "metrics.jsonl"),
        )
        os.makedirs(os.path.dirname(metrics_path), exist_ok=True)

        # Load existing session IDs to skip
        existing_ids = set()
        if os.path.exists(metrics_path):
            with open(metrics_path) as f:
                for line in f:
                    try:
                        existing_ids.add(json.loads(line).get("session_id"))
                    except json.JSONDecodeError:
                        continue

        files = sorted(f for f in os.listdir(extracts_dir) if f.endswith(".json") and not f.startswith("_"))
        processed = 0
        skipped = 0

        for fname in files:
            fpath = os.path.join(extracts_dir, fname)
            try:
                with open(fpath) as f:
                    v1 = json.load(f)
                sid = v1.get("session_id", fname.replace(".json", ""))
                if sid in existing_ids:
                    skipped += 1
                    continue
                metrics = backfill_from_v1(fpath)
                with open(metrics_path, "a") as f:
                    f.write(json.dumps(metrics) + "\n")
                processed += 1
                print(f"  Backfilled: {fname} (friction={metrics['friction_score']})")
            except Exception as e:
                print(f"  Error: {fname}: {e}")

        print(f"\nBackfill complete: {processed} new, {skipped} skipped -> {metrics_path}")

    else:
        # Single session mode
        messages_path = mode
        session_id = None
        project = "unknown"

        if "--session-id" in sys.argv:
            idx = sys.argv.index("--session-id")
            if idx + 1 < len(sys.argv):
                session_id = sys.argv[idx + 1]

        if "--project" in sys.argv:
            idx = sys.argv.index("--project")
            if idx + 1 < len(sys.argv):
                project = sys.argv[idx + 1]

        if not session_id:
            session_id = os.path.basename(messages_path).replace(".json", "")

        with open(messages_path) as f:
            data = json.load(f)

        metrics = compute_session_metrics(data, session_id, project)
        print(json.dumps(metrics))
