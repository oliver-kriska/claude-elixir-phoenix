---
name: start
description: "Start or resume an Elixir rewrite of an app in any language (Rails, Django, PHP, Node, Go, Java, .NET, others) and show its status. Use when someone wants to port, migrate or rewrite an app into Elixir/Phoenix."
effort: medium
argument-hint: "[<legacy-app-path>] [--steering <dir>] [--status] [--auto]"
---

# Rewrite Start — Entry, Resume, Status

The front door of the rewrite workflow. It explains the method once, finds
where an existing rewrite stands, checks that the legacy source has not
changed underneath it, and routes to the next phase.

```text
/rewrite:start → /rewrite:analyze → /rewrite:architect → /rewrite:roadmap
                                                             ↓ per slice
                         /rewrite:verify ← /phx:work ← /phx:plan
```

## Iron Laws

1. **ONE PHASE AT A TIME** — route to the next phase; with `--auto`, chain only analyze → architect → roadmap
2. **IDENTITY BEFORE RESUME** — compare the source snapshot before trusting earlier artifacts
3. **STATE COMES FROM FILES** — read `.claude/rewrite/` and the ledger script, never memory of a previous session
4. **`--auto` STOPS AT DECISIONS** — it never approves ASSUMED choices, never starts `/phx:work`, never deploys or touches production data
5. **LEGACY STAYS READ-ONLY** — never write into or execute the source app

## Workflow

### 1. Check dependencies and detect state

If the `phx:plan` skill is not in this session's skill list, tell the user to
install `elixir-phoenix` from the marketplace that provided `rewrite`
(`/plugin install elixir-phoenix@oliver-kriska`, or that marketplace's
name), then run `/reload-plugins`. Without it the architect consults and
the `/phx:plan` handoff fail, so `--auto` stops after analyze.

```bash
ls .claude/rewrite/ .claude/rewrite/architecture/ 2>/dev/null && sed -n '1,40p' .claude/rewrite/status.md
python3 "${CLAUDE_SKILL_DIR}/../architect/scripts/ledger.py" check --rewrite-dir .claude/rewrite  # once architecture.md exists
```

Read the first matching row, top to bottom. An active slice comes before
seeding a new one:

| Found | State | Next |
|-------|-------|------|
| nothing | new | step 2, then `/rewrite:analyze <path>` |
| phase `analyzing`, or an `analysis/*.md` missing | analyze incomplete | `/rewrite:analyze <Source path>` |
| `analysis/*.md`, no ADR-000 | analyzed | `/rewrite:architect` |
| ADR-000, no `architecture.md` | architect incomplete | `/rewrite:architect` (resumes at step 4) |
| ADR-000 + `architecture.md`, but `decisions.md` or `divergences.md` missing, phase `architecting`, or `ledger.py check` fails | architect incomplete | `/rewrite:architect` (resumes at step 4 or 5) |
| ADR-000 + `architecture.md` + `decisions.md` + `divergences.md`, clean ledger, no `roadmap.md` | architected | `/rewrite:roadmap` |
| a slice `planned` or `in-progress` whose `plan.md` has at least one `- [x]` and no `- [ ]` | awaiting gate | `/rewrite:verify NN` |
| a slice `planned` or `in-progress` | building | `/phx:work .claude/plans/{slug}/plan.md`, then `/rewrite:verify NN` |
| `roadmap.md` with `ready` or `seeded` slices | slicing | `/rewrite:roadmap --next` |
| every slice `done` | complete | release rehearsal slice, or close out |

### 2. New rewrite: explain once, then analyze

In five lines or fewer, tell the user how this works: features are goals,
every mechanism's purpose is recovered before it is ported, the
compatibility bar comes before architecture, slices go to `/phx:plan`, and
parity needs evidence. Then run `/rewrite:analyze` with the path (ask for it
if missing). The artifacts go to `./.claude/rewrite/` in the current
directory; that must be the Elixir project or an empty workspace, not the
legacy app.

### 3. Resume: check identity

```bash
SOURCE=$(sed -n 's/^Source path: //p' .claude/rewrite/status.md)
TARGET=$(sed -n 's/^Target path: //p' .claude/rewrite/status.md); [ "$(pwd -P)" = "$TARGET" ]
python3 "${CLAUDE_SKILL_DIR}/../analyze/scripts/inventory.py" "$SOURCE" \
  --compare .claude/rewrite/inventory/inventory.json
```

Stop and name `Target path` when the cwd differs. Exit 1 from `--compare`
lists the changed identity fields. For a git source, show what changed
since the recorded sha:

```bash
git -C "$SOURCE" diff --stat {recorded_sha}..HEAD
```

Ask whether to re-analyze the changed areas (`/rewrite:analyze --scope …`).
Mark evidence `stale` for ledger rows whose anchors fall in changed files.

### 4. Status (`--status`, or always on resume)

```bash
python3 "${CLAUDE_SKILL_DIR}/../architect/scripts/ledger.py" stats --rewrite-dir .claude/rewrite
grep -E "^\| [0-9]{2}[a-z]? " .claude/rewrite/roadmap.md
```

Show: phase, ADR-000 status (accepted or ASSUMED), ledger verified-of-
denominator with UNDECIDED and accepted-risk counts, slices by state,
pending divergences, and the single next command.

### 5. `--auto` chain

Run `/rewrite:analyze <path> --auto` (passing any `--steering`), then `/rewrite:architect --auto`,
then `/rewrite:roadmap --auto`, each via the Skill tool from this session.
Stop early when a phase reports a blocker. End with the list of `ASSUMED`
decisions the user must approve and the next command; `/phx:plan` runs only
when no consequential decision is ASSUMED or pending.

Headless or CI runs (`claude -p`) stop background agents 10 minutes after
the last turn. Lift that ceiling for the whole chain:

```bash
CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0 claude -p "/rewrite:start /path/to/legacy --auto"
```

## Artifacts (`.claude/rewrite/`)

| Path | Written by |
|------|------------|
| `status.md`, `charter.md`, `inventory/`, `kb/`, `analysis/` (incl. `budget.md`) | analyze |
| `ledger.md`, `architecture/` (`ADR-000-compatibility-bar.md`, `architecture.md`, `decisions.md`, `divergences.md`, `adr/`, `consults/`) | architect |
| `roadmap.md`, `../plans/rewrite-NN-*/interview.md` + `scratchpad.md` | roadmap |
| `verify/NN/` (preflight, evidence, idiom, parity, report), `verify/accepted-risks.md` | verify (risks: user only) |

## Arguments

- `<legacy-app-path>` — the app to rewrite (new rewrites)
- `--status` — report only
- `--auto` — chain analyze → architect → roadmap without questions; defaults recorded as ASSUMED
