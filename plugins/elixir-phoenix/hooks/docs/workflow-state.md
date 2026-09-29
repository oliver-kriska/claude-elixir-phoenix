# Workflow State (`PostToolUse`, `SessionStart` compact, `StopFailure`, `Stop`)

Six hooks that keep the plan workflow coherent across the things that normally
destroy it: compaction, API failures, and closing the laptop.

The filesystem is the state machine — `plan.md` checkboxes are the source of
truth — so these hooks exist to make sure Claude keeps *looking* at that state.

| Script | Event | Job |
|---|---|---|
| `plan-stop-reminder.sh` | `PostToolUse` on `Write(*plan.md)` | Stop after planning; do not auto-implement |
| `log-progress.sh` | `PostToolUse` on `Edit`/`Write` | Append edit metrics (JSONL) |
| `compact-rules.sh` | `SessionStart` (matcher `compact`) | Re-inject phase rules after context is squashed |
| `compact-verify.sh` | `SessionStart` (matcher `compact`) | Point Claude back at the active plan |
| `stop-failure-log.sh` | `StopFailure` | Record an API failure for next session |
| `check-pending-plans.sh` | `Stop` | Warn about session-created risks on exit |

---

## `plan-stop-reminder.sh`

The single most behavior-changing hook in the plugin. When a new `plan.md` is
written, it hard-stops the run:

```text
==========================================
STOP: Plan file created.
==========================================
Don't start implementing — the user reviews the plan first.
Present a brief summary of the plan to the user,
then use AskUserQuestion with options:
  - Start in fresh session (recommended)
  - Get a briefing (/phx:brief)
  - Start here
  - Review or adjust the plan
==========================================
```

Planning burns a lot of context. Rolling straight into implementation in the
same window means the *execution* phase starts already half-full, which is
exactly when quality drops.

Three conditions must all hold:

1. The path matches `.claude/plans/<slug>/plan.md`.
2. It was a **`Write`**, not an `Edit`. `Write` carries `tool_input.content`;
   `Edit` carries `old_string`. Checking for `content` distinguishes plan
   *creation* from routine checkbox updates.
3. `/phx:full` autonomous mode is **not** active — detected by a `progress.md`
   containing a `**State**:` field, written by `workflow-orchestrator` during
   INITIALIZING. Stopping an autonomous cycle to ask a question would defeat it.

---

## `log-progress.sh` (async)

Appends one JSON line per edit to
`$CLAUDE_PLUGIN_DATA/skill-metrics/edits-YYYY-MM.jsonl`:

```json
{"ts":"2026-08-19T10:22:31+02:00","file":"lib/my_app/accounts.ex","project":"my_app"}
```

Feeds `/skill-monitor`. Fully silent, never blocks, `|| true` on every write.

### What it used to do

Until v2.8.3 this hook appended to `progress.md`. It picked the most recently
modified `progress.md` across **all** plans, so with more than one plan in
flight it wrote entries into unrelated plans (issue #38). The `/phx:work` skill
logs structured progress itself, so the hook's version was both redundant and
wrong. It was replaced with metrics-only.

---

## `compact-rules.sh`

After compaction, re-injects the rules for whatever phase you are in.

Iron Laws live in the system prompt and survive compaction on their own. What
does **not** survive is skill-specific procedure loaded into conversation
context — so only that is re-injected.

The hook detects the phase from the filesystem:

| Detected state | Re-injected |
|---|---|
| `progress.md` has `**State**:` | `/phx:full` autonomous mode — continue the cycle, re-read `progress.md` for cycle count |
| `research/` exists, no `plan.md`; or `plan.md` has `Status: PENDING` | `/phx:plan` — the STOP-after-planning rule, verbatim |
| `plan.md` has unchecked `- [ ]` tasks | `/phx:work` — verify after every task, max 3 retries then BLOCKER, never auto-start `/phx:review` |

It also appends the **Dead Ends** section of the active plan's scratchpad:

```text
Scratchpad dead ends (approaches that already failed — don't retry them):
- Tried supervising the cache in the app tree — Repo isn't started yet at that point
```

Losing that across a compaction means re-walking a dead end you already paid for.

Output is plain **stdout** on `SessionStart` with the `compact` matcher — the
channel CC documents for re-injecting context after compaction. Until v3.1.2
this ran on `PreCompact`, first with `hookSpecificOutput.additionalContext`
(rejected: `PreCompact` has no such field), then with `systemMessage`, which CC
shows to the user only. Neither version ever reached Claude. `PreCompact` and
`PostCompact` have no channel to the model; `PreCompact` can only block.

---

## `compact-verify.sh`

The other half of the pair, on the same `SessionStart` `compact` matcher. After compaction, if any plan still has unchecked
tasks:

```text
POST-COMPACTION: Active plan 'multi-agent-port' detected.
Re-read .claude/plans/multi-agent-port/plan.md and
.claude/plans/multi-agent-port/scratchpad.md to restore context.
```

Plain stdout. It used to be a `PostCompact` hook with exit 2 + stderr, which
CC shows to the user only.

---

## `stop-failure-log.sh`

Fires when a turn ends because of an API error. Appends to the most recent
plan's scratchpad:

```markdown
## API Failure — 2026-08-19 14:32

Turn ended due to API error. Check progress.md for last completed task.
Resume with: /phx:work --continue
```

**The write is the entire job.** Claude Code ignores this event's exit code and
output completely — it cannot block and it cannot message. An earlier version
emitted `exit 2` + stderr, which was a silent no-op.

The signal propagates through the filesystem instead: next session,
`check-scratchpad.sh` reads that scratchpad and surfaces it in the startup
banner. That is the whole mechanism.

---

## `check-pending-plans.sh`

Fires on every `Stop`, and stays **silent almost always**.

It only speaks when there is a *session-created* signal the user could not
otherwise know about — running `background_tasks[]` or scheduled
`session_crons[]` (both added to `Stop` input in Claude Code 2.1.145). A
forgotten `mix phx.server` is exactly the thing `SessionStart` cannot warn you
about tomorrow.

```text
⚠ Before you leave:
  • 1 background task(s) still running — stop them or detach explicitly
  • 3 plan(s) have uncompleted tasks
  • 7 uncommitted change(s) on 'feat/notifications' — commit or stash before switching/rebasing
```

Pending plans and a dirty tree appear **only as supporting context once a
background signal has already fired**. They are already surfaced at
`SessionStart` by `check-resume.sh` and `check-branch-freshness.sh`, so
re-warning them on every single turn would be pure noise. On a clean stop the
hook exits before spawning `git` or `grep` at all.

### Why `systemMessage` and not `additionalContext`

This is the `Stop` event's defining constraint:

| Channel | Effect |
|---|---|
| Plain stdout | Debug log only — never shown in the transcript |
| `additionalContext` / exit 2 | Feeds Claude and **continues the turn** |
| JSON `systemMessage` | Shown to the **user**; Claude still stops |

An advisory reminder must not force Claude to keep working, so `systemMessage`
is the only correct channel. The hook also exits early when `stop_hook_active`
is true, which prevents a recursive stop loop.

## Related

- [Session Lifecycle](session-lifecycle.md) — where the `StopFailure` breadcrumb gets read
- [Code Quality](code-quality.md) — the other `PostToolUse` hooks
- `/phx:work`, `/phx:full`, `/phx:brief`
