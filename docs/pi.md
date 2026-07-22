# Pi skills package

The generated Pi package provides all 51 canonical Elixir/Phoenix skills and
their bundled resources. It was tested with Pi **0.79.1**. This is a focused
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

To test a branch before merge, pin that ref:

```bash
pi install git:github.com/oliver-kriska/claude-elixir-phoenix@feat/pi-skills-package
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

A pinned branch remains on that branch and advances when the package is updated.
Tags and commit hashes remain fixed. Run `pi install ...@new-ref` to switch refs.
Remove the user-level package with:

```bash
pi remove git:github.com/oliver-kriska/claude-elixir-phoenix
```

For a project-local package, pass `-l` to `pi remove` from that project.

## Supported capabilities

- all canonical skills generated from `plugins/elixir-phoenix/skills`;
- complete skill subtrees, including resources outside `references/`;
- exact non-Markdown bytes and preserved executable mode bits;
- Pi-native `/skill:phx-*`, `/skill:lv-*`, and `/skill:ecto-*` references;
- resource paths rewritten relative to each generated skill;
- usable, sequential `phx-investigate` and read-only `phx-review` workflows;
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
not disabled in Pi settings. A clean reinstall is:

```bash
pi remove git:github.com/oliver-kriska/claude-elixir-phoenix
pi install git:github.com/oliver-kriska/claude-elixir-phoenix
```

The generated package manifest deliberately declares `pi.skills` as an array.
Pi 0.79.1 expects resource values to be arrays; a string can prevent package
resource discovery.

## Maintainer workflow

The Claude Code skills remain canonical. Never hand-edit `targets/pi`.

```bash
make pi-skills           # regenerate targets/pi
make pi-skills-sync      # regenerate, then verify committed output
make pi-skills-validate  # read-only drift check
```

Generation stages and validates the complete package before replacing the target
with in-process rollback. A failed build preserves the previous target. Drift
validation detects additions, removals, content changes, node-type changes, and
mode-only changes. CI runs it without weakening the existing Amp or Codex checks.
