# Hooks per target

Claude Code defines 9 hook events. Per-target support varies; the port
pipeline handles the mapping.

## Event support matrix

| Source event           | Claude | Codex                  | OpenCode                             | Pi                              |
|------------------------|:------:|:----------------------:|:------------------------------------:|:-------------------------------:|
| PreToolUse             | yes    | yes                    | `tool.execute.before`                | `tool_call` (block)             |
| PostToolUse            | yes    | yes                    | `tool.execute.after`                 | `tool_call` (post)              |
| PostToolUseFailure     | yes    | drop                   | `tool.execute.after` (with error)    | `tool_result` (isError)         |
| SubagentStart          | yes    | **yes** (cli ≥0.133.0) | `experimental.chat.system.transform` | `before_agent_start`            |
| SessionStart           | yes    | yes                    | `event` filter (`session.created`)   | `session_start`                 |
| PreCompact             | yes    | yes                    | `experimental.session.compacting`    | not supported                   |
| PostCompact            | yes    | yes                    | not supported                        | not supported                   |
| StopFailure            | yes    | drop                   | not supported                        | not supported                   |
| Stop                   | yes    | yes                    | `event` filter (`session.*`)         | `session_shutdown`              |

Codex additionally exposes `SubagentStop`, `UserPromptSubmit`, and
`PermissionRequest` (no source-plugin hooks use them yet). OpenCode
additionally exposes `permission.ask`, `tool.definition`, `chat.params`,
and `dispose`.

## Codex (`targets/codex/hooks/`)

`hooks.json` lists supported events with `${PLUGIN_ROOT}` substitution
for script paths — Codex injects `PLUGIN_ROOT` (native) and
`CLAUDE_PLUGIN_ROOT` (compat) into plugin hook env (source-verified in
`codex-rs/hooks/src/engine/discovery.rs`). Dropped events are listed in
the support matrix above and emitted in the `make port` build log — they
are kept out of `hooks.json` to avoid a non-standard `_meta` key that
strict validators may reject. Source shell scripts referenced by the kept
events copy verbatim; scripts orphaned by a dropped event are skipped.

`SubagentStart` (codex-cli 0.133.0+, PR #22782) injects the Iron Laws
into every subagent via `additionalContext` — the same contract as Claude
Code. The generated `install-codex-agents.sh` runs at SessionStart and
copies sub-agent TOMLs into `~/.codex/agents/`.

**Trust caveat:** Codex gates non-managed hooks behind per-hook trust
(`trusted_hash` in `~/.codex/config.toml`); plugin hooks were not
observed executing under `codex exec` on 0.139.0 even with
`--dangerously-bypass-hook-trust`. See `codex.md` → "Hook trust" for the
verification status and the manual agents-install fallback.

## OpenCode (`targets/opencode/server.ts`)

A single TS module default-exports a `PluginModule { id, server }` where
`server` is a `Plugin` **function** `(input) => Promise<Hooks>` (typed
with `@opencode-ai/plugin`; verified live on opencode 1.17.2). Every hook
receives `(input, output)` as two parameters:

```ts
const server: Plugin = async (_input) => ({
  "tool.execute.before": async (input, output) => {
    if (input.tool !== "bash") return;
    const cmd = (output.args?.command ?? "") as string;
    if (/mix\s+ecto\.(reset|drop)/.test(cmd)) {
      throw new Error("BLOCKED: destructive ecto operation.");
    }
  },
  // ... full impl in generated server.ts
});
export default { id: "opencode-elixir-phoenix", server };
```

Runtime-verified on opencode 1.17.2: a real session that attempted
`mix ecto.reset` was blocked by `tool.execute.before` with the message
above.

Iron Laws are injected via `experimental.chat.system.transform`
(`output.system.push(IRON_LAWS)` — the system prompt is a `string[]`),
and re-injected across compaction via `experimental.session.compacting`
(`output.context.push(IRON_LAWS)`) — the PreCompact equivalent.

PostToolUse Elixir-specific scripts (format, iron-law-verifier,
debug-statement-warning) are spawned as bash subprocesses to keep parity
with the source pipeline. Bun's `child_process` makes this trivial.

## Pi (`targets/pi/extensions/iron-laws.ts`)

Pi exposes hooks via TypeScript extensions (API verified against the
`@earendil-works/pi-coding-agent` 0.79.1 type declarations). Two are
shipped:

- `iron-laws.ts` — `before_agent_start` appends the laws to the system
  prompt; `tool_call` blocks dangerous bash patterns. The event carries
  `toolName` / `input` (not `tool` / `args`), and blocking is the typed
  return `{ block: true, reason }` — not a thrown error.
- `orchestration.ts` — registers `phx-plan` / `phx-work` / `phx-review`
  commands. `sendUserMessage` lives on the top-level `ExtensionAPI`
  (captured in closure), not on the command handler's context.

Pi doesn't have a Compact event today, so PreCompact / PostCompact /
StopFailure are simply dropped.

## Why drop events?

Each dropped event represents Claude-specific UX (subagent isolation
boundary, plan-state-survival-after-compaction, API-failure resume
detection). The behavioural goals are achieved differently per target:

- **SubagentStart** → ported natively on Codex (0.133.0+); OpenCode and
  Pi inject via system-prompt transform. Codex reference skills ALSO
  inline the Iron Laws as defence in depth (hook trust is user-granted).
- **PostToolUseFailure** → Codex doesn't auto-refit on bash failures
  (no equivalent UX); OpenCode chains `tool.execute.after` to inspect
  the result for failure markers.
- **StopFailure** → Codex/OpenCode/Pi don't have CC's API-resume
  semantics; users restart sessions instead.

These are documented per-target in `codex.md`, `opencode.md`, `pi.md`.
