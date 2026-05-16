# Multi-agent Elixir/Phoenix plugin

This plugin's canonical home is **Claude Code**, but as of **v3.0.0** the
same skills, commands, sub-agents, and hooks ship to three additional
agents: **Codex CLI**, **OpenCode**, and **Pi** — full parity in one
release.

> Single source of truth: `plugins/elixir-phoenix/`. Per-agent ports are
> generated into `targets/<agent>/` by `scripts/port.py`. Mirrored to
> per-agent GitHub repos at release-tag time.

## Quickstart

| Agent       | Install                                                                    |
|-------------|----------------------------------------------------------------------------|
| Claude Code | `/plugin install elixir-phoenix@oliver-kriska` (existing)                  |
| Codex       | `codex plugin marketplace add oliver-kriska/claude-elixir-phoenix --ref main` then enable in the picker |
| OpenCode    | `"plugin": ["oliver-kriska/opencode-elixir-phoenix"]` in `opencode.json`   |
| Pi          | `pi install ./targets/pi` (local) — see [pi.md](pi.md) for the mirror      |

See per-agent docs:

- [Codex install + tradeoffs](codex.md)
- [OpenCode install + tradeoffs](opencode.md)
- [Pi install + tradeoffs](pi.md)
- [Architecture: source-of-truth + port pipeline](architecture.md)
- [Contributing](contributing.md)

## Capability matrix (v3.0.0)

| Feature                    | Claude | Codex             | OpenCode              | Pi                  |
|----------------------------|:------:|:-----------------:|:---------------------:|:-------------------:|
| Skills auto-load           | yes    | yes               | yes                   | yes                 |
| Command invocation         | `/phx:foo` | none — skills auto-load by description | `/skill-name` | `/skill-name` |
| Sub-agents                 | yes (`Agent`) | TOML drop  | `.opencode/agent/`    | extension dispatch  |
| Hooks                      | 9 events | 6 events        | TS module (4 hooks)   | TS extensions       |
| Iron Laws (auto-injected)  | SubagentStart | inlined per skill | system-prompt transform | before_agent_start extension |
| Tidewave MCP               | yes    | stdio             | http (snippet)        | extension config    |
| `descriptions_short.yaml`  | n/a    | yes               | n/a                   | n/a                 |

`inlined` means the skill body has the laws appended, since the target
lacks a SubagentStart-equivalent hook today (Codex). Rendering is
generated; do not edit `targets/` by hand — run `make port`.

## When to use which agent

- **Claude Code** is the canonical experience: full sub-agent
  orchestration, all 9 hook events, native skill auto-loading.
- **Codex** is closest in feature shape to Claude. Native skill loading;
  installs directly from this repo (no mirror) via its own
  `.agents/plugins/marketplace.json`.
- **OpenCode** is for Bun-runtime users. TS hooks module is a cleaner
  authoring experience than CC's bash scripts.
- **Pi** is the lightweight option: agentskills.io-native, skills +
  prompt-template commands work without any extension; the TS
  orchestration/Iron-Laws extensions are best-effort (see [pi.md](pi.md)).
