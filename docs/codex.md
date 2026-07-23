# Codex Skills Plugin

The Codex edition is a generated native plugin containing all 51 canonical
Elixir/Phoenix skills and their complete resource trees. It was tested with
`codex-cli 0.145.0`.

This is a skills-first baseline, not full Claude Code feature parity. The generator
normalizes names (`phx:review` → `phx-review`), rewrites cross-skill and resource
paths, converts Claude command references to Codex `$skill-name` syntax, and
applies Codex-only workflow overlays without changing canonical Claude files.
It also projects one synchronous native safety hook from the canonical plugin.
It projects descriptions to at most 120 characters while preserving key
capability and trigger cues. Route-sensitive skills retain explicit exclusions
to avoid collisions. This reduces pressure on Codex's shared skills catalog
budget without changing canonical descriptions or skill bodies.

## Install from GitHub

Marketplace registration and plugin installation are separate operations:

```bash
# 1. Fetch and register this repository's marketplace snapshot
codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --ref main

# 2. Install and enable the plugin from that snapshot
codex plugin add elixir-phoenix@oliver-kriska

# 3. Verify the installed/enabled state
codex plugin list
codex plugin list --json
```

Start a fresh Codex session after installation. The marketplace entry resolves
`./targets/codex` inside the fetched Git snapshot, so branch and pull-request
testing uses the target committed on the requested ref rather than silently
falling back to `main`.

To test a feature branch before merge:

```bash
codex plugin remove elixir-phoenix@oliver-kriska 2>/dev/null || true
codex plugin marketplace remove oliver-kriska 2>/dev/null || true
codex plugin marketplace add \
  oliver-kriska/claude-elixir-phoenix \
  --ref feat/codex-skills-plugin
codex plugin add elixir-phoenix@oliver-kriska
```

## Use Skills

Invoke a skill explicitly by mentioning its generated name:

```text
$elixir-phoenix:phx-investigate FunctionClauseError after saving the profile form
$elixir-phoenix:phx-review
$elixir-phoenix:ecto-n1-check Accounts
$elixir-phoenix:lv-assigns UserDashboardLive
```

Codex namespaces plugin-owned skills with the plugin manifest name. There are no
automatic unqualified aliases, so `$phx-investigate` alone does not explicitly
load this plugin's skill. Selecting a skill through `/skills` inserts the fully
qualified name automatically.

Use `/skills` in an interactive Codex session to open the skill selector and
manage individual skills. Codex can also select a skill implicitly when the user
request matches its generated description; explicit `$skill-name` invocation is
preferred when a specific workflow is required. For plugin skills, the complete
name is `$plugin-name:skill-name`.

Codex allocates a shared model-context budget to enabled skills. Large combined
catalogs may still produce a description-shortening warning, especially when
several plugins or project skills are enabled. The generated descriptions are
kept compact to preserve routing signal, while explicit invocation always loads
the complete `SKILL.md`. Disable unused skills or plugins if the warning remains.

### Flagship workflow behavior

`$elixir-phoenix:phx-investigate` preserves reproduce-before-fix and
root-cause-first analysis.
It uses Tidewave when available but falls back to local files, logs, tests, and
`mix` commands. Native Codex subagents are optional; the same tracks can run
sequentially without named custom agents.

`$elixir-phoenix:phx-review` is read-only, scopes findings to changed files,
checks available requirements, cites file/line evidence, assigns severity,
deduplicates findings, and returns a verdict. It may use native Codex subagents
for independent tracks, but a sequential same-session review is fully supported.

`$elixir-phoenix:phx-plan` and `$elixir-phoenix:phx-work` also have focused
portable adaptations. Planning tracks research in the plan scratchpad and
preserves the canonical `.claude/plans/{slug}/plan.md` schema. Work uses plan
checkboxes plus `progress.md` for ordered, resumable execution and verification.
Generic native subagents and Tidewave remain optional; the same-session
sequential path is complete. These adaptations do not require hooks or a separate
task UI.

`$elixir-phoenix:phx-pr-review` uses an available GitHub connector or
authenticated `gh`, keeps triage read-only unless fixes are explicitly approved,
and reports mutations only after confirmed replies/resolutions.
`$elixir-phoenix:phx-full` preserves the gated, bounded plan → work → verify →
read-only review → compound lifecycle by invoking portable skills or executing
them sequentially in-session. Other workflows remain baseline projections and
may not be fully portable.

## Optional Native Safety Hook

The generated plugin includes one synchronous `PreToolUse` command hook for
Codex's `Bash` tool. It blocks:

- `mix ecto.reset` and `mix ecto.drop` in Elixir projects;
- unguarded `git push --force` / `git push -f` while allowing
  `--force-with-lease`;
- accidental `MIX_ENV=prod mix ...` commands in Elixir projects.

Codex discovers plugin hooks but does not silently trust them. Review and enable
the hook through `/hooks`; if it is untrusted, disabled, or disallowed by policy,
all skills still work. Plugin updates that change the hook may require another
trust review. Do not use `--dangerously-bypass-hook-trust` for normal sessions.

Only this audited synchronous safeguard is projected. The canonical Claude hook
file contains runtime-specific conditions, events, and asynchronous handlers
that are intentionally not copied. Codex 0.145.0 skips general async hooks;
Claude-only fields and events are omitted rather than relied upon.

## Update

Codex does not currently expose a separate plugin-update command. Refresh the
Git marketplace, reinstall the plugin, and start a fresh session:

```bash
codex plugin marketplace upgrade oliver-kriska
codex plugin add elixir-phoenix@oliver-kriska
codex plugin list --json
```

For a clean reinstall:

```bash
codex plugin remove elixir-phoenix@oliver-kriska
codex plugin marketplace upgrade oliver-kriska
codex plugin add elixir-phoenix@oliver-kriska
```

## Uninstall

Remove the plugin, then optionally remove the marketplace source:

```bash
codex plugin remove elixir-phoenix@oliver-kriska
codex plugin marketplace remove oliver-kriska
```

## Project and Global Scope

An installed plugin is enabled for the active `CODEX_HOME`, so its skill metadata
is available across projects using that home. The skills remain most relevant in
Elixir/Phoenix repositories; implicit selection is model-driven.

For isolated or project-specific testing, use a dedicated home. Set both
`CODEX_HOME` and `HOME` because the personal marketplace is discovered through
`HOME` separately from Codex's plugin cache:

```bash
export CODEX_TEST_ROOT="$(mktemp -d)"
export CODEX_HOME="$CODEX_TEST_ROOT/codex"
export HOME="$CODEX_TEST_ROOT/home"
mkdir -p "$CODEX_HOME" "$HOME"
codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --ref main
codex plugin add elixir-phoenix@oliver-kriska
```

This does not alter the normal `~/.codex` installation.

## Supported and Deferred Capabilities

Supported now:

- all 51 current canonical skills;
- complete skill subtrees, including Markdown outside `references/`;
- byte-identical non-Markdown resources and preserved executable modes;
- native plugin installation, `/skills`, explicit `$skill-name`, and implicit
  skill selection;
- Codex-specific `$elixir-phoenix:phx-investigate` and
  `$elixir-phoenix:phx-review`, `$elixir-phoenix:phx-plan`, and
  `$elixir-phoenix:phx-work`, `$elixir-phoenix:phx-pr-review`, and
  `$elixir-phoenix:phx-full` workflow adaptations.
- compact discovery descriptions generated from canonical capability and trigger
  text to reduce shared skills-context pressure.
- an optional, trust-gated native safety hook for destructive shell commands.

Intentionally deferred:

- the remaining Claude Code hooks, including async and unsupported events;
- generated or automatically installed custom-agent TOMLs;
- bundled Tidewave MCP configuration;
- plugin-root `AGENTS.md` or copied `CLAUDE.md` instructions;
- exact Claude slash-command syntax such as `/phx:review`.

Some non-flagship skills still describe richer Claude Code orchestration APIs.
They are packaged for domain guidance and progressive migration, but the plugin
does not claim complete workflow parity until those paths receive focused Codex
adaptations.

## Troubleshooting

### Marketplace is present but the plugin is absent

`codex plugin marketplace add` only registers/materializes the marketplace. Run:

```bash
codex plugin add elixir-phoenix@oliver-kriska
codex plugin list --json
```

The list entry should report the plugin as installed and enabled.

### Skills do not appear

Start a new Codex session after install/reinstall. In the TUI, use `/skills` and
search for `phx-review`. If the marketplace cache is stale, use the clean
reinstall sequence above.

### The safety hook does not run

Open `/hooks` in a fresh Codex session and review the plugin hook's trust state.
The hook is optional and may remain disabled under user or enterprise policy.
If Codex reports skipped async hooks or invalid hook output, remove stale older
plugin experiments and clean-reinstall this generated plugin; its hook config has
no async handler or Claude-only `if` field.

### A branch install appears to use `main`

Remove the marketplace and add it again with the desired `--ref`, then reinstall:

```bash
codex plugin remove elixir-phoenix@oliver-kriska
codex plugin marketplace remove oliver-kriska
codex plugin marketplace add \
  oliver-kriska/claude-elixir-phoenix \
  --ref your-branch
codex plugin add elixir-phoenix@oliver-kriska
```

## Generated Target Maintenance

Canonical skill sources live in `plugins/elixir-phoenix/skills`; the native
safeguard comes from `plugins/elixir-phoenix/hooks/scripts/block-dangerous-ops.sh`.
Do not hand-edit `targets/codex`.

```bash
make codex-skills           # regenerate targets/codex
make codex-skills-validate  # read-only drift check
make codex-skills-sync      # regenerate, then validate
make codex-runtime-smoke    # optional isolated native runtime acceptance
```

The smoke target generates from the current checkout into a temporary local
marketplace, installs and enables it through `codex plugin`, checks the installed
51-skill tree and a packaged executable resource byte-for-byte and mode-for-mode,
removes it, and checks again in a fresh process. It sets temporary `HOME` and
`CODEX_HOME`, never copies authentication, and performs no model or
network-dependent prompt. Codex does not expose a stable structured command for
enumerating every plugin skill, so the exact count is an installed-tree check;
`plugin list --json` verifies the native installed and enabled state.

Generation stages and validates a complete replacement before swapping it into
place, with rollback on installation failure. Drift checking compares paths,
types, bytes, and mode bits, and reports additions, removals, content changes,
and mode-only changes. CI runs the drift check without changing the existing Amp
validation.
