# End-to-end runs — 2026-10-09

Headless `claude -p "/rewrite:start $SOURCE --auto"` runs on three public apps,
with phx, ecto, lv and rewrite loaded through `--plugin-dir`. Each directory
holds the workspace's `.claude/rewrite/` output (`rewrite/`) and the roadmap's
`/phx:plan` seeds (`plans/`). The materialized KB copies (`rewrite/kb/`, which
equal the plugin's `elixir-way/references/` at run time) and `inventory.json`
are left out. `inventory.md` carries the same facts. Raw stream-json
transcripts are not kept.

Paths are normalized: `$S` is the session scratchpad that held the testbeds
and workspaces, and `~` is the home directory. The legacy sources were never
executed, and nothing else in these files was edited.

| Directory | Source | Plugin state | Ledger check today |
|-----------|--------|--------------|--------------------|
| `campfire/` | `basecamp/once-campfire` (Rails 8, SQLite, Action Cable) | before the Amp review fixes; run 2 resumed run 1 | OK |
| `node/` | Node/Express/Prisma RealWorld @ `30b68e1` | before the Amp review fixes; run 2 resumed run 1 | 4 errors: R-20/22/23/25 accounted for in prose only, which the stricter parser rejects |
| `django-v2/` | Django RealWorld @ `29c9d42` | after all review fixes; one invocation | OK: 74 rows, verified 0, UNDECIDED 10 |
| `django-v2-handoff/` | `django-v2` seed 00a, approval simulated | fresh-session `/phx:plan` on the seed | n/a: every seeded ID retained across `plan.md` and `scratchpad.md` (`plan.md` cites only D-06, X-04); task coverage not established |

`campfire/report.md` grades the Campfire run against an Amp-written oracle
(kept locally in `.claude/research/`): 86/100 with 0 hard failures, but only
after a manual resume. The first unattended run died in the architect phase,
and its defects 1–9 are fixed in the plugin. Cost figures in it are redacted.
`campfire/ledger-check.txt` is the check output at the time of the run.

The `django-v2-handoff/` seed differs from `django-v2/plans/` only in its
`Status:` line and one approval line, since `--auto` correctly blocks every
handoff. The other files are the `plan.md` and `scratchpad.md` that phx wrote,
plus the research note from its dependency check. This run used the earlier
ID-retention check; roadmap step 5 now also maps each decision to a plan
task, which this run did not exercise. The plan's P-2 caught the
architecture's boot fence (a `restart: :temporary` Task cannot stop the app),
and its P-1 caught ecto_sqlite3 converting the legacy file to WAL. Both are
now rules in the KB (`data-compat.md`, `sqlite-on-beam.md`).

What these runs do not cover: `/phx:work` on a seeded plan, `/rewrite:verify`
against a built slice, and any app that is not a public demo or Campfire.
