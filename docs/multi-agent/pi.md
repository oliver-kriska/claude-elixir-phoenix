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

## Phase 2C TS extensions — scaffold, API surface unverified

`targets/pi/extensions/{iron-laws,orchestration}.ts` ship in v2.9.0 but
should be treated as **code-not-yet-active**. They reference an API
surface (`pi.command`, `ctx.invoke_prompt`, `pi.system_prompt_append`,
`pi.root`, `pi.on`) and an import (`@pi-ai/extensions`) that have not
been verified against the actual published Pi package
(`@earendil-works/pi-coding-agent`). Phase 2C ships the TS as the
intended contract; runtime verification lands in v3.0.0 after a real
Pi smoke test.

Practical impact for v2.9.0 users:

- Skills + slash commands (43 + 29) work today via Pi's native
  agentskills.io and prompt-template loading — no extension required.
- The Iron Laws and orchestration extensions may fail to load at
  `pi install` time. If so, Pi continues without them and the rest of
  the package still works. The skills' inlined Iron Laws and
  per-skill Iron Law headers carry the same content.

## What's deferred to v3.0.0

- TS extension API verification against `@earendil-works/pi-coding-agent`
  (rename imports, fix any signature mismatches)
- Specialist agent prompt templates dispatched by extension
- Decision: `@tintinweb/pi-subagents` vs native — see Phase 2C in `plan.md`

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
