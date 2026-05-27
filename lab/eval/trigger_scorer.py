#!/usr/bin/env python3
"""Behavioral trigger evaluation against a routing-judge model.

Tests whether the chosen model routes user prompts to the correct skill
by sending all skill descriptions + one test prompt to the judge.

Default judge is claude-haiku-4-5. Use --model to evaluate against other
models (sonnet, opus, full IDs). Per-model results are cached separately so
haiku/sonnet baselines stay independent.

Usage:
    python3 -m lab.eval.trigger_scorer --skill plan
    python3 -m lab.eval.trigger_scorer --all
    python3 -m lab.eval.trigger_scorer --all --cache               # Reuse cached results
    python3 -m lab.eval.trigger_scorer --all --model sonnet        # Evaluate against sonnet
    python3 -m lab.eval.trigger_scorer --skill plan --model claude-sonnet-4-6

Cost: ~$0.001 per test prompt on haiku, ~$0.04 for all 45 skills × ~8 prompts.
Sonnet is roughly 12× more expensive per call.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(EVAL_DIR))
sys.path.insert(0, PROJECT_ROOT)

from lab.eval.matchers import parse_frontmatter
from lab.eval.schemas import ScoreRequest, ScoreResult
from lab.eval.triggers.deviation_classifier import classify_failures

PLUGIN_ROOT = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix")
TRIGGERS_DIR = os.path.join(EVAL_DIR, "triggers")
RESULTS_DIR = os.path.join(TRIGGERS_DIR, "results")
DEFAULT_MODEL = "claude-haiku-4-5"

# CC CLI accepts both aliases and full IDs. Canonicalize so 'haiku' and
# 'claude-haiku-4-5' share one cache rather than two.
MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}


def canonicalize_model(model: str) -> str:
    """Resolve a model alias (`haiku`, `sonnet`, `opus`) to its full ID."""
    return MODEL_ALIASES.get(model, model)


def _model_slug(model: str) -> str:
    """Filesystem-safe slug for a model identifier."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", model).strip("-")


def cache_dir_for_model(model: str) -> str:
    """Where to read/write cached per-skill results for this model.

    Default haiku keeps the legacy flat path so existing caches stay valid.
    Other models get a per-model subdirectory to keep baselines independent.
    """
    model = canonicalize_model(model)
    if model == DEFAULT_MODEL:
        return RESULTS_DIR
    return os.path.join(RESULTS_DIR, "by-model", _model_slug(model))


def aggregate_path_for_model(model: str) -> str:
    """Where to persist the multi-skill aggregate for this model."""
    model = canonicalize_model(model)
    if model == DEFAULT_MODEL:
        return os.path.join(RESULTS_DIR, "_aggregate.json")
    return os.path.join(cache_dir_for_model(model), "_aggregate.json")


def load_all_descriptions() -> dict[str, str]:
    """Load all skill names and descriptions."""
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


def load_trigger_file(skill_name: str) -> dict | None:
    """Load trigger test prompts for a skill."""
    path = os.path.join(TRIGGERS_DIR, f"{skill_name}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def ask_model(all_descriptions: dict[str, str], prompt: str, model: str = DEFAULT_MODEL) -> list[str]:
    """Ask the chosen routing-judge model which skill(s) it would load for a given prompt."""
    desc_list = "\n".join(f"- {name}: {desc[:150]}" for name, desc in all_descriptions.items())

    system_prompt = f"""You are testing skill routing for a Claude Code plugin.

Given these available skills:
{desc_list}

The user says: "{prompt}"

Which skill(s) should be loaded? Reply with ONLY the skill name(s), one per line.
If no skill should be loaded, reply with "none".
List at most 3 skills, ordered by relevance."""

    try:
        result = subprocess.run(
            [
                "claude", "-p", system_prompt,
                "--model", model,
                "--output-format", "text",
                "--max-budget-usd", "0.50",
                "--no-session-persistence",
            ],
            capture_output=True, text=True, timeout=30,
        )

        if result.returncode != 0:
            return []

        text = result.stdout.strip()
        # Parse skill names from response — one per line, strip bullets/numbers
        skills = []
        for line in text.split("\n"):
            line = line.strip().lstrip("-*0123456789.) ").strip()
            # Remove explanations after dashes or parentheses
            if " — " in line:
                line = line.split(" — ")[0].strip()
            if " (" in line:
                line = line.split(" (")[0].strip()
            if " -" in line:
                line = line.split(" -")[0].strip()
            line = line.strip("`").strip()
            if line and line != "none" and not line.startswith("No "):
                skills.append(line)
        return skills

    except (subprocess.TimeoutExpired, Exception):
        return []


def score_triggers(request: ScoreRequest) -> ScoreResult:
    """Score trigger accuracy for one skill. Pure function — no I/O side effects.
    Caller handles cache reads (via request.use_cache + request.cache_dir) and writes.
    """
    skill_name = request.target_name
    triggers = request.triggers or {}
    all_descriptions = request.all_descriptions or {}

    # Cache read — request-prep step, not a side effect
    if request.use_cache and request.cache_dir:
        cache_path = os.path.join(request.cache_dir, f"{skill_name}.json")
        if os.path.isfile(cache_path):
            with open(cache_path) as f:
                cached = json.load(f)
            # Backfill deviations on pre-Phase-1 cache files (no API cost)
            if "deviations" not in cached:
                deviations = classify_failures(skill_name, cached, all_descriptions)
                cached["deviations"] = [d.to_dict() for d in deviations]
            return _result_from_dict(cached, request)

    should_trigger = triggers.get("should_trigger", [])
    should_not = triggers.get("should_not_trigger", [])

    judge_model = request.model or DEFAULT_MODEL
    results = []
    for prompt in should_trigger:
        chosen = ask_model(all_descriptions, prompt, judge_model)
        results.append({
            "prompt": prompt, "expected": True, "chosen": chosen,
            "correct": skill_name in chosen,
        })
    for prompt in should_not:
        chosen = ask_model(all_descriptions, prompt, judge_model)
        results.append({
            "prompt": prompt, "expected": False, "chosen": chosen,
            "correct": skill_name not in chosen,
        })

    total = len(results)
    correct_count = sum(1 for r in results if r["correct"])
    tp = sum(1 for r in results if r["expected"] and r["correct"])
    fp = sum(1 for r in results if not r["expected"] and not r["correct"])
    fn = sum(1 for r in results if r["expected"] and not r["correct"])
    tn = sum(1 for r in results if not r["expected"] and r["correct"])

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    accuracy = correct_count / total if total > 0 else 0.0

    # Classify routing failures by deviation type
    metadata_payload = {
        "skill": skill_name,
        "results": results,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }
    deviations = classify_failures(skill_name, metadata_payload, all_descriptions)

    return ScoreResult(
        target_name=skill_name,
        target_path=request.target_path,
        target_kind="trigger",
        composite=accuracy,
        dimensions={},
        metadata={
            "accuracy": accuracy,
            "precision": precision,
            "recall": recall,
            "total": total,
            "correct": correct_count,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": judge_model,
            "results": results,
            "deviations": [d.to_dict() for d in deviations],
        },
        cache_hit=False,
    )


def _result_from_dict(cached: dict, request: ScoreRequest) -> ScoreResult:
    """Hydrate a ScoreResult from cached JSON for cache-hit paths."""
    return ScoreResult(
        target_name=cached.get("skill", request.target_name),
        target_path=request.target_path,
        target_kind="trigger",
        composite=cached.get("accuracy", 0.0),
        dimensions={},
        metadata={k: v for k, v in cached.items() if k != "skill"},
        cache_hit=True,
    )


def score_skill_triggers(
    skill_name: str,
    triggers: dict,
    all_descriptions: dict[str, str],
    use_cache: bool = False,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Backwards-compatible wrapper. Builds ScoreRequest, calls score_triggers,
    returns the legacy dict shape. Writes cache file (legacy callers expect this).

    Cache is per-model: haiku uses the legacy flat path, other models get
    a per-model subdirectory under results/by-model/{slug}/.
    """
    cache_dir = cache_dir_for_model(model)
    request = ScoreRequest(
        target_path="",
        target_kind="trigger",
        target_name=skill_name,
        use_cache=use_cache,
        cache_dir=cache_dir,
        triggers=triggers,
        all_descriptions=all_descriptions,
        model=model,
    )
    result = score_triggers(request)
    score_data = result.to_dict()

    if not result.cache_hit:
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, f"{skill_name}.json")
        with open(cache_path, "w") as f:
            json.dump(score_data, f, indent=2)
            f.write("\n")

    return score_data


def main():
    parser = argparse.ArgumentParser(description="Test skill trigger accuracy against a routing-judge model")
    parser.add_argument("--skill", help="Test one skill")
    parser.add_argument("--all", action="store_true", help="Test all skills with trigger files")
    parser.add_argument("--cache", action="store_true", help="Use cached results")
    parser.add_argument("--summary", action="store_true", help="Print summary only")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Routing-judge model (alias like 'sonnet' or full ID). Default: {DEFAULT_MODEL}",
    )
    args = parser.parse_args()

    all_descriptions = load_all_descriptions()
    judge_model = canonicalize_model(args.model)

    if args.skill:
        triggers = load_trigger_file(args.skill)
        if not triggers:
            print(f"No trigger file for {args.skill}", file=sys.stderr)
            sys.exit(1)
        result = score_skill_triggers(args.skill, triggers, all_descriptions, args.cache, model=judge_model)
        if args.summary:
            print(f"{args.skill} [{judge_model}]: accuracy={result['accuracy']:.0%} precision={result['precision']:.0%} recall={result['recall']:.0%}")
        else:
            print(json.dumps(result, indent=2))

    elif args.all:
        skills_tested = 0
        total_accuracy = 0
        results = {}

        print(f"Judge model: {judge_model}\n")
        for name in sorted(all_descriptions.keys()):
            triggers = load_trigger_file(name)
            if not triggers:
                continue
            print(f"  Testing {name}...", end=" ", flush=True)
            result = score_skill_triggers(name, triggers, all_descriptions, args.cache, model=judge_model)
            results[name] = result
            total_accuracy += result["accuracy"]
            skills_tested += 1
            print(f"accuracy={result['accuracy']:.0%} (P={result['precision']:.0%} R={result['recall']:.0%})")

        avg = total_accuracy / skills_tested if skills_tested else 0
        print(f"\n{skills_tested} skills tested against {judge_model}, average accuracy: {avg:.0%}")

        if not args.summary:
            # Save aggregate
            aggregate_path = aggregate_path_for_model(judge_model)
            os.makedirs(os.path.dirname(aggregate_path), exist_ok=True)
            with open(aggregate_path, "w") as f:
                json.dump({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "model": judge_model,
                    "skills_tested": skills_tested,
                    "average_accuracy": round(avg, 4),
                    "per_skill": {k: {"accuracy": v["accuracy"], "precision": v["precision"], "recall": v["recall"]}
                                  for k, v in results.items()},
                }, f, indent=2)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
