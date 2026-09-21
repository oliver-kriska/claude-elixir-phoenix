#!/usr/bin/env python3
"""Generate `claude plugin eval` trigger cases from lab/eval/triggers/*.json.

The trigger JSON files stay the single source of truth; this writes one case
per prompt under lab/plugin_eval/cases/triggers/<skill>/ (gitignored). Each case
runs a real Claude Code session against a small Phoenix fixture with the phx,
ecto and lv plugins loaded, and grades whether `phx:<skill>` was invoked.

Why the cases live here instead of plugins/elixir-phoenix/evals/:
- phx declares dependencies on ecto and lv. Loaded alone, CC disables it with
  `dependency-unsatisfied`, and `plugins:` entries must sit under the directory
  the eval runs against — so the suite runs from the repo root.
- Keeping cases out of the plugin keeps them out of every user's install.

Usage:
    python3 -m lab.plugin_eval.generate                  # all skills
    python3 -m lab.plugin_eval.generate --skill verify   # one skill
    python3 -m lab.plugin_eval.generate --max-turns 3
"""

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
TRIGGERS_DIR = os.path.join(PROJECT_ROOT, "lab", "eval", "triggers")
SKILLS_DIR = os.path.join(PROJECT_ROOT, "plugins", "elixir-phoenix", "skills")
CASES_DIR = os.path.join(HERE, "cases")
OUT_DIR = os.path.join(CASES_DIR, "triggers")
FIXTURE = os.path.join(HERE, "fixture.sh")
FLAVORS_DIR = os.path.join(HERE, "flavors")

# Prompts for these skills refer to artifacts ("this plan", "the review
# findings", "my Ash resource"). Without them Claude searches, finds nothing and
# never routes — a fixture gap, not a description problem. Flavors are appended
# to the base fixture for that skill's positive and negative cases.
SKILL_FLAVORS = {
    "brief": ["plan"],
    "work": ["plan"],
    "triage": ["plan", "review"],
    "ash-framework": ["ash"],
}
PLUGIN_DIRS = ["plugins/elixir-phoenix", "plugins/ecto", "plugins/lv"]

# Read-only tools only: routing is decided in the first turns, and nothing a
# skill tells Claude to run (mix, git) should execute inside a trigger eval.
ALLOWED_TOOLS = ["Read", "Glob", "Grep", "Skill"]


def skill_matcher(skill: str) -> str:
    # Namespace is required: CC ships built-in skills (verify, debug, run,
    # simplify) that a bare-name match would wrongly count as phx hits.
    return f'"skill"\\s*:\\s*"phx:{skill}"'


def yaml_str(value: str) -> str:
    return json.dumps(value)


def load_triggers(only: set[str] | None) -> dict[str, dict]:
    triggers = {}
    for name in sorted(os.listdir(TRIGGERS_DIR)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        skill = name[:-5]
        if only and skill not in only:
            continue
        if not os.path.isfile(os.path.join(SKILLS_DIR, skill, "SKILL.md")):
            print(f"skip {skill}: no plugins/elixir-phoenix/skills/{skill}/SKILL.md", file=sys.stderr)
            continue
        with open(os.path.join(TRIGGERS_DIR, name)) as f:
            triggers[skill] = json.load(f)
    return triggers


def build_fixture(flavors: list[str]) -> str:
    with open(FIXTURE) as f:
        script = f.read()
    for flavor in flavors:
        with open(os.path.join(FLAVORS_DIR, f"{flavor}.sh")) as f:
            script += "\n" + f.read()
    return script


def write_case(case_dir: str, name: str, prompt: str, tags: list[str], grader: str, max_turns: int, timeout: int,
               flavors: list[str] | None = None) -> None:
    os.makedirs(os.path.join(case_dir, "graders"), exist_ok=True)
    fixture_path = os.path.join(case_dir, "fixture.sh")
    with open(fixture_path, "w") as f:
        f.write(build_fixture(flavors or []))
    os.chmod(fixture_path, 0o755)
    rel_root = os.path.relpath(PROJECT_ROOT, case_dir)
    plugins = ", ".join(yaml_str(os.path.join(rel_root, p)) for p in PLUGIN_DIRS)
    with open(os.path.join(case_dir, "case.yaml"), "w") as f:
        f.write(f'schema_version: "1.1"\nname: {name}\nplugins: [{plugins}]\ncontext:\n  scaffold_script: fixture.sh\n')
    with open(os.path.join(case_dir, "prompt.md"), "w") as f:
        f.write(
            "---\n"
            f"tags: [{', '.join(tags)}]\n"
            "runs: 1\n"
            f"max_turns: {max_turns}\n"
            f"timeout_seconds: {timeout}\n"
            f"allowed_tools: [{', '.join(ALLOWED_TOOLS)}]\n"
            "---\n\n"
            f"{prompt.strip()}\n"
        )
    with open(os.path.join(case_dir, "graders", "skill.md"), "w") as f:
        f.write(grader)


def generate(only: set[str] | None, max_turns: int, timeout: int) -> tuple[int, int]:
    triggers = load_triggers(only)
    targets = [OUT_DIR] if not only else [os.path.join(OUT_DIR, s) for s in only]
    for target in targets:
        shutil.rmtree(target, ignore_errors=True)

    pos = neg = 0
    for skill, data in triggers.items():
        matcher = skill_matcher(skill)
        flavors = SKILL_FLAVORS.get(skill, [])
        for i, prompt in enumerate(data.get("should_trigger", []), 1):
            grader = f"---\ntype: tool_used\ntool: Skill\ninput_match: '{matcher}'\n---\n"
            write_case(os.path.join(OUT_DIR, skill, f"pos-{i}"), f"{skill}--pos-{i}", prompt,
                       ["trigger", "trigger-pos", skill], grader, max_turns, timeout, flavors)
            pos += 1
        for i, prompt in enumerate(data.get("should_not_trigger", []), 1):
            grader = f"---\ntype: tool_used\ntool: Skill\ninput_match: '{matcher}'\nmin: 0\nmax: 0\narm: both\n---\n"
            write_case(os.path.join(OUT_DIR, skill, f"neg-{i}"), f"{skill}--neg-{i}", prompt,
                       ["trigger", "trigger-neg", skill], grader, max_turns, timeout, flavors)
            neg += 1
    return pos, neg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skill", action="append", help="limit to this skill (repeatable)")
    parser.add_argument("--max-turns", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    pos, neg = generate(set(args.skill) if args.skill else None, args.max_turns, args.timeout)
    print(f"wrote {pos} positive + {neg} negative cases to {os.path.relpath(OUT_DIR, PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
