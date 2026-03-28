#!/usr/bin/env python3
"""Generate targeted hard negatives for confusable skill pairs.

Reads the confusion matrix from cached trigger results to identify
which skill pairs haiku confuses most, then generates boundary prompts
targeting those specific pairs.

Research basis:
  - "Not All Negatives are Equal" (Suresh & Ong, EMNLP 2021)
    — label-aware contrastive negatives for fine-grained classification
  - Dynabench (Kiela et al., NAACL 2021)
    — adversarial benchmark targeting current model weaknesses

Usage:
    python3 lab/eval/triggers/generate_confusable_pairs.py --show     # Show confusion matrix
    python3 lab/eval/triggers/generate_confusable_pairs.py --top 10   # Generate for top-10 pairs
    python3 lab/eval/triggers/generate_confusable_pairs.py --inject   # Add to trigger files
"""

import argparse
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.matchers import parse_frontmatter
from lab.eval.trigger_scorer import build_confusion_matrix, load_all_descriptions

PLUGIN_ROOT = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix")
TRIGGERS_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(TRIGGERS_DIR, "results")

# Known confusable pairs (from domain knowledge, to be augmented by confusion matrix)
KNOWN_CONFUSABLE_PAIRS = [
    ("investigate", "review"),
    ("investigate", "perf"),
    ("n1-check", "ecto-patterns"),
    ("n1-check", "perf"),
    ("plan", "full"),
    ("plan", "work"),
    ("quick", "investigate"),
    ("quick", "work"),
    ("review", "challenge"),
    ("liveview-patterns", "phoenix-contexts"),
    ("ecto-patterns", "phoenix-contexts"),
    ("perf", "assigns-audit"),
]


def get_all_descriptions() -> dict[str, str]:
    """Read all skill descriptions."""
    skills_dir = os.path.join(PLUGIN_ROOT, "skills")
    descriptions = {}
    for name in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, name, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue
        with open(skill_path) as f:
            content = f.read()
        fm = parse_frontmatter(content)
        desc = str(fm.get("description", ""))
        if desc:
            descriptions[name] = desc
    return descriptions


def get_top_confusable_pairs(matrix: dict, top_n: int = 10) -> list[tuple[str, str, int]]:
    """Extract top-N most confused skill pairs from the matrix."""
    pairs: list[tuple[str, str, int]] = []
    seen = set()
    for skill, confusions in matrix.items():
        for other, count in confusions.items():
            key = tuple(sorted([skill, other]))
            if key not in seen:
                seen.add(key)
                pairs.append((skill, other, count))
    pairs.sort(key=lambda x: -x[2])
    return pairs[:top_n]


def generate_boundary_prompts(
    skill_a: str, desc_a: str,
    skill_b: str, desc_b: str,
    count: int = 5,
) -> list[dict] | None:
    """Generate prompts that sit on the decision boundary between two skills."""
    prompt = f"""Generate {count} user prompts that are GENUINELY HARD to route between these two skills:

SKILL A: {skill_a} — {desc_a[:200]}
SKILL B: {skill_b} — {desc_b[:200]}

Each prompt should be ambiguous — a reasonable person could argue it belongs to either skill.

Output JSON array:
[
  {{
    "prompt": "the ambiguous user message",
    "correct_skill": "{skill_a}" or "{skill_b}",
    "confidence": 0.6,
    "reasoning": "why this is hard to route"
  }}
]

RULES:
- Prompts MUST be realistic developer messages
- Do NOT mention skill names or commands in prompts
- confidence 0.5-0.7 = genuinely ambiguous boundary cases
- Mix formality: some terse, some verbose, some with typos
- Output ONLY valid JSON, nothing else"""

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--model", "sonnet",
                "--output-format", "text",
                "--max-budget-usd", "0.50",
                "--no-session-persistence",
            ],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            return None

        text = result.stdout.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return None

    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate confusable pair boundary prompts")
    parser.add_argument("--show", action="store_true", help="Show confusion matrix only")
    parser.add_argument("--top", type=int, default=10, help="Number of top pairs to target")
    parser.add_argument("--inject", action="store_true", help="Add prompts to trigger files")
    parser.add_argument("--count", type=int, default=5, help="Boundary prompts per pair")
    parser.add_argument("--known-only", action="store_true", help="Use known pairs (skip confusion matrix)")
    args = parser.parse_args()

    all_descriptions = get_all_descriptions()

    # Build confusion matrix from cached results
    if not args.known_only:
        matrix = build_confusion_matrix(all_descriptions)
        if matrix:
            pairs = get_top_confusable_pairs(matrix, args.top)
            print(f"Confusion matrix: {len(pairs)} top pairs from cached results")
        else:
            print("No cached results — using known confusable pairs", file=sys.stderr)
            pairs = [(a, b, 0) for a, b in KNOWN_CONFUSABLE_PAIRS[:args.top]]
    else:
        pairs = [(a, b, 0) for a, b in KNOWN_CONFUSABLE_PAIRS[:args.top]]

    if args.show:
        print(f"\nTop {len(pairs)} confusable pairs:")
        print("-" * 60)
        for a, b, count in pairs:
            print(f"  {a} <-> {b} (confusions: {count})")
        return

    # Generate boundary prompts for each pair
    all_boundary_prompts: dict[str, list[dict]] = {}
    for a, b, count in pairs:
        if a not in all_descriptions or b not in all_descriptions:
            continue
        print(f"  Generating {args.count} boundary prompts for {a} <-> {b}...", end=" ", flush=True)
        prompts = generate_boundary_prompts(
            a, all_descriptions[a],
            b, all_descriptions[b],
            args.count,
        )
        if prompts:
            all_boundary_prompts[f"{a}:{b}"] = prompts
            print(f"got {len(prompts)}")
        else:
            print("FAILED")

    # Save boundary prompts
    output_path = os.path.join(TRIGGERS_DIR, "_confusable_pairs.json")
    with open(output_path, "w") as f:
        json.dump({
            "generated_at": __import__("datetime").datetime.now().isoformat(),
            "pairs": all_boundary_prompts,
            "total_prompts": sum(len(v) for v in all_boundary_prompts.values()),
        }, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nSaved to {output_path}: {sum(len(v) for v in all_boundary_prompts.values())} boundary prompts")

    # Optionally inject into trigger files
    if args.inject:
        injected = 0
        for pair_key, prompts in all_boundary_prompts.items():
            skill_a, skill_b = pair_key.split(":")
            for p in prompts:
                correct = p.get("correct_skill", skill_a)
                wrong = skill_b if correct == skill_a else skill_a

                # Add as hard_should_not_trigger for the wrong skill
                trigger_path = os.path.join(TRIGGERS_DIR, f"{wrong}.json")
                if not os.path.isfile(trigger_path):
                    continue

                with open(trigger_path) as f:
                    data = json.load(f)

                if "hard_should_not_trigger" not in data:
                    data["hard_should_not_trigger"] = []

                data["hard_should_not_trigger"].append({
                    "prompt": p["prompt"],
                    "axis": "confusable",
                    "confusable_with": correct,
                })
                injected += 1

                with open(trigger_path, "w") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")

        print(f"Injected {injected} boundary prompts into trigger files")


if __name__ == "__main__":
    main()
