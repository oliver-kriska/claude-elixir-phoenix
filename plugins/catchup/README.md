# catchup

Async-team return-from-absence briefing for Claude Code.

Coming back Monday morning, after a flight, or after a long weekend
costs 30–60 minutes of manually scanning PRs, reviews, Linear tickets,
git history, and calendar before the first line of code. `/catchup`
fans out to those sources and emits **one prioritized brief** — not a
firehose of links.

Framework-agnostic: any developer on a distributed team has this
problem, regardless of stack.

## Install

```
/plugin marketplace add oliver-kriska/claude-elixir-phoenix
/plugin install catchup@oliver-kriska
```

## Usage

```
/catchup                                  # since you were last active here
/catchup --since "friday"
/catchup --since "2h" --focus reviews-requested
/catchup --sources github,git --depth quick
/catchup --scope all                      # include cross-repo pings/reviews
```

| Flag | Default | Values |
|------|---------|--------|
| `--since` | `last-active` | `last-active`, `last-session`, `last-commit`/`last-mine`, `2h`/`3d`, `yesterday`, `friday`, a date |
| `--scope` | `repo` | `repo` (this repo only), `all` (cross-repo, listed separately) |
| `--sources` | all detected | `github`, `git`, `linear`, `calendar` |
| `--depth` | `standard` | `quick`, `standard`, `deep` |
| `--focus` | none | `prs`, `reviews-requested`, `mentions`, `impact` |

**Scope.** Default is repo-scoped: every GitHub signal (reviews
requested of you, notifications, mentions) is filtered to the repo you
run `/catchup` in — a per-repo catch-up does not surface another repo's
queue. `--scope all` re-includes cross-repo activity, listed in its own
**Other repos** section, never mixed into this repo's lists.

## Sources (MVP)

| Source | Tool | Needs |
|--------|------|-------|
| GitHub | `gh` CLI | `gh` installed + authed |
| Git | `git log` | a git repo (always works) |
| Linear | Linear MCP | optional — falls back to ticket-ref harvest |
| Calendar | Google Calendar MCP | optional — skipped with a note if absent |

Missing sources degrade the brief, never break it. `git log` alone
produces a valid minimum brief.

## Output

The full brief is written to `.claude/catchup/brief-YYYY-MM-DD.md` and
a tight summary is printed inline. Format follows the 10-element
Context Brief Framework scoped to a personal catch-up brief: Intent +
ranked priorities, what moved, conflict risks, today's timeline.

## What it reads and where data goes

- **GitHub**, through your own `gh` login: notifications, pull requests
  and review requests for the current repo (all repos with
  `--scope all`). Read-only.
- **Git**: `git fetch` of the default branch from `origin`, then
  `git log` and `git diff`. Commit authors' names and emails are read
  to separate your commits from others'.
- **Linear and Google Calendar**, only through MCP connectors you have
  already installed. The plugin declares none of its own.
- **Your last activity**: the modification time of this repo's Claude
  Code session files under `~/.claude/projects/`, never their content.

The brief is written to `.claude/catchup/brief-YYYY-MM-DD.md` in your
project. It holds one-line excerpts and the names of people involved,
never raw issue, PR or thread bodies. Nothing is sent anywhere else, and
there is no telemetry. Slack and Gmail are v2, opt-in, and
double-gated; see `skills/catchup/references/config-schema.md` for the
designed (not yet built) v2 surface.

## Status

MVP. Tracks [issue #47](https://github.com/oliver-kriska/claude-elixir-phoenix/issues/47).
