# OpenCode skills

This generated skills-only baseline is tested with OpenCode 1.17.2. Runtime
acceptance used `opencode/north-mini-code-free`; skill behavior still depends on
the model selected by each user. OpenCode recursively discovers `SKILL.md` files
below `.opencode/skill/` and `.opencode/skills/` (and the equivalent global
config roots). It does not provide a native Git or package installer for skills,
so installation is a sparse Git checkout.

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

After this feature merges, both commands use the default `main` branch. Reviewers
can test this branch before merge by adding the branch to `git clone`:

```bash
git clone --branch feat/opencode-skills-package --filter=blob:none --sparse \
  https://github.com/oliver-kriska/claude-elixir-phoenix.git \
  .opencode/skills/elixir-phoenix
git -C .opencode/skills/elixir-phoenix sparse-checkout set targets/opencode
```

Start a fresh OpenCode session after installation. A project checkout affects
only that project; a global checkout makes the skills available in every
OpenCode project and may influence model-driven skill selection there.

## Use

The flagship generated records are `/phx-investigate` and `/phx-review`.
OpenCode may select a skill from its description, but the most reliable explicit
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
configuration. OpenCode itself exposes discovered skills as slash commands.
Native OpenCode subagents are an optional optimization in the flagship
workflows, and the sequential fallback is valid. Tidewave is optional and its
MCP setup is deferred. Exact Claude colon syntax such as `/phx:review` is not
registered; use `/phx-review`. The investigation, review, plan, work, PR-review,
and full-lifecycle workflows have explicit OpenCode adaptations. PR review uses a
GitHub connector or authenticated `gh` without fabricating mutations; full
preserves user gates and bounded sequential fallback. Plan keeps its canonical
artifact schema and a scratchpad research checklist; work uses plan checkboxes and
`progress.md` for ordered, resumable execution. Other generated workflows
receive portable frontmatter, resource, and command projection but may still
describe optional Claude-specific orchestration APIs; those capabilities are
deferred rather than silently emulated.

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
