# Context Injection (`UserPromptSubmit`, `SubagentStart`)

Two hooks that put text directly into a model's context. They exist because of
the same measured failure: **instructions written as prose in `CLAUDE.md` do not
reliably fire.**

| Script | Event | Injects into |
|---|---|---|
| `route-intent.sh` | `UserPromptSubmit` | The main conversation, per prompt |
| `inject-iron-laws.sh` | `SubagentStart` | Every spawned subagent |

---

## `route-intent.sh`

Detects high-signal task intents in your prompt and injects a one-line `/phx:`
suggestion.

### Why this is a hook

Session analysis across 400 sessions measured `CLAUDE.md` prose routing rules
firing **~0% of the time**. The rules were correct and simply never consulted.

`UserPromptSubmit` is one of only two events whose stdout is injected into
Claude's context (the other is `SessionStart`), so detection here actually
reaches the model. The routing table still exists in `CLAUDE.md` for the
ambiguous multi-step cases, but the high-signal cases moved into this hook.

### Categories

| Category | Trigger | Suggestion |
|---|---|---|
| `pr-review` | A GitHub PR URL, or phrasing like "review this PR", "reviewer feedback", "address the review" | `/phx:pr-review` |
| `investigate-ui` | A Tidewave `<context name="current-page">` block on the prompt | `/phx:investigate` |
| `investigate-error` | An Elixir crash signature — `** (SomeError)`, an `(elixir 1.x)` / `(ecto …)` frame line, or a `lib/foo.ex:42` stack frame | `/phx:investigate` |

Output is always marked as advisory:

```text
[plugin hint] Looks like a stack trace / error paste — /phx:investigate does
structured root-cause analysis (add --parallel for deep dives). (suggestion only)
```

### Anti-annoyance design

Three properties keep this from becoming noise:

1. **Never fires on a slash command.** If your prompt starts with `/`, you have
   already routed yourself.
2. **Once per category per session.** State lives in
   `/tmp/.claude-elixir-routing/$SESSION_ID/<category>`, keyed by session so a
   new session starts fresh.
3. **One suggestion per prompt.** First match wins; hints never stack.

The error category requires a real exception *shape*, not the word "error" —
otherwise "fix the error message copy" would trigger it.

### Performance

Only the first 4000 characters of the prompt are scanned. Long pastes keep their
signal up front, and grepping a 50 KB prompt on every submit is wasted work.
This keeps the hook well under 100 ms.

### Never exit 2 here

For `UserPromptSubmit`, **exit 2 blocks processing and erases the user's
prompt.** Every path in this script exits 0, and there is no `set -e`, so a
non-zero from an internal `grep` or `jq` can never destroy what you typed.

---

## `inject-iron-laws.sh`

Injects all 26 Iron Laws into every spawned subagent via
`hookSpecificOutput.additionalContext`.

This addresses the #1 finding from session analysis: **zero skill auto-loading
in subagents**. A subagent starts with a fresh context. It does not inherit the
conversation, and plugin skill `references/*.md` live outside the project
directory in `~/.claude/plugins/cache/`, so agents cannot reliably read them at
runtime. Without this hook, a review agent would apply generic Elixir knowledge
rather than the project's non-negotiable constraints.

The injected block is the condensed one-line-per-law form, covering LiveView,
Ecto, Oban, security, OTP, Elixir idioms, code style, and verification.

### Relationship to `omitClaudeMd`

These are separate mechanisms, and the distinction matters when writing agents:

| Mechanism | What it controls |
|---|---|
| `omitClaudeMd: true` in agent frontmatter | Skips the project `CLAUDE.md` body — commit rules, lint guidance, scope cues |
| This hook | Injects Iron Laws, on **every** subagent spawn |

So `omitClaudeMd: true` is safe on read-only agents: it trims the parts they do
not need while the Iron Laws still arrive. Set it freely.

### Gating

Skipped when the project has no `mix.exs`. A subagent working in a Rust or
Python repo should not be told about `assign_async` and `cast_assoc`.

## Related

- [Session Lifecycle](session-lifecycle.md) — the other event whose stdout reaches Claude
- [Workflow State](workflow-state.md) — post-compaction re-injection (`SessionStart`, matcher `compact`)
- `CLAUDE.md` → "Workflow Routing (Hook-Driven)"
