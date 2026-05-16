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
/catchup                                  # since your last session here
/catchup --since "friday"
/catchup --since "2h" --focus reviews-requested
/catchup --sources github,git --depth quick
```

| Flag | Default | Values |
|------|---------|--------|
| `--since` | `last-session` | `last-session`, `2h`/`3d`, `yesterday`, `friday`, a date |
| `--sources` | all detected | `github`, `git`, `linear`, `calendar` |
| `--depth` | `standard` | `quick`, `standard`, `deep` |
| `--focus` | none | `prs`, `reviews-requested`, `mentions` |

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

## Privacy

Excerpt-only by default. No raw issue/PR/thread bodies in the brief.
Slack and Gmail are v2, opt-in, and double-gated. See
`skills/catchup/references/config-schema.md` for the (designed, not yet
built) v2 surface: scheduling, per-project config, cross-project rollup.

## Status

MVP. Tracks [issue #47](https://github.com/oliver-kriska/claude-elixir-phoenix/issues/47).
