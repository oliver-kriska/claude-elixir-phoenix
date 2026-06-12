#!/usr/bin/env python3
"""Skill description tournament runner.

Applies autoreason's three-way tournament to skill descriptions,
targeting trigger accuracy improvement for weak skills.

Usage:
    python3 -m lab.tournament.description_tournament --skill plan
    python3 -m lab.tournament.description_tournament --weak
    python3 -m lab.tournament.description_tournament --skill plan --dry-run
"""

import argparse
import json
import os
import random
import re
import sys
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.matchers import (
    description_keywords,
    description_length,
    description_no_vague,
    parse_frontmatter,
)
from lab.tournament.config import load_config
from lab.tournament.llm import call_llm
from lab.tournament.prompts import (
    author_prompt,
    critic_prompt,
    judge_prompt,
    synthesizer_prompt,
)
from lab.tournament.tournament import (
    TournamentState,
    aggregate_borda,
    check_convergence,
    parse_ranking,
    randomize_for_judge,
)

PLUGIN_ROOT = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix")
TRIGGERS_DIR = os.path.join(PROJECT_ROOT, "lab", "eval", "triggers")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "lab", "tournament", "results")

_SKILL_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


def validate_skill_name(name: str) -> str:
    """Ensure skill name is a simple directory name (no path separators)."""
    if not _SKILL_NAME_RE.match(name):
        raise ValueError(f"Invalid skill name: {name!r}")
    return name


_PREAMBLE_PREFIXES = ("here", "sure", "the ", "revised", "updated", "new ", "rewritten")


def _extract_description(response: str) -> str:
    """Extract description from LLM response, skipping common preamble."""
    lines = response.strip().split("\n")
    for line in lines:
        stripped = line.strip().strip('"').strip("`")
        if stripped and not stripped.lower().startswith(_PREAMBLE_PREFIXES):
            return stripped
    return lines[0].strip().strip('"') if lines else ""


def validate_description(description: str) -> tuple[bool, list[str]]:
    """Run structural gate on a description. Returns (passed, failures).

    Checks: length (50-250), keyword count (>=3), no vague words.
    Constructs a minimal SKILL.md content string for matchers.
    """
    import yaml as _yaml
    content = "---\n" + _yaml.dump({"description": description}, default_flow_style=False) + "---\n"
    failures = []

    passed_len, evidence_len = description_length(content, min=50, max=250)
    if not passed_len:
        failures.append(evidence_len)

    passed_kw, evidence_kw = description_keywords(content, min=3)
    if not passed_kw:
        failures.append(evidence_kw)

    passed_vague, evidence_vague = description_no_vague(content)
    if not passed_vague:
        failures.append(evidence_vague)

    return len(failures) == 0, failures


def load_all_descriptions() -> dict[str, str]:
    """Load all skill names and descriptions from plugin."""
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


def load_trigger_prompts(skill_name: str, split: str = "train") -> list[str] | None:
    """Load trigger prompts for a skill.

    Args:
        skill_name: Skill name.
        split: "train" for tournament judges (should_trigger),
               "test" for validation (should_trigger_test),
               "all" for both combined.

    Returns:
        List of prompts, or None if no trigger file exists.
    """
    path = os.path.join(TRIGGERS_DIR, f"{skill_name}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        data = json.load(f)

    train = data.get("should_trigger", [])
    test = data.get("should_trigger_test", [])

    if split == "train":
        return train
    elif split == "test":
        return test if test else train
    elif split == "all":
        return train + test
    return train


def run_pass(
    skill_name: str,
    current_a: str,
    all_descriptions: dict[str, str],
    trigger_prompts: list[str],
    config: dict,
) -> tuple[str, str, dict]:
    """Run one tournament pass: critic → author B → synthesizer AB → 3 judges → Borda.

    Returns (winner_label, winner_text, pass_result_dict).
    """
    budget = str(config.get("max_budget_per_call", "0.50"))

    # --- Critic ---
    sys_p, usr_p = critic_prompt(skill_name, current_a, all_descriptions, trigger_prompts)
    critique = call_llm(
        sys_p, usr_p,
        model=config["critic_model"],
        timeout=config["call_timeout"],
        max_budget=budget,
        verbose=True,
    )
    if critique is None:
        return "A", current_a, {"error": "critic_failed"}

    # --- Author B ---
    sys_p, usr_p = author_prompt(skill_name, current_a, critique, trigger_prompts)
    author_response = call_llm(
        sys_p, usr_p,
        model=config["author_model"],
        timeout=config["call_timeout"],
        max_budget=budget,
        verbose=True,
    )
    if author_response is None:
        return "A", current_a, {"error": "author_failed"}

    # Extract description — skip common LLM preamble patterns
    version_b = _extract_description(author_response)
    if len(version_b) > config["max_description_chars"]:
        version_b = version_b[:config["max_description_chars"]]

    # --- Synthesizer ---
    # Randomize A/B presentation to prevent positional bias
    if random.random() < 0.5:
        vx, vy = current_a, version_b
    else:
        vx, vy = version_b, current_a

    sys_p, usr_p = synthesizer_prompt(skill_name, vx, vy, trigger_prompts)
    synth_response = call_llm(
        sys_p, usr_p,
        model=config["synthesizer_model"],
        timeout=config["call_timeout"],
        max_budget=budget,
        verbose=True,
    )

    version_ab = _extract_description(synth_response) if synth_response else current_a
    if len(version_ab) > config["max_description_chars"]:
        version_ab = version_ab[:config["max_description_chars"]]

    # --- Judge Panel ---
    versions = {"A": current_a, "B": version_b, "AB": version_ab}
    rankings = []

    for judge_idx in range(config["num_judges"]):
        proposals_text, order_map = randomize_for_judge(versions)
        sys_p, usr_p = judge_prompt(skill_name, proposals_text, trigger_prompts, all_descriptions)
        judge_response = call_llm(
            sys_p, usr_p,
            model=config["judge_model"],
            timeout=config["call_timeout"],
            max_budget=budget,
        )

        ranking = parse_ranking(judge_response, order_map) if judge_response else None
        rankings.append(ranking)

    # --- Borda Aggregation ---
    winner, scores, valid_rankings = aggregate_borda(rankings, tiebreak_winner="A")

    winner_text = versions[winner]

    pass_result = {
        "versions": versions,
        "critique": critique[:200],
        "rankings": [r if r else None for r in rankings],
        "borda_scores": scores,
        "winner": winner,
        "valid_judges": len(valid_rankings),
    }

    return winner, winner_text, pass_result


def run_tournament(
    skill_name: str,
    all_descriptions: dict[str, str],
    trigger_prompts: list[str],
    config: dict | None = None,
    dry_run: bool = False,
) -> dict:
    """Run full tournament for one skill's description.

    Args:
        skill_name: Skill to optimize.
        all_descriptions: All skill descriptions for routing context.
        trigger_prompts: Prompts that should trigger this skill.
        config: Override config (uses default if None).
        dry_run: If True, print what would happen without LLM calls.

    Returns:
        Tournament result dict with before/after descriptions and pass history.
    """
    if config is None:
        config = load_config()

    incumbent = all_descriptions.get(skill_name, "")
    if not incumbent:
        return {"error": f"No description found for {skill_name}"}

    if dry_run:
        return {
            "skill": skill_name,
            "mode": "dry_run",
            "incumbent": incumbent,
            "trigger_prompts": trigger_prompts,
            "config": {k: v for k, v in config.items() if not k.endswith("_model")},
        }

    state = TournamentState(incumbent=incumbent)
    original = incumbent
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Tournament: {skill_name}")
    print(f"Incumbent: \"{incumbent}\"")
    print(f"Trigger prompts: {len(trigger_prompts)}")
    print(f"{'='*60}")

    for pass_num in range(1, config["max_passes"] + 1):
        state.pass_number = pass_num
        print(f"\n--- Pass {pass_num} ---")

        winner, winner_text, pass_result = run_pass(
            skill_name, state.incumbent, all_descriptions, trigger_prompts, config,
        )

        if "error" in pass_result:
            print(f"  Error: {pass_result['error']} — incumbent survives (not counted as A-win)")
            # Don't count errors toward convergence — masks systematic LLM failures
        elif winner == "A":
            state.consecutive_a_wins += 1
            print(f"  Winner: A (incumbent) — streak: {state.consecutive_a_wins}")
        else:
            state.consecutive_a_wins = 0
            state.incumbent = winner_text
            print(f"  Winner: {winner} — \"{winner_text[:80]}...\"")

        pass_result["pass"] = pass_num
        pass_result["winner"] = winner
        state.history.append(pass_result)

        # Log pass to results
        results_path = os.path.join(RESULTS_DIR, f"{skill_name}.jsonl")
        with open(results_path, "a") as f:
            entry = {
                "pass": pass_num,
                "winner": winner,
                "borda_scores": pass_result.get("borda_scores", {}),
                "description_a": pass_result.get("versions", {}).get("A", ""),
                "description_winner": winner_text[:250],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            f.write(json.dumps(entry) + "\n")

        if check_convergence(state, k=config["convergence_threshold"]):
            print(f"\n  Converged after {pass_num} passes (A won {config['convergence_threshold']} consecutive)")
            break

    # --- Structural Gate (post-tournament) ---
    structural_passed = True
    structural_failures = []
    if state.incumbent != original:
        structural_passed, structural_failures = validate_description(state.incumbent)
        if not structural_passed:
            print(f"\n  STRUCTURAL GATE FAILED: {structural_failures}")
            print("  Reverting to original description")
            state.incumbent = original

    result = {
        "skill": skill_name,
        "description_before": original,
        "description_after": state.incumbent,
        "changed": original != state.incumbent,
        "passes": state.pass_number,
        "converged": check_convergence(state, k=config["convergence_threshold"]),
        "structural_gate": {"passed": structural_passed, "failures": structural_failures},
        "history_summary": [
            {"pass": h["pass"], "winner": h["winner"], "scores": h.get("borda_scores", {})}
            for h in state.history
        ],
    }

    print(f"\n{'='*60}")
    print(f"Result: {'CHANGED' if result['changed'] else 'UNCHANGED'}")
    if result["changed"]:
        print(f"Before: \"{original}\"")
        print(f"After:  \"{state.incumbent}\"")
    elif structural_failures:
        print(f"Reverted due to structural failures: {structural_failures}")
    print(f"Passes: {state.pass_number}, Converged: {result['converged']}")
    print(f"{'='*60}")

    return result


def find_weak_skills(threshold: float = 0.75) -> list[tuple[str, float]]:
    """Find skills with trigger accuracy below threshold using cached results."""
    results_dir = os.path.join(TRIGGERS_DIR, "results")
    if not os.path.isdir(results_dir):
        return []
    weak = []
    for fname in os.listdir(results_dir):
        if fname.startswith("_") or not fname.endswith(".json"):
            continue
        with open(os.path.join(results_dir, fname)) as f:
            data = json.load(f)
        if data.get("accuracy", 1.0) < threshold:
            weak.append((data["skill"], data["accuracy"]))
    return sorted(weak, key=lambda x: x[1])  # worst first


def main():
    parser = argparse.ArgumentParser(description="Run skill description tournament")
    parser.add_argument("--skill", help="Run tournament for one skill")
    parser.add_argument("--weak", action="store_true", help="Auto-target skills below 75%% accuracy")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without LLM calls")
    parser.add_argument("--config", help="Override config file path")
    args = parser.parse_args()

    config = load_config(args.config) if args.config else load_config()
    all_descriptions = load_all_descriptions()

    if args.skill:
        validate_skill_name(args.skill)
        trigger_prompts = load_trigger_prompts(args.skill)
        if not trigger_prompts:
            print(f"No trigger file for {args.skill}", file=sys.stderr)
            sys.exit(1)
        result = run_tournament(args.skill, all_descriptions, trigger_prompts, config, args.dry_run)
        print(json.dumps(result, indent=2))

    elif args.weak:
        weak = find_weak_skills()
        if not weak:
            print("No skills below 75% accuracy threshold")
            sys.exit(0)
        print(f"Found {len(weak)} weak skills: {', '.join(f'{s} ({a:.0%})' for s, a in weak)}")
        for skill_name, accuracy in weak:
            trigger_prompts = load_trigger_prompts(skill_name)
            if not trigger_prompts:
                continue
            result = run_tournament(skill_name, all_descriptions, trigger_prompts, config, args.dry_run)
            print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
