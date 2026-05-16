---
name: catchup
description: "Summarize and review what changed while you were away. Use after a weekend, vacation, or flight to check missed PRs, git commits, Linear tickets, and meetings — one prioritized brief, not a firehose."
effort: high
disable-model-invocation: true
argument-hint: "[--since \"friday\"|\"2h\"|\"last-session\"] [--sources github,git,linear,calendar] [--depth quick|standard|deep] [--focus prs,reviews-requested,mentions,impact]"
allowed-tools: Read, Grep, Glob, Bash, Write, WebFetch
---

# Catchup — Async-Team Return Briefing

You've been away. Reconstruct "what happened and what needs me first"
from multiple sources, then emit ONE prioritized Context Brief.

## Usage

```
/catchup
/catchup --since "friday"
/catchup --since "2h" --focus reviews-requested
/catchup --sources github,git --depth quick
```

## Iron Laws

1. **Detect every source before querying** — never assume Linear or
   Calendar MCP exists. Probe, skip cleanly, note the gap in one line.
2. **Excerpt-only** — never paste raw issue/PR/thread bodies into the
   brief. One-line excerpts or summaries. Privacy default is opt-out.
3. **Prioritize, don't dump** — every item must answer "why does this
   need me". Drop noise (bot PRs, your own merged work, CI greens).
4. **One brief file per run** — no fragmented output.
5. **Never pass raw user input to a shell unquoted** — validate the
   time ref against the grammar before it reaches `git`/`gh`.
6. **Stop after the brief** — never auto-transition to another command.

## Workflow

### 1. Parse arguments

From `$ARGUMENTS` extract: `--since`, `--sources`, `--depth`,
`--focus`. Defaults: `--since last-session`, all detected sources,
`--depth standard`, no focus filter.

### 2. Resolve the time window

Read `${CLAUDE_SKILL_DIR}/references/time-window.md` and resolve
`--since` to an absolute `SINCE_ISO` timestamp + a human label
("3 days, since Fri May 13"). For `last-session`, map the current
working dir to `~/.claude/projects/-<slug>/` and take the newest
`*.jsonl` mtime; fall back to 24h with a noted assumption if no signal.

### 3. Detect sources (before any query)

```
gh:       command -v gh && gh auth status         → github source ON
git:      git rev-parse --is-inside-work-tree      → git source ON
linear:   a Linear MCP tool is available           → linear source ON
calendar: a Google Calendar MCP tool is available  → calendar source ON
```

For every requested source that is OFF, record a one-line skip note
for the brief's **Risks/assumptions** block (e.g. "Linear MCP absent —
ticket signal harvested from commit/PR refs only"). Never hard-fail.

### 4. Fan out (parallel where independent)

Run independent source queries in ONE batch. Read
`${CLAUDE_SKILL_DIR}/references/source-adapters.md` for the exact
recipes. Summary:

- **GitHub** — `gh search prs`/`gh pr list`/`gh api` for PRs updated in
  window, review-requested-of-you, your PRs with new comments/CI state.
- **Git** — `git log --since` on the default branch and your local
  branches, authored by others; surface migrations/lockfile churn.
- **Linear** — if MCP ON: tickets assigned to you, status-changed,
  new comments in window. If OFF: harvest `[A-Z]{2,}-\d+` ticket refs
  from git/PR titles as a proxy and label them unverified.
- **Calendar** — if MCP ON: meetings missed in window + today's agenda
  in the user's TZ. If OFF: skip with a note.
- **Your in-flight scope** — compute the file set you are currently
  working on (open PR files, local feature-branch diffs vs default,
  uncommitted working tree). Recipes in `source-adapters.md` §Impact.

### 4b. Impact on your scope (the differentiator)

Intersect *files moved by others* on the default branch in the window
with *your in-flight scope* from step 4. Report, ranked above generic
"what moved":

- **Direct overlap** — a specific file you're editing also changed
  upstream → concrete conflict/semantic risk, name both sides.
- **Adjacent** — same module/dir touched → "may affect your work".

At `--depth deep`, read the incoming diff for overlapping files and
write a one-line *semantic* impact ("ENA-9168 changed the survey
schema your branch depends on — regen your migration"). This answers
"how do these changes impact my current/future work", not just "what
did I miss". `--focus impact` = brief is *only* this section.

`--depth quick` = counts + top 3 per source, no excerpts. `standard` =
prioritized items + one-line excerpts + impact overlap by filename.
`deep` = + CI failure detail, cross-source links (PR ↔ ticket),
per-file semantic impact analysis.

### 5. Assemble the Context Brief

Read `${CLAUDE_SKILL_DIR}/references/brief-format.md` and map findings
onto the 10-element template scoped to a personal catch-up brief.
Lead with **Intent** ("you've been off N days; do these 3 first"), a
ranked **Top priorities** list, then an **Impact on your work** block
(promote a direct overlap into Top priorities — it outranks a review
request). Cross-link PRs to tickets when a shared `XXX-####` ref is
found. Flag risks ("unmerged migration #10933 may conflict with your
local branch `feat/foo`").

### 6. Output

- Write the full brief to `<cwd>/.claude/catchup/brief-<YYYY-MM-DD>.md`
  (create the dir). One file per run; overwrite same-day reruns.
- Print a tight inline summary: Intent line + numbered Top priorities +
  per-source counts + any skipped-source notes. Keep it under ~25 lines
  — the file holds the detail.

### 7. Stop

Present the summary and the brief path. **Do NOT** auto-invoke any
other command. The user decides what to act on first.

## Sources at MVP

GitHub (`gh`), Git (`git`), Linear MCP (optional), Google Calendar MCP
(optional). Slack/Gmail are **v2 opt-in** — never queried at MVP, never
piped raw. Scheduling and per-project config are designed in
`${CLAUDE_SKILL_DIR}/references/config-schema.md` but not built at MVP.

## Graceful degradation contract

A missing source degrades the brief, never breaks it. The minimum
viable brief uses only `git log` (always available in a repo). Every
absent source becomes one honest line under Risks/assumptions, so the
reader knows what the brief does *not* cover.
