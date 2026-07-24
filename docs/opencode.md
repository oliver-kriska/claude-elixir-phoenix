# OpenCode skills

This generated skills-only baseline is tested with OpenCode 1.17.2. Runtime
acceptance used `opencode/north-mini-code-free`; skill behavior still depends on
the model selected by each user. OpenCode recursively discovers `SKILL.md` files
below the documented `.opencode/skills/` project path and equivalent global
config root. It does not provide a native Git or package installer for skills,
so installation is a sparse Git checkout. The nested checkout layout relies on
recursive discovery verified with OpenCode 1.17.2; the documented portable
layout places each skill directly under `.opencode/skills/`.

See the [runtime support matrix](runtime-support.md) for a concise comparison
with Claude Code, Amp, Codex, and Pi.

## Install

Project-local installation keeps the Elixir/Phoenix guidance scoped to one
repository:

```bash
cd /path/to/your-phoenix-project
git clone --filter=blob:none --sparse \
  https://github.com/oliver-kriska/claude-elixir-phoenix.git \
  .opencode/skills/elixir-phoenix
git -C .opencode/skills/elixir-phoenix sparse-checkout set targets/opencode
```

To install globally, use the same checkout under the OpenCode config root:

```bash
git clone --filter=blob:none --sparse \
  https://github.com/oliver-kriska/claude-elixir-phoenix.git \
  ~/.config/opencode/skills/elixir-phoenix
git -C ~/.config/opencode/skills/elixir-phoenix sparse-checkout set targets/opencode
```

Both commands use the default `main` branch. Reviewers can test a feature branch
or tag before merge by adding its ref to `git clone`:

```bash
git clone --branch <branch-or-tag> --filter=blob:none --sparse \
  https://github.com/oliver-kriska/claude-elixir-phoenix.git \
  .opencode/skills/elixir-phoenix
git -C .opencode/skills/elixir-phoenix sparse-checkout set targets/opencode
```

Start a fresh OpenCode session after installation. A project checkout affects
only that project; a global checkout makes the skills available in every
OpenCode project and may influence model-driven skill selection there.

## Use

The flagship generated skill names are `phx-investigate` and `phx-review`.
OpenCode may select a skill from its description, but the documented explicit
prompt is:

```text
Use the skill tool to load the phx-investigate skill, then investigate this LiveView reset.
```

OpenCode selects the model implicitly; these skills do not configure a model.
All 51 canonical skills and their complete supporting resource subtrees are
included. Markdown is adapted to OpenCode's hyphenated names; non-Markdown
resources are copied byte-for-byte.

This is a focused baseline, not full Claude Code parity. It does not install
hooks, custom agents, separate command definitions, MCP servers, AGENTS.md, or
configuration. OpenCode 1.17.2 also projects discovered skills as slash commands
when their names do not collide with existing commands; the documented
skill-tool prompt above is the portable explicit invocation.
Native OpenCode subagents are an optional optimization in the flagship
workflows, and the sequential fallback is valid. Tidewave is optional and its
MCP registration is external. Exact Claude colon syntax such as `/phx:review` is not
registered; use `/phx-review`. The investigation, review, plan, work, PR-review,
and full-lifecycle workflows have explicit OpenCode adaptations. PR review uses
a GitHub connector or authenticated `gh` without fabricating mutations; full
preserves user gates and bounded sequential fallback. Plan keeps its canonical
artifact schema and a scratchpad research checklist; work uses plan checkboxes
and `progress.md` for ordered, resumable execution. `phx-trace` uses direct
`mix xref` discovery, `phx-audit` runs five health tracks, and `phx-research`
uses native web or HTTP capabilities with a local-source fallback. Other
generated workflows receive portable frontmatter, resource, and command
projection but may still describe optional Claude-specific orchestration APIs;
those capabilities are deferred rather than silently emulated. In particular,
`phx-perf` describes Claude specialist agents; run its quoted analysis tracks
directly or with generic OpenCode subagents.
`phx-learn-from-fix` still targets Claude-specific personal skill and memory
locations. `phx-freeze` is adapted to an advisory current-session scope and
does not claim hook enforcement.

### Optional Tidewave MCP

Installing these skills does not configure MCP. When the Phoenix project runs
Tidewave, add its endpoint to the project `opencode.json` (or the global
`~/.config/opencode/opencode.json`) and replace `$PORT`:

```json
{
  "mcp": {
    "tidewave": {
      "type": "remote",
      "url": "http://localhost:$PORT/tidewave/mcp",
      "enabled": true
    }
  }
}
```

Generated workflows retain a complete fallback when Tidewave is unavailable.

## Runtime acceptance

The OpenCode 1.17.2 acceptance run verified all 51 generated skills in an
isolated home, native skill-tool loading, a bundled resource outside
`references/`, executable resource mode, fresh-process removal, and both
flagship workflows. `/phx-investigate` reproduced a planted `FunctionClauseError`
before identifying the atom/string-key mismatch with file and line evidence.
`/phx-review` found a planted cross-account invoice lookup, returned
`REQUIRES CHANGES`, cited the changed lines, and left the tracked diff and status
unchanged.

## Verify and troubleshoot

List discovered JSON skill records:

```bash
opencode debug skill
```

Confirm that `phx-investigate` and `phx-review` appear and that their paths point
inside the checkout. If discovery remains stale, close OpenCode, remove the
checkout, repeat the install, and start a clean session.

Update or uninstall with:

```bash
git -C .opencode/skills/elixir-phoenix pull --ff-only
rm -rf .opencode/skills/elixir-phoenix
```

The pull updates only the currently checked-out branch. A tag or commit checkout
remains pinned until you explicitly switch refs. Start a fresh OpenCode process
after updating or removing the checkout because skill discovery is session-cached.

For a global install, substitute
`~/.config/opencode/skills/elixir-phoenix`. Removing the checkout is the complete
uninstall; no OpenCode config mutation needs to be reverted.

## Maintainers

Generate and drift-check the target with:

```bash
make opencode-skills
make opencode-skills-validate
make opencode-skills-sync
make opencode-runtime-smoke
```

The optional smoke target generates the current checkout into a temporary
global-style skills tree (the closest local equivalent to the documented sparse
Git checkout), then checks discovery, resources, and removal in fresh OpenCode
processes using `opencode debug skill --pure`. All `HOME` and XDG roots are
temporary. It never copies credentials and performs no model or
network-dependent prompt.

CI runs the read-only drift check. `targets/opencode` and this document are
ignored in local development, so release orchestration must force-add them when
publishing the target.
