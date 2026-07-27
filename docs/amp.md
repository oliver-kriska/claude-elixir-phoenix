# Use the Elixir/Phoenix Skills with Amp

The Amp edition brings the plugin's Elixir, Phoenix, LiveView, Ecto, Oban,
testing, security, and workflow knowledge to Amp as standard Agent Skills. Two
generated Amp plugins accompany them: `elixir-phoenix.ts` adds deterministic
command-palette invocation, five enforced read-only domain specialists, bounded
parallel review/investigation, and native edit/verification guards;
`phx-watch-pr.ts` adds the keep-alive and durable event lifecycle required by
`phx-watch-pr`. All are generated projections of the full Claude Code plugin—not
second hand-maintained implementations.

The canonical source remains `plugins/elixir-phoenix/`. Amp-specific naming and
path constraints never flow back into the Claude Code plugin, so both targets
can evolve without weakening Claude Code support.

Installable artifacts are promoted only after validation in the standalone
[`amp-elixir-phoenix`](https://github.com/oliver-kriska/amp-elixir-phoenix)
distribution repository. The commands below use its gated `stable` branch.

See the [runtime support matrix](runtime-support.md) for a concise comparison
with Claude Code, Codex, Pi, and OpenCode.

## What you get

- All 51 skills and their complete bundled resources.
- 40 public workflow commands plus five native plugin commands in Amp's palette.
- Five focused Elixir, Ecto, LiveView, security, and testing child agents with
  only `Read` and `finder` tools.
- Parallel review and investigation tools with fixed fan-out, local child
  threads, partial-failure handling, and parent-thread synthesis.
- A persistent workspace edit lock and a bounded `phx-full` verification gate.
- Amp-compatible names and frontmatter.
- Rewritten cross-skill links and resource paths.
- An Amp-native `phx-watch-pr` lifecycle plugin with bounded Orb keep-alive,
  durable state, required-check filtering, and serialized same-thread fix
  events for actionable review feedback and required CI failures.
- Project-local and user-wide installation options.
- Compatibility with project-specific skills already in `.claude/skills/`.

The Amp edition ports five of the canonical 26 custom agents. It does not
install the other 21 agents, Claude Code hooks or permission settings, or MCP
configuration. See [Feature compatibility](#feature-compatibility) before
relying on a workflow or administration skill.

## Requirements

1. Install [Amp](https://ampcode.com/).
2. Run the installation from the Elixir/Phoenix project where Amp will work.

The child agents default to `anthropic/claude-haiku-4-5-20251001` for bounded,
lower-cost specialist work. Confirm that model is available with
`amp plugins show-agent-options`; [choose another model](#choose-the-specialist-model)
when necessary.

## Install in one project (recommended)

Project-local installation keeps this opinionated guidance scoped to an
Elixir/Phoenix repository. From the project that should use the skills:

```bash
amp skill add \
  https://github.com/oliver-kriska/amp-elixir-phoenix/tree/stable/skills \
  --target "$PWD/.agents/skills"

mkdir -p .amp/plugins
plugin=".amp/plugins/elixir-phoenix.ts"
temporary="$(mktemp "${plugin}.XXXXXX")"
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/oliver-kriska/amp-elixir-phoenix/stable/plugins/elixir-phoenix.ts \
  --output "$temporary" && mv "$temporary" "$plugin"
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
skills from `.agents/skills/`. The workspace plugin is installed under
`.amp/plugins/`; choose independently whether to commit it.

### Install the PR lifecycle plugin

The standard skills work without a plugin. `phx-watch-pr` requires its generated
Amp plugin because only the Plugin API can hold an Orb keep-alive lease and wake
the same thread after inactivity:

```bash
amp plugins add \
  https://raw.githubusercontent.com/oliver-kriska/claude-elixir-phoenix/main/targets/amp/plugins/phx-watch-pr.ts \
  --target workspace
```

Start a fresh Amp process or run `plugins: reload`. Plugins execute code; audit
the generated TypeScript before installing it. The plugin never merges,
deploys, publishes, or changes repository webhooks.

## Install for every project

Use a global installation only if most of your Amp work is Elixir/Phoenix:

```bash
amp skill add \
  https://github.com/oliver-kriska/amp-elixir-phoenix/tree/stable/skills \
  --global

mkdir -p "$HOME/.config/amp/plugins"
plugin="$HOME/.config/amp/plugins/elixir-phoenix.ts"
temporary="$(mktemp "${plugin}.XXXXXX")"
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/oliver-kriska/amp-elixir-phoenix/stable/plugins/elixir-phoenix.ts \
  --output "$temporary" && mv "$temporary" "$plugin"
```

Amp installs global skills in `~/.config/agents/skills/` and system plugins in
`~/.config/amp/plugins/`.

## Verify the installation

Start a fresh Amp process from the target project after installing or updating
the skills:

```bash
cd /path/to/your-phoenix-project
amp skill list
amp plugins list
amp
```

`amp skill list` should show entries such as `phx-investigate`, `testing`, and
`tidewave-integration`. `amp plugins list` should include
`elixir-phoenix.ts`. For a project-local installation, the skill base
directories should resolve under the project's `.agents/skills/` directory.
`amp plugins list` should also show `phx-watch-pr` with the
`elixir_phoenix_watch_pr` tool.

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

### Invoke a workflow deterministically

The generated plugin exposes every public workflow in Amp's command palette:

1. Open the command palette with `Ctrl+O`.
2. Select `phx: investigate`, `phx: review`, or another generated entry.
3. Send the task in your next prompt.

The command arms that workflow for one turn in the current thread. Amp shows a
confirmation notification; on the next `agent.start`, the plugin reads the
installed `SKILL.md` directly and appends its full instructions as hidden
context. The pending workflow is consumed once. Run `phx: clear pending
workflow` to cancel it before submitting a prompt.

Command metadata and skill locations are fixed at generation time, so the
invocation path does not spawn `amp skill list`. This avoids dynamic discovery
latency and does not depend on the model deciding to select the workflow.

You can also name the skill in your prompt. This is convenient for reusable
prompts, handoffs, and non-interactive `amp -x` calls:

```text
Load phx-investigate and investigate this LiveView filter reset.
```

```text
Load phx-review, liveview-patterns, and testing. Review the current changes,
read the relevant bundled references, and report which skills you loaded.
```

The palette keeps the familiar command namespaces:

| Claude Code | Amp |
| --- | --- |
| `/phx:plan` | Palette: `phx: plan` |
| `/phx:investigate` | Palette: `phx: investigate` |
| `/ecto:n1-check` | Palette: `ecto: n1-check` |
| `/lv:assigns` | Palette: `lv: assigns` |
| `liveview-patterns` | Automatic selection or explicit prompt request |

For example, the familiar workflows translate as follows:

| Goal | Claude Code | Amp |
| --- | --- | --- |
| Review changes | `/phx:review` | Choose `phx: review`, then describe the review scope. |
| Investigate a bug | `/phx:investigate <bug>` | Choose `phx: investigate`, then send the bug details. |
| Check an Ecto N+1 | `/ecto:n1-check` | Choose `ecto: n1-check`, then send the query or scope. |

Typing only `investigate` as a normal prompt may cause Amp to choose
`phx-investigate`, but that remains model-driven. Use the generated palette
command when you need certainty.

## Run native specialists and parallel workflows

The generated plugin projects five canonical agents: Elixir, Ecto, LiveView,
security, and testing. Their prompt knowledge comes from
`plugins/elixir-phoenix/agents/`, but their Amp tool set is deliberately smaller:
only `Read` and `finder`. They cannot edit or create files, run shell commands,
or invoke more agents.

Choose `phx: specialist` to select one specialist, enter its task, and run it in
a local child thread. The result is returned to the current thread for evidence
checking and synthesis. If no thread exists yet, the command creates and shows a
medium-mode parent thread first.

Two commands guarantee bounded fan-out without depending on the main model to
choose a tool:

- `phx: parallel review` runs all five domain specialists concurrently.
- `phx: parallel investigate` runs four private read-only tracks concurrently:
  reproduction, root cause, impact, and fix strategy.

The `phx-review` and `phx-investigate` skills can also call
`elixir_phoenix_parallel_review` and
`elixir_phoenix_parallel_investigate` directly. Review may select only relevant
specialists to avoid unnecessary work. Fan-out is fixed at five or four child
threads, child runs have a five-minute timeout, and `Promise.allSettled` keeps a
single failed track from discarding successful results. The parent verifies and
deduplicates findings; failed concerns fall back to sequential analysis rather
than being respawned.

Child threads use Amp's `local` executor and are linked to the parent thread.
Starting the plugin does not run a model. A model is billed only when a
specialist command or tool actually runs, once per selected child plus the
normal parent synthesis turn.

### Choose the specialist model

The default child model is Claude Haiku 4.5. Override it for the Amp process
with any current public `provider/model` ID:

```bash
amp plugins show-agent-options

ELIXIR_PHOENIX_AMP_SPECIALIST_MODEL=openai/gpt-5-mini amp
```

Restart Amp or reload plugins after changing the environment. An invalid model
identifier falls back to the default; a syntactically valid but unavailable
model fails only that child run, and the parent receives the partial-failure
fallback instructions.

## Enforce an edit scope

Choose `phx: edit lock` to:

- freeze all recognized edits;
- allow edits only beneath comma- or newline-separated workspace-relative
  prefixes;
- inspect the current lock; or
- turn it off.

The lock is stored in Amp's workspace configuration and applies across threads
and plugin reloads until explicitly disabled. At `tool.call`, the plugin uses
Amp's native file-modification classifier to reject recognized edit, create,
patch, and in-place `sed` calls outside the allowed scope. It disables all shell
tools while locked because arbitrary shell commands cannot be proven read-only.

This is real enforcement for the tool calls Amp can classify, but it is not a
claim of complete Claude-hook parity. Unknown third-party tools that mutate the
workspace without reporting files through Amp's helper cannot be classified.
The generated `phx-freeze` skill therefore remains an advisory workflow; use
`phx: edit lock` when native enforcement is required.

## Guard full-workflow verification

When `phx: full` is explicitly armed, the plugin tracks Amp-recognized edits and
successful Elixir verification shell results in that thread. If the turn stops
after an edit without a verified zero-exit format check (`mix format
--check-formatted`), compile, test, Credo, Dialyzer, audit, or repository
verification command, `agent.end` starts one bounded follow-up asking the agent
to verify. The command must be the shell invocation itself; piped, chained, or
neutralized commands do not satisfy the gate. A second incomplete stop is
reported to the user instead of looping, and a no-edit lifecycle expires after
eight turns.

This guard enforces only the observable verification boundary. Plan approval,
review quality, compounding, arbitrary shell side effects, and unknown custom
tools still rely on the portable `phx-full` state machine and user review.

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
latest validated skills from `stable`:

```bash
cd /path/to/your-phoenix-project
amp skill add \
  https://github.com/oliver-kriska/amp-elixir-phoenix/tree/stable/skills \
  --target "$PWD/.agents/skills" \
  --overwrite
```

For a global update:

```bash
amp skill add \
  https://github.com/oliver-kriska/amp-elixir-phoenix/tree/stable/skills \
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

Amp currently restricts `amp plugins add` and directive-based auto-updates to
Amp-hosted plugins. Update this GitHub-hosted plugin by downloading the current
validated file again, or remove it with Amp:

```bash
# Update the workspace plugin atomically
plugin=".amp/plugins/elixir-phoenix.ts"
temporary="$(mktemp "${plugin}.XXXXXX")"
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/oliver-kriska/amp-elixir-phoenix/stable/plugins/elixir-phoenix.ts \
  --output "$temporary" && mv "$temporary" "$plugin"

# Remove the workspace-scoped installation
amp plugins remove elixir-phoenix.ts --target workspace
```

## Feature compatibility

| Capability | Claude Code plugin | Amp edition |
| --- | --- | --- |
| 51 skills and bundled resources | Full | Full |
| Domain knowledge and Iron Laws | Full | Full |
| Automatic skill selection | Supported | Supported, model-driven |
| Explicit workflow loading | Slash command | 45 generated palette commands plus `skill: invoke` |
| 26 named custom subagents | Full | Five focused read-only agents |
| Parallel workflow orchestration | Full | Review/investigate child threads plus sequential fallback |
| Lifecycle and enforcement hooks | Full | Edit lock, bounded `phx-full` verification gate, and `phx-watch-pr` keep-alive |
| Claude permission settings | Full | Not installed |
| Tidewave MCP connection | User-configured | User-configured |

Domain and reference skills such as `liveview-patterns`, `ecto-patterns`,
`testing`, and `security` work directly. The flagship `phx-investigate`,
`phx-review`, `phx-plan`, `phx-work`, `phx-pr-review`, and `phx-full` workflows,
plus `phx-trace`, `phx-audit`, and `phx-research`, are adapted to use native
capabilities with complete same-session fallbacks. They do not require named
Claude subagents, task APIs, hooks, or MCP tools. Other generated workflow
skills may still retain Claude-specific orchestration as reference guidance
unless the compatibility table says otherwise.

The generated `phx-freeze` skill is adapted to a current-session advisory scope
and does not write `.claude/.freeze`. The separate `phx: edit lock` command
enforces only the file edits Amp can classify and blocks shell while active; it
does not claim universal hook enforcement.

These remaining workflow and administration skills are primarily reference
material in Amp:

| Skill | Claude-specific dependency |
| --- | --- |
| `phx-perf` | Describes Claude specialist agents; run the quoted tracks directly or with generic Amp workers. |
| `phx-learn-from-fix` | Targets Claude-specific personal skill and memory locations. |
| `phx-permissions` | Manages Claude permission settings. |
| `phx-init` | Installs Claude-specific project instructions. |

`phx-watch-pr` is adapted through its focused plugin. It acquires
`amp.system.executor.keepAlive()`, polls required checks and unresolved review
threads without model turns, and persists state in workspace Amp configuration.
Deployment, release, preview, production, and prod checks are reported
separately and never determine readiness.

Defaults are 60-second polling, a 15-minute activity-based quiet period after
readiness, and a 2-hour active-watch maximum. The quiet period intentionally
covers delayed reviews that have no dedicated check and exceeds Amp's normal
five-minute inactivity pause, at the cost of up to fifteen additional Orb
minutes after the last relevant activity. The two-hour cap covers normal
pipelines while bounding HIGH-worker billing; each watch may configure 30–300
seconds, 5–60 minutes, and 0.5–24 hours respectively. Timeout is incomplete and
always releases the lease.

The first green snapshot is not immediate success. A new current-head SHA,
required-check transition, unresolved-thread change, top-level PR comment, or
submitted review restarts the quiet clock. This covers account-level automated
reviews that may publish several minutes after CI starts and may be silent when
they find nothing. Routine pending/pass progress and non-actionable review
activity do not wake model inference. Deployment-like activity remains
excluded, does not delay readiness, and stays silent while remaining visible in
explicit status and terminal summaries.

Failed/cancelled required non-deployment checks and unresolved review threads
are actionable. Each distinct actionable snapshot wakes the worker once. With
`--fix`, it appends one serialized event to the same worker thread and directs
it to the installed `phx-pr-review` workflow with check names, links, and review
evidence. The worker validates comments and logs, fixes only valid branch-owned
causes, verifies, pushes the authorized PR branch update, replies, and resolves
where appropriate. It never blindly reruns shared CI, merges, or deploys.

The plugin also registers an optional durable Amp webhook and writes its bearer
URL to an owner-only file under `~/.config/amp/phx-watch-pr/`. A repository
administrator may configure GitHub to send check and review events there; the
plugin itself never performs that shared change. Without external webhook
configuration, polling stops after the quiet period and a later human comment
cannot wake a paused Orb. Forwarded events must identify the exact watched PR
number or current watched head SHA; empty and unrelated repository events do
not acquire a lease or schedule a poll.

The generated files mark unsupported Claude hook paths explicitly and contain
no unresolved `${CLAUDE_SKILL_DIR}` or `${CLAUDE_PLUGIN_ROOT}` variables.
The plugin injects a skill's Markdown instructions; it does not emulate native
activation of skill-bundled MCP configuration. The current generated skills do
not ship such configuration, and Tidewave registration remains external.

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
description. Open the command palette, choose the generated workflow command,
and then send the task. For non-interactive use, name the skill explicitly and
ask Amp to report the loaded base directory.

### `/phx:review` does not run in Amp

This is expected. Amp uses a command palette rather than user-defined prompt
slash commands. Press `Ctrl+O`, choose `phx: review`, then send the review
scope. The installed workflow is the same generated skill; only the invocation
surface differs.

### The workflow command is missing

Run `amp plugins list` and confirm `elixir-phoenix.ts` is installed at the
intended workspace or system scope. Start a fresh Amp process after installing
the plugin. Skills alone provide model-driven selection; deterministic palette
entries require the generated plugin.

### A specialist child fails before returning findings

Run `amp plugins show-agent-options` and confirm the configured child model is
available. Remove or correct `ELIXIR_PHOENIX_AMP_SPECIALIST_MODEL`, then restart
Amp. Parallel results preserve successful children and tell the parent to cover
only failed concerns sequentially.

### The edit lock blocks a verification command

This is intentional: arbitrary shell commands cannot be proven read-only. Use
`phx: edit lock` to inspect or turn off the persistent workspace lock, run
verification, then re-enable the lock if the task still needs it.

### A workflow mentions Claude-only tools

The adapted workflows should not require Claude-only tools. If one does,
report generated-target drift and reinstall the current release. For other
workflow or administration skills, treat those steps as reference guidance and
ask Amp to adapt them using Amp-native tools. Do not assume that unported Claude
hooks, agents, or permission enforcement are active merely because a skill is
installed.

## Delivery roadmap

All four planned phases are implemented with stable Amp APIs:

1. **Deterministic workflows:** 51 skills and 45 palette commands, one-turn
   workflow arming, hidden installed-skill injection, drift checks, and runtime
   loading.
2. **Specialist agents:** five canonical domain prompts projected into custom
   Amp agents with an enforced `Read`/`finder` tool boundary.
3. **Parallel orchestration:** bounded local review and deep-investigation
   fan-out, lower-cost configurable child models, parent-linked threads,
   `Promise.allSettled` fan-in, and sequential partial-failure fallback.
4. **Safe lifecycle behavior:** a persistent classified-edit lock and one
   bounded `phx-full` verification continuation after observable edits.

The remaining gaps are explicit product boundaries, not unfinished phases:
Amp cannot classify arbitrary third-party mutating tools, and this plugin does
not port all 26 Claude agents, Claude's complete hook graph, permission files,
or project-specific MCP registration.

## Maintain the generated target

Never edit `targets/amp` manually. Change the canonical Claude skill, the Amp
generator, or the Amp source under `plugins/elixir-phoenix/amp/`, then
regenerate and verify the complete target with one command:

```bash
make amp-target-sync
git add targets/amp
```

`make amp-target` is available when generation without a follow-up drift check
is useful; `make amp-target-validate` is the read-only check used by hooks and
CI. The older `amp-skills*` target names remain as compatible aliases.

The Husky pre-commit hook runs `make amp-target-validate` only when files under
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
5. generates command IDs, categories, descriptions, argument hints, and direct
   skill paths from canonical frontmatter;
6. projects five validated canonical agents into read-only Amp prompts and
   generates the parallel tools, edit lock, and verification guard;
7. replaces the target only after the staged build passes, with rollback if the
   final replacement fails;
8. supports the read-only drift check used by CI.

The canonical Claude plugin remains independently verifiable:

```bash
make validate
make eval-all
```

Maintainers with Amp installed can run a model-free native acceptance check:

```bash
make amp-runtime-smoke
```

The acceptance run builds the target in a temporary directory, loads both
generated plugins through the current Amp runtime, installs the skills with
`amp skill add`, verifies exact JSON discovery of all 51 skills plus bundled
resource bytes and executable modes, removes every skill with
`amp skill remove`, and confirms a fresh `amp skill list` no longer discovers
them from any location. It loads all agent/tool/lifecycle registrations but does
not invoke a model. Temporary home, XDG, settings, and log paths isolate normal
user configuration. Update checks and tracing are disabled; an unreachable
loopback service URL makes unexpected API requests fail closed.

## Further reading

- [Amp Agent Skills documentation](https://ampcode.com/manual#agent-skills)
- [Full Claude Code plugin README](../README.md)
