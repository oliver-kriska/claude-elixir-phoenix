#!/usr/bin/env python3
"""Generate trigger test prompts for all skills using haiku.

Reads each skill's name + description, asks haiku to generate realistic
user prompts that should/shouldn't trigger the skill.

Usage:
    python3 lab/eval/triggers/generate_triggers.py              # All skills
    python3 lab/eval/triggers/generate_triggers.py --skill plan  # One skill
    python3 lab/eval/triggers/generate_triggers.py --dry-run     # Show what would be generated
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


def generate_for_skill(skill_name: str, skill_desc: str, all_descriptions: dict[str, str]) -> dict | None:
    """Use haiku to generate trigger prompts for one skill."""

    # Build context: show ALL skill descriptions so haiku understands the landscape
    other_skills = "\n".join(
        f"- {name}: {desc[:100]}"
        for name, desc in all_descriptions.items()
        if name != skill_name
    )

    prompt = f"""You are generating test prompts for a Claude Code plugin skill trigger evaluation.

TARGET SKILL: {skill_name}
DESCRIPTION: {skill_desc}

OTHER SKILLS IN THE PLUGIN (for context — generate should_not_trigger prompts that match THESE instead):
{other_skills}

Generate EXACTLY this JSON (no markdown, no explanation):
{{
  "skill": "{skill_name}",
  "should_trigger": [
    "realistic user request that SHOULD load {skill_name}",
    "different phrasing, same intent",
    "casual/informal version",
    "edge case still in {skill_name}'s domain",
    "another scenario {skill_name} handles"
  ],
  "should_not_trigger": [
    "similar-sounding prompt that belongs to a different skill",
    "too generic, no specific skill needed",
    "adjacent domain but different skill"
  ]
}}

RULES:
- Prompts must be realistic — what a real developer would actually type
- should_trigger: Must clearly match {skill_name}'s description
- should_not_trigger: Must NOT match {skill_name} but COULD match another skill or none
- CRITICAL: Do NOT annotate prompts with skill names, dashes, or hints about which skill they belong to. Each prompt must stand alone as a realistic user message with NO metadata
- Mix formal and casual phrasing
- Include Elixir/Phoenix-specific terms where natural
- Keep each prompt 5-20 words
- Output ONLY valid JSON, nothing else"""

    try:
        result = subprocess.run(
            [
                "claude", "-p", prompt,
                "--model", "haiku",
                "--output-format", "text",
                "--max-budget-usd", "0.50",
                "--no-session-persistence",
            ],
            capture_output=True, text=True, timeout=60,
        )

        if result.returncode != 0:
            print(f"  ERROR: claude returned {result.returncode}", file=sys.stderr)
            return None

        text = result.stdout.strip()

        # Strip any markdown fences
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        # Find the JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            return data

        print("  ERROR: Could not parse JSON from output", file=sys.stderr)
        return None

    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT for {skill_name}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ERROR for {skill_name}: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate trigger test prompts")
    parser.add_argument("--skill", help="Generate for one skill only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    parser.add_argument("--force", action="store_true", help="Overwrite existing trigger files")
    args = parser.parse_args()

    all_descriptions = get_all_skill_descriptions()
    print(f"Found {len(all_descriptions)} skills")

    if args.skill:
        skills_to_generate = [args.skill]
    else:
        skills_to_generate = sorted(all_descriptions.keys())

    generated = 0
    skipped = 0
    failed = 0

    for skill_name in skills_to_generate:
        trigger_path = os.path.join(TRIGGERS_DIR, f"{skill_name}.json")

        if os.path.isfile(trigger_path) and not args.force:
            skipped += 1
            continue

        if skill_name not in all_descriptions:
            print(f"  SKIP: {skill_name} (no description)")
            skipped += 1
            continue

        if args.dry_run:
            print(f"  Would generate: {skill_name}")
            continue

        print(f"  Generating: {skill_name}...", end=" ", flush=True)
        data = generate_for_skill(skill_name, all_descriptions[skill_name], all_descriptions)

        if data and "should_trigger" in data and "should_not_trigger" in data:
            with open(trigger_path, "w") as f:
                json.dump(data, f, indent=2)
                f.write("\n")
            st = len(data["should_trigger"])
            snt = len(data["should_not_trigger"])
            print(f"OK ({st} trigger, {snt} non-trigger)")
            generated += 1
        else:
            print("FAILED")
            failed += 1

    print(f"\nDone: {generated} generated, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
