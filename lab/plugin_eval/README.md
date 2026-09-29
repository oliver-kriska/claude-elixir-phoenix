# Real-session trigger eval (`claude plugin eval`)

`make eval-triggers` asks Haiku "which skill would you load?" given a list of
skill descriptions. This suite measures the same thing inside a real Claude
Code session with the phx, ecto and lv plugins loaded: the full system prompt,
built-in skills competing for the same prompts (`verify`, `debug`, `run`,
`simplify`, `code-review`), our hooks, and a Phoenix-shaped workspace. It needs
Claude Code 2.1.269+ (`claude plugin eval`) and, since CC 2.1.283, git 2.31+.

| | `make eval-triggers` | `make eval-plugin` |
|---|---|---|
| Router | Haiku, descriptions only | Real CC session (Sonnet 5.5 pinned; `MODEL=` overrides) |
| Sees | first 150 chars of each description | full listing, built-ins, hooks, workspace |
| Cost | ~$1.50, ~60 min | ~$53 list price, ~27 min at `J=8` (full suite) |
| Signal | description wording | whether the skill actually fires |

Both read the same prompts from `lab/eval/triggers/*.json` — edit prompts there.

## Run

```bash
make eval-plugin                          # all 566 cases (502 train + 64 held-out val)
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

## Held-out split

A description tuned until its own test prompts pass has only learned those
prompts. Each trigger file therefore holds a train set and a validation set,
following Anthropic's skill-creator description loop (`run_loop.py`): tune on
train, accept on val, 3 runs per prompt.

| Field | Split | Case dir | Role |
|---|---|---|---|
| `should_trigger` | train | `pos-N` | Prompts you may read while rewriting a description |
| `should_not_trigger` | train | `neg-N` | Near-miss negatives |
| `should_trigger_test` | val | `val-pos-N` | Held-out positives (3 or more) that accept or reject a rewrite |
| `should_not_trigger_test` | val | `val-neg-N` | Held-out near-miss negatives |

Every case is tagged `split-train` or `split-val`, plus `train-<skill>` or
`val-<skill>`. `--tag` values are OR-ed, so the per-skill tags are the only way
to select one skill's split. `TAG=split-train` selects the original 502
cases. `make eval-triggers` (Haiku) reads only the train fields.

```bash
RUNS=3 TAG=split-val MAX_COST=25 make eval-plugin                    # acceptance numbers, every skill with a val split
RUNS=3 TAG="train-perf val-perf" MAX_COST=5 make eval-plugin         # one skill, both splits
```

When both splits run together, the analyzer's per-skill recall combines them.
The case names (`val-pos-N`) show which split each row came from.

Rules for a description change:

1. **Fix prompts first, then measure.** Never edit a prompt after seeing how a
   description scores on it. A prompt about a module the fixture doesn't have
   (`ProfileComponent`, a payments schema, a router) measures Claude's search,
   not routing. Point it at what `fixture.sh` creates: `MyApp.Accounts`, `User`,
   `UserLive` and `accounts_test.exs`.
2. **Write val prompts the way a user types them in a Phoenix project**: a
   pasted error, a vague "this page is slow", lowercase. Don't reuse words from
   the description. Negatives should be near-misses: prompts that share
   vocabulary with the skill but belong to a different one.
3. **Tune on train.** Generalize from the user intent behind the failures, and
   never paste words from a failed prompt into the description.
4. **Accept on val.** Measure the old and new description with `RUNS=3`, on the
   same model and in the same session window. Keep the new one only if val
   recall rises and the skill's negatives stay clean. Otherwise restore the old
   text byte for byte.

`lab/tournament/description_tournament.py` refuses skills that have no
`should_trigger_test`. Override with `--allow-unvalidated`.
Its judges only ever see train prompts, so a winning description stays a
candidate until the val split accepts it. `load_trigger_prompts(split="test")`
raises instead of falling back to train prompts.

First held-out pass (2026-09-29, Sonnet 5.5, CC 2.1.284). The seven skills
that scored 0/5 in the full run. Hits out of runs, 3 runs per prompt. The
"before" column uses the old description and the already-fixed prompts.

| Skill | Train before → after | Val before → after | Negatives after | Kept |
|---|---|---|---|---|
| document | 5/15 → 15/15 | 5/12 → 9/12 | 8/8 | yes |
| ecto-patterns | 3/15 → 9/15 | 0/12 → 6/12 | 6/6 | yes |
| oban | 3/15 → 12/15 | 3/12 → 7/12 | 8/8 | yes |
| perf | 6/15 → 10/15 | 0/12 → 9/12 | 6/6 | yes (second rewrite) |
| help | 0/15 → 0/15 | 0/9 → 3/9 | 10/10 | yes (one prompt, 6/6 over two replicates) |
| trace | 0/15 → 0/15 | 0/12 → 6/24 | 6/6 | yes (weak: two replicates) |
| quick | 0/15 → 1/15 | 0/15 → 0/15 | — | no, two rewrites reverted |

Fixing the fixture-gap prompts alone lifted document, ecto-patterns and perf
train recall off zero. The rewrites that won all lead with the user's task and
tell Claude to load the skill *before* acting ("even for a how-to question",
"even if the cause looks obvious"). Noun catalogs lost: Sonnet 5.5 skips a
skill it believes it can replace with its own knowledge. `quick`, `trace` and
`help` stay low because the fixture's three files make those tasks trivial to
do directly.

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
- **SessionStart hook exit 1 with empty stderr** is Claude Code reporting a hook
  as `outcome: "cancelled"`, not a script failure. It hits only the first hook of
  each SessionStart matcher group (`setup-dirs.sh`, `check-scratchpad.sh`) and
  scales with machine load: 5 of ~1,000 sessions on 2026-09-12, up to 34% of a
  run on 2026-09-29 while three evals ran at once, 0% for the same code at low
  load. A 30-session A/B (CC 2.1.284) ruled out the scripts: draining stdin
  (4/30 vs 3/30) and a pre-existing `.claude/` (4/30) changed nothing. It only
  costs the directory setup or scratchpad banner in that session; ignore it when
  scoring, and keep `J` low when a clean trace matters.

## Results

| Run | Model / CC | Cases | Positive recall | Negatives clean | Cost |
|---|---|---|---|---|---|
| Baseline 2026-09-12 | Sonnet 5 / 2.1.269 | 502 | 176/269 (65%) | 233/233 | $53 |
| After description rewrite | Sonnet 5 / 2.1.269 | 303 | 171/269 (64%)¹ | 34/34 | $31 |
| Sonnet 5.5 baseline 2026-09-29 | Sonnet 5.5 / 2.1.284 | 502 | 164/269 (61%)² | 233/233 | $40 |

¹ Includes the two rewrites later reverted and the plan/review fixture flavors;
the controlled per-skill A/B is in CHANGELOG.

² v3.1.2 branch. Descriptions were byte-identical to the Sonnet 5 baseline (only
skill/agent bodies and hooks changed, which routing doesn't see), so the −12 is
the model change plus single-run noise. Only oban (3→0), techdebt (5→2) and
brief (1→4) moved more than ±2 of 5. Compare future runs against this row.

## Quality evals

The trigger suite asks whether a skill fires. `make eval-quality` asks whether
what it produces is good, and whether it beats Claude with no plugin. Six
hand-written cases in `lab/plugin_eval/quality/` (committed; results go to the
ignored `quality/results/`) each invoke a skill explicitly and grade the files
it writes or its final message. Every case runs twice per run: with phx, ecto
and lv loaded, and with no plugin. The no-plugin arm gets the same text;
without the plugin, Claude treats the unknown `/phx:` command as a plain request
("`/phx:quick` isn't installed, so I handled this as a plain request").

```bash
make eval-quality                          # 6 cases × 1 run × 2 arms, ~$2, ~5 min
RUNS=3 make eval-quality                   # ~$5.50, ~13 min; the least to quote a Δ from
CASE=money-field RUNS=3 make eval-quality  # one case (--case name glob)
MAX_COST=5 J=2 make eval-quality           # ceiling (default $15), concurrency (default 4)
python3 -m lab.plugin_eval.quality lab/plugin_eval/quality/results/<ts>   # re-summarize for free
```

| Case | Invokes | Trap in the fixture | Graders |
|---|---|---|---|
| `money-field` | `/phx:quick` | Every numeric column is `:float`, including a legacy `shipping_cost`; the prompt says to follow the existing numeric fields | price is `:decimal` or integer cents in schema and migration, never `:float`, cast in the changeset (regex on files); final answer flags `shipping_cost` (llm) |
| `review-orders` | `/phx:review` | Branch with 5 obvious defects (N+1, `String.to_atom` on a param, float money, no authorization in `handle_event`, query in `mount`) and 4 subtle ones (no `@external_resource`, unsupervised `Task.start`, Gettext locale lost in it, `order.user` not preloaded) | one grader per defect on the final message (regex where a keyword is unavoidable, llm otherwise); no `Edit` calls |
| `plan-favorites` | `/phx:plan` | Feature spanning Accounts and Catalog | `plans/favorites/plan.md` exists, has `- [ ]` tasks, a unique index, streams/`assign_async`, a `mix test`/`compile` step; no Write/Edit under `lib/`, `priv/`, `test/` |
| `investigate-newsletter` | `/phx:investigate` | `attrs[:newsletter]` read on string-keyed form params, a test that passes atom keys, and a `/phx:compound` doc for a related incident in `.claude/solutions/` | root cause, why the test passes, fix uses the cast boolean not the `"false"` string (llm); names the key mismatch, uses the prior solution doc (regex) |
| `liveview-products` | `/phx:quick` | 50k products; the existing `UserLive` queries in `mount`, and the prompt asks for the same style | no `assign(..., Catalog.list_...)` in mount, `assign_async`/`connected?`, a stream, pagination (regex on the file) |
| `oban-welcome` | `/phx:quick` | none | string-key `perform/1` match, no atom keys, enqueue with the id, `unique:` or a sent guard, cancel/discard on a missing user (regex on files) |

### Why it is shaped this way

- **Only user-invocable skills can be invoked.** `ecto-patterns`,
  `liveview-patterns` and `oban` are `user-invocable: false`. `/phx:oban ...`
  ends a `-p` run after 0 turns with an empty result and no error, so the
  with-plugin arm scores as if the plugin had broken. The implementation cases
  use `/phx:quick` instead, which leaves the reference skills to their `paths:`
  activation and the hooks, as in a real session. `test_quality.py` rejects a
  case that invokes a non-invocable skill.
- **`.claude/` is write-protected in eval runs.** Writes there are denied in
  dontAsk mode even with `--allow-tools Write "Write(.claude/**)"`, so the
  plugin's `.claude/plans/...` artifacts can't be written or graded. The plan
  prompt names `plans/favorites/plan.md`. The review is graded on its final
  message: agents fail to save their reports and the skill falls back to their
  chat replies, as its missing-file path intends. The summary lists every denial.
- **Graders read files or the final message, never `trace`.** The with-plugin
  trace contains hook output (the SessionStart banner) but never the prompt or
  the expanded skill, and it records no PostToolUse hook or `paths:` skill
  activation. File targets take exact paths (a glob throws), so prompts name the
  files to write. A missing file fails even a `not_contains` grader.
- **Regex graders on prose miss paraphrases.** The review's first `mount`
  pattern failed on "runs on both the dead and connected renders". A finding
  that can be stated without one fixed keyword gets an `llm` grader
  (`--judge-model sonnet`). `test_quality.py` pins every regex grader against a
  good and a bad sample.
- **mix is not granted.** The fixture has no deps and the sandbox has no network,
  so every compile would fail. Prompts say so and both arms skip it.
  `Bash(git *)` is granted for review's diff. When the plan skill runs its depth
  preflight (`echo $CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`), that is denied too.
  For this small feature it spawned no research agents in runs 2–3.
- **Traps are deliberate.** Several fixtures hold an existing bad pattern and ask
  Claude to follow conventions. That is where the Iron Laws should beat pattern
  copying, and where a no-plugin arm is most likely to slip.

### Reading quality results

`quality.py` prints each grader's passes per arm with a verdict. `plugin +`
means the grader separates the arms. `both pass` means Claude already does it
without the plugin, so the grader guards against regressions but measures no
plugin value. `both fail` is an improvement target. Treat any single-grader
difference below 2 of 5 runs as noise.

### Quality results

Sonnet 5.5, CC 2.1.284, judge Sonnet, 2026-09-29. Runs 2 and 3 used identical
definitions for the five non-review cases and are pooled (5 runs per arm);
`review-orders` changed graders between runs and is listed per run.

| Case | With | Without | Δ | Graders that separate the arms (with / without) |
|---|---|---|---|---|
| `money-field` | 0.97 | 0.77 | +0.20 | no-plugin copied `:float` for price in 1/5; flags `shipping_cost` 4/5 vs 2/5 |
| `liveview-products` | 0.95 | 0.75 | +0.20 | `assign_async`/`connected?` 4/5 vs 1/5; pagination 5/5 vs 4/5 |
| `investigate-newsletter` | 1.00 | 0.84 | +0.16 | uses the prior solution doc 5/5 vs 1/5 |
| `plan-favorites` | 1.00 | 0.94 | +0.06 | `- [ ]` checkbox tasks 5/5 vs 3/5 |
| `oban-welcome` | 0.84 | 0.80 | +0.04 | `unique:`/sent guard 1/5 vs 0/5 |
| `review-orders` | 0.93–1.00 | 0.90–1.00 | −0.05 to +0.10 | none reliably; 8 runs per arm |

- **No-plugin Sonnet 5.5 is strong at reading code.** It found all nine seeded
  review defects in most runs, including the four subtle ones, and got the
  investigation's root cause, test gap and `"false"`-string trap right every
  time. The plugin's measurable edge is in writing code against a bad local
  convention (float money, query in `mount`) and in using project knowledge
  (`.claude/solutions/`), not in spotting defects.
- **`oban-welcome` idempotency is a gap in both arms.** Iron Law 7 says jobs
  must be idempotent, but the with-plugin worker added `unique:` or a sent
  guard in 1 of 5 runs. In 2 of 5 it returned `{:discard, ...}`, which the
  oban skill never teaches (it teaches `{:cancel, ...}`), so the path-scoped
  oban skill did not reliably shape `/phx:quick` output.
- **Costs.** About $0.10 per run for `/phx:quick` cases, $0.20 for plan and
  investigate, $0.25 for review (2–3 subagents). Run 3 (6 cases × 3 runs × 2
  arms): $5.40, 12.5 min at `J=4`.
