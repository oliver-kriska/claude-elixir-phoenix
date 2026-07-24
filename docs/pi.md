# Pi skills package

The generated Pi package provides all 51 canonical Elixir/Phoenix skills and
their bundled resources. It was tested with Pi **0.81.1**. This is a focused
skills baseline, not full Claude Code feature parity.

See the [runtime support matrix](runtime-support.md) for a concise comparison
with Claude Code, Amp, Codex, and OpenCode.

## Install

Install globally for every Pi project:

```bash
pi install git:github.com/oliver-kriska/claude-elixir-phoenix
pi list
```

Or install only in the current project (`.pi/settings.json`):

```bash
pi install -l git:github.com/oliver-kriska/claude-elixir-phoenix --approve
pi list --approve
```

Pi clones Git packages into its package cache. Start a fresh session after
installation. The repository root manifest points Pi at the committed generated
skills in `targets/pi/skills`.

To test a branch, tag, or commit before merge, configure that ref:

```bash
pi install git:github.com/oliver-kriska/claude-elixir-phoenix@<branch-tag-or-commit>
```

## Use skills

Force a flagship workflow with Pi's native skill-command syntax:

```text
/skill:phx-investigate FunctionClauseError while creating an invoice
/skill:phx-review
```

Other namespaced Claude skills follow the same normalized convention:

```text
/skill:phx-plan Add audit logging
/skill:lv-assigns lib/my_app_web/live/dashboard_live.ex
/skill:ecto-n1-check
```

Pi also exposes skill names and descriptions to the model so it can select a
relevant skill implicitly. Explicit `/skill:<name>` invocation is preferable
when a workflow must be loaded reliably.

## Update and uninstall

Update the installed Git package:

```bash
pi update git:github.com/oliver-kriska/claude-elixir-phoenix
```

Pi accepts an explicit `@ref` as a branch, tag, or commit. Updates keep targeting
that configured ref: a moving branch—and a moved tag—can resolve to a newer
commit, while a commit SHA remains fixed. Run `pi install ...@new-ref` to
deliberately change the configured target.

Remove the user-level package with:

```bash
pi remove git:github.com/oliver-kriska/claude-elixir-phoenix
```

For a project-local package, remove it from that project with the same trust
boundary used during installation:

```bash
pi remove -l git:github.com/oliver-kriska/claude-elixir-phoenix --approve
```

`--approve` is required only when project trust has not already been persisted.
Start a fresh Pi process after an install, update, ref change, or removal.

## Supported capabilities

- all canonical skills generated from `plugins/elixir-phoenix/skills`;
- complete skill subtrees, including resources outside `references/`;
- exact non-Markdown bytes and preserved executable mode bits;
- Pi-native `/skill:phx-*`, `/skill:lv-*`, and `/skill:ecto-*` references;
- resource paths rewritten relative to each generated skill;
- usable, sequential `phx-investigate` and read-only `phx-review` workflows;
- portable `phx-plan` research checklists and resumable `phx-work` plan-file
  progress tracking, with complete same-session sequential fallbacks;
- portable `phx-pr-review` connector/`gh` triage and mutation confirmation, plus
  gated, bounded `phx-full` plan → work → verify → review → compound execution;
- automatic skill selection through Pi's native Agent Skills support.

## Intentionally deferred

- Pi extensions or hook-like event handlers;
- generated prompt templates and short `/phx-*` aliases;
- custom agents or subagent orchestration;
- bundled Tidewave MCP configuration (Pi does not natively bundle MCP);
- package-root `AGENTS.md` or other automatic instructions;
- exact Claude `/phx:*` command syntax.

The flagship workflows do not require those capabilities. Tidewave and native
subagents are optional optimizations when independently available; each workflow
has a same-session sequential path.

Some non-flagship skills remain baseline projections and may describe richer
Claude Code orchestration APIs. They are included for domain guidance and
progressive migration, not as a claim of complete workflow parity.

## Project and global scope

A default install writes to Pi's user settings and applies to all Pi sessions.
`pi install -l` writes `.pi/settings.json`, keeping the package declaration in
one repository. Project resources are trust-gated. The `--approve` flag trusts
project files only for that command; use Pi's `/trust` command and restart to
persist the decision for future sessions. `pi list --approve` is only an
inspection command. Neither install mode copies custom agents, hooks, MCP
configuration, or `AGENTS.md` into user directories.

## Troubleshooting

Confirm Pi and the package are visible:

```bash
pi --version
pi list
```

If skills do not appear, start a fresh session and confirm skill commands were
not disabled in Pi settings. A clean user-level reinstall is:

```bash
pi remove git:github.com/oliver-kriska/claude-elixir-phoenix
pi install git:github.com/oliver-kriska/claude-elixir-phoenix
```

For a project-local clean reinstall, run from that project:

```bash
pi remove -l git:github.com/oliver-kriska/claude-elixir-phoenix --approve
pi install -l git:github.com/oliver-kriska/claude-elixir-phoenix --approve
```

For non-interactive Git-backed updates, set `GIT_TERMINAL_PROMPT=0` so missing
credentials fail instead of waiting for a prompt.

The generated package manifest deliberately declares `pi.skills` as an array.
Pi 0.81.1 expects resource values to be arrays; a string can prevent package
resource discovery.

## Maintainer workflow

The Claude Code skills remain canonical. Never hand-edit `targets/pi`.

```bash
make pi-skills           # regenerate targets/pi
make pi-skills-sync      # regenerate, then verify committed output
make pi-skills-validate  # read-only drift check
make pi-runtime-smoke    # optional isolated native runtime acceptance
```

The smoke target generates a temporary local Pi package, installs it with an
isolated `HOME` and `PI_CODING_AGENT_DIR`, and uses RPC `get_commands` to verify
all 51 native `/skill:*` commands without requiring credentials or making a
model call. It also checks a retained executable resource byte-for-byte and
mode-for-mode, removes the package, and confirms a fresh Pi process no longer
discovers it. `PI_OFFLINE=1` and `PI_TELEMETRY=0` prevent startup network and
telemetry activity.

Generation stages and validates the complete package before replacing the target
with in-process rollback. A failed build preserves the previous target. Drift
validation detects additions, removals, content changes, node-type changes, and
mode-only changes. CI runs it without weakening the existing Amp or Codex checks.
