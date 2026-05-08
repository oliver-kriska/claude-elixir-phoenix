# Pi (`pi-elixir-phoenix`)

Pi is agentskills.io-native — it reads `skills/<name>/SKILL.md` directly
without transformation. The generated tree at `targets/pi/` is mirrored
to `oliver-kriska/pi-elixir-phoenix` at release-tag time.

## Install

```bash
pi install git:github.com/oliver-kriska/pi-elixir-phoenix
```

`pi-package` keyword in `package.json` makes the listing discoverable
through pi.dev/packages once the mirror is live.

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

## What works (v2.9.0)

- 43 skills as agentskills.io-spec SKILL.md files
- 29 prompt templates for slash commands
- `AGENTS.md` / `CLAUDE.md` companion
- `package.json` with `pi-package` keyword for gallery discovery
- `engines.pi: ">=0.1.0"`

## What's deferred to v3.0.0

- TS extensions:
  - `targets/pi/extensions/iron-laws.ts` — `tool_call` interceptor +
    `session_start` injection
  - `targets/pi/extensions/orchestration.ts` — Plan→Work→Review cycle
- Specialist agent prompt templates dispatched by extension
- Decision: `@tintinweb/pi-subagents` vs native — see Phase 2C

## Tradeoffs vs. Claude Code

- No sub-agents in v2.9.0. Sequential prompt-based flow only.
- No hook events — extensions land in v3.0.0.
- Slash commands trigger Pi prompts, which is closer to "user types this
  template" than "agent runs this skill". Behavioral parity is high but
  not identical.

## If `oh-my-pi` eclipses upstream Pi

`oh-my-pi` is a 4 K-star fork that re-adds Claude-like features. If it
becomes the dominant install base, Phase 2C's strategy switches to
`oh-my-pi` primitives. Decision deferred — track adoption between now and
the v3.0.0 release.

## Manual smoke test

After install:

```
pi
```

In the chat: `/phx-help` should produce the command list. `/phx-quick add
a unique index on users.email` should produce a migration.
