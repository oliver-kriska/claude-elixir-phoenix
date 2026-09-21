# Real-session trigger eval (`claude plugin eval`)

`make eval-triggers` asks Haiku "which skill would you load?" given a list of
skill descriptions. This suite measures the same thing inside a real Claude
Code session with the phx, ecto and lv plugins loaded: the full system prompt,
built-in skills competing for the same prompts (`verify`, `debug`, `run`,
`simplify`, `code-review`), our hooks, and a Phoenix-shaped workspace. It needs
Claude Code 2.1.269+ (`claude plugin eval`).

| | `make eval-triggers` | `make eval-plugin` |
|---|---|---|
| Router | Haiku, descriptions only | Real CC session (Sonnet 5 pinned) |
| Sees | first 150 chars of each description | full listing, built-ins, hooks, workspace |
| Cost | ~$1.50, ~60 min | ~$53 list price, ~27 min at `J=8` (full suite) |
| Signal | description wording | whether the skill actually fires |

Both read the same prompts from `lab/eval/triggers/*.json` — edit prompts there.

## Run

```bash
make eval-plugin                          # all 502 cases (269 positive, 233 negative)
SKILL=brief make eval-plugin              # one skill, ~$1
SKILL="perf review" make eval-plugin      # several skills
TAG=trigger-pos make eval-plugin          # positives only (tags are OR-ed)
MIN_RECALL=0.6 make eval-plugin           # exit 1 if any skill's recall is below 60%
MAX_COST=20 make eval-plugin              # hard list-price ceiling (exit 2, partial)
```

Every run is a real session billed to your plan or API key. `run.sh`
regenerates cases, runs `claude plugin eval`, archives traces into
`lab/plugin_eval/cases/results/<ts>/traces/`, writes `summary.json`, prints the
analysis, and deletes the sealed sandboxes `--keep-temp` left in `/private/tmp`.
Re-analyze any past run without spending anything:

```bash
python3 -m lab.plugin_eval.analyze lab/plugin_eval/cases/results/<ts>
```

## Layout

```
lab/plugin_eval/
├── fixture.sh      # scaffold: tiny Phoenix app, git repo, one uncommitted change
├── generate.py     # lab/eval/triggers/*.json → cases/triggers/<skill>/{pos,neg}-N/
├── analyze.py      # skills invoked, load/hook/run errors, recall, stray fires
├── run.sh          # generate → eval → archive → analyze → clean sandboxes
└── cases/          # generated + results (gitignored)
```

Each case is `case.yaml` (plugins + scaffold), `prompt.md` (the trigger prompt,
`max_turns: 3`, read-only tools plus `Skill`) and one `tool_used: Skill` grader
matching `phx:<skill>`. Negative cases set `min: 0, max: 0, arm: both`.

## Why it is shaped this way

- **Runs from the repo root, not `plugins/elixir-phoenix/evals/`.** phx declares
  `dependencies: ["ecto", "lv"]`. Loaded alone, CC disables it with
  `dependency-unsatisfied` and `claude plugin eval` still prints "Plugin under
  test" and scores every run — as routing misses. Cases therefore list all three
  plugin dirs in `plugins:`, and those entries must sit under the directory the
  eval runs against. The analyzer exits 2 whenever a trace shows `plugin_errors`.
  This also keeps ~500 generated case dirs out of every user's install.
- **Matchers require the `phx:` namespace.** CC ships a built-in `verify` skill;
  `(?:ns:)?verify` would count it as a hit for ours.
- **`max_turns: 3`.** Routing is decided in the first turns. Uncapped runs spent
  3× the tokens on work the grader ignores. The resulting "Reached maximum number
  of turns" error is expected; any *other* run error (rate limit, timeout) is
  reported as unreliable.
- **A scaffolded workspace.** In an empty directory Claude answers "there is no
  project here" instead of routing. `--scaffold` is required and only runs our
  own `fixture.sh`.
- **`--ablation none`.** A no-plugin arm can never invoke `phx:*`, so Δ carries
  no information for a trigger suite and would double the cost.

## Reading results

- **Recall swings ±2 of 5 between identical runs.** Never keep or revert a
  description on one run per prompt. For a change, run both arms with
  `--runs 2`–`3` in the same window (see the 2026-09-12 A/B in CHANGELOG).
- **`(none)` misroutes are mostly "Claude just did the task".** Skills load on
  the first tool call or not at all; reference skills load for how-to questions
  far more often than for implementation requests.
- **Some skills cannot score well here, by construction:** `research` (web
  tools are not granted), `tidewave-integration` (no Tidewave MCP), `recall`
  (no ccrider), `brief`/`work`/`triage` (prompts assume an earlier conversation
  or a single unambiguous plan — Claude asks "which plan?"), and `help`/`intro`/
  `quick` (answering from the skill listing or making the one-line edit is fine).
- **SessionStart hook exit 1 with empty stderr** appeared in 5 of ~1,000 runs
  at `J=8` (4 of them in Ash-flavored runs). It did not reproduce in 18 runs
  with every SessionStart script instrumented with an EXIT trap, nor in 240
  local concurrent hook runs. Unexplained; if it recurs, re-add the trap
  (`trap 'echo "HOOKTRACE <name> exit=$? line=$LINENO" >&2' EXIT`) and grep the
  archived traces for `HOOKTRACE`.

## Results (Sonnet 5, CC 2.1.269)

| Run | Cases | Positive recall | Negatives clean | Cost |
|---|---|---|---|---|
| Baseline 2026-09-12 | 502 | 176/269 (65%) | 233/233 | $53 |
| After description rewrite | 303 | 171/269 (64%)¹ | 34/34 | $31 |

¹ Includes the two rewrites later reverted and the plan/review fixture flavors;
the controlled per-skill A/B is in CHANGELOG.
