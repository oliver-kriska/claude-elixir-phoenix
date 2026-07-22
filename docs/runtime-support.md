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

| Capability | Claude Code | Amp | Codex | Pi | OpenCode |
| --- | --- | --- | --- | --- | --- |
| 51 canonical skills | Full | Generated | Generated | Generated | Generated |
| Complete skill resource trees | Full | Generated | Generated | Generated | Generated |
| Executable resource modes | Full | Preserved | Preserved | Preserved | Preserved |
| Automatic skill selection | Full | Model-driven | Model-driven | Model-driven | Model-driven |
| Flagship `phx-investigate` | Full | Generated guidance | Adapted | Adapted | Adapted |
| Flagship read-only `phx-review` | Full | Generated guidance | Adapted | Adapted | Adapted |
| Claude namespaced slash commands | Full | Not applicable | Not applicable | Not applicable | Not applicable |
| Bundled custom agents | Full | Deferred | Deferred | Deferred | Deferred |
| Lifecycle/enforcement hooks | Full | Deferred | Deferred | Deferred | Deferred |
| Bundled Tidewave MCP setup | Full | External | External | External | External |
| Plugin-root instructions | Full | Deferred | Deferred | Deferred | Deferred |
| Deterministic generated target | Canonical source | Yes | Yes | Yes | Yes |
| Mode-aware CI drift validation | Not applicable | Yes | Yes | Yes | Yes |

“External” Tidewave support means a skill may use Tidewave when the project and
runtime already expose it. Generated flagship workflows must still complete
without Tidewave, named custom agents, or Claude-only task APIs.

## Native invocation and installation

| Runtime | Reliable explicit invocation | Distribution | Guide |
| --- | --- | --- | --- |
| Claude Code | `/phx:investigate`, `/phx:review` | Claude plugin marketplace | [Claude Code installation](../README.md#claude-code) |
| Amp | Command palette → `skill: invoke`, or explicitly request the skill in the prompt | Direct GitHub Agent Skills install | [Amp guide](amp.md) |
| Codex | `$elixir-phoenix:phx-investigate`, `$elixir-phoenix:phx-review` | Native Codex Git marketplace plugin | [Codex guide](codex.md) |
| Pi | `/skill:phx-investigate`, `/skill:phx-review` | Native Pi Git package | [Pi guide](pi.md) |
| OpenCode | `/phx-investigate`, `/phx-review`, or ask the skill tool to load the skill | Sparse Git checkout | [OpenCode guide](opencode.md) |

Codex plugin skills are qualified by the plugin manifest name. OpenCode 1.17.2
does not provide a native Git skills-package installer, so a sparse checkout is
the supported installation and update mechanism. Start a fresh process after
installing, updating, or removing skills because runtime discovery may be
cached when a session starts.

## Runtime-specific boundaries

### Claude Code

`plugins/elixir-phoenix/` is the source of truth and retains the complete
plugin: skills, commands, agents, hooks, root instructions, permission settings,
and Tidewave MCP integration. Portability fixes must not weaken this behavior.

### Amp

Amp installs `targets/amp/skills` as standard Agent Skills. The generated target
is intentionally stable and does not install Claude hooks, agents, permissions,
or MCP configuration. Exact Claude slash-command syntax is replaced by Amp's
native skill picker and explicit skill-loading prompts.

### Codex

Codex installs `targets/codex` as a native plugin. `/skills` opens the selector,
and explicit skill references use the `elixir-phoenix:` plugin namespace.
Plugin-root agent definitions and `AGENTS.md` are not automatically activated.
Hooks, generated agent TOMLs, and bundled MCP configuration are separate future
capabilities rather than hidden installation side effects.

### Pi

Pi consumes `targets/pi/skills` through the repository's Pi package declaration.
Generated references use native `/skill:<name>` syntax. Extensions, prompt
templates, custom-agent orchestration, package-root instructions, and bundled
MCP configuration are deferred.

### OpenCode

OpenCode recursively discovers `SKILL.md` files in the installed
`targets/opencode` tree. The generated package does not install hooks, custom
agents, separate commands, MCP servers, root instructions, or configuration.
Use `opencode debug skill --pure` for deterministic discovery diagnostics.

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

Runtime acceptance additionally verifies installation or discovery, all 51
skills, explicit flagship loading, a resource outside `references/`, an
executable resource, update/removal behavior, and fresh-process rediscovery.
Behavioral probes use a controlled fixture and require `phx-investigate` to
reproduce before identifying a planted root cause and `phx-review` to find a
planted defect without modifying the fixture.

### Isolation rules

Runtime smoke tests must not read, overwrite, or remove a developer's normal
configuration. Use temporary homes and start a fresh runtime process for each
discovery boundary.

For Codex, isolate both locations because marketplace metadata and the plugin
cache use separate roots:

```bash
export TEST_ROOT="$(mktemp -d)"
export HOME="$TEST_ROOT/home"
export CODEX_HOME="$TEST_ROOT/codex"
mkdir -p "$HOME" "$CODEX_HOME"
```

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
runtime generator, then regenerate and validate only that target:

```bash
make amp-skills-sync
make codex-skills-sync
make pi-skills-sync
make opencode-skills-sync
```

The corresponding `*-skills-validate` commands are read-only and run in CI.
When shared transformation behavior changes, run all four validations and prove
that unaffected targets remain byte- and mode-identical.
