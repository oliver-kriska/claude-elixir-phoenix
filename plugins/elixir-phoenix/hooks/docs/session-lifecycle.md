# Session Lifecycle (`SessionStart`)

Six hooks that run when a session begins. `SessionStart` stdout **is** added to
Claude's context (one of only two events with that property, the other being
`UserPromptSubmit`), so what these print is read by the model, not just shown to
you.

They split across two matchers:

| Matcher | Scripts | Runs on |
|---|---|---|
| `""` (all) | `setup-dirs.sh`, `detect-tidewave.sh`, `detect-ash.sh` | Every session start, including `clear` and `compact` |
| `startup\|resume\|fork` | `check-scratchpad.sh`, `check-resume.sh`, `check-branch-freshness.sh` | Only genuinely new or resumed sessions |

That split is deliberate. Directory setup and capability detection are cheap and
idempotent, so they run always. The resume banner would be noise if it reprinted
after every `/clear`.

Three of the six are `async: true` — they do not delay the first prompt.

---

## `setup-dirs.sh`

Creates the workflow directories so skills never have to check first:

```text
.claude/plans .claude/reviews .claude/solutions
.claude/audit .claude/skill-metrics .claude/research
```

Plus `$CLAUDE_PLUGIN_DATA/skill-metrics` when available (Claude Code v2.1.78+),
which survives plugin updates.

Gated on `mix.exs` — without that gate the plugin littered `.claude/plans/` and
friends into every non-Elixir repo you opened (issue #55).

---

## `detect-tidewave.sh` (async)

Probes `http://localhost:4000/tidewave/mcp` with a JSON-RPC `ping`.

```text
✓ Tidewave MCP available — prefer mcp__tidewave__project_eval over mix eval/test,
  mcp__tidewave__get_docs over WebSearch for Elixir docs,
  mcp__tidewave__execute_sql_query over psql
```

Session analysis found Tidewave becomes the **primary** tool where it is
available — 55%+ of tool calls — so telling Claude it exists changes behavior
materially.

**It only probes when `tidewave` is actually a dependency** (checked in
`mix.exs`, `mix.lock`, `apps/*/mix.exs`). A blind probe logged a stray
`POST /tidewave/mcp` in the server output of any Phoenix app listening on :4000,
which was confusing for people not using Tidewave at all (issue #72).

This is also why the plugin uses a direct HTTP probe rather than an
`mcp_tool`-type hook: `SessionStart` fires before MCP servers finish connecting.
Reserve `mcp_tool` hooks for `PreToolUse` / `PostToolUse` / `Stop`, where the
connection is already live.

---

## `detect-ash.sh` (async)

Detects Ash Framework via `:ash,` in `mix.exs` or `use Ash.Resource` /
`use Ash.Domain` under `lib/`, then prints the Ash-specific ground rules:

```text
✓ Ash Framework detected — ash-framework skill auto-loads on Ash file edits
  Iron Laws: domain code interfaces, actor on query, generators first, codegen after changes
  Generators: mix ash.gen.resource | mix ash.gen.domain (use --yes)
  Migrations: mix ash.codegen <name> && mix ash.migrate  (NOT hand-edit; NOT mix ecto.migrate)
```

It additionally checks whether `usage_rules` is installed **and** configured. If
either is missing you get an install hint, because without it Ash documentation
lookups can return guidance for a different version than the one you have:

```text
⚠ usage_rules not configured — Ash docs may not match your installed versions.
  Install: mix igniter.install usage_rules
  Sync:    mix usage_rules.sync
```

When it is configured, the line becomes a research command instead:
`mix usage_rules.search_docs "<topic>" -p ash -p ash_phoenix -p ash_postgres`.

---

## `check-scratchpad.sh`

Two jobs.

**Reports existing scratchpads**, with a specific callout for dead ends — the
most valuable section on resume:

```text
Scratchpad: 22 note(s) found — latest: .claude/plans/cc-2-1-226-adoption/scratchpad.md
  (3 dead-end entries — read them before retrying an approach)
```

Only bullets inside the `## Dead Ends` section count. Until v3.1.2 it counted
every `- ` line in the file, so the template's Handoff bullets alone reported
"3 dead-end entries" on a scratchpad with none.

**Initializes a template** for any plan directory that has a `plan.md` but no
scratchpad, with sections for Dead Ends, Decisions, Open Questions, and Handoff
(branch, plan path, next step).

---

## `check-resume.sh`

Counts checkboxes in every `plan.md` and prints one line per plan with
outstanding work:

```text
↻ Plan 'multi-agent-port' has 11 remaining tasks (73 done).
  Resume with: /phx:work .claude/plans/multi-agent-port/plan.md
```

When nothing is pending, an Elixir project instead gets the idle banner:

```text
Elixir/Phoenix plugin loaded — describe your task and I'll suggest the right workflow
```

This script is the **sole owner** of that banner — a duplicate `echo` entry in
`hooks.json` used to print it twice and was removed.

Its gate is wider than the usual `mix.exs` check: `mix.exs` **or** an existing
`.claude/plans/*/plan.md`. That way a non-Elixir repo stays quiet, while a repo
already using the plan workflow (this plugin's own repo, for instance) keeps its
resume hints.

### One counting detail worth knowing

`grep -c` prints `0` and exits 1 on no match. The idiomatic-looking
`grep -c … || echo 0` therefore appends a **second** line, and the resulting
two-line value breaks the `-gt` comparison and garbles the banner. The scripts
use `VAR=${VAR:-0}` instead. The same pattern appears in `check-scratchpad.sh`
and `detect-ash.sh`.

---

## `check-branch-freshness.sh` (async)

```text
⚠ Branch 'feat/notifications' is 12 commits behind origin/main (as of your last fetch). Consider rebasing.
```

Silent on `main` / `master`, silent when fresh, silent outside a git repo or a
project without `mix.exs`. It does **not** run `git fetch`: it compares against
`origin/main` as it stood at your last fetch. A hook that fetched on every
session start would contact your remotes with your SSH key or credential
helper, in the background, without being asked, and the Anthropic plugin
directory flags that.

## Related

- [Workflow State](workflow-state.md) — how `StopFailure` feeds the resume banner
- [Context Injection](context-injection.md) — the other event whose stdout reaches Claude
- `/phx:work --continue` — resume an interrupted plan
