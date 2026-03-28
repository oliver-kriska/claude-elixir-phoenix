#!/usr/bin/env python3
"""Generate a diverse adversarial prompt corpus for behavioral eval.

Uses Sonnet (NOT haiku, since haiku is the judge) to generate realistic
developer prompts with controlled variation across difficulty axes.

Research basis:
  - Dynabench (Kiela et al., NAACL 2021) — adversarial, non-saturating benchmarks
  - LiveBench (White et al., 2024) — temporal refresh prevents saturation
  - Model Collapse (Shumailov et al., Nature 2024) — use different model than judge
  - AdaTest (Ribeiro & Lundberg, ACL 2022) — LLM-adversarial test generation

Usage:
    python3 lab/eval/triggers/generate_hard_corpus.py                    # Generate full corpus
    python3 lab/eval/triggers/generate_hard_corpus.py --count 50         # Generate 50 prompts
    python3 lab/eval/triggers/generate_hard_corpus.py --dry-run          # Show prompt only
    python3 lab/eval/triggers/generate_hard_corpus.py --confusable-only  # Only confusable pairs
"""

import argparse
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.matchers import parse_frontmatter

PLUGIN_ROOT = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix")
TRIGGERS_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_PATH = os.path.join(TRIGGERS_DIR, "_corpus.json")

# Difficulty axes from CheckList (Ribeiro et al., ACL 2020)
AXES = [
    "terse",              # 1-3 words, minimal context
    "typo",               # Realistic misspellings
    "multi_intent",       # Two skills needed
    "verbose",            # Long, rambling, frustrated
    "confusable",         # Boundary between two similar skills
    "context_dependent",  # Needs file context to route
]

# Formality levels from real developer input
FORMALITY_LEVELS = [
    "terse_command",      # "fix auth"
    "casual_question",    # "hey why isn't my form working?"
    "formal_request",     # "Please review the authentication module"
    "frustrated_rant",    # "this keeps breaking and I've tried everything"
    "copy_pasted_error",  # "** (Ecto.NoResultsError) expected at least..."
]


def get_all_skill_descriptions() -> dict[str, str]:
    """Read all skill names and descriptions."""
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


def generate_batch(
    all_descriptions: dict[str, str],
    batch_size: int = 20,
    axis: str | None = None,
    formality: str | None = None,
) -> list[dict] | None:
    """Generate a batch of adversarial prompts using Sonnet."""
    desc_list = "\n".join(f"- {name}: {desc[:120]}" for name, desc in all_descriptions.items())

    axis_instruction = f"Focus on the '{axis}' difficulty axis." if axis else "Mix all difficulty axes evenly."
    formality_instruction = f"Use '{formality}' formality level." if formality else "Mix all formality levels."

    prompt = f"""You are generating adversarial test prompts for a skill routing evaluation.

AVAILABLE SKILLS:
{desc_list}

DIFFICULTY AXES:
- terse: 1-3 words only ("fix auth", "ecto preloads")
- typo: Realistic misspellings ("liveveiw crashs", "chageset validation")
- multi_intent: Two skills in one ("review auth and plan billing")
- verbose: Long frustrated rambling with buried intent
- confusable: Sits on boundary between 2 similar skills
- context_dependent: Needs file context to route ("this doesn't work")

FORMALITY LEVELS:
- terse_command, casual_question, formal_request, frustrated_rant, copy_pasted_error

{axis_instruction}
{formality_instruction}

Generate EXACTLY {batch_size} prompts as a JSON array. Each entry:
{{
  "prompt": "the user's message",
  "correct_skill": "skill-name or null if ambiguous",
  "axis": "terse|typo|multi_intent|verbose|confusable|context_dependent",
  "formality": "terse_command|casual_question|formal_request|frustrated_rant|copy_pasted_error",
  "confusable_with": "other-skill-name (only for confusable axis, else null)",
  "confidence": 0.9
}}

RULES:
- Prompts must be realistic developer messages, NOT test descriptions
- Do NOT include skill names, command names, or routing hints in prompts
- Each prompt should be genuinely hard to route
- confidence: 1.0 = unambiguous, 0.5 = genuinely ambiguous, 0.0 = impossible without context
- For confusable: pick skill pairs that are genuinely hard to distinguish
- For typo: use realistic typos (adjacent keys, missing letters, transpositions)
- For verbose: 20-50 words of frustrated developer rambling
- Output ONLY valid JSON array, nothing else"""

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--model", "sonnet",
                "--output-format", "text",
                "--max-budget-usd", "1.00",
                "--no-session-persistence",
            ],
            capture_output=True, text=True, timeout=120,
        )

        if result.returncode != 0:
            print(f"  ERROR: claude returned {result.returncode}", file=sys.stderr)
            return None

        text = result.stdout.strip()
        # Strip markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        # Find JSON array
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])

        print(f"  ERROR: No JSON array found in response", file=sys.stderr)
        return None

    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate adversarial prompt corpus")
    parser.add_argument("--count", type=int, default=100, help="Total prompts to generate")
    parser.add_argument("--batch-size", type=int, default=20, help="Prompts per API call")
    parser.add_argument("--axis", help="Focus on one difficulty axis")
    parser.add_argument("--formality", help="Focus on one formality level")
    parser.add_argument("--confusable-only", action="store_true", help="Only generate confusable prompts")
    parser.add_argument("--dry-run", action="store_true", help="Show prompt template only")
    parser.add_argument("--append", action="store_true", help="Append to existing corpus")
    args = parser.parse_args()

    all_descriptions = get_all_skill_descriptions()

    if args.dry_run:
        print(f"Would generate {args.count} prompts across {len(all_descriptions)} skills")
        print(f"Axes: {AXES}")
        print(f"Formality levels: {FORMALITY_LEVELS}")
        print(f"Estimated cost: ~${args.count * 0.001:.2f}")
        return

    axis = args.axis or ("confusable" if args.confusable_only else None)

    # Load existing corpus if appending
    corpus = []
    if args.append and os.path.isfile(CORPUS_PATH):
        with open(CORPUS_PATH) as f:
            corpus = json.load(f)
        print(f"Loaded {len(corpus)} existing prompts")

    # Generate in batches
    generated = 0
    batches_needed = (args.count + args.batch_size - 1) // args.batch_size

    for i in range(batches_needed):
        remaining = args.count - generated
        batch_size = min(args.batch_size, remaining)
        print(f"  Batch {i + 1}/{batches_needed} ({batch_size} prompts)...", end=" ", flush=True)

        batch = generate_batch(all_descriptions, batch_size, axis, args.formality)
        if batch:
            corpus.extend(batch)
            generated += len(batch)
            print(f"got {len(batch)} prompts")
        else:
            print("FAILED")

    # Save corpus
    with open(CORPUS_PATH, "w") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nCorpus saved to {CORPUS_PATH}: {len(corpus)} total prompts ({generated} new)")

    # Print axis distribution
    axis_counts: dict[str, int] = {}
    for p in corpus:
        a = p.get("axis", "unknown")
        axis_counts[a] = axis_counts.get(a, 0) + 1
    print("Axis distribution:", json.dumps(axis_counts, indent=2))


if __name__ == "__main__":
    main()
