#!/usr/bin/env python3
"""Analyze Claude Code session data for recurring patterns.

Works in two modes:
  1. Single session: parse one ccrider JSON file, extract friction/patterns
  2. Aggregate: combine multiple single-session results into cross-session summary

Usage:
    # Single session analysis
    python3 analyze-sessions.py session.json --session-id abc123

    # Single session, write to file
    python3 analyze-sessions.py session.json --session-id abc123 --output result.json

    # Aggregate mode: summarize a directory of single-session results
    python3 analyze-sessions.py results_dir/ --mode aggregate

    # Aggregate mode with output file
    python3 analyze-sessions.py results_dir/ --mode aggregate --output summary.json
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime


# ─── Constants ──────────────────────────────────────────────────────────────

# Friction score weights (aligned with compute-metrics.py patterns)
FRICTION_WEIGHTS = {
    "user_corrections": 2.5,
    "debugging_loops": 3.0,
    "error_ratio": 2.0,
}

# Sigmoid normalization parameters
FRICTION_SIGMOID_K = 3.0
FRICTION_SIGMOID_MIDPOINT = 1.5

# Correction patterns in user messages
CORRECTION_RE = re.compile(
    r"\b(no[,.]?\s|wrong|instead|actually|that'?s not|not what I|"
    r"I meant|I said|please don'?t|stop|undo|revert|not that)\b",
    re.IGNORECASE,
)

# Session type classification keywords
SESSION_TYPE_KEYWORDS = {
    "bug-fix": re.compile(
        r"\b(fix|bug|broken|error|issue|crash|fail|debug|wrong)\b", re.IGNORECASE
    ),
    "feature": re.compile(
        r"\b(add|implement|build|create|new feature|scaffold)\b", re.IGNORECASE
    ),
    "exploration": re.compile(
        r"\b(explore|understand|how does|what is|explain|look at)\b", re.IGNORECASE
    ),
    "review": re.compile(
        r"\b(review|PR|pull request|code review|feedback)\b", re.IGNORECASE
    ),
    "maintenance": re.compile(
        r"\b(deps?|update|upgrade|bump|version|migrate|refactor)\b", re.IGNORECASE
    ),
}

# Tool name detection from assistant messages
TOOL_MENTION_RE = re.compile(
    r"\b(Read|Edit|Write|Bash|Grep|Glob|Agent|Task|NotebookEdit|WebFetch|WebSearch)\b"
)

# Error indicators in assistant messages
ERROR_RE = re.compile(
    r"\b(error|Error|ERROR|failed|Failed|FAILED|traceback|Traceback"
    r"|\*\*\s*\(exit|\*\*\s*\(EXIT|CompileError|RuntimeError"
    r"|UndefinedFunctionError|FunctionClauseError)\b"
)

# Action verbs for task type detection
ACTION_VERB_RE = re.compile(
    r"^(create|fix|add|update|delete|remove|test|review|implement|build|refactor|move"
    r"|rename|extract|deploy|configure|setup|install|migrate|write|debug|check)\b",
    re.IGNORECASE,
)

# Stop words for phrase extraction
STOP_WORDS = frozenset({
    "a", "an", "the", "is", "it", "to", "in", "for", "of", "and", "or",
    "on", "at", "by", "with", "from", "that", "this", "be", "as", "are",
    "was", "were", "been", "has", "have", "had", "do", "does", "did",
    "will", "would", "could", "should", "can", "may", "might", "shall",
    "not", "but", "if", "so", "up", "out", "no", "yes", "all", "any",
    "i", "me", "my", "we", "you", "your", "he", "she", "they", "them",
    "its", "our", "their", "some", "just", "also", "then", "than",
    "about", "into", "over", "after", "before", "when", "where", "how",
    "what", "which", "who", "whom", "why", "each", "every", "both",
    "few", "more", "most", "other", "such", "only", "very", "too",
    "here", "there", "now", "still", "already", "please", "like",
})


# ─── Helpers ────────────────────────────────────────────────────────────────


def sigmoid(raw):
    """Apply sigmoid normalization to raw friction score (0.0 to 1.0)."""
    return 1.0 / (1.0 + math.exp(-FRICTION_SIGMOID_K * (raw - FRICTION_SIGMOID_MIDPOINT)))


def safe_load_json(path):
    """Load JSON from file with error handling.

    Supports both a single JSON document (ccrider output) and JSONL
    (raw Claude Code transcripts from ~/.claude/projects/) — JSONL is
    parsed line-by-line into a list of entries.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Warning: File not found: {path}", file=sys.stderr)
        return None
    except UnicodeDecodeError as e:
        print(f"Warning: Could not parse {path}: {e}", file=sys.stderr)
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # JSONL fallback: one JSON object per line
    entries = []
    bad_lines = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            bad_lines += 1
    if entries:
        if bad_lines:
            print(f"Warning: JSONL parse skipped {bad_lines} bad lines in {path}", file=sys.stderr)
        return entries

    print(f"Warning: Could not parse {path}: not JSON or JSONL", file=sys.stderr)
    return None


# ─── Message Parsing ────────────────────────────────────────────────────────


def parse_messages(data):
    """Parse ccrider message JSON into a list of message dicts.

    Handles multiple formats produced by ccrider + Write tool:
    - Dict with 'messages' key (standard ccrider response)
    - Dict with 'returned_from' key (confirmed ccrider envelope)
    - Dict with 'result.messages' (MCP response wrapper still present)
    - Bare list of message objects
    - Double-serialized JSON string
    """
    # Handle double-serialized: data might be a string containing JSON
    if isinstance(data, str):
        try:
            data = json.loads(data)
            print(f"DEBUG: Double-serialized JSON detected, re-parsed", file=sys.stderr)
        except (json.JSONDecodeError, TypeError):
            print(f"DEBUG: Data is a string but not valid JSON, length={len(data)}", file=sys.stderr)
            return []

    if isinstance(data, dict):
        print(
            f"DEBUG: Input type=dict, keys={sorted(data.keys())}",
            file=sys.stderr,
        )

        # Filter out ccrider metadata keys that are NOT messages
        metadata_keys = {"truncated", "truncated_message"}

        # Standard ccrider response with 'returned_from' confirms envelope format
        if "returned_from" in data and "messages" in data:
            messages = data["messages"]
            print(f"DEBUG: ccrider envelope detected (returned_from={data.get('returned_from')})", file=sys.stderr)
        # Standard ccrider response with 'messages' key
        elif "messages" in data:
            messages = data["messages"]
        # MCP response wrapper: result.messages
        elif "session_id" in data and "messages" not in data:
            messages = data.get("result", {}).get("messages", [])
            if messages:
                print(f"DEBUG: Unwrapped MCP result wrapper", file=sys.stderr)
            else:
                print(f"DEBUG: Dict has session_id but no messages or result.messages", file=sys.stderr)
        else:
            # Last resort: try 'result' key directly
            result = data.get("result")
            if isinstance(result, dict) and "messages" in result:
                messages = result["messages"]
                print(f"DEBUG: Found messages inside 'result' key", file=sys.stderr)
            elif isinstance(result, list):
                messages = result
                print(f"DEBUG: 'result' key contains bare list", file=sys.stderr)
            else:
                print(f"DEBUG: No messages found in dict", file=sys.stderr)
                messages = []

        # Filter out metadata entries that aren't real messages
        if isinstance(messages, list):
            messages = [
                m for m in messages
                if isinstance(m, dict) and not metadata_keys.intersection(m.keys())
            ]

    elif isinstance(data, list):
        print(
            f"DEBUG: Input type=list, length={len(data)}",
            file=sys.stderr,
        )
        # Filter out any metadata entries mixed into the list
        metadata_keys = {"truncated", "truncated_message"}
        messages = [
            m for m in data
            if isinstance(m, dict) and not metadata_keys.intersection(m.keys())
        ]
    else:
        print(f"DEBUG: Unexpected input type={type(data).__name__}", file=sys.stderr)
        return []

    print(f"DEBUG: Messages found: {len(messages)}", file=sys.stderr)
    if messages:
        first = messages[0]
        print(
            f"DEBUG: First message type={first.get('type', first.get('role', 'unknown'))}",
            file=sys.stderr,
        )
    return messages


def get_role(msg):
    """Get message role, supporting ccrider (type) and API (role) formats.

    Also filters out ccrider metadata entries (truncated, truncated_message)
    that are not actual messages.
    """
    if not isinstance(msg, dict):
        return ""
    # Skip metadata entries that ccrider adds for large responses
    if "truncated" in msg or "truncated_message" in msg:
        return ""
    return msg.get("type", msg.get("role", msg.get("message", {}).get("role", "")))


def get_content(msg):
    """Get message text content, supporting ccrider and API formats."""
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content", msg.get("message", {}).get("content", ""))
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # API format: concatenate text blocks
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return " ".join(parts)
    return ""


def get_timestamp(msg):
    """Extract timestamp from message, return as datetime or None."""
    if not isinstance(msg, dict):
        return None
    ts = msg.get("timestamp")
    if not ts:
        return None
    # Try ISO format parsing
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except (ValueError, TypeError):
            continue
    # Fallback: try fromisoformat (Python 3.7+)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


# ─── Extraction Functions ───────────────────────────────────────────────────


def extract_user_messages(messages):
    """Extract meaningful user message texts, filtering system injections."""
    user_msgs = []
    for msg in messages:
        role = get_role(msg)
        if role != "user":
            continue
        content = get_content(msg)
        if not content or len(content) < 5:
            continue
        # Filter out system-injected and tool-output messages
        if content.startswith(("<system-reminder>", "<local-command-caveat>",
                               "<local-command-stdout>", "<command-name>",
                               "<bash-input>", "<bash-stdout>", "<bash-stderr>",
                               "Base directory for this skill:",
                               "Async agent launched", "Full transcript available")):
            continue
        # Skip very long messages (likely tool output, not human input)
        if len(content) > 5000:
            continue
        user_msgs.append(content)
    return user_msgs


def extract_assistant_messages(messages):
    """Extract assistant message texts."""
    assistant_msgs = []
    for msg in messages:
        role = get_role(msg)
        if role != "assistant":
            continue
        content = get_content(msg)
        if content and len(content) > 5:
            assistant_msgs.append(content)
    return assistant_msgs


def extract_tool_usage(assistant_msgs):
    """Count tool mentions in assistant messages."""
    tool_counts = Counter()
    for text in assistant_msgs:
        mentions = TOOL_MENTION_RE.findall(text)
        for tool in mentions:
            tool_counts[tool] += 1
    return dict(tool_counts.most_common())


def extract_errors(assistant_msgs):
    """Count error indicators in assistant messages."""
    error_count = 0
    for text in assistant_msgs:
        if ERROR_RE.search(text):
            error_count += 1
    return error_count


def detect_debugging_loops(assistant_msgs):
    """Detect same tool call pattern appearing 3+ consecutive times.

    Looks for repeated patterns in assistant messages that suggest
    retrying the same operation.
    """
    loop_count = 0
    # Extract dominant tool per message
    tools_per_msg = []
    for text in assistant_msgs:
        mentions = TOOL_MENTION_RE.findall(text)
        if mentions:
            # Use first mentioned tool as representative
            tools_per_msg.append(mentions[0])
        else:
            tools_per_msg.append("")

    # Find consecutive same-tool runs of length >= 3
    if len(tools_per_msg) < 3:
        return 0

    run_length = 1
    for i in range(1, len(tools_per_msg)):
        if tools_per_msg[i] and tools_per_msg[i] == tools_per_msg[i - 1]:
            run_length += 1
            if run_length >= 3:
                loop_count += 1
                run_length = 1  # Reset after counting
        else:
            run_length = 1

    return loop_count


def count_user_corrections(user_msgs):
    """Count user messages that look like corrections."""
    corrections = 0
    for text in user_msgs:
        # Only check first 500 chars to avoid false positives in long messages
        if CORRECTION_RE.search(text[:500]):
            corrections += 1
    return corrections


def extract_task_types(user_msgs):
    """Extract action verb frequencies from user messages."""
    task_counts = Counter()
    for text in user_msgs:
        match = ACTION_VERB_RE.match(text.strip())
        if match:
            verb = match.group(1).lower()
            task_counts[verb] += 1
    return dict(task_counts.most_common())


def classify_session_type(user_msgs):
    """Classify session type based on keyword frequency in user messages."""
    type_scores = Counter()
    combined_text = " ".join(user_msgs)

    for session_type, pattern in SESSION_TYPE_KEYWORDS.items():
        matches = pattern.findall(combined_text)
        type_scores[session_type] = len(matches)

    if not type_scores:
        return "unknown"

    best_type = type_scores.most_common(1)[0]
    if best_type[1] == 0:
        return "unknown"
    return best_type[0]


def extract_duration_minutes(messages):
    """Estimate session duration from first to last timestamp."""
    timestamps = []
    for msg in messages:
        ts = get_timestamp(msg)
        if ts:
            timestamps.append(ts)

    if len(timestamps) < 2:
        return 0

    earliest = min(timestamps)
    latest = max(timestamps)
    delta = (latest - earliest).total_seconds() / 60.0
    return round(delta, 1)


def extract_recurring_phrases(user_msgs, min_count=3, max_words=4):
    """Extract 2-4 word phrases appearing min_count+ times in user messages.

    Uses sliding window n-gram extraction with stop word filtering.
    """
    phrase_counter = Counter()

    for text in user_msgs:
        # Normalize: lowercase, keep only alphanumeric + spaces
        normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        words = [w for w in normalized.split() if w and w not in STOP_WORDS and len(w) > 1]

        # Generate 2-gram and 3-gram phrases
        for n in range(2, max_words + 1):
            for i in range(len(words) - n + 1):
                phrase = " ".join(words[i:i + n])
                phrase_counter[phrase] += 1

    # Filter to phrases appearing min_count+ times
    recurring = [
        {"phrase": phrase, "count": count}
        for phrase, count in phrase_counter.most_common(20)
        if count >= min_count
    ]

    return recurring


# ─── Friction Score ─────────────────────────────────────────────────────────


def compute_friction_score(user_corrections, debugging_loops, error_count, total_msgs):
    """Compute friction score normalized to 0-1 with sigmoid.

    Raw = (corrections * 2.5 + loops * 3.0 + error_ratio * 2.0)
    Then sigmoid normalization.
    """
    error_ratio = error_count / max(total_msgs, 1)

    raw = (
        user_corrections * FRICTION_WEIGHTS["user_corrections"]
        + debugging_loops * FRICTION_WEIGHTS["debugging_loops"]
        + error_ratio * FRICTION_WEIGHTS["error_ratio"]
    )

    return round(sigmoid(raw), 3)


# ─── Single Session Analysis ───────────────────────────────────────────────


def analyze_single_session(data, session_id="unknown"):
    """Analyze a single ccrider session JSON and return metrics dict."""
    messages = parse_messages(data)

    if not messages:
        return {
            "session_id": session_id,
            "message_count": 0,
            "duration_minutes": 0,
            "friction_score": 0.0,
            "session_type": "unknown",
            "recurring_asks": [],
            "user_corrections": 0,
            "tool_usage": {},
            "debugging_loops": 0,
            "error_count": 0,
            "task_types": {},
            "user_message_count": 0,
            "assistant_message_count": 0,
            "tools_mentioned": [],
            "error": "No messages found in session data",
        }

    # Extract message groups
    user_msgs = extract_user_messages(messages)
    assistant_msgs = extract_assistant_messages(messages)

    # Compute metrics
    total_msgs = len(messages)
    duration = extract_duration_minutes(messages)
    tool_usage = extract_tool_usage(assistant_msgs)
    error_count = extract_errors(assistant_msgs)
    debugging_loops = detect_debugging_loops(assistant_msgs)
    user_corrections = count_user_corrections(user_msgs)
    task_types = extract_task_types(user_msgs)
    session_type = classify_session_type(user_msgs)
    recurring_asks = extract_recurring_phrases(user_msgs)

    friction = compute_friction_score(
        user_corrections, debugging_loops, error_count, total_msgs
    )

    # Count truncated messages for diagnostics
    truncated_count = sum(
        1 for m in messages if isinstance(m, dict) and m.get("truncated")
    )

    # Build result with extra context even when few patterns found
    result = {
        "session_id": session_id,
        "message_count": total_msgs,
        "user_message_count": len(user_msgs),
        "assistant_message_count": len(assistant_msgs),
        "duration_minutes": duration,
        "friction_score": friction,
        "session_type": session_type,
        "recurring_asks": recurring_asks,
        "user_corrections": user_corrections,
        "tool_usage": tool_usage,
        "tools_mentioned": sorted(tool_usage.keys()) if tool_usage else [],
        "debugging_loops": debugging_loops,
        "error_count": error_count,
        "task_types": task_types,
    }

    if truncated_count > 0:
        result["truncated_messages"] = truncated_count

    return result


# ─── Aggregate Analysis ────────────────────────────────────────────────────


def analyze_aggregate(results_dir):
    """Aggregate multiple single-session results into a cross-session summary."""
    results = []

    # Load all JSON files in directory
    if not os.path.isdir(results_dir):
        return {"error": f"Not a directory: {results_dir}", "sessions_analyzed": 0}

    for filename in sorted(os.listdir(results_dir)):
        if not filename.endswith(".json"):
            continue
        # Skip temp files and the aggregate output itself
        if filename.startswith("_tmp_") or filename == "sessions-summary.json":
            continue
        filepath = os.path.join(results_dir, filename)
        data = safe_load_json(filepath)
        if not data or not isinstance(data, dict):
            print(f"DEBUG aggregate: Skipping {filename} (not a dict or empty)", file=sys.stderr)
            continue
        # Accept if it has session_id (scored result) OR message_count (alternative format)
        if "session_id" in data or "message_count" in data:
            # Skip sessions that had errors and produced 0 messages
            if data.get("error") and data.get("message_count", 0) == 0:
                print(f"DEBUG aggregate: Skipping {filename} (0 messages, has error)", file=sys.stderr)
                continue
            results.append(data)
        else:
            print(f"DEBUG aggregate: Skipping {filename} (no session_id or message_count, keys={sorted(data.keys())[:5]})", file=sys.stderr)

    if not results:
        return {
            "sessions_analyzed": 0,
            "avg_friction_score": 0.0,
            "session_type_distribution": {},
            "cross_session_patterns": [],
            "total_user_corrections": 0,
            "common_debugging_loops": [],
            "error": "No valid session result files found",
        }

    sessions_analyzed = len(results)

    # Average friction score
    friction_scores = [r.get("friction_score", 0.0) for r in results]
    avg_friction = round(sum(friction_scores) / len(friction_scores), 3)

    # Session type distribution
    type_dist = Counter()
    for r in results:
        st = r.get("session_type", "unknown")
        type_dist[st] += 1

    # Total user corrections
    total_corrections = sum(r.get("user_corrections", 0) for r in results)

    # Cross-session recurring asks: phrases appearing in 3+ sessions
    phrase_sessions = defaultdict(set)  # phrase -> set of session_ids
    for r in results:
        sid = r.get("session_id", "unknown")
        for ask in r.get("recurring_asks", []):
            phrase = ask.get("phrase", "")
            if phrase:
                phrase_sessions[phrase].add(sid)

    cross_patterns = []
    for phrase, sessions in sorted(phrase_sessions.items(), key=lambda x: -len(x[1])):
        count = len(sessions)
        if count >= 3:
            confidence = "high" if count >= 5 else "medium"
            cross_patterns.append({
                "pattern": phrase,
                "sessions": count,
                "confidence": confidence,
            })
    cross_patterns = cross_patterns[:20]  # Top 20

    # Common tools with debugging loops
    loop_tools = Counter()
    for r in results:
        if r.get("debugging_loops", 0) > 0:
            tool_usage = r.get("tool_usage", {})
            # The most-used tool in sessions with loops is likely the loop source
            if tool_usage:
                top_tool = max(tool_usage.items(), key=lambda x: x[1])[0]
                loop_tools[top_tool] += 1

    common_loop_tools = [tool for tool, _ in loop_tools.most_common(5)]

    # Aggregate tool usage
    total_tool_usage = Counter()
    for r in results:
        for tool, count in r.get("tool_usage", {}).items():
            total_tool_usage[tool] += count

    # Aggregate task types
    total_task_types = Counter()
    for r in results:
        for task, count in r.get("task_types", {}).items():
            total_task_types[task] += count

    # High-friction sessions
    high_friction = [
        {"session_id": r["session_id"], "friction_score": r["friction_score"]}
        for r in results
        if r.get("friction_score", 0) > 0.5
    ]
    high_friction.sort(key=lambda x: -x["friction_score"])

    return {
        "sessions_analyzed": sessions_analyzed,
        "avg_friction_score": avg_friction,
        "session_type_distribution": dict(type_dist.most_common()),
        "cross_session_patterns": cross_patterns,
        "total_user_corrections": total_corrections,
        "common_debugging_loops": common_loop_tools,
        "total_tool_usage": dict(total_tool_usage.most_common()),
        "total_task_types": dict(total_task_types.most_common()),
        "high_friction_sessions": high_friction[:10],
        "friction_distribution": {
            "low": sum(1 for s in friction_scores if s < 0.3),
            "medium": sum(1 for s in friction_scores if 0.3 <= s < 0.6),
            "high": sum(1 for s in friction_scores if s >= 0.6),
        },
    }


# ─── Main ──────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Claude Code session data for recurring patterns.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Analyze a single session
  %(prog)s session.json --session-id abc123

  # Analyze and save to file
  %(prog)s session.json --session-id abc123 --output result.json

  # Aggregate multiple session results
  %(prog)s results_dir/ --mode aggregate --output summary.json
""",
    )
    parser.add_argument(
        "input_path",
        help="Session JSON file (single mode) or directory of results (aggregate mode).",
    )
    parser.add_argument(
        "--mode",
        choices=["single", "aggregate"],
        default="single",
        help="Analysis mode: single session or aggregate (default: single).",
    )
    parser.add_argument(
        "--session-id",
        default="unknown",
        help="Session identifier for single mode (default: unknown).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON to this file instead of stdout.",
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input_path)

    if args.mode == "single":
        if not os.path.isfile(input_path):
            print(f"Error: {input_path} is not a file.", file=sys.stderr)
            sys.exit(1)

        data = safe_load_json(input_path)
        if data is None:
            print(f"Error: Could not parse {input_path}", file=sys.stderr)
            sys.exit(1)

        # Debug: show what we loaded before parsing
        if isinstance(data, dict):
            print(
                f"DEBUG: Loaded JSON dict, keys={sorted(data.keys())}, "
                f"session_id={data.get('session_id', 'N/A')}, "
                f"total_count={data.get('total_count', 'N/A')}",
                file=sys.stderr,
            )
        elif isinstance(data, list):
            print(f"DEBUG: Loaded JSON list, length={len(data)}", file=sys.stderr)
        elif isinstance(data, str):
            print(f"DEBUG: Loaded JSON string, length={len(data)}", file=sys.stderr)
        else:
            print(f"DEBUG: Loaded JSON type={type(data).__name__}", file=sys.stderr)

        result = analyze_single_session(data, session_id=args.session_id)

    elif args.mode == "aggregate":
        if not os.path.isdir(input_path):
            print(f"Error: {input_path} is not a directory.", file=sys.stderr)
            sys.exit(1)

        result = analyze_aggregate(input_path)

    else:
        print(f"Error: Unknown mode: {args.mode}", file=sys.stderr)
        sys.exit(1)

    # Output
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
