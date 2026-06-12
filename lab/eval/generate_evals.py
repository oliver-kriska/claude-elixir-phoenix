#!/usr/bin/env python3
"""Generate eval definitions for all skills that don't have one yet.

Reads each SKILL.md, analyzes its structure, and creates a tailored eval JSON.
Skips skills that already have an eval file.

Usage:
    python -m lab.eval.generate_evals
    python -m lab.eval.generate_evals --force  # Overwrite existing
"""

import argparse
import json
import os
import re

from lab.eval.matchers import parse_frontmatter, get_sections

PLUGIN_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "plugins", "elixir-phoenix")
EVALS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evals")


def classify_skill(skill_name: str, fm: dict, sections: dict, content: str) -> str:
    """Classify skill type: command, workflow, reference, internal."""
    if fm.get("disable-model-invocation"):
        return "command"
    if skill_name in ("plan", "work", "review", "full", "compound", "brief", "triage", "quick", "verify"):
        return "workflow"
    if skill_name in ("intent-detection", "hexdocs-fetcher", "tidewave-integration", "compound-docs"):
        return "internal"
    if skill_name in ("challenge", "examples"):
        return "reference"
    # Reference skills typically have no argument-hint and are auto-loaded
    if "argument-hint" not in fm:
        return "reference"
    return "command"


def detect_references(skill_path: str) -> list[str]:
    """List reference files for a skill."""
    refs_dir = os.path.join(os.path.dirname(skill_path), "references")
    if not os.path.isdir(refs_dir):
        return []
    return [f for f in os.listdir(refs_dir) if f.endswith(".md")]


def count_iron_laws(sections: dict) -> int:
    """Count items in Iron Laws section."""
    for name, body in sections.items():
        if "iron law" in name.lower():
            return len(re.findall(r'^\s*[-*\d]+[\.\)]\s+', body, re.MULTILINE))
    return 0


def has_section(sections: dict, name: str) -> bool:
    return any(s.lower() == name.lower() or name.lower() in s.lower() for s in sections)


def generate_eval(skill_name: str, skill_path: str) -> dict:
    """Generate eval definition for one skill."""
    with open(skill_path) as f:
        content = f.read()

    fm = parse_frontmatter(content)
    sections = get_sections(content)
    skill_type = classify_skill(skill_name, fm, sections, content)
    refs = detect_references(skill_path)
    iron_law_count = count_iron_laws(sections)

    # --- Build completeness checks ---
    completeness_checks = [
        {"type": "frontmatter_field", "field": "name", "desc": "Has name field"},
        {"type": "frontmatter_field", "field": "description", "desc": "Has description field"},
    ]

    if has_section(sections, "Iron Laws"):
        min_laws = max(1, min(iron_law_count, 3))
        completeness_checks.append(
            {"type": "has_iron_laws", "min_count": min_laws, "desc": f"At least {min_laws} Iron Laws"}
        )
    else:
        # Should have Iron Laws
        completeness_checks.append(
            {"type": "section_exists", "section": "Iron Laws", "desc": "Has Iron Laws section"}
        )

    if has_section(sections, "Usage"):
        completeness_checks.append({"type": "section_exists", "section": "Usage", "desc": "Has Usage section"})

    if skill_type == "command" and "argument-hint" in fm:
        completeness_checks.append(
            {"type": "frontmatter_field", "field": "argument-hint", "desc": "Has argument-hint"}
        )

    # Check for key content patterns based on skill domain
    domain_patterns = {
        "ecto-patterns": [("cast|changeset|schema", "Mentions Ecto core concepts")],
        "liveview-patterns": [("mount|handle_event|assign", "Mentions LiveView lifecycle")],
        "security": [("auth|session|token", "Mentions auth concepts")],
        "testing": [("ExUnit|assert|test", "Mentions testing concepts")],
        "oban": [("worker|perform|queue", "Mentions Oban concepts")],
        "deploy": [("Dockerfile|fly\\.toml|release", "Mentions deployment concepts")],
        "phoenix-contexts": [("context|boundary|scope", "Mentions context concepts")],
        "elixir-idioms": [("GenServer|pattern match|pipe", "Mentions Elixir idioms")],
    }
    if skill_name in domain_patterns:
        for pattern, desc in domain_patterns[skill_name]:
            completeness_checks.append({"type": "content_present", "pattern": pattern, "desc": desc})

    if refs:
        completeness_checks.append(
            {"type": "content_present", "pattern": "references/", "desc": "Has References section"}
        )

    # --- Build accuracy checks ---
    accuracy_checks = [
        {"type": "valid_skill_refs", "desc": "All skill references valid"},
        {"type": "valid_agent_refs", "desc": "All agent references valid"},
    ]
    if refs:
        accuracy_checks.append({"type": "valid_file_refs", "desc": "All reference file paths valid"})

    # --- Build conciseness checks ---
    # Determine line target based on type
    if skill_type == "command":
        target, tolerance = 100, 85  # up to 185
    elif skill_type == "workflow":
        target, tolerance = 100, 95  # up to 195
    elif skill_type == "reference":
        target, tolerance = 100, 50  # up to 150
    else:  # internal
        target, tolerance = 100, 85

    conciseness_checks = [
        {"type": "line_count", "target": target, "tolerance": tolerance,
         "desc": f"Near {target}-line target ({target + tolerance} max)"},
        {"type": "max_section_lines", "max": 45, "desc": "No section exceeds 45 lines"},
        {"type": "content_absent", "pattern": "In this section|As mentioned above|It is important to note",
         "desc": "No filler phrases"},
    ]

    # --- Build triggering checks ---
    triggering_checks = [
        {"type": "description_length", "min": 50, "max": 250, "desc": "Description under 250-char plugin listing budget"},
        {"type": "description_keywords", "min": 3, "desc": "Enough domain keywords"},
        {"type": "description_no_vague", "desc": "No vague words in description"},
    ]

    # --- Build safety checks ---
    safety_checks = [
        {"type": "no_dangerous_patterns", "desc": "No unsafe code patterns"},
    ]
    if iron_law_count > 0 or has_section(sections, "Iron Laws"):
        min_laws = max(1, min(iron_law_count, 3))
        safety_checks.insert(0,
            {"type": "has_iron_laws", "min_count": min_laws, "desc": f"At least {min_laws} Iron Laws"}
        )

    # Add prohibition check for command/workflow skills
    if skill_type in ("command", "workflow"):
        safety_checks.append(
            {"type": "content_present", "pattern": "NEVER|MUST NOT|DO NOT|CRITICAL",
             "desc": "Has explicit prohibitions or critical rules"}
        )

    # --- Build clarity checks (NEW: from SkillsBench, MePO) ---
    # Command/workflow skills need higher action density (imperative instructions)
    # Reference/review skills can be lower (checklists, questions are also actionable)
    action_threshold = 0.25 if skill_type in ("command", "workflow") else 0.10
    clarity_checks = [
        {"type": "action_density", "min_ratio": action_threshold,
         "desc": f"Action density (>{int(action_threshold*100)}% actionable lines)"},
        {"type": "no_duplication", "desc": "No cross-section duplication"},
    ]
    if skill_type in ("command", "workflow"):
        clarity_checks.append(
            {"type": "workflow_step_coverage", "desc": "No missing workflow steps"}
        )

    # --- Build specificity checks (NEW: from SkillsBench, SWE-Skills-Bench) ---
    specificity_checks = [
        {"type": "specificity_ratio", "min_ratio": 0.15, "desc": "Concrete over vague (>15% specific lines)"},
        {"type": "has_examples", "min_blocks": 1, "desc": "Has code examples"},
        {"type": "description_structure", "desc": "Description has what+when components"},
    ]

    return {
        "skill": skill_name,
        "skill_path": f"plugins/elixir-phoenix/skills/{skill_name}/SKILL.md",
        "dimensions": {
            "completeness": {"weight": 0.15, "checks": completeness_checks},
            "accuracy": {"weight": 0.10, "checks": accuracy_checks},
            "conciseness": {"weight": 0.12, "checks": conciseness_checks},
            "triggering": {"weight": 0.10, "checks": triggering_checks},
            "safety": {"weight": 0.08, "checks": safety_checks},
            "clarity": {"weight": 0.13, "checks": clarity_checks},
            "specificity": {"weight": 0.12, "checks": specificity_checks},
            "behavioral": {"weight": 0.20, "checks": []},
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Generate eval definitions for plugin skills")
    parser.add_argument("--force", action="store_true", help="Overwrite existing eval files")
    args = parser.parse_args()

    skills_dir = os.path.join(PLUGIN_ROOT, "skills")
    os.makedirs(EVALS_DIR, exist_ok=True)

    generated = 0
    skipped = 0

    for skill_name in sorted(os.listdir(skills_dir)):
        skill_path = os.path.join(skills_dir, skill_name, "SKILL.md")
        if not os.path.isfile(skill_path):
            continue

        eval_path = os.path.join(EVALS_DIR, f"{skill_name}.json")
        if os.path.isfile(eval_path) and not args.force:
            skipped += 1
            continue

        eval_def = generate_eval(skill_name, skill_path)
        with open(eval_path, "w") as f:
            json.dump(eval_def, f, indent=2)
            f.write("\n")

        generated += 1
        print(f"  Generated: {skill_name} ({len(eval_def['dimensions']['completeness']['checks'])} completeness, "
              f"{len(eval_def['dimensions']['accuracy']['checks'])} accuracy checks)")

    print(f"\nDone: {generated} generated, {skipped} skipped (already exist)")


if __name__ == "__main__":
    main()
