# OpenCode (`opencode-elixir-phoenix`)

OpenCode runs on the Bun runtime and reads `.opencode/skill/`,
`.opencode/command/`, and `.opencode/agent/` directories. The generated
tree at `targets/opencode/` is mirrored to a dedicated repo at
release-tag time.

## Install

Add to your `opencode.json`:

```json
{
  "plugin": ["oliver-kriska/opencode-elixir-phoenix"]
}
```

OpenCode resolves the GitHub shorthand and pulls the mirror repo
(`oliver-kriska/opencode-elixir-phoenix`). No npm publish required.

## Usage

Slash commands work as `/phx-skill-name` (`:` is not allowed in
OpenCode command names, so the namespace separator is rewritten to a dash):

```
/phx-quick add a unique constraint to the email column
/phx-plan multi-tenant billing with Stripe webhooks
/ecto-n1-check
/lv-assigns
```

Reference skills auto-load on file context (Bun-native). The 22 Iron
Laws are NOT inlined — Phase 2B's `experimental.chat.system.transform`
hook injects them dynamically (cleaner than Claude's PostToolUse approach).

## Free wins on OpenCode

- TypeScript hooks module (Phase 2B) is type-safe — Bun loads `server.ts`
  and the `@opencode-ai/plugin` types validate the hook shapes.
- Sub-agent definitions in `.opencode/agent/<name>.md` use the same
  frontmatter shape as Claude's, with two field renames.
- MCP config sits inside `opencode.json` (the `mcp` block) — no separate
  `.mcp.json` to maintain.

## What works (v2.9.0)

- 43 skills under `.opencode/skill/`
- 29 commands under `.opencode/command/`
- `AGENTS.md` (Claude's `CLAUDE.md` aliased)
- `package.json` with `engines.opencode: ">=0.1.0"`, `exports["./server"]`
- Stub `server.ts` (no hooks yet)
- `bunfig.toml`

## What's deferred to v3.0.0

- Sub-agents into `.opencode/agent/<name>.md` — Phase 2B
- TS hooks module:
  - `tool.execute.before` — block dangerous ops port
  - `tool.execute.after` — format / iron-law / debug ports
  - `experimental.chat.system.transform` — Iron Law injection
  - `event` filter — SessionStart-equivalent
- MCP block written into `opencode.json` (Tidewave)

## Tradeoffs vs. Claude Code

- Bun runtime required. Acceptable for OpenCode users (it's the runtime).
- No `descriptions_short.yaml` budget pressure — OpenCode has no listing
  byte ceiling.
- Mirror repo means commits to source don't reach OpenCode users until
  a release tag is pushed. Use prereleases (`v2.9.0-alpha.X`) to ship
  quickly during development.

## Manual smoke test

```bash
echo '{"plugin": ["oliver-kriska/opencode-elixir-phoenix"]}' > opencode.json
opencode
```

In the chat, `/phx-help` should list commands. If it does, install path is good.

## Running with local models

Johanna Larsson's [Running local models on M4](https://jola.dev/posts/running-local-models-on-m4)
(May 2026) tests OpenCode against `qwen3.5-9b@q4_k_s` on a 24 GB M4 MacBook
Pro via LM Studio with thinking enabled — about 40 tok/s, 128 K context.
Sampling that worked for her:

```
temperature=0.6, top_p=0.95, top_k=20, min_p=0.0,
presence_penalty=0.0, repetition_penalty=1.0
```

Plus `{%- set enable_thinking = true %}` in the LM Studio prompt template.

The model handled tight interactive edits (e.g. four parallel
`length(list) > 0 → list != []` Credo rewrites) but failed multi-step
recovery (a `mix.lock` merge conflict — diagnosed but forgot to apply the
edit). Treat a local 9 B in this slot as a step-by-step pair, not an
autonomous loop — the plugin's orchestration agents will struggle here.

Models she rated unusable for this workflow: Qwen 3.6 Q3, GPT-OSS 20B,
Devstral Small 24B. Gemma 4B ran but struggled with tool use.
