#!/usr/bin/env python3
"""Compare trigger-scorer accuracy across N routing-judge models.

Loads per-model `_aggregate.json` files written by `lab.eval.trigger_scorer`
and produces a per-skill table with accuracy per model + spread, plus a
per-model summary. Default output is ASCII; `--format json` for machines.

Usage:
    python3 -m lab.eval.compare_models --models haiku,sonnet
    python3 -m lab.eval.compare_models --models haiku,sonnet,opus --sort spread
    python3 -m lab.eval.compare_models --models haiku,sonnet --skill help
    python3 -m lab.eval.compare_models --aggregates path/a.json path/b.json
    python3 -m lab.eval.compare_models --models haiku,sonnet --format json
"""

import argparse
import json
import os
import sys

from lab.eval.trigger_scorer import aggregate_path_for_model, canonicalize_model


def load_aggregate(path: str) -> dict:
    if not os.path.isfile(path):
        sys.exit(f"ERROR: aggregate not found: {path}\n"
                 f"Hint: run `python3 -m lab.eval.trigger_scorer --all --model <name>` first.")
    with open(path) as f:
        return json.load(f)


def resolve_aggregate_paths(models: list[str] | None, paths: list[str] | None) -> list[tuple[str, str]]:
    """Return [(label, path)] pairs. Label is the canonical model ID for `--models`,
    or the basename of the parent dir for `--aggregates`."""
    if models:
        return [(canonicalize_model(m), aggregate_path_for_model(m)) for m in models]
    if paths:
        out = []
        for p in paths:
            with open(p) as f:
                d = json.load(f)
            label = d.get("model") or os.path.basename(os.path.dirname(p)) or os.path.basename(p)
            out.append((label, p))
        return out
    sys.exit("ERROR: provide --models or --aggregates")


def build_table(aggregates: list[tuple[str, dict]], skill_filter: str | None) -> dict:
    """Build per-skill accuracy matrix + per-model summary.

    Returns dict with shape:
        {"models": [label, ...],
         "per_skill": {skill: {label: accuracy or None, ...}},
         "summary":   {label: {"mean": float, "n": int}}}
    """
    labels = [label for label, _ in aggregates]
    all_skills: set[str] = set()
    for _, agg in aggregates:
        all_skills.update(agg.get("per_skill", {}).keys())

    per_skill: dict[str, dict[str, float | None]] = {}
    for skill in sorted(all_skills):
        if skill_filter and skill != skill_filter:
            continue
        row = {}
        for label, agg in aggregates:
            entry = agg.get("per_skill", {}).get(skill)
            row[label] = entry["accuracy"] if entry else None
        per_skill[skill] = row

    summary = {}
    for label, agg in aggregates:
        summary[label] = {
            "mean": agg.get("average_accuracy"),
            "n": agg.get("skills_tested"),
            "timestamp": agg.get("timestamp"),
        }

    return {"models": labels, "per_skill": per_skill, "summary": summary}


def render_ascii(table: dict, sort: str) -> str:
    labels = table["models"]
    rows = []
    for skill, accs in table["per_skill"].items():
        values = [v for v in accs.values() if v is not None]
        if not values:
            continue
        spread = max(values) - min(values)
        rows.append((skill, accs, spread))

    if sort == "spread":
        rows.sort(key=lambda r: r[2], reverse=True)
    elif sort == "skill":
        rows.sort(key=lambda r: r[0])
    elif sort == "worst":
        rows.sort(key=lambda r: min(v for v in r[1].values() if v is not None))

    skill_w = max((len(r[0]) for r in rows), default=20)
    skill_w = max(skill_w, len("skill"))
    col_w = max(8, max((len(label) for label in labels), default=8))

    out = []
    header = "skill".ljust(skill_w) + "  " + "  ".join(label.rjust(col_w) for label in labels) + "  " + "spread".rjust(7)
    out.append(header)
    out.append("-" * len(header))
    for skill, accs, spread in rows:
        cells = []
        for label in labels:
            v = accs.get(label)
            cells.append(("—" if v is None else f"{v:.0%}").rjust(col_w))
        marker = ""
        if spread >= 0.20:
            marker = " ⚠"
        elif spread >= 0.10:
            marker = " ↕"
        out.append(skill.ljust(skill_w) + "  " + "  ".join(cells) + "  " + f"{spread:.0%}".rjust(7) + marker)

    out.append("")
    out.append("Summary:")
    summary_w = max(len(label) for label in labels)
    for label in labels:
        s = table["summary"][label]
        mean = s.get("mean")
        n = s.get("n")
        mean_str = f"{mean:.1%}" if isinstance(mean, (int, float)) else "—"
        out.append(f"  {label.ljust(summary_w)}  mean={mean_str}  skills={n}  ts={s.get('timestamp', '')}")

    # Apples-to-apples mean over skills present in every model.
    # Only worth showing when skill sets differ — otherwise it duplicates the per-model means above.
    intersection_skills = [
        skill for skill, accs in table["per_skill"].items()
        if all(accs.get(label) is not None for label in labels)
    ]
    skill_counts = {len(intersection_skills)} | {table["summary"][label].get("n") for label in labels}
    if len(intersection_skills) > 0 and len(skill_counts) > 1:
        intersection_means = {
            label: sum(table["per_skill"][s][label] for s in intersection_skills) / len(intersection_skills)
            for label in labels
        }
        out.append("")
        means_parts = [f"{label}={intersection_means[label]:.1%}" for label in labels]
        skill_word = "skill" if len(intersection_skills) == 1 else "skills"
        out.append(f"  intersection ({len(intersection_skills)} {skill_word}): " + "  ".join(means_parts))
        if len(labels) == 2:
            delta = intersection_means[labels[1]] - intersection_means[labels[0]]
            sign = "+" if delta >= 0 else "−"
            out.append(f"  Δ ({labels[1]} − {labels[0]}) = {sign}{abs(delta):.1%}")

    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Compare trigger-scorer accuracy across N models")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--models", help="Comma-separated model aliases/IDs (e.g., 'haiku,sonnet')")
    group.add_argument("--aggregates", nargs="+", help="Explicit paths to aggregate JSON files")
    parser.add_argument("--skill", help="Compare a single skill only")
    parser.add_argument("--sort", choices=["spread", "skill", "worst"], default="spread",
                        help="Row order: spread=largest model disagreement first")
    parser.add_argument("--format", choices=["ascii", "json"], default="ascii")
    args = parser.parse_args()

    models = [m.strip() for m in args.models.split(",")] if args.models else None
    pairs = resolve_aggregate_paths(models, args.aggregates)
    aggregates = [(label, load_aggregate(path)) for label, path in pairs]
    table = build_table(aggregates, args.skill)

    if args.format == "json":
        print(json.dumps(table, indent=2))
    else:
        print(render_ascii(table, args.sort))


if __name__ == "__main__":
    main()
