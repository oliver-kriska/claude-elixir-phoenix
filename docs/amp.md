# Use the Elixir/Phoenix Skills with Amp

The Amp edition brings the plugin's Elixir, Phoenix, LiveView, Ecto, Oban,
testing, security, and workflow knowledge to Amp as standard Agent Skills. It is
a generated, skills-only projection of the full Claude Code plugin—not a second
hand-maintained implementation.

The canonical source remains `plugins/elixir-phoenix/`. Amp-specific naming and
path constraints never flow back into the Claude Code plugin, so both targets
can evolve without weakening Claude Code support.

See the [runtime support matrix](runtime-support.md) for a concise comparison
with Claude Code, Codex, Pi, and OpenCode.

## What you get

- All 51 skills and their complete bundled resources.
- Amp-compatible names and frontmatter.
- Rewritten cross-skill links and resource paths.
- Project-local and user-wide installation options.
- Compatibility with project-specific skills already in `.claude/skills/`.

The Amp edition does not install the Claude Code hooks, 26 custom subagents,
permission settings, or MCP configuration. See [Feature compatibility](#feature-compatibility)
before relying on a workflow or administration skill.

## Requirements

1. Install [Amp](https://ampcode.com/).
2. Run the installation from the Elixir/Phoenix project where Amp will work.

## Install in one project (recommended)

Project-local installation keeps this opinionated guidance scoped to an
Elixir/Phoenix repository. From the project that should use the skills:

```bash
amp skill add \
  https://github.com/oliver-kriska/claude-elixir-phoenix/tree/main/targets/amp/skills \
  --target "$PWD/.agents/skills"
```

The result should contain 51 directories such as:

```text
.agents/skills/
├── ecto-patterns/
├── liveview-patterns/
├── phx-investigate/
├── phx-review/
├── testing/
└── tidewave-integration/
```

Choose whether to commit `.agents/skills/` so the whole team receives the same
version, or add it to `.gitignore` and install it per developer. Do not leave
individual skill directories at the repository root; Amp discovers project
skills from `.agents/skills/`.

## Install for every project

Use a global installation only if most of your Amp work is Elixir/Phoenix:

```bash
amp skill add \
  https://github.com/oliver-kriska/claude-elixir-phoenix/tree/main/targets/amp/skills \
  --global
```

Amp installs global skills in `~/.config/agents/skills/`.

## Verify the installation

Start a fresh Amp process from the target project after installing or updating
the skills:

```bash
cd /path/to/your-phoenix-project
amp skill list
amp
```

`amp skill list` should show entries such as `phx-investigate`, `testing`, and
`tidewave-integration`. For a project-local installation, their displayed base
directories should resolve under the project's `.agents/skills/` directory.

For an explicit end-to-end check, start a fresh thread and ask:

```text
Load phx-investigate. State the skill's base directory, then summarize the
investigation workflow and the bundled references you can use.
```

The tool result should report a path like:

```text
/path/to/your-phoenix-project/.agents/skills/phx-investigate
```

## Use the skills

Amp discovers each installed skill's name and description. It loads the rest of
`SKILL.md` and any relevant bundled resources only when the skill is invoked.

### Let Amp choose

Describe the engineering outcome naturally:

```text
Investigate why this LiveView filter resets after the server patch. Reproduce
the problem and identify the first state boundary that diverges before editing.
```

Amp may select `phx-investigate`, `liveview-patterns`, and `testing` from their
descriptions. Selection is model-driven, so it is useful but not guaranteed on
every prompt.

### Request explicit use

Amp supports deterministic, user-invoked skills. In the Amp CLI:

1. Open the command palette with `Ctrl+O`, or type `/`.
2. Run `skill: invoke`.
3. Select `phx-investigate`, `phx-review`, or another installed skill.
4. Send the task in your next message.

Amp forces the selected skill to load for that message. In Amp editor
extensions, open the command palette with `Cmd+Shift+A` or `Alt+Shift+A`, then
follow the same `skill: invoke` flow.

This is the closest native equivalent to invoking `/phx:investigate` or
`/phx:review` in Claude Code. Amp's command palette replaces the old slash menu,
so the exact Claude namespaced syntax is not registered as a prompt command.

You can also name the skill in your prompt. This is convenient for reusable
prompts, handoffs, and non-interactive `amp -x` calls:

```text
Load phx-investigate and investigate this LiveView filter reset.
```

```text
Load phx-review, liveview-patterns, and testing. Review the current changes,
read the relevant bundled references, and report which skills you loaded.
```

The names use hyphens rather than Claude Code command namespaces:

| Claude Code | Amp |
| --- | --- |
| `/phx:plan` | `phx-plan` |
| `/phx:investigate` | `phx-investigate` |
| `/ecto:n1-check` | `ecto-n1-check` |
| `/lv:assigns` | `lv-assigns` |
| `liveview-patterns` | `liveview-patterns` |

For example, the familiar workflows translate as follows:

| Goal | Claude Code | Amp |
| --- | --- | --- |
| Review changes | `/phx:review` | Invoke `phx-review`, then describe the review scope. |
| Investigate a bug | `/phx:investigate <bug>` | Invoke `phx-investigate`, then send the bug details. |
| Check an Ecto N+1 | `/ecto:n1-check` | Invoke `ecto-n1-check`, then send the query or scope. |

Typing only `investigate` as a normal prompt may cause Amp to choose
`phx-investigate`, but that remains model-driven. Use `skill: invoke` when you
need certainty.

## Coexist with project and Claude Code skills

Amp can read both native `.agents/skills/` and Claude-compatible
`.claude/skills/`. According to the Amp manual, duplicate names use this
precedence, from highest to lowest:

1. `~/.config/agents/skills/`
2. `~/.agents/skills/`
3. `~/.config/amp/skills/`
4. `.agents/skills/`
5. `.claude/skills/`
6. `~/.claude/skills/`
7. plugins, legacy locations, and built-in skills

This means an Amp-native project installation overrides an existing
project-local Claude skill with the same name. Skills with different names
coexist, allowing an application to keep specific skills—for example,
deployment or incident workflows—alongside the general Elixir/Phoenix set.

Use `amp skill list` to confirm which copy won. Amp can ignore Claude Code skill
directories entirely through the `amp.skills.disableClaudeCodeSkills` setting
if an isolated compatibility test requires it.

## Update or remove

Amp copies skills when `amp skill add` runs; starting Amp does not fetch updates
automatically. Rerun the remote installation with `--overwrite` to install the
latest generated skills from `main`:

```bash
cd /path/to/your-phoenix-project
amp skill add \
  https://github.com/oliver-kriska/claude-elixir-phoenix/tree/main/targets/amp/skills \
  --target "$PWD/.agents/skills" \
  --overwrite
```

For a global update:

```bash
amp skill add \
  https://github.com/oliver-kriska/claude-elixir-phoenix/tree/main/targets/amp/skills \
  --global \
  --overwrite
```

`--overwrite` replaces installed skills with the same name. It may leave an
obsolete directory when a future release removes or renames a skill. If exact
synchronization matters, compare the installed names with
`targets/amp/skills/` and remove only obsolete directories from this package.

To remove a project-local installation, delete only the skill directories that
came from this target—or remove `.agents/skills/` if it contains nothing else.
For a global installation, apply the same rule under
`~/.config/agents/skills/`; that directory may contain unrelated skills, so do
not delete it wholesale unless it contains nothing else.

Amp also provides native removal for one known skill at a time:

```bash
# Project-local
amp skill remove phx-review --target "$PWD/.agents/skills"

# Global (skill remove has no --global flag)
amp skill remove phx-review --target "$HOME/.config/agents/skills"
```

Repeat that command only for names installed by this package. A clean reinstall
removes every known package-owned skill, reruns `amp skill add`, and starts a
fresh Amp process. Do not loop over every directory in a shared skills root;
that can remove unrelated project or personal skills. `--overwrite` is the
normal update path, but removal followed by installation is the exact-sync path
when a release deletes or renames a skill.

## Feature compatibility

| Capability | Claude Code plugin | Amp edition |
| --- | --- | --- |
| 51 skills and bundled resources | Full | Full |
| Domain knowledge and Iron Laws | Full | Full |
| Automatic skill selection | Supported | Supported, model-driven |
| Explicit skill loading | Slash command | Command palette: `skill: invoke` |
| 26 named custom subagents | Full | Not installed |
| Parallel workflow orchestration | Full | Amp adapts where possible |
| Lifecycle and enforcement hooks | Full | Not installed |
| Claude permission settings | Full | Not installed |
| Plugin MCP configuration | Full | Not installed |

Domain and reference skills such as `liveview-patterns`, `ecto-patterns`,
`testing`, and `security` work directly. Workflow skills such as `phx-plan`,
`phx-review`, and `phx-full` retain their knowledge, but instructions that rely
on named Claude subagents or lifecycle hooks require Amp-native adaptation.

These administration skills are primarily reference material in Amp:

| Skill | Claude-specific dependency |
| --- | --- |
| `phx-freeze` | Enforcement requires a Claude `PreToolUse` hook. |
| `phx-permissions` | Manages Claude permission settings. |
| `phx-init` | Installs Claude-specific project instructions. |
| `phx-watch-pr` | Uses Claude background-monitor lifecycle tools. |

The generated files mark unsupported Claude hook paths explicitly and contain
no unresolved `${CLAUDE_SKILL_DIR}` or `${CLAUDE_PLUGIN_ROOT}` variables.

## Troubleshooting

### A skill is on disk but Amp does not list it

- Confirm it is under `.agents/skills/<name>/SKILL.md`, not the project root.
- Start a fresh Amp process from the project after installation.
- Run `amp skill list` and inspect the reported base directory.
- Validate that `SKILL.md` has `name` and `description` frontmatter.

### Amp loads a different copy

Run `amp skill list` and compare the displayed path with the precedence list
above. A user-wide skill can override a project-local skill. Use a unique name,
remove the higher-priority duplicate, or install into the intended location.

### Amp does not select a relevant skill automatically

Automatic selection depends on the model matching the prompt to the skill
description. Open the command palette, run `skill: invoke`, and select the skill
before sending the task. For non-interactive use, name the skill explicitly and
ask Amp to report the loaded base directory.

### `/phx:review` does not run in Amp

This is expected. Amp uses a command palette rather than user-defined prompt
slash commands. Type `/` or press `Ctrl+O`, run `skill: invoke`, select
`phx-review`, then send the review scope. The installed workflow is the same
generated skill; only the invocation surface differs.

### A workflow mentions Claude-only tools

Treat those steps as guidance and ask Amp to adapt them using Amp-native tools.
Do not assume that hooks, named Claude subagents, or permission enforcement are
active merely because their workflow skill is installed.

## Maintain the generated target

Never edit `targets/amp/skills` manually. Change the canonical Claude skill,
then regenerate and verify the complete target with one command:

```bash
make amp-skills-sync
git add targets/amp/skills
```

`make amp-skills` remains available when generation without a follow-up drift
check is useful; `make amp-skills-validate` is the read-only check used by hooks
and CI.

The Husky pre-commit hook runs `make amp-skills-validate` only when files under
`plugins/elixir-phoenix/skills/` are staged. It blocks the commit when the Amp
target has drift or regenerated target changes were not staged. GitHub Actions
runs the same drift check for every pull request and push to protect contributors
who do not have Husky installed.

Clone the repository only when changing the canonical plugin or generator. Amp
users installing the published skills should use the remote commands above.

The builder:

1. validates normalized names and detects collisions before writing;
2. copies complete skill subtrees, transforming Markdown only;
3. preserves non-Markdown content and executable mode bits;
4. validates frontmatter, resource paths, and unresolved Claude tokens;
5. replaces the target only after the staged build passes, with rollback if the
   final replacement fails;
6. supports the read-only drift check used by CI.

The canonical Claude plugin remains independently verifiable:

```bash
make validate
make eval-all
```

Maintainers with Amp installed can run a model-free native acceptance check:

```bash
make amp-runtime-smoke
```

Tested with Amp `0.0.1784796539-g051498`, this builds the target in a temporary
directory, installs it with `amp skill add`, verifies exact JSON discovery of
all 51 skills plus bundled resource bytes and executable modes, removes every
skill with `amp skill remove`, and confirms a fresh `amp skill list` no longer
discovers them from any location. Temporary home, XDG, settings, and log paths
isolate normal user configuration. Update checks and tracing are disabled; an
unreachable loopback service URL makes unexpected API requests fail closed.

## Further reading

- [Amp Agent Skills documentation](https://ampcode.com/manual#agent-skills)
- [Full Claude Code plugin README](../README.md)
