# Runtime support

Claude Code is the canonical implementation of this plugin. Amp, Codex, Pi,
and OpenCode receive deterministic projections of the same 51 canonical skills.
Those projections preserve skill resources and executable files, but they do
not imply that every runtime implements Claude Code's hooks, agents, commands,
or MCP integration.

Use this page to choose a runtime, identify the native invocation syntax, and
understand which capabilities are deliberately deferred. Runtime-specific
installation and troubleshooting remain in the linked guides.

## Support levels

- **Full**: maintained as a native part of the canonical Claude Code plugin.
- **Generated**: generated and drift-checked from the canonical skills, with
  runtime-specific syntax and focused workflow adaptations.
- **External**: the runtime may provide the capability, but this package does
  not configure or install it.
- **Deferred**: intentionally excluded until it has a safe, native design and
  runtime acceptance coverage.
- **Not applicable**: the runtime uses a different interaction model.

## Capability matrix

| Capability | Claude Code | Amp | Codex | Pi | OpenCode | dsh |
| --- | --- | --- | --- | --- | --- | --- |
| 51 canonical skills | Full | Generated | Generated | Generated | Generated | Generated |
| Complete skill resource trees | Full | Generated | Generated | Generated | Generated | Generated |
| Executable resource modes | Full | Preserved | Preserved | Preserved | Preserved | Preserved |
| Automatic skill selection | Full | Model-driven | Model-driven | Model-driven | Model-driven | Model-driven |
| Flagship `phx-investigate` | Full | Adapted | Adapted | Adapted | Adapted | Adapted |
| Flagship read-only `phx-review` | Full | Adapted | Adapted | Adapted | Adapted | Adapted |
| `phx-plan` / `phx-work` | Full | Adapted | Adapted | Adapted | Adapted | Adapted |
| `phx-pr-review` / `phx-full` | Full | Adapted | Adapted | Adapted | Adapted | Adapted |
| `phx-trace` | Full | Adapted | Adapted | Adapted | Adapted | Adapted |
| `phx-audit` / `phx-research` | Full | Adapted | Adapted | Adapted | Adapted | Adapted |
| `phx-watch-pr` | Background monitor | Native keep-alive plugin | Guidance/baseline | Guidance/baseline | Guidance/baseline | Guidance/baseline |
| `phx-freeze` | Hook-enforced advisory lock | Advisory skill + native classified edit lock | Advisory only | Advisory only | Advisory only | Advisory only |
| Remaining workflow/admin skills | Full | Guidance/baseline | Guidance/baseline | Guidance/baseline | Guidance/baseline | Guidance/baseline |
| Claude namespaced slash commands | Full | Not applicable | Not applicable | Not applicable | Not applicable | Not applicable |
| Deterministic workflow invocation | Slash commands | Native `skill: invoke`; 40 wrappers when paired locally | Skill reference | `/skill:*` | Skill tool | `/phx-*` token or skill tool |
| Bundled custom agents | Full | Five read-only specialists | Deferred | Deferred | Deferred | Not applicable |
| Lifecycle/enforcement hooks | Full | Edit lock; bounded verification gate only through paired `phx: full` | One optional safeguard | Deferred | Deferred | Deferred |
| Tidewave MCP connection | External | External | External | External | External | External |
| Plugin-root instructions | Full | Deferred | Deferred | Deferred | Deferred | Native `CLAUDE.md` read |
| Deterministic generated target | Canonical source | Yes | Yes | Yes | Yes | Yes |
| Mode-aware CI drift validation | Not applicable | Yes | Yes | Yes | Yes | Yes |
| Golden target snapshot | Not applicable | Yes | Yes | Yes | Yes | Yes |
| Isolated native smoke command | Not applicable | Yes | Yes | Yes | Yes | No runtime introspection API |

“External” Tidewave support means a skill may use Tidewave when the project and
runtime already expose it. Installing Tidewave in a Phoenix app starts the MCP
server but does not register its project-specific URL with any client. Adapted
workflows in every generated target must still complete without
Tidewave, named custom agents, or Claude-only task APIs.

## Native invocation and installation

| Runtime | Reliable explicit invocation | Distribution | Guide |
| --- | --- | --- | --- |
| Claude Code | `/phx:investigate`, `/phx:review` | Claude plugin marketplace | [Claude Code installation](../README.md#claude-code) |
| Amp | Native `skill: invoke`; paired-full also provides `phx: investigate` and `phx: review` | Personal/workspace hosted repositories or direct GitHub/curl | [Amp guide](amp.md) |
| Codex | `$elixir-phoenix:phx-investigate`, `$elixir-phoenix:phx-review` | Native Codex Git marketplace plugin | [Codex guide](codex.md) |
| Pi | `/skill:phx-investigate`, `/skill:phx-review` | Native Pi Git package | [Pi guide](pi.md) |
| OpenCode | Ask the skill tool to load the skill; in the tested 1.17.2 setup, `/phx-investigate` and `/phx-review` also work | Sparse Git checkout | [OpenCode guide](opencode.md) |
| dsh | `/phx-investigate`, `/phx-review` (host-injected), or the skill tool | Sparse Git checkout into a scanned skill root | [dsh guide](dsh.md) |

Codex plugin skills are qualified by the plugin manifest name. OpenCode 1.17.2
does not provide a native Git skills-package installer, so a sparse checkout is
the supported installation and update mechanism. Start a fresh process after
installing, updating, or removing skills because runtime discovery may be
cached when a session starts.

Amp's **hosted-native** profile publishes skills and plugin independently to
personal or workspace hosted repositories and uses native `skill: invoke`.
Specialists, parallel commands, and edit lock do not need filesystem skill
resolution. The 40 wrappers cannot resolve hosted-only skills, and native
`phx-full` does not activate the plugin gate. **Paired-full** installs matching
skills and plugin at supported local roots, preserving all wrappers and the
wrapper-activated gate. `amp skill add --global` is machine-local, not personal
hosted/account-wide. The standalone repository, green-only mutable `stable`
branch, generated target, paired install, and GitHub/curl fallback are retained.

The same lifecycle boundary applies to every generated runtime: install,
update, clean reinstall, ref change, and uninstall affect newly started
processes. Standalone list/debug commands are already fresh processes; they do
not refresh the catalog of an existing interactive session.

The latest Amp acceptance run recorded on 2026-07-26 used
0.0.1785055505-g9690ae. The cross-runtime acceptance baseline recorded on
2026-07-23 used Codex CLI 0.145.0, Pi 0.81.1, and OpenCode 1.17.2.

## Runtime-specific boundaries

### Claude Code

`plugins/elixir-phoenix/` is the source of truth and retains the complete
plugin: skills, commands, agents, hooks, root instructions, permission settings,
and Tidewave-aware workflows. Users register the Tidewave MCP endpoint for each
project and port. Portability fixes must not weaken this behavior.

### Amp

Amp installs `targets/amp/skills` as standard Agent Skills and
`targets/amp/plugins/elixir-phoenix.ts` as a native command-palette plugin. The
plugin exposes all 40 public workflows plus clear, specialist, parallel review,
parallel investigation, and edit-lock commands. Native `skill: invoke` resolves
local, built-in, personal hosted, and workspace hosted skills after Amp's full
precedence. Filesystem wrappers inject a matching supported local skill once on
`agent.start`; the Plugin API cannot resolve or invoke hosted skills and does
not expose Amp's original nested invocation path. The plugin projects five
canonical agents with only `Read`/`finder` and provides bounded local
review/investigation fan-out. Its workspace edit lock enforces Amp-classified
file changes and blocks shell while active. Only the paired `phx: full` wrapper
arms the bounded verification follow-up; native invocation loads the skill's
instructions but not the plugin gate. The generated target does not install the
other 21 Claude agents, complete Claude hook graph, permissions, or MCP
configuration. A second plugin, `targets/amp/plugins/phx-watch-pr.ts`, adds a
bounded keep-alive lease, durable polling state, and same-thread event delivery
for PR watching.

### Codex

Codex installs `targets/codex` as a native plugin. `/skills` opens the selector,
and explicit skill references use the `elixir-phoenix:` plugin namespace.
Plugin-root agent definitions and `AGENTS.md` are not automatically activated.
The plugin includes one optional, synchronous, trust-gated safeguard for
destructive shell commands. The remaining Claude hooks, generated agent TOMLs,
and plugin-root instructions are separate future capabilities rather than
hidden installation side effects. Tidewave MCP registration remains external.

### Pi

Pi consumes `targets/pi/skills` through the repository's Pi package declaration.
Generated references use native `/skill:<name>` syntax. Extensions, prompt
templates, custom-agent orchestration, package-root instructions, and bundled
MCP configuration are not installed. Tidewave remains optional when exposed by
the host independently.

### OpenCode

OpenCode recursively discovers `SKILL.md` files in the installed
`targets/opencode` tree. The generated package does not install hooks, custom
agents, separate commands, MCP servers, root instructions, or configuration.
Use `opencode debug skill --pure` for deterministic discovery diagnostics.

### dsh

DeepSeek Harness discovers `targets/dsh/skills` through its filesystem skill
provider, which scans `<projectRoot>/.dsh/skills`, `<projectRoot>/.agents/skills`,
`customSkillDirs`, `$DSH_HOME/skills`, and `$DSH_AGENTS_HOME/skills`. Discovery
is deliberately **one level deep**, so the target is installed by pointing
`customSkillDirs` at the generated `skills/` directory or by copying its contents
into a scanned root — a nested checkout is invisible.

A whitespace-bounded `/phx-*` token naming a user-invocable skill is recognized
by the host pre-step boundary anywhere in a user message and injects the rendered
skill body deterministically, which is the closest equivalent to a Claude Code
slash command. dsh reads `CLAUDE.md` natively (its instruction candidates default
to `['AGENTS.md', 'CLAUDE.md']`), so `/phx:init` output needs no porting.

The generated target does not install hooks, custom agents, separate commands,
MCP servers, or configuration. Custom agents are *not applicable* rather than
deferred: dsh has no markdown agent registry, only a persona string on its
`subagent` tool. The Claude Code hook bridge covers 7 of 30 events and drops
`if:` gating, so no hook port ships. dsh exposes no scriptable skill
introspection, so this target has no smoke harness.

## Acceptance contract for generated runtimes

Every generated target must pass repository tests that prove:

1. every canonical skill has one valid, uniquely named generated skill;
2. complete resource subtrees are represented;
3. non-Markdown bytes and executable mode bits are preserved;
4. generated references use complete native command tokens;
5. repeated generation produces identical paths, bytes, and modes;
6. failed generation preserves the previous target;
7. read-only drift checks detect additions, removals, content changes, node-type
   changes, and mode-only changes; and
8. generation does not mutate canonical sources or another runtime target.

The optional Amp, Codex, Pi, and OpenCode smoke harnesses additionally verify native
installation or discovery, all 51 skills, retained resources and executable
modes, removal behavior, and fresh-process rediscovery. Behavioral acceptance
uses controlled fixtures and requires `phx-investigate` to reproduce before
identifying a planted root cause and `phx-review` to find a planted defect
without modifying the fixture.

### Isolation rules

Runtime smoke tests must not read, overwrite, or remove a developer's normal
configuration. Use temporary homes and start a fresh runtime process for each
discovery boundary.

For Amp, isolate `HOME`, all XDG roots, `AMP_SETTINGS_FILE`, and `AMP_LOG_FILE`.
The smoke harness disables update checks and tracing, supplies a placeholder API
key, and uses only local `amp skill` commands. An unreachable loopback `AMP_URL`
makes any unexpected Amp API request fail closed without using normal credentials.

For Codex, isolate both locations because marketplace metadata and the plugin
cache use separate roots:

```bash
export TEST_ROOT="$(mktemp -d)"
export HOME="$TEST_ROOT/home"
export CODEX_HOME="$TEST_ROOT/codex"
mkdir -p "$HOME" "$CODEX_HOME"
```

Do not pass `--ignore-user-config` when testing Codex plugin hooks: that option
suppresses the installed plugin hooks as well as unrelated user configuration.
An isolated `HOME` and `CODEX_HOME` provide the required separation without
disabling the behavior under test.

For Pi, isolate `HOME`, `PI_CODING_AGENT_DIR`, and
`PI_CODING_AGENT_SESSION_DIR`; remove inherited `PI_PACKAGE_DIR`. Set
`PI_OFFLINE=1`, `PI_SKIP_VERSION_CHECK=1`, and `PI_TELEMETRY=0` to keep package
discovery model-free and offline.

For OpenCode, isolate every XDG root in addition to `HOME`:

```bash
export TEST_ROOT="$(mktemp -d)"
export HOME="$TEST_ROOT/home"
export XDG_CONFIG_HOME="$TEST_ROOT/config"
export XDG_DATA_HOME="$TEST_ROOT/data"
export XDG_CACHE_HOME="$TEST_ROOT/cache"
export XDG_STATE_HOME="$TEST_ROOT/state"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" \
  "$XDG_CACHE_HOME" "$XDG_STATE_HOME"
```

Model-, network-, or credential-dependent behavioral probes are optional local
acceptance checks, not mandatory CI. Deterministic generation, drift, manifest,
resource, and mode checks remain the hermetic CI gate.

## Maintainer commands

Never hand-edit a generated target. Change the canonical skill or the relevant
runtime generator. To regenerate all four targets and validate their reviewed
golden snapshots, run:

```bash
make generated-skills-sync
```

Target-specific commands remain available for focused work:

```bash
make amp-target-sync
make codex-skills-sync
make pi-skills-sync
make opencode-skills-sync
```

The corresponding `*-skills-validate` commands are read-only and run in CI.
Intentional generated-target changes also require an explicit
`make generated-skills-snapshots` update; the aggregate sync command validates
snapshots but never blesses new output.
The generators share audited subtree-copying and strict tree-comparison
primitives, including byte, node-type, and executable-mode checks. When shared
transformation behavior changes, run all four validations and prove that
unaffected targets remain byte- and mode-identical.
