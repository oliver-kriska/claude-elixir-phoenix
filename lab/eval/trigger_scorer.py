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
    python3 -m lab.eval.trigger_scorer --skill plan --model claude-sonnet-5

Cost: approximately $1.50 and 60 minutes for all 51 skills on Haiku.
Sonnet is roughly 12× more expensive per call.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
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
DEFAULT_MIN_ACCURACY = 0.75
JUDGE_TIMEOUT_SECONDS = 60
JUDGE_ATTEMPTS = 2


class JudgeInvocationError(RuntimeError):
    """The routing judge failed before producing a valid routing decision."""

# CC CLI accepts both aliases and full IDs. Canonicalize so 'haiku' and
# 'claude-haiku-4-5' share one cache rather than two.
MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5",
    "sonnet": "claude-sonnet-5",
    "opus": "claude-opus-5",
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
        description = fm.get("description")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"canonical skill has no valid description: {name}")
        descriptions[name] = description
    return descriptions


def load_trigger_file(skill_name: str) -> dict | None:
    """Load trigger test prompts for a skill."""
    path = os.path.join(TRIGGERS_DIR, f"{skill_name}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_all_trigger_files(skill_names: set[str]) -> dict[str, dict]:
    """Load and validate the exact trigger-fixture set for canonical skills."""
    fixture_names = {
        os.path.splitext(name)[0]
        for name in os.listdir(TRIGGERS_DIR)
        if name.endswith(".json") and not name.startswith("_")
    }
    missing = sorted(skill_names - fixture_names)
    stale = sorted(fixture_names - skill_names)
    if missing or stale:
        details = []
        if missing:
            details.append(f"missing fixtures: {', '.join(missing)}")
        if stale:
            details.append(f"fixtures without canonical skills: {', '.join(stale)}")
        raise ValueError("trigger fixture set does not match canonical skills (" + "; ".join(details) + ")")

    fixtures = {}
    for name in sorted(skill_names):
        fixture = load_trigger_file(name)
        if not isinstance(fixture, dict):
            raise ValueError(f"trigger fixture must be a JSON object: {name}")
        for key in ("should_trigger", "should_not_trigger"):
            prompts = fixture.get(key)
            if not isinstance(prompts, list) or not all(isinstance(prompt, str) and prompt for prompt in prompts):
                raise ValueError(f"trigger fixture {name} has invalid {key}")
        if not fixture["should_trigger"] or not fixture["should_not_trigger"]:
            raise ValueError(f"trigger fixture {name} must include positive and negative prompts")
        fixtures[name] = fixture
    return fixtures


def _parse_judge_output(text: str, skill_names: set[str]) -> list[str] | None:
    """Parse the judge's deliberately small output protocol."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines == ["none"]:
        return []
    if not 1 <= len(lines) <= 3:
        return None

    skills = []
    for line in lines:
        candidate = line.lstrip("-*0123456789.) ").strip().strip("`").strip()
        if candidate not in skill_names or candidate in skills:
            return None
        skills.append(candidate)
    return skills


def ask_model(all_descriptions: dict[str, str], prompt: str, model: str = DEFAULT_MODEL) -> list[str]:
    """Ask the chosen routing-judge model which skill(s) it would load for a given prompt."""
    desc_list = "\n".join(f"- {name}: {desc}" for name, desc in all_descriptions.items())

    system_prompt = f"""You are testing skill routing for a Claude Code plugin.

Given these available skills:
{desc_list}

The user says: "{prompt}"

Which skill(s) should be loaded? Reply with ONLY the skill name(s), one per line.
If no skill should be loaded, reply with "none".
List at most 3 skills, ordered by relevance."""

    errors = []
    for attempt in range(1, JUDGE_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                [
                    "claude", "-p", system_prompt,
                    "--model", model,
                    "--output-format", "text",
                    "--max-budget-usd", "0.50",
                    "--no-session-persistence",
                ],
                capture_output=True,
                text=True,
                timeout=JUDGE_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            errors.append(f"attempt {attempt}: timed out after {JUDGE_TIMEOUT_SECONDS}s")
            continue
        except OSError as error:
            errors.append(f"attempt {attempt}: could not start Claude CLI: {error}")
            continue

        text = result.stdout.strip()
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no output"
            errors.append(f"attempt {attempt}: exit {result.returncode}: {detail}")
            continue
        if not text:
            errors.append(f"attempt {attempt}: Claude CLI returned empty output")
            continue

        skills = _parse_judge_output(text, set(all_descriptions))
        if skills is None:
            errors.append(f"attempt {attempt}: invalid routing response: {text}")
            continue
        return skills

    raise JudgeInvocationError("routing judge failed: " + "; ".join(errors))


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
        cache_path = os.path.join(cache_dir, f"{skill_name}.json")
        _write_json_atomic(cache_path, score_data)

    return score_data


def _write_json_atomic(path: str, payload: dict) -> None:
    """Replace a JSON result only after its complete contents reach disk."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as temporary:
            temporary_path = temporary.name
            json.dump(payload, temporary, indent=2)
            temporary.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def skills_below_threshold(results: dict[str, dict], threshold: float) -> list[tuple[str, float]]:
    """Return skills below the required accuracy, ordered worst first."""
    return sorted(
        (
            (name, float(result.get("accuracy", 0.0)))
            for name, result in results.items()
            if float(result.get("accuracy", 0.0)) < threshold
        ),
        key=lambda item: (item[1], item[0]),
    )


def main() -> int:
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
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=DEFAULT_MIN_ACCURACY,
        help=f"Fail when any tested skill is below this accuracy. Default: {DEFAULT_MIN_ACCURACY}",
    )
    args = parser.parse_args()

    if not 0.0 <= args.min_accuracy <= 1.0:
        parser.error("--min-accuracy must be between 0 and 1")

    try:
        all_descriptions = load_all_descriptions()
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
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
        if result["accuracy"] < args.min_accuracy:
            print(
                f"{args.skill} is below the {args.min_accuracy:.0%} minimum trigger accuracy",
                file=sys.stderr,
            )
            return 1

    elif args.all:
        try:
            all_triggers = load_all_trigger_files(set(all_descriptions))
        except (json.JSONDecodeError, OSError, ValueError) as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 1

        skills_tested = 0
        total_accuracy = 0
        results = {}

        print(f"Judge model: {judge_model}\n")
        for name in sorted(all_descriptions.keys()):
            triggers = all_triggers[name]
            print(f"  Testing {name}...", end=" ", flush=True)
            result = score_skill_triggers(name, triggers, all_descriptions, args.cache, model=judge_model)
            results[name] = result
            total_accuracy += result["accuracy"]
            skills_tested += 1
            print(f"accuracy={result['accuracy']:.0%} (P={result['precision']:.0%} R={result['recall']:.0%})")

        avg = total_accuracy / skills_tested if skills_tested else 0
        print(f"\n{skills_tested} skills tested against {judge_model}, average accuracy: {avg:.0%}")

        below = skills_below_threshold(results, args.min_accuracy)
        if below:
            print(f"\n{len(below)} skills below the {args.min_accuracy:.0%} minimum:")
            for name, accuracy in below:
                print(f"  {name}: {accuracy:.0%}")

        _write_json_atomic(aggregate_path_for_model(judge_model), {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": judge_model,
            "skills_tested": skills_tested,
            "average_accuracy": round(avg, 4),
            "per_skill": {k: {"accuracy": v["accuracy"], "precision": v["precision"], "recall": v["recall"]}
                          for k, v in results.items()},
        })

        if below:
            return 1

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
