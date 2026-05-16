# Pi (`pi-elixir-phoenix`)

Pi is agentskills.io-native — it reads `skills/<name>/SKILL.md` directly
without transformation. The generated tree at `targets/pi/` is mirrored
to `oliver-kriska/pi-elixir-phoenix` at release-tag time.

## Install

```bash
# Local checkout of the generated tree (verified form):
pi install ./targets/pi          # add -l for project-local (.pi/) scope

# Or from the mirror once it is live:
pi install /path/to/pi-elixir-phoenix
```

`pi install <dir>` takes an absolute or relative path; the package
self-describes via `package.json` `"pi": { … }` (skills / prompts /
extensions). The `pi-package` keyword makes the mirror discoverable
through pi.dev/packages once it is live.

## Usage

Slash commands map to `targets/pi/prompts/<name>.md` Pi prompt templates
(with `args: $@`):

```
/phx-quick add a unique constraint to the email column
/phx-plan multi-tenant billing with Stripe webhooks
/ecto-n1-check
/lv-assigns
```

The 14 reference skills auto-load on file context.

## Free wins on Pi

- Pi reads `AGENTS.md` (which is the same as `CLAUDE.md`), so the
  Behavioral Instructions section ports unchanged.
- agentskills.io spec compliance means descriptions live at the top of
  each `SKILL.md` and Pi auto-discovers them.

## What ships (v3.0.0)

- 43 skills as agentskills.io-spec SKILL.md files
- 29 prompt templates for slash commands
- TS extensions (`extensions/{iron-laws,orchestration}.ts`) written
  against the verified `@earendil-works/pi-coding-agent` API
- `AGENTS.md` / `CLAUDE.md` companion
- `package.json` with `pi-package` keyword + a
  `@earendil-works/pi-coding-agent` (>=0.74.0) devDependency for the
  type-only import
- `engines.pi: ">=0.1.0"`

## TS extensions — verified API, smoke test pending

`targets/pi/extensions/{iron-laws,orchestration}.ts` now target the
**verified** Pi extension API (checked against
`@earendil-works/pi-coding-agent` docs, 2026-05-16):

- `import type { ExtensionAPI } from "@earendil-works/pi-coding-agent"`
  (the package was renamed from `@mariozechner/` on 2026-05-07 — the day
  before this port was first written; the old `@pi-ai/extensions` import
  in the original scaffold never existed).
- default-export factory `export default function (pi: ExtensionAPI)`
- `pi.on("before_agent_start", …)` returning `{ systemPrompt }` to append
  the 22 Iron Laws (baked in at port time — no runtime file read)
- `pi.on("tool_call", …)` to block destructive bash
- `pi.registerCommand(name, { description, handler })` +
  `ctx.sendUserMessage(...)` for `/phx-plan|work|review`

What is **not** yet verified: the exact `tool_call` block return contract
and end-to-end behaviour on a live Pi. These are covered by a manual
post-merge smoke test. If the block contract differs, Pi still loads the
extension and the skills' inlined Iron Laws carry the same content
(defence in depth with the Codex/Claude hooks).

Skills + slash commands (43 + 29) work via Pi's native agentskills.io and
prompt-template loading with **no extension required** — the extensions
are an enhancement, not a dependency.

## Tradeoffs vs. Claude Code

- Sub-agent orchestration is prompt-based (the `orchestration.ts`
  extension dispatches `/phx-plan|work|review` prompt templates), not the
  parallel `Agent`-spawning model Claude uses. Sequential by nature.
- Hooks are the two TS extensions, not Claude's 9-event hook system —
  `before_agent_start` (Iron Laws) + `tool_call` (destructive-bash block).
- Slash commands trigger Pi prompts, which is closer to "user types this
  template" than "agent runs this skill". Behavioral parity is high but
  not identical.

## If `oh-my-pi` eclipses upstream Pi

`oh-my-pi` is a 4 K-star fork that re-adds Claude-like features. If it
becomes the dominant install base, the extension strategy switches to
`oh-my-pi` primitives. Decision deferred — track adoption post-v3.0.0.

## Manual smoke test

After install:

```
pi
```

In the chat: `/phx-help` should produce the command list. `/phx-quick add
a unique index on users.email` should produce a migration.

## Running with local models

Jola's [Running local models on M4](https://jola.dev/posts/running-local-models-on-m4)
covers Pi alongside OpenCode — see the OpenCode page's "Running with local
models" section for the exact model tag (`qwen3.5-9b@q4_k_s`), sampling
settings, and the LM Studio `enable_thinking` template flag.

Her Pi-specific note: it "feels a bit snappier" than OpenCode but ships
with fewer sensible defaults, so expect to spend more time tweaking the
agent surface itself before the plugin's commands feel right. Same
9 B-class caveat applies — local works for step-by-step interactive use,
not autonomous orchestration.
