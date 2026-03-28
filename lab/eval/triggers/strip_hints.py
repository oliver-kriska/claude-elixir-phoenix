#!/usr/bin/env python3
"""Strip routing hints from trigger test prompts.

Removes em-dash annotations like " — belongs to plan skill" and
" — /phx:investigate (debugging specific error)" from trigger prompts.
These hints leak the correct answer to haiku during behavioral testing.

Research basis: Oren et al. (ICLR 2024) "Proving Test Set Contamination
in Black Box Language Models" — indirect contamination via answer leakage.

Usage:
    python3 lab/eval/triggers/strip_hints.py              # Clean all files
    python3 lab/eval/triggers/strip_hints.py --dry-run     # Show what would change
    python3 lab/eval/triggers/strip_hints.py --stats        # Count hints only
"""

import argparse
import json
import os
import re
import sys

TRIGGERS_DIR = os.path.dirname(os.path.abspath(__file__))

# Match hint annotations at end of prompts:
# " — belongs to plan skill" (em-dash)
# " → ecto-patterns (broad Ecto guidance)" (arrow)
# " (should use: security)" (parenthetical at end)
# " (→ /ecto-patterns)" (parenthetical arrow)
HINT_PATTERN = re.compile(
    r"("
    r"\s*\u2014\s*.+$"     # em-dash: " — hint"
    r"|\s*\u2192\s*.+$"    # arrow: " → hint"
    r"|\s+\(should use:\s*.+\)$"  # parenthetical: " (should use: X)"
    r"|\s*\(\u2192\s*.+\)$"  # parenthetical arrow: " (→ /skill)"
    r")"
)


def strip_hint(prompt: str) -> str:
    """Remove em-dash hint annotation from a prompt."""
    return HINT_PATTERN.sub("", prompt).strip()


def process_file(path: str, dry_run: bool = False) -> dict:
    """Process one trigger JSON file. Returns change stats."""
    with open(path) as f:
        data = json.load(f)

    stats = {"file": os.path.basename(path), "changes": 0, "details": []}

    for key in ["should_trigger", "should_not_trigger",
                "hard_should_trigger", "hard_should_not_trigger"]:
        if key not in data:
            continue
        prompts = data[key]
        for i, prompt in enumerate(prompts):
            # Handle both string prompts and dict prompts (hard tier)
            if isinstance(prompt, str):
                cleaned = strip_hint(prompt)
                if cleaned != prompt:
                    stats["changes"] += 1
                    stats["details"].append({
                        "key": key, "index": i,
                        "before": prompt, "after": cleaned,
                    })
                    if not dry_run:
                        prompts[i] = cleaned
            elif isinstance(prompt, dict) and "prompt" in prompt:
                cleaned = strip_hint(prompt["prompt"])
                if cleaned != prompt["prompt"]:
                    stats["changes"] += 1
                    stats["details"].append({
                        "key": key, "index": i,
                        "before": prompt["prompt"], "after": cleaned,
                    })
                    if not dry_run:
                        prompt["prompt"] = cleaned

    if not dry_run and stats["changes"] > 0:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Strip routing hints from trigger prompts")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--stats", action="store_true", help="Count hints only")
    args = parser.parse_args()

    total_changes = 0
    total_files = 0
    files_changed = 0

    for filename in sorted(os.listdir(TRIGGERS_DIR)):
        if not filename.endswith(".json") or filename.startswith("_"):
            continue
        path = os.path.join(TRIGGERS_DIR, filename)
        total_files += 1

        stats = process_file(path, dry_run=args.dry_run or args.stats)

        if stats["changes"] > 0:
            files_changed += 1
            total_changes += stats["changes"]

            if not args.stats:
                print(f"\n{stats['file']}: {stats['changes']} hint(s) stripped")
                for d in stats["details"]:
                    print(f"  [{d['key']}][{d['index']}]")
                    print(f"    BEFORE: {d['before']}")
                    print(f"    AFTER:  {d['after']}")

    mode = "DRY RUN" if args.dry_run else ("STATS" if args.stats else "DONE")
    print(f"\n[{mode}] {total_changes} hints stripped from {files_changed}/{total_files} files")


if __name__ == "__main__":
    main()
