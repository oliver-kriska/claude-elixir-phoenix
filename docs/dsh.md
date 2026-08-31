# DeepSeek Harness (dsh) skills

This generated skills-only target follows the skill contract in
[`deepseek-ai/deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness)
as of `dsh v0.1.1-rc.2`. It is a filesystem projection: dsh's
`@deepseek-ai/dsh-skill-filesystem` provider scans a fixed set of roots and loads
single-level `<name>/SKILL.md` bundles, so installation is a checkout into one of
those roots — no plugin manifest, no npm package, no build step.

> **dsh is a developer preview.** Its README states there will be
> compatibility-breaking changes, and the CLI is on release candidates. This
> target deliberately ships only the skill layer, which is the most stable and
> least dsh-specific part of the system. Hooks, subagents, and Cordis plugin
> internals are not ported — see [Deliberate boundaries](#deliberate-boundaries).

See the [runtime support matrix](runtime-support.md) for a concise comparison
with Claude Code, Amp, Codex, Pi, and OpenCode.

## Discovery roots

dsh resolves the project root as the nearest ancestor containing `.git`, then
scans these roots in rank order (lower rank wins a duplicate name):

| Rank | Source | Path |
| --- | --- | --- |
| 100 | `project-dsh` | `<projectRoot>/.dsh/skills` |
| 200 | `project-agents` | `<projectRoot>/.agents/skills` |
| 300 | `custom` | `customSkillDirs` config |
| 400 | `user-dsh` | `$DSH_HOME/skills` (default `~/.dsh/skills`) |
| 500 | `user-agents` | `$DSH_AGENTS_HOME/skills` (default `~/.agents/skills`) |

`.agents/skills` is the cross-agent Agent Skills convention, so it is the
recommended root: the same checkout is readable by other runtimes that adopt it.

## Install

**dsh does not recurse.** Only `<root>/<name>/SKILL.md` and `<root>/<name>.md`
are discovered, so a checkout parked at `.agents/skills/elixir-phoenix/targets/dsh/…`
is invisible. Both options below account for that.

### Option A — copy into a scanned root (recommended)

Works in every profile and preset with no configuration, because each agent
preset mounts its own `skill-filesystem` row against the default roots:

```bash
cd /path/to/your-phoenix-project
tmp="$(mktemp -d)"
git clone --filter=blob:none --sparse \
  https://github.com/oliver-kriska/claude-elixir-phoenix.git "$tmp/src"
git -C "$tmp/src" sparse-checkout set targets/dsh
mkdir -p .agents/skills
cp -R "$tmp/src/targets/dsh/skills/." .agents/skills/
rm -rf "$tmp"
```

For a user-level install available in every project, use `~/.agents/skills`
instead of `.agents/skills`. Re-run the same block to update.

### Option B — `customSkillDirs` (advanced, profile-dependent)

Keeps the checkout updatable with `git pull`, but you must know which row your
profile actually mounts. **In the default `web` profile the base
`skill-filesystem` row is disabled**: `dsh-web-app` sets `disabled: true` on it
because agent presets own local discovery. Configuring that row without
re-enabling it silently does nothing.

```bash
cd /path/to/your-phoenix-project
git clone --filter=blob:none --sparse \
  https://github.com/oliver-kriska/claude-elixir-phoenix.git \
  .dsh/vendor/elixir-phoenix
git -C .dsh/vendor/elixir-phoenix sparse-checkout set targets/dsh
```

In your profile's `cordis.patch.yml`
(`$DSH_HOME/profiles/<name>/cordis.patch.yml`):

```yaml
- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  disabled: false
  config:
    customSkillDirs:
      - /absolute/path/to/your-phoenix-project/.dsh/vendor/elixir-phoenix/targets/dsh/skills
```

A patch replaces a row's entire `config` rather than merging keys, and must
restate every key the row needs — including `disabled: false` to undo the
web bundle's override. This registers the provider into the skill registry's
**global** layer, which merges with the active preset's layer; a preset skill of
the same name wins. Confirm with `dsh --profile <name> --dump-config`.

Update later with `git -C .dsh/vendor/elixir-phoenix pull`.

To test a feature branch or tag before merge, add its ref to `git clone`:

```bash
git clone --branch <branch-or-tag> --filter=blob:none --sparse \
  https://github.com/oliver-kriska/claude-elixir-phoenix.git "$tmp/src"
```

dsh watches its skill roots with Chokidar, so a newly copied skill is picked up
without a restart. A frontmatter change re-reads the catalog; a body-only edit
affects the next load without a catalog message.

## Use

All 51 canonical skills are included with their complete resource subtrees.
Markdown is adapted to dsh's hyphenated names; non-Markdown resources are copied
byte-for-byte with their executable mode bits preserved.

Two invocation paths work, and they load the identical body:

```text
/phx-investigate this LiveView reset
```

dsh's pre-step boundary recognizes a whitespace-bounded `/name` token naming a
user-invocable skill **anywhere in the message** and injects the rendered skill
content deterministically — the model receives the full body without choosing to
load it. This is the closest equivalent to a Claude Code slash command.

```text
Load the phx-review skill, then review the staged diff.
```

The model can also select a skill itself through the `skill` tool, driven by the
catalog of names and descriptions.

Exact Claude colon syntax such as `/phx:review` is not registered; use
`/phx-review`. A name that collides with a host command resolves to the command.

## Deliberate boundaries

This is a focused skills baseline, not Claude Code parity.

**Not included, because dsh has no equivalent:**

- **Custom agents.** dsh's `ctx.subagents` takes `{ description, prompt }` plus an
  optional persona string. There is no markdown agent registry, no named agent
  types, and no `model:`/`tools:`/`effort:` frontmatter, so the plugin's 26
  specialists have no declarative home. The flagship workflows treat native dsh
  subagents as an optional optimization with a valid sequential fallback.
- **Markdown commands.** `ctx.commands.register()` takes a TypeScript handler and
  its result never enters model history. The `user-invocable` skill path above is
  the supported command surface.

**Not included, because the bridge is too partial to be honest:**

- **Lifecycle hooks.** `@deepseek-ai/dsh-hooks-claude-code` bridges 7 of Claude
  Code's 30 hook events and is not in the `dsh-base` bundle. Against this
  plugin's 30 hooks that means: `PostToolUseFailure`, `PreCompact`, `PostCompact`,
  and `StopFailure` are unsupported outright; `SessionStart` accepts only JSON
  `additionalContext`, so the plugin's stdout-based session hooks are silent; the
  `Stop` hook's `systemMessage` is logged but never surfaced; and `if:` conditions
  are not honored, so the file-extension gating on the `PostToolUse` formatting
  and Iron Law hooks would disappear and fire on every write. dsh's model-facing
  tools are also lowercase (`read`, `write`, `edit`, `bash`), so every matcher
  would need a dsh-specific variant. A hooks port is tracked for after dsh
  stabilises.

**External, as on every non-Claude runtime:**

- **Tidewave MCP.** dsh has a working MCP client (`@deepseek-ai/dsh-mcp-client`,
  tools registered as `mcp__<server>__<tool>` exactly as in Claude Code), but no
  server is enabled by default. Register Tidewave yourself with a `cordis.yml`
  plugin row.

**Already free, no action needed:**

- **Workspace instructions.** dsh's `@deepseek-ai/dsh-agent-instructions` defaults
  its candidates to `['AGENTS.md', 'CLAUDE.md']` (plus `.local.md` overlays),
  walked from the project root down to the session cwd. A `CLAUDE.md` written by
  `/phx:init` — Iron Laws, skill auto-load table, reference auto-load table — is
  read verbatim by dsh with no porting step.

## Generation and validation

The target is generated from the canonical plugin, never hand-edited:

```bash
make dsh-skills           # regenerate targets/dsh/
make dsh-skills-validate  # fail on drift against the canonical source
make dsh-skills-sync      # both
```

`make ci` runs `dsh-skills-validate` alongside the other targets, and
`scripts/generated_target_snapshots.json` carries a golden byte-and-mode digest
so an unreviewed change to the generated tree fails CI.

Two dsh-specific rules are enforced at build time beyond the shared Agent Skills
validation:

- **Description bound.** dsh's `catalogDescriptionMaxLength` defaults to 500
  characters and **truncates silently** past it. The builder fails instead, so a
  description can never lose its routing tail unnoticed. (Current longest: 251.)
- **One-level discovery.** dsh deliberately does not support nested
  `**/SKILL.md`. The builder rejects a nested skill rather than shipping one that
  would be invisible at runtime.

```bash
make dsh-runtime-smoke    # optional; needs `dsh` on PATH
```

Unlike the other targets, dsh exposes no *CLI* skill introspection — its surface
is only `dsh --profile`, `dsh plugin`, and `dsh web`. Discovery is therefore
verified over the loopback RPC bridge instead: the smoke installs the target
into an isolated workspace, boots `dsh web --no-open` against a temporary
`$DSH_HOME`, and round-trips two Typert RPC calls on the host's `/api` handler:

| Call | Payload | Assertion |
| --- | --- | --- |
| `POST /api/session.create` | `{ cwd }` | returns a `sessionId` |
| `POST /api/skill.list` | `{ sessionId }` | all 51 generated skills present and `modelInvocable` |

Neither call invokes a provider, so the smoke needs no API key and no model.

Executed against an installed `dsh 0.1.1-rc.2`: the host answered on an
ephemeral loopback port, `session.create` returned
`{ agentPreset, sessionId }` (the smoke asserts only `sessionId`), and
`skill.list` returned all 51 generated skills as
`{ name, description, modelInvocable }` with `modelInvocable: true` throughout.

The same run confirmed the one-level rule empirically. With the identical 51
skills installed one directory deeper — `.agents/skills/elixir-phoenix/<name>/`,
the mistake the install section warns about — dsh discovered **zero** of them
and did not expose the containing directory as a skill either.

> **Treat this as the target's canary.** The endpoints are generated `@Remote`
> descriptors on a pre-1.0 contract, so this is the most breakage-prone part of
> the target — which is also the point: it is the earliest signal that a dsh
> release moved the skill surface.

## Tested against

| Component | Version |
| --- | --- |
| dsh | `0.1.1-rc.2` (installed; smoke executed against it) |
| Skill provider | `@deepseek-ai/dsh-skill-filesystem` |
| Skills generated | 51 |
