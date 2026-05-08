# Multi-agent Elixir/Phoenix plugin

This plugin's canonical home is **Claude Code**, but the same skills,
commands, and (in v3.0.0) sub-agents and hooks ship to three additional
agents: **Codex CLI**, **OpenCode**, and **Pi**.

> Single source of truth: `plugins/elixir-phoenix/`. Per-agent ports are
> generated into `targets/<agent>/` by `scripts/port.py`. Mirrored to
> per-agent GitHub repos at release-tag time.

## Quickstart

| Agent       | Install                                                                    |
|-------------|----------------------------------------------------------------------------|
| Claude Code | `/plugin install elixir-phoenix@oliver-kriska` (existing)                  |
| Codex       | `codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --sparse targets/codex` |
| OpenCode    | `"plugin": ["oliver-kriska/opencode-elixir-phoenix"]` in `opencode.json`   |
| Pi          | `pi install git:github.com/oliver-kriska/pi-elixir-phoenix`                |

See per-agent docs:

- [Codex install + tradeoffs](codex.md)
- [OpenCode install + tradeoffs](opencode.md)
- [Pi install + tradeoffs](pi.md)
- [Architecture: source-of-truth + port pipeline](architecture.md)
- [Contributing](contributing.md)

## Capability matrix (v2.9.0)

| Feature                    | Claude | Codex             | OpenCode              | Pi                  |
|----------------------------|:------:|:-----------------:|:---------------------:|:-------------------:|
| Skills auto-load           | yes    | yes               | yes                   | yes                 |
| Slash commands             | yes    | `$skill-name`     | `/skill-name`         | `/skill-name`       |
| Sub-agents                 | yes (`Agent`) | TOML drop  | `.opencode/agent/`    | extension dispatch  |
| Hooks                      | 9 events | 6 events        | TS module (4 hooks)   | TS extensions       |
| Iron Laws (auto-injected)  | SubagentStart | inlined per skill | system-prompt transform | session_start extension |
| Tidewave MCP               | yes    | stdio             | http (snippet)        | extension config    |
| `descriptions_short.yaml`  | n/a    | yes               | n/a                   | n/a                 |

`inlined` means the skill body has the laws appended, since the target
lacks a SubagentStart-equivalent hook today (Codex). Rendering is
generated; do not edit `targets/` by hand — run `make port`.

## When to use which agent

- **Claude Code** is the canonical experience: full sub-agent
  orchestration, all 9 hook events, native skill auto-loading.
- **Codex** is closest in feature shape to Claude. Native skill loading,
  `--sparse` install means you stay on the source repo (no mirror).
- **OpenCode** is for Bun-runtime users. TS hooks module is a cleaner
  authoring experience than CC's bash scripts.
- **Pi** is the lightweight option: agentskills.io-native, no
  sub-agents in v2.9.0, well-suited for read/refactor tasks.
