#!/usr/bin/env python3
"""Merge findings from all 6 layer analysis files.

Reads .md files from a layers directory, parses YAML frontmatter from each
finding block, deduplicates similar findings, cross-references across layers,
and scores by priority.

Three-level deduplication:
  Level 1: Title-similarity merge (existing) — merges near-identical findings
  Level 2: Semantic linking — cross-references findings sharing file paths
  Level 3: Contradiction detection — flags config-vs-code opposing conclusions

Outputs JSON to stdout (or to --output file).

Supports both directory layouts:
  Shallow mode: layers/{layer}.md files directly in directory
  Deep mode:    L1/consolidated.md, L2/consolidated.md, etc.

Usage:
    python merge-findings.py .claude/inspector/layers/
    python merge-findings.py .claude/inspector/layers/ --output merged.json
    python merge-findings.py --self-test
"""

import argparse
import json
import os
import re
import sys
import tempfile
from collections import Counter


# ---------------------------------------------------------------------------
# YAML frontmatter parser (no pyyaml dependency)
# ---------------------------------------------------------------------------

def parse_yaml_value(raw):
    """Parse a single YAML value string into a Python type."""
    raw = raw.strip()
    if not raw:
        return ""
    # Inline array: [item1, item2, item3]
    if raw.startswith('[') and raw.endswith(']'):
        inner = raw[1:-1]
        items = [item.strip().strip('"').strip("'") for item in inner.split(',') if item.strip()]
        return items
    # Quoted string
    if (raw.startswith('"') and raw.endswith('"')) or \
       (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    # Integer
    if re.match(r'^-?\d+$', raw):
        return int(raw)
    # Float
    if re.match(r'^-?\d+\.\d+$', raw):
        return float(raw)
    # Boolean
    if raw.lower() in ("true", "yes"):
        return raw  # Keep as string to match schema (yes/no/partial)
    if raw.lower() in ("false", "no"):
        return raw
    return raw


def parse_yaml_frontmatter(text, source_name="<unknown>"):
    """Extract YAML frontmatter blocks from markdown text.

    Finds all blocks delimited by --- markers and parses key: value pairs.
    Handles both raw YAML frontmatter and code-fenced YAML (```yaml ... ```).
    Returns a list of (frontmatter_dict, body_text) tuples.

    Args:
        text: The markdown content to parse.
        source_name: Filename for error reporting.
    """
    findings = []

    # Strip code fence markers that agents sometimes wrap around YAML blocks.
    # Removes lines like ```yaml, ```yml, ```markdown, ```md, or bare ```
    # Must handle fences both around the whole block AND around individual findings.
    text = re.sub(r'^\s*```(?:yaml|yml|markdown|md)?\s*$', '', text, flags=re.MULTILINE)

    # Split on --- delimiters. Pattern: line with 3+ dashes and optional whitespace.
    # Handle varying whitespace around --- markers.
    parts = re.split(r'^\s*-{3,}\s*$', text, flags=re.MULTILINE)

    # parts[0] is text before first ---, parts[1] is first frontmatter,
    # parts[2] is body after first block (until next ---), etc.
    # Finding blocks: frontmatter is at odd indices (1, 3, 5, ...)
    i = 1
    while i < len(parts):
        frontmatter_text = parts[i]
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        fm = _parse_yaml_block(frontmatter_text, source_name=source_name,
                               block_index=(i // 2))
        if fm and "id" in fm:
            findings.append((fm, body))
        elif fm:
            # Has YAML content but no id — report for debugging
            keys_found = list(fm.keys())[:5]
            print(
                f"  Warning: YAML block in {source_name} (block {i // 2}) "
                f"has no 'id' field. Keys found: {keys_found}",
                file=sys.stderr,
            )
        i += 2

    return findings


def _parse_yaml_block(text, source_name="<unknown>", block_index=0):
    """Parse a YAML block into a dict.

    Handles:
    - Scalar key: value pairs
    - YAML arrays (indented "- value" lines)
    - Inline arrays: [item1, item2]
    - Multi-line folded scalars (>)
    - Multi-line literal scalars (|)
    - Quoted strings
    - Various id formats (L1-001, L1-A01, L1_001)
    """
    result = {}
    current_key = None
    current_array = None
    multiline_mode = None  # None, "folded" (>), or "literal" (|)
    multiline_buffer = []
    lines = text.splitlines()

    def _flush_multiline():
        """Flush accumulated multi-line buffer into result."""
        nonlocal multiline_mode, multiline_buffer
        if current_key and multiline_buffer and multiline_mode:
            if multiline_mode == "folded":
                # > folded: newlines become spaces, blank lines become \n
                paragraphs = []
                current_para = []
                for ml in multiline_buffer:
                    if ml == "":
                        if current_para:
                            paragraphs.append(" ".join(current_para))
                            current_para = []
                        paragraphs.append("")
                    else:
                        current_para.append(ml)
                if current_para:
                    paragraphs.append(" ".join(current_para))
                result[current_key] = "\n".join(paragraphs).strip()
            elif multiline_mode == "literal":
                # | literal: preserve newlines as-is
                result[current_key] = "\n".join(multiline_buffer).strip()
        multiline_mode = None
        multiline_buffer = []

    for line_num, line in enumerate(lines):
        stripped = line.strip()

        # Skip blank lines and comments, but blank lines in multiline mode matter
        if not stripped:
            if multiline_mode:
                multiline_buffer.append("")
            continue
        if stripped.startswith("#"):
            continue

        # Determine indentation level
        indent = len(line) - len(line.lstrip())

        # If we're in multiline mode, indented lines are continuation
        if multiline_mode and indent > 0 and not re.match(r'^[a-z_][a-z0-9_]*\s*:', line):
            multiline_buffer.append(stripped)
            continue
        elif multiline_mode and (indent == 0 or re.match(r'^[a-z_][a-z0-9_]*\s*:', line)):
            # End of multiline block — flush and fall through to parse this line
            _flush_multiline()

        # Array item (indented "- value")
        array_match = re.match(r'^\s+-\s+(.*)', line)
        if array_match and current_key is not None:
            value = array_match.group(1).strip()
            # Remove surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if current_array is None:
                current_array = []
            current_array.append(value)
            result[current_key] = current_array
            continue

        # Key: value pair
        kv_match = re.match(r'^([a-z_][a-z0-9_]*)\s*:\s*(.*)', line)
        if kv_match:
            key = kv_match.group(1)
            value_str = kv_match.group(2).strip()
            current_key = key
            current_array = None

            # Check for multi-line indicators
            if value_str == ">":
                multiline_mode = "folded"
                multiline_buffer = []
                result[key] = ""
                continue
            elif value_str == "|":
                multiline_mode = "literal"
                multiline_buffer = []
                result[key] = ""
                continue

            if value_str:
                result[key] = parse_yaml_value(value_str)
            else:
                # Value might be an array on subsequent lines, or empty
                result[key] = None
            continue

        # Multi-line continuation (indented text not matching above)
        # Append to current key if it exists and is a string
        if current_key and current_key in result and isinstance(result[current_key], str):
            result[current_key] += " " + stripped

    # Flush any remaining multi-line content
    _flush_multiline()

    # Validate id format if present (accept L1-001, L1-A01, L1_001 etc.)
    if "id" in result:
        fid = str(result["id"])
        if not re.match(r'^L\d[-_A-Za-z0-9+]+', fid):
            print(
                f"  Warning: unusual id format '{fid}' in {source_name} "
                f"block {block_index}",
                file=sys.stderr,
            )

    return result


# ---------------------------------------------------------------------------
# File reading
# ---------------------------------------------------------------------------

LAYER_FILES = [
    "git-history.md",
    "pr-reviews.md",
    "code-docs.md",
    "claude-config.md",
    "sessions.md",
    "architecture.md",
]

# Deep mode subdirectory names (L1 through L6)
_DEEP_SUBDIRS = [f"L{i}" for i in range(1, 7)]


def _detect_layout(layers_dir):
    """Detect whether the directory uses shallow or deep layout.

    Returns "deep" if L1/, L2/, etc. subdirectories exist with consolidated.md.
    Returns "shallow" otherwise.
    """
    deep_count = 0
    for subdir in _DEEP_SUBDIRS:
        consolidated = os.path.join(layers_dir, subdir, "consolidated.md")
        if os.path.isfile(consolidated):
            deep_count += 1
    # If at least 1 consolidated.md exists, treat as deep mode
    return "deep" if deep_count >= 1 else "shallow"


def read_layer_files(layers_dir):
    """Read all layer .md files from layers_dir.

    Supports two layouts:
      Shallow: layers/{layer}.md files directly in directory
      Deep:    L1/consolidated.md, L2/consolidated.md, etc. subdirectories

    Returns list of (filename, content) tuples.
    """
    results = []
    if not os.path.isdir(layers_dir):
        print(f"Warning: layers directory does not exist: {layers_dir}", file=sys.stderr)
        return results

    layout = _detect_layout(layers_dir)
    print(f"Detected layout: {layout}", file=sys.stderr)

    if layout == "deep":
        return _read_deep_layout(layers_dir)
    else:
        return _read_shallow_layout(layers_dir)


def _read_deep_layout(layers_dir):
    """Read consolidated.md from L1/ through L6/ subdirectories."""
    results = []
    for subdir in _DEEP_SUBDIRS:
        consolidated = os.path.join(layers_dir, subdir, "consolidated.md")
        if os.path.isfile(consolidated):
            try:
                with open(consolidated, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                results.append((f"{subdir}/consolidated.md", content))
            except (OSError, IOError) as e:
                print(f"Warning: could not read {consolidated}: {e}", file=sys.stderr)
        else:
            print(f"Note: no {subdir}/consolidated.md (layer may have been skipped)",
                  file=sys.stderr)

    # Also check for any extra .md files directly in layers_dir (hybrid case)
    extra = _read_shallow_layout(layers_dir, warn_missing=False)
    if extra:
        print(f"  Also found {len(extra)} shallow .md file(s) alongside deep layout",
              file=sys.stderr)
        results.extend(extra)

    return results


def _read_shallow_layout(layers_dir, warn_missing=True):
    """Read .md files directly in layers_dir (shallow/standard mode)."""
    results = []
    seen = set()

    # Read known layer files first, then any additional .md files
    for filename in LAYER_FILES:
        path = os.path.join(layers_dir, filename)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                results.append((filename, content))
                seen.add(filename)
            except (OSError, IOError) as e:
                print(f"Warning: could not read {path}: {e}", file=sys.stderr)
        elif warn_missing:
            print(f"Warning: missing layer file: {path}", file=sys.stderr)

    # Also pick up any extra .md files not in the standard list
    try:
        for entry in sorted(os.listdir(layers_dir)):
            if entry.endswith(".md") and entry not in seen:
                path = os.path.join(layers_dir, entry)
                if os.path.isfile(path):
                    try:
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        results.append((entry, content))
                    except (OSError, IOError) as e:
                        print(f"Warning: could not read {path}: {e}", file=sys.stderr)
    except OSError:
        pass

    return results


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "a", "an", "the", "for", "in", "of", "to", "and", "on", "up", "is",
    "it", "by", "at", "or", "so", "if", "be", "as", "no", "not", "with",
    "from", "that", "this", "into", "some", "all", "has", "are", "was",
    "were", "been", "have", "had", "but", "when", "which", "who", "how",
    "its", "can", "may", "does", "did", "than", "then", "each", "any",
    "more", "also", "very", "just", "only", "about", "over", "such",
}


def significant_words(title):
    """Extract significant words from a title (lowercase, no stopwords)."""
    words = re.findall(r'[a-z][a-z0-9_]+', title.lower())
    return set(w for w in words if w not in STOP_WORDS and len(w) > 2)


def titles_similar(title_a, title_b, threshold=3):
    """Check if two titles share enough significant words to be duplicates."""
    words_a = significant_words(title_a)
    words_b = significant_words(title_b)
    if not words_a or not words_b:
        return False
    shared = words_a & words_b
    return len(shared) >= threshold


def merge_findings_pair(primary, secondary):
    """Merge secondary finding into primary. Mutates primary in place."""
    # Combine IDs
    merged_from = primary.get("merged_from", [primary["id"]])
    if secondary["id"] not in merged_from:
        merged_from.append(secondary["id"])
    primary["merged_from"] = merged_from

    # Combine layers
    layers = list(primary.get("layers", [primary.get("layer", "unknown")]))
    sec_layer = secondary.get("layer", "unknown")
    if sec_layer not in layers:
        layers.append(sec_layer)
    primary["layers"] = layers

    # Combined ID string
    primary["id"] = "+".join(primary["merged_from"])

    # Keep highest severity
    sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    primary_sev = sev_order.get(str(primary.get("severity", "low")).lower(), 1)
    secondary_sev = sev_order.get(str(secondary.get("severity", "low")).lower(), 1)
    if secondary_sev > primary_sev:
        primary["severity"] = secondary.get("severity", primary.get("severity"))

    # Keep smallest effort (easier to fix = better)
    eff_order = {"tiny": 1, "small": 2, "medium": 3, "large": 4}
    primary_eff = eff_order.get(str(primary.get("effort", "large")).lower(), 4)
    secondary_eff = eff_order.get(str(secondary.get("effort", "large")).lower(), 4)
    if secondary_eff < primary_eff:
        primary["effort"] = secondary.get("effort", primary.get("effort"))

    # Combine evidence arrays
    primary_evidence = primary.get("evidence", [])
    secondary_evidence = secondary.get("evidence", [])
    if isinstance(primary_evidence, str):
        primary_evidence = [primary_evidence]
    if isinstance(secondary_evidence, str):
        secondary_evidence = [secondary_evidence]
    combined_evidence = list(primary_evidence)
    for e in secondary_evidence:
        if e not in combined_evidence:
            combined_evidence.append(e)
    primary["evidence"] = combined_evidence

    # Combine artifact_types
    primary_arts = primary.get("artifact_types", [])
    secondary_arts = secondary.get("artifact_types", [])
    if isinstance(primary_arts, str):
        primary_arts = [primary_arts]
    if isinstance(secondary_arts, str):
        secondary_arts = [secondary_arts]
    combined_arts = list(primary_arts)
    for a in secondary_arts:
        if a not in combined_arts:
            combined_arts.append(a)
    primary["artifact_types"] = combined_arts

    # Sum frequencies
    primary_freq = primary.get("frequency", 0)
    secondary_freq = secondary.get("frequency", 0)
    if isinstance(primary_freq, str):
        try:
            primary_freq = int(primary_freq)
        except ValueError:
            primary_freq = 0
    if isinstance(secondary_freq, str):
        try:
            secondary_freq = int(secondary_freq)
        except ValueError:
            secondary_freq = 0
    primary["frequency"] = primary_freq + secondary_freq

    # Upgrade confidence based on layer count
    layer_count = len(primary["layers"])
    if layer_count >= 3:
        primary["confidence"] = "high"
    elif layer_count >= 2:
        primary["confidence"] = "medium"

    # Merge titles: keep longer/more descriptive one, add cross-layer note
    if len(str(secondary.get("title", ""))) > len(str(primary.get("title", ""))):
        primary["title"] = secondary["title"]

    # Keep automatable: prefer yes > partial > no
    auto_order = {"yes": 3, "partial": 2, "no": 1}
    primary_auto = auto_order.get(str(primary.get("automatable", "no")).lower(), 1)
    secondary_auto = auto_order.get(str(secondary.get("automatable", "no")).lower(), 1)
    if secondary_auto > primary_auto:
        primary["automatable"] = secondary.get("automatable")

    return primary


def deduplicate_findings(findings):
    """Deduplicate findings based on title similarity and category match.

    Returns (deduplicated_list, merge_count).
    """
    if not findings:
        return [], 0

    # Initialize each finding with layers list and merged_from
    for f in findings:
        if "layers" not in f:
            f["layers"] = [f.get("layer", "unknown")]
        if "merged_from" not in f:
            f["merged_from"] = [f["id"]]

    merged = []
    used = set()
    merge_count = 0

    for i, finding_a in enumerate(findings):
        if i in used:
            continue

        current = dict(finding_a)  # Shallow copy
        current["evidence"] = list(finding_a.get("evidence", []))
        current["artifact_types"] = list(finding_a.get("artifact_types", []))
        current["layers"] = list(finding_a.get("layers", []))
        current["merged_from"] = list(finding_a.get("merged_from", []))

        for j, finding_b in enumerate(findings):
            if j <= i or j in used:
                continue

            title_a = str(current.get("title", ""))
            title_b = str(finding_b.get("title", ""))
            cat_a = str(current.get("category", "")).lower()
            cat_b = str(finding_b.get("category", "")).lower()

            # Merge candidates: same category + similar title, OR very similar title alone
            same_category = cat_a == cat_b and cat_a != ""
            similar_title = titles_similar(title_a, title_b, threshold=3)
            very_similar_title = titles_similar(title_a, title_b, threshold=4)

            if (same_category and similar_title) or very_similar_title:
                merge_findings_pair(current, finding_b)
                used.add(j)
                merge_count += 1

        merged.append(current)
        used.add(i)

    return merged, merge_count


# ---------------------------------------------------------------------------
# Level 2: Semantic Linking
# ---------------------------------------------------------------------------

# Regex to extract Elixir file paths from evidence strings
_FILE_PATH_RE = re.compile(r'(?:lib|test|config|priv)/[\w/\-]+\.(?:ex|exs|eex|heex|sface)')


def extract_file_paths(finding):
    """Extract Elixir file paths from a finding's evidence array."""
    evidence = finding.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    paths = set()
    for entry in evidence:
        entry_str = str(entry)
        for match in _FILE_PATH_RE.findall(entry_str):
            paths.add(match)
    return paths


def semantic_link_findings(findings):
    """Level 2: Link findings that reference the same files (same category, 2+ shared paths).

    Adds 'related_to' field to each finding. Does not merge — only cross-references.
    Returns list of findings (mutated in place) and link count.
    """
    if len(findings) < 2:
        return findings, 0

    # Pre-compute file paths per finding
    path_cache = []
    for f in findings:
        path_cache.append(extract_file_paths(f))

    link_count = 0

    for i in range(len(findings)):
        for j in range(i + 1, len(findings)):
            cat_i = str(findings[i].get("category", "")).lower()
            cat_j = str(findings[j].get("category", "")).lower()

            # Same category required
            if cat_i != cat_j or not cat_i:
                continue

            shared_paths = path_cache[i] & path_cache[j]
            if len(shared_paths) >= 2:
                # Link bidirectionally
                id_i = findings[i].get("id", "")
                id_j = findings[j].get("id", "")

                if id_j not in findings[i].get("related_to", []):
                    findings[i].setdefault("related_to", []).append(id_j)
                if id_i not in findings[j].get("related_to", []):
                    findings[j].setdefault("related_to", []).append(id_i)

                link_count += 1

    return findings, link_count


# ---------------------------------------------------------------------------
# Level 3: Contradiction Detection
# ---------------------------------------------------------------------------

# Layer prefix mapping: finding ID prefix -> layer number
_LAYER_NUMBER_RE = re.compile(r'^L(\d)')

# Keywords that signal enforcement in L4 config findings
_ENFORCED_KEYWORDS = {"enforced", "required", "configured", "enabled", "checked", "rule"}

# Keywords that signal violations in L3 code or L6 architecture findings
_VIOLATION_KEYWORDS = {"violation", "missing", "absent", "inconsistent", "broken",
                       "unused", "dead", "uncovered", "untested", "hardcoded",
                       "skipped", "ignored", "drift"}


def _get_layer_number(finding):
    """Extract layer number (1-6) from finding ID prefix."""
    fid = str(finding.get("id", ""))
    m = _LAYER_NUMBER_RE.match(fid)
    if m:
        return int(m.group(1))
    return 0


def _extract_topic_words(title):
    """Extract topic words from a title for contradiction matching."""
    return significant_words(title)


def detect_contradictions(findings):
    """Level 3: Detect contradictions between config (L4) and code/arch (L3/L6).

    When L4 says a rule is 'enforced' but L3 or L6 shows violations of the
    same topic, flag as contradiction.

    Adds 'contradicts' field to involved findings.
    Returns list of findings (mutated), contradiction records, and count.
    """
    if len(findings) < 2:
        return findings, [], 0

    # Separate by layer
    l4_findings = []
    code_findings = []  # L3 and L6

    for idx, f in enumerate(findings):
        layer_num = _get_layer_number(f)
        if layer_num == 4:
            l4_findings.append((idx, f))
        elif layer_num in (3, 6):
            code_findings.append((idx, f))

    contradictions = []

    for l4_idx, l4_finding in l4_findings:
        l4_title = str(l4_finding.get("title", "")).lower()
        l4_words = _extract_topic_words(l4_title)

        # Check if L4 finding signals enforcement
        has_enforced = bool(_ENFORCED_KEYWORDS & set(l4_title.split()))
        if not has_enforced:
            # Also check in significant words
            has_enforced = bool(_ENFORCED_KEYWORDS & l4_words)

        if not has_enforced:
            continue

        for code_idx, code_finding in code_findings:
            code_title = str(code_finding.get("title", "")).lower()
            code_words = _extract_topic_words(code_title)

            # Check if code finding signals violation
            has_violation = bool(_VIOLATION_KEYWORDS & set(code_title.split()))
            if not has_violation:
                has_violation = bool(_VIOLATION_KEYWORDS & code_words)

            if not has_violation:
                continue

            # Check topic overlap: shared significant words (excluding enforcement/violation keywords)
            topic_a = l4_words - _ENFORCED_KEYWORDS - _VIOLATION_KEYWORDS
            topic_b = code_words - _ENFORCED_KEYWORDS - _VIOLATION_KEYWORDS

            shared_topic = topic_a & topic_b
            if shared_topic:
                l4_id = l4_finding.get("id", "")
                code_id = code_finding.get("id", "")
                topic_label = ", ".join(sorted(shared_topic)[:3])

                # Mark bidirectional contradiction
                if code_id not in l4_finding.get("contradicts", []):
                    findings[l4_idx].setdefault("contradicts", []).append(code_id)
                if l4_id not in code_finding.get("contradicts", []):
                    findings[code_idx].setdefault("contradicts", []).append(l4_id)

                contradictions.append({
                    "finding_a": l4_id,
                    "finding_b": code_id,
                    "topic": topic_label,
                })

    return findings, contradictions, len(contradictions)


# ---------------------------------------------------------------------------
# Sub-agent Extraction
# ---------------------------------------------------------------------------

# Mapping from layer name to sub-agent identifier
_LAYER_TO_SUBAGENT = {
    "git-history": "git-history-analyzer",
    "pr-reviews": "pr-review-analyzer",
    "code-docs": "code-docs-analyzer",
    "claude-config": "config-analyzer",
    "sessions": "session-analyzer",
    "architecture": "architecture-analyzer",
}


def extract_sub_agent(finding):
    """Determine which specialist sub-agent produced a finding from its layer."""
    layer = str(finding.get("layer", "")).lower()
    if layer in _LAYER_TO_SUBAGENT:
        return _LAYER_TO_SUBAGENT[layer]

    # Fallback: try to extract from ID prefix
    fid = str(finding.get("id", ""))
    layer_num = 0
    m = _LAYER_NUMBER_RE.match(fid)
    if m:
        layer_num = int(m.group(1))
    layer_names = {1: "git-history", 2: "pr-reviews", 3: "code-docs",
                   4: "claude-config", 5: "sessions", 6: "architecture"}
    layer_name = layer_names.get(layer_num, "")
    return _LAYER_TO_SUBAGENT.get(layer_name, "")


# ---------------------------------------------------------------------------
# Theme Assignment
# ---------------------------------------------------------------------------

def _build_adjacency(findings):
    """Build adjacency list from related_to and contradicts links."""
    id_to_idx = {}
    for idx, f in enumerate(findings):
        id_to_idx[f.get("id", "")] = idx

    adj = {i: set() for i in range(len(findings))}

    for idx, f in enumerate(findings):
        for related_id in f.get("related_to", []):
            if related_id in id_to_idx:
                other = id_to_idx[related_id]
                adj[idx].add(other)
                adj[other].add(idx)
        # Contradictions also form theme connections
        for contra_id in f.get("contradicts", []):
            if contra_id in id_to_idx:
                other = id_to_idx[contra_id]
                adj[idx].add(other)
                adj[other].add(idx)

    return adj


def _find_connected_components(adj, n):
    """Find connected components using BFS. Returns list of sets of indices."""
    visited = set()
    components = []

    for start in range(n):
        if start in visited:
            continue
        component = set()
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            for neighbor in adj.get(node, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
        components.append(component)

    return components


def _name_theme(findings, indices):
    """Generate a theme name from the most common category words in the component."""
    word_counts = Counter()
    categories = Counter()

    for idx in indices:
        f = findings[idx]
        cat = str(f.get("category", "uncategorized")).lower()
        categories[cat] += 1
        # Also collect title words for more specific naming
        title = str(f.get("title", ""))
        for word in significant_words(title):
            word_counts[word] += 1

    # Use most common category as base
    top_category = categories.most_common(1)[0][0] if categories else "uncategorized"

    # If there are specific topic words, use top 1-2 for specificity
    top_words = [w for w, _ in word_counts.most_common(3)]

    if top_words:
        # Combine category context with specific words
        specifics = "-".join(top_words[:2])
        theme_name = f"{top_category}/{specifics}"
    else:
        theme_name = top_category

    return theme_name


def assign_themes(findings):
    """Assign theme labels to findings based on connected components.

    Findings linked via related_to or contradicts form theme groups.
    Isolated findings get theme from their category.

    Returns findings (mutated with 'theme' field) and theme summary list.
    """
    if not findings:
        return findings, []

    adj = _build_adjacency(findings)
    components = _find_connected_components(adj, len(findings))

    themes_summary = []

    for component in components:
        if len(component) == 1:
            # Singleton: theme is just category
            idx = next(iter(component))
            cat = str(findings[idx].get("category", "uncategorized")).lower()
            findings[idx]["theme"] = cat
            # Don't add singleton themes to the summary (too noisy)
            continue

        # Multi-finding component: generate descriptive theme name
        theme_name = _name_theme(findings, component)
        finding_ids = []
        total_priority = 0.0

        for idx in component:
            findings[idx]["theme"] = theme_name
            finding_ids.append(findings[idx].get("id", ""))
            total_priority += findings[idx].get("priority_score", 0)

        themes_summary.append({
            "name": theme_name,
            "finding_ids": sorted(finding_ids),
            "total_priority": round(total_priority, 2),
        })

    # Sort themes by total_priority descending
    themes_summary.sort(key=lambda t: t["total_priority"], reverse=True)

    return findings, themes_summary


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

SEVERITY_SCORES = {"critical": 4, "high": 3, "medium": 2, "low": 1}
EFFORT_SCORES = {"tiny": 4, "small": 3, "medium": 2, "large": 1}
AUTOMATABLE_BONUS = {"yes": 1.5, "partial": 1.0, "no": 0.5}
CONFIDENCE_BONUS = {"high": 1.5, "medium": 1.0, "low": 0.7}


def score_finding(finding):
    """Compute priority score for a finding."""
    severity = str(finding.get("severity", "low")).lower()
    effort = str(finding.get("effort", "large")).lower()
    automatable = str(finding.get("automatable", "no")).lower()
    confidence = str(finding.get("confidence", "low")).lower()

    severity_score = SEVERITY_SCORES.get(severity, 1)
    effort_score = EFFORT_SCORES.get(effort, 1)
    automatable_bonus = AUTOMATABLE_BONUS.get(automatable, 0.5)
    confidence_bonus = CONFIDENCE_BONUS.get(confidence, 0.7)

    priority = severity_score * effort_score * automatable_bonus * confidence_bonus
    return round(priority, 2)


def compute_roi(finding):
    """Compute ROI score: (frequency × severity) / effort.

    ROI answers "what gives me the most bang for the buck?" — higher frequency
    and severity with lower effort = highest return on fixing.
    """
    frequency = finding.get("frequency", 1)
    if isinstance(frequency, str):
        # Extract number from strings like "23 commits" or "8/15 sessions"
        import re as _re
        nums = _re.findall(r'\d+', str(frequency))
        frequency = int(nums[0]) if nums else 1

    severity = str(finding.get("severity", "low")).lower()
    effort = str(finding.get("effort", "large")).lower()

    severity_score = SEVERITY_SCORES.get(severity, 1)
    # Effort as cost (inverse of effort_score): tiny=1, small=2, medium=3, large=4
    effort_cost = {"tiny": 1, "small": 2, "medium": 3, "large": 4}.get(effort, 4)

    roi = round((frequency * severity_score) / effort_cost, 1)
    return roi


def detect_root_causes(findings):
    """Detect root cause chains across layers.

    If a code-layer finding (L3/L6) references the same files/modules as a
    git/PR-layer finding (L1/L2), the code finding is likely the root cause.
    Fixing it would resolve the git/PR symptoms.
    """
    root_cause_links = []

    # Group findings by layer type
    code_findings = [f for f in findings if _get_layer_number(f) in (3, 6)]
    symptom_findings = [f for f in findings if _get_layer_number(f) in (1, 2)]

    for cause in code_findings:
        cause_id = cause.get("id", "")
        cause_files = extract_file_paths(cause)
        cause_words = _significant_words(cause.get("title", ""))

        for symptom in symptom_findings:
            symptom_id = symptom.get("id", "")
            symptom_words = _significant_words(symptom.get("title", ""))

            # Check if they share significant title words (same topic)
            shared = cause_words & symptom_words
            if len(shared) >= 2:
                # Code finding is likely root cause of git/PR symptom
                if "root_cause_of" not in cause:
                    cause["root_cause_of"] = []
                cause["root_cause_of"].append(symptom_id)
                root_cause_links.append({
                    "cause": cause_id,
                    "symptom": symptom_id,
                    "shared_topic": sorted(shared)[:3],
                })

    return root_cause_links


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_finding(finding, priority_score):
    """Format a finding dict for JSON output."""
    # Ensure all expected fields exist. Use `or` to handle None values
    # from YAML keys that had no value (parsed as None, not missing).
    layers = finding.get("layers") or [finding.get("layer", "unknown")]
    merged_from = finding.get("merged_from") or [finding.get("id", "?")]
    evidence = finding.get("evidence") or []
    artifact_types = finding.get("artifact_types") or []
    frequency = finding.get("frequency") or 0

    if isinstance(evidence, str):
        evidence = [evidence]
    if isinstance(artifact_types, str):
        artifact_types = [artifact_types]
    if isinstance(frequency, str):
        try:
            frequency = int(frequency)
        except ValueError:
            frequency = 0

    return {
        "id": finding.get("id", "?"),
        "layers": layers,
        "category": str(finding.get("category", "uncategorized")).lower(),
        "title": str(finding.get("title", "Untitled finding")),
        "severity": str(finding.get("severity", "low")).lower(),
        "effort": str(finding.get("effort", "medium")).lower(),
        "automatable": str(finding.get("automatable", "no")).lower(),
        "artifact_types": artifact_types,
        "evidence": evidence,
        "frequency": frequency,
        "confidence": str(finding.get("confidence", "low")).lower(),
        "priority_score": priority_score,
        "roi_score": compute_roi(finding),
        "merged_from": merged_from,
        # Level 2: semantic links
        "related_to": finding.get("related_to", []),
        "root_cause_of": finding.get("root_cause_of", []),
        # Level 3: contradiction links
        "contradicts": finding.get("contradicts", []),
        # Theme and sub-agent
        "theme": finding.get("theme", "uncategorized"),
        "sub_agent": extract_sub_agent(finding),
    }


def build_summaries(formatted_findings):
    """Build category, severity, and artifact summary dicts."""
    by_category = Counter()
    by_severity = Counter()
    artifact_counts = Counter()
    automatable_count = 0

    for f in formatted_findings:
        category = f.get("category", "uncategorized")
        by_category[category] += 1

        severity = f.get("severity", "low")
        by_severity[severity] += 1

        for art in f.get("artifact_types", []):
            artifact_counts[art] += 1

        if f.get("automatable", "no") in ("yes", "partial"):
            automatable_count += 1

    return {
        "by_category": dict(sorted(by_category.items())),
        "by_severity": dict(sorted(by_severity.items(), key=lambda x: SEVERITY_SCORES.get(x[0], 0), reverse=True)),
        "automatable_count": automatable_count,
        "artifact_summary": dict(sorted(artifact_counts.items())),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _merge_and_output(layers_dir, output_path=None):
    """Core merge logic shared by main() and self-test.

    Returns the result dict (for testability) or None on empty input.
    """
    # Step 1: Read all layer files
    layer_files = read_layer_files(layers_dir)

    empty_result = {
        "total_findings": 0,
        "merged_findings": 0,
        "findings": [],
        "by_category": {},
        "by_severity": {},
        "automatable_count": 0,
        "artifact_summary": {},
        "themes": [],
        "contradictions": [],
    }

    if not layer_files:
        output_json = json.dumps(empty_result, indent=2, ensure_ascii=False)
        if output_path:
            _write_output(output_path, output_json)
        else:
            print(output_json)
        return empty_result

    # Step 2: Parse YAML frontmatter from each finding
    all_findings = []
    parse_errors = 0

    for filename, content in layer_files:
        try:
            findings = parse_yaml_frontmatter(content, source_name=filename)
            found_count = len(findings)
            for fm, body in findings:
                all_findings.append(fm)
            if found_count == 0:
                print(
                    f"Warning: no findings parsed from {filename} "
                    f"({len(content)} bytes, {content.count('---')} '---' markers found)",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Error parsing {filename}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)
            parse_errors += 1

    if not all_findings:
        print(
            f"Warning: no findings parsed from {len(layer_files)} files "
            f"({parse_errors} parse errors).",
            file=sys.stderr,
        )
        output_json = json.dumps(empty_result, indent=2, ensure_ascii=False)
        if output_path:
            _write_output(output_path, output_json)
        else:
            print(output_json)
        return empty_result

    total_before_dedup = len(all_findings)

    # Step 3: Level 1 — Title-similarity deduplication
    deduplicated, merge_count = deduplicate_findings(all_findings)

    # Step 4: Level 2 — Semantic linking (cross-reference by shared file paths)
    deduplicated, link_count = semantic_link_findings(deduplicated)

    # Step 5: Level 3 — Contradiction detection (config vs code/arch)
    deduplicated, contradictions, contradiction_count = detect_contradictions(deduplicated)

    # Step 6: Score and sort
    scored = []
    for finding in deduplicated:
        priority = score_finding(finding)
        formatted = format_finding(finding, priority)
        scored.append(formatted)

    # Step 7: Detect root cause chains (before sorting, needs raw findings)
    root_cause_chains = detect_root_causes(deduplicated)
    # Re-format after root_cause_of may have been added
    scored = []
    for finding in deduplicated:
        priority = score_finding(finding)
        formatted = format_finding(finding, priority)
        scored.append(formatted)

    # Step 8: Sort by priority descending
    scored.sort(key=lambda f: f["priority_score"], reverse=True)

    # Step 9: Assign themes (needs priority_score in findings)
    scored, themes = assign_themes(scored)

    # Build summaries
    summaries = build_summaries(scored)

    # Top ROI findings
    top_roi = sorted(scored, key=lambda f: f.get("roi_score", 0), reverse=True)[:5]

    result = {
        "total_findings": len(scored),
        "merged_findings": merge_count,
        "findings": scored,
        "by_category": summaries["by_category"],
        "by_severity": summaries["by_severity"],
        "automatable_count": summaries["automatable_count"],
        "artifact_summary": summaries["artifact_summary"],
        # Level 2+3 summaries
        "themes": themes,
        "contradictions": contradictions,
        # ROI and root cause analysis
        "top_roi": [{"id": f["id"], "title": f["title"], "roi_score": f.get("roi_score", 0)} for f in top_roi],
        "root_cause_chains": root_cause_chains,
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)

    if output_path:
        _write_output(output_path, output_json)
    else:
        print(output_json)

    # Summary to stderr
    parts = [
        f"Merged {total_before_dedup} findings -> {len(scored)} ({merge_count} merged)",
    ]
    if link_count:
        parts.append(f"{link_count} semantic links")
    if contradiction_count:
        parts.append(f"{contradiction_count} contradictions")
    if themes:
        parts.append(f"{len(themes)} themes")
    parts.append(
        f"Top priority: {scored[0]['priority_score'] if scored else 'N/A'}"
    )
    print(". ".join(parts), file=sys.stderr)

    return result


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

# Sample 1: Clean YAML frontmatter (no code fences)
_SAMPLE_SHALLOW_CLEAN = """\
# Layer 1: Git History

## Findings

---
id: L1-001
layer: git-history
category: translation
title: "Missing gettext calls in user-facing templates"
severity: high
effort: small
automatable: yes
artifact_types: [credo-check, ci-step]
evidence:
  - "abc1234: fix missing gettext in user profile"
  - "PR #142: reviewer comment about gettext"
frequency: 23
confidence: high
---

This pattern was found across 23 commits over the last 6 months.

---
id: L1_002
layer: git-history
category: naming
title: "Inconsistent module naming for billing contexts"
severity: medium
effort: medium
automatable: partial
artifact_types:
  - credo-check
evidence:
  - "def5678: renamed billing to payments"
  - "lib/app/billing.ex vs lib/app/payments.ex"
frequency: 8
confidence: medium
---

Two different naming conventions used for the same domain.
"""

# Sample 2: Code-fenced YAML (```yaml ... ```)
_SAMPLE_SHALLOW_FENCED = """\
# Layer 3: Code & Docs

## Findings

```yaml
---
id: L3-A01
layer: code-docs
category: security
title: "Authorization checks missing in admin LiveViews"
severity: critical
effort: medium
automatable: partial
artifact_types: [review-prompt, claude-md-rule]
evidence:
  - "lib/app_web/live/admin/users_live.ex:12 — no authorize in mount"
  - "lib/app_web/live/admin/settings_live.ex:8 — no authorize in handle_event"
frequency: 5
confidence: high
---
```

Critical security gap — admin views lack per-event authorization.

```yaml
---
id: L3-A02
layer: code-docs
category: documentation
title: >
  Missing @moduledoc in context modules
  across billing and accounts domains
severity: low
effort: tiny
automatable: yes
artifact_types: [credo-check]
evidence:
  - "lib/app/billing.ex — no @moduledoc"
  - "lib/app/accounts.ex — no @moduledoc"
frequency: 12
confidence: medium
---
```

Most context modules lack documentation.
"""

# Sample 3: Deep mode consolidated.md with mixed formats and extra whitespace
_SAMPLE_DEEP_CONSOLIDATED = """\
# Layer 6: Architecture — Deep Analysis

**Mode**: deep (3 specialist sub-agents)
**Sub-agents**: 3/3 successful
**Raw findings**: 5
**After dedup**: 3

## Findings

---
id: L6-001
layer: architecture
category: architecture
title: "Cross-boundary calls from web to internal contexts"
severity: high
effort: large
automatable: no
artifact_types: [review-prompt]
evidence:
  - "lib/app_web/live/dashboard_live.ex calls App.Internal.Metrics directly"
  - "lib/app_web/live/report_live.ex calls App.Internal.Analytics directly"
frequency: 7
confidence: high
---

Web layer bypasses the public API of internal contexts.

  ---
id: L6-002
layer: architecture
category: architecture
title: |
  Circular dependency between Accounts
  and Billing contexts detected by xref
severity: high
effort: large
automatable: no
artifact_types:
  - review-prompt
  - skill
evidence:
  - "mix xref graph shows Accounts -> Billing -> Accounts cycle"
frequency: 1
confidence: high
  ---

This creates compile-time dependency issues and makes testing harder.

---
id: L6-003
layer: architecture
category: ci-cd
title: "Dead code modules detected by mix xref unreachable"
severity: low
effort: small
automatable: yes
artifact_types: [ci-step]
evidence:
  - "lib/app/legacy/old_importer.ex — unreachable"
  - "lib/app/legacy/csv_parser.ex — unreachable"
frequency: 2
confidence: medium
---

Two modules are completely unreachable from the application's entry points.

## Sub-Agent Status

| Sub-Agent | Status | Findings | Notes |
|-----------|--------|----------|-------|
| L6a Boundary | OK | 1 | |
| L6b Coupling | OK | 1 | |
| L6c Growth | OK | 1 | |
"""


def _run_self_test():
    """Run self-test with 3 sample fixtures. Returns True on pass."""
    print("Running self-test...", file=sys.stderr)
    failures = []

    with tempfile.TemporaryDirectory(prefix="merge-findings-test-") as tmpdir:
        # ---------------------------------------------------------------
        # Test 1: Shallow mode — clean YAML (no code fences)
        # ---------------------------------------------------------------
        shallow_dir = os.path.join(tmpdir, "shallow")
        os.makedirs(shallow_dir)
        with open(os.path.join(shallow_dir, "git-history.md"), "w") as f:
            f.write(_SAMPLE_SHALLOW_CLEAN)

        result1 = _merge_and_output(shallow_dir, output_path=os.path.join(tmpdir, "out1.json"))
        test1_count = result1["total_findings"]
        if test1_count != 2:
            failures.append(f"Test 1 (clean YAML): expected 2 findings, got {test1_count}")
        else:
            # Verify id formats: L1-001 and L1_002
            ids = {f["id"] for f in result1["findings"]}
            if "L1-001" not in ids:
                failures.append(f"Test 1: missing L1-001 in {ids}")
            if "L1_002" not in ids:
                failures.append(f"Test 1: missing L1_002 in {ids}")

        # ---------------------------------------------------------------
        # Test 2: Shallow mode — code-fenced YAML + multi-line folded title
        # ---------------------------------------------------------------
        fenced_dir = os.path.join(tmpdir, "fenced")
        os.makedirs(fenced_dir)
        with open(os.path.join(fenced_dir, "code-docs.md"), "w") as f:
            f.write(_SAMPLE_SHALLOW_FENCED)

        result2 = _merge_and_output(fenced_dir, output_path=os.path.join(tmpdir, "out2.json"))
        test2_count = result2["total_findings"]
        if test2_count != 2:
            failures.append(f"Test 2 (fenced YAML): expected 2 findings, got {test2_count}")
        else:
            ids2 = {f["id"] for f in result2["findings"]}
            if "L3-A01" not in ids2:
                failures.append(f"Test 2: missing L3-A01 in {ids2}")
            if "L3-A02" not in ids2:
                failures.append(f"Test 2: missing L3-A02 in {ids2}")
            # Check that multi-line folded title was parsed
            for f in result2["findings"]:
                if f["id"] == "L3-A02":
                    if "moduledoc" not in f["title"].lower():
                        failures.append(
                            f"Test 2: folded title not parsed. Got: {f['title']!r}"
                        )

        # ---------------------------------------------------------------
        # Test 3: Deep mode — L{N}/consolidated.md layout
        # ---------------------------------------------------------------
        deep_dir = os.path.join(tmpdir, "deep")
        os.makedirs(os.path.join(deep_dir, "L6"))
        with open(os.path.join(deep_dir, "L6", "consolidated.md"), "w") as f:
            f.write(_SAMPLE_DEEP_CONSOLIDATED)

        result3 = _merge_and_output(deep_dir, output_path=os.path.join(tmpdir, "out3.json"))
        test3_count = result3["total_findings"]
        if test3_count != 3:
            failures.append(f"Test 3 (deep mode): expected 3 findings, got {test3_count}")
        else:
            ids3 = {f["id"] for f in result3["findings"]}
            for expected_id in ["L6-001", "L6-002", "L6-003"]:
                if expected_id not in ids3:
                    failures.append(f"Test 3: missing {expected_id} in {ids3}")
            # Check literal block title for L6-002
            for f in result3["findings"]:
                if f["id"] == "L6-002":
                    if "circular" not in f["title"].lower():
                        failures.append(
                            f"Test 3: literal title not parsed. Got: {f['title']!r}"
                        )

        # ---------------------------------------------------------------
        # Test 4: Combined — shallow + deep in same run (all 3 files)
        # ---------------------------------------------------------------
        combined_dir = os.path.join(tmpdir, "combined")
        os.makedirs(os.path.join(combined_dir, "L6"))
        with open(os.path.join(combined_dir, "git-history.md"), "w") as f:
            f.write(_SAMPLE_SHALLOW_CLEAN)
        with open(os.path.join(combined_dir, "code-docs.md"), "w") as f:
            f.write(_SAMPLE_SHALLOW_FENCED)
        with open(os.path.join(combined_dir, "L6", "consolidated.md"), "w") as f:
            f.write(_SAMPLE_DEEP_CONSOLIDATED)

        result4 = _merge_and_output(combined_dir, output_path=os.path.join(tmpdir, "out4.json"))
        test4_count = result4["total_findings"]
        if test4_count != 7:
            failures.append(
                f"Test 4 (combined): expected 7 findings, got {test4_count}"
            )

    # Report
    total_tests = 4
    passed = total_tests - len(failures)

    if failures:
        print(f"\nSelf-test: {passed}/{total_tests} passed, {len(failures)} FAILED",
              file=sys.stderr)
        for f in failures:
            print(f"  FAIL: {f}", file=sys.stderr)
        return False
    else:
        print(f"\nSelf-test: {total_tests}/{total_tests} passed", file=sys.stderr)
        return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Merge findings from Inspector layer analysis files. "
            "Deduplicates similar findings, cross-references across layers, "
            "and scores by priority."
        ),
    )
    parser.add_argument(
        "layers_dir",
        nargs="?",
        default=None,
        help="Directory containing layer .md files (e.g., .claude/inspector/layers/)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write JSON to this file instead of stdout.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in self-test with sample fixtures and exit.",
    )
    args = parser.parse_args()

    if args.self_test:
        ok = _run_self_test()
        sys.exit(0 if ok else 1)

    if not args.layers_dir:
        parser.error("layers_dir is required (or use --self-test)")

    layers_dir = os.path.abspath(args.layers_dir)

    if not os.path.isdir(layers_dir):
        print(f"Error: not a directory: {layers_dir}", file=sys.stderr)
        sys.exit(1)

    _merge_and_output(layers_dir, output_path=args.output)


def _write_output(path, content):
    """Write content to a file, creating directories as needed."""
    out_dir = os.path.dirname(os.path.abspath(path))
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")
    print(f"Output written to {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
