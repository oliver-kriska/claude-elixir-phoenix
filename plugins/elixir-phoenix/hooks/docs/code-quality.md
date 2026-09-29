# Code Quality Checks (`PostToolUse`)

Four hooks that run **after** an `Edit` or `Write` lands and feed a message back
to Claude. They cannot undo the edit — they force a correction on the next turn.

All four use **exit 2 + stderr**. That is not a stylistic choice: `PostToolUse`
stdout goes to verbose mode only, so a hook that `echo`s its finding to stdout
is talking to nobody. See [Output Rules](../README.md#output-rules-per-event).

| Script | Fires on | Checks |
|---|---|---|
| `format-elixir.sh` | `*.ex`, `*.exs` | `mix format --check-formatted` |
| `iron-law-verifier.sh` | `*.ex`, `*.exs` | 7 Iron Laws, by scanning code content |
| `debug-statement-warning.sh` | `*.ex` (not tests) | `IO.inspect`, `dbg()`, `IO.puts` |
| `security-reminder.sh` | Elixir files with auth-ish names | Reminds of 4 security Iron Laws |

Each is registered with an `if` condition (`"if": "Edit(*.ex)"`) so editing a
`.ts` or `.md` file never spawns the shell at all.

---

## `format-elixir.sh`

Runs `mix format --check-formatted` on the file you just touched.

```text
NEEDS FORMAT: lib/my_app/accounts.ex — run 'mix format' before committing
```

**It only warns — it never rewrites the file.** Formatting the file from a
`PostToolUse` hook causes the "file has been modified since read" race: the hook
changes bytes on disk that Claude believes it just wrote, and the next `Edit`
against that file fails. Warning is the correct trade.

---

## `iron-law-verifier.sh`

The plugin's action verifier. Where `security-reminder.sh` matches on
**filenames**, this one scans **code content** and names the specific law you
broke.

The pattern comes from AutoHarness (Lou et al., 2026), "harness-as-action-
verifier": deterministic code validates LLM output and feeds the specific
violation back for retry, rather than hoping the model self-checks.

Laws checked:

| Law | Detects |
|---|---|
| #4 | `:float` on a money-ish field (`price`, `amount`, `total`, `fee`, `balance`, …) in a schema **or** a migration |
| #10 | `String.to_atom(` in non-test code — atom exhaustion DoS |
| #12 | `raw(` called with a variable rather than a literal — XSS |
| #14 | Bare `GenServer.start_link` / `Agent.start_link` outside a supervisor or a `start_link` / `child_spec` / `init` definition |
| #15 | Implicit cross join — `from(a in A, b in B)` with no `on:` |
| #21 | `assign_new` for `:current_user`, `:locale`, `:timezone`, `:current_org` — values that must refresh every mount |

### Blame awareness

This is the important property. The hook scans **only the content this edit
introduced** — `tool_input.new_string` for `Edit`, `tool_input.content` for
`Write` — never the whole file.

A blame-unaware version fires on pre-existing violations in untouched regions of
a file you happened to open, which pushes Claude into unrequested refactors and
burns turns on code the user never asked about (session analysis, 2026-06-11).

The consequence to know when reading output: **line numbers are relative to the
edit, not to the file.** The message says so explicitly.

```text
IRON LAW VIOLATION(S) in the change you just made to accounts.ex
(line numbers are relative to your edit, not the file):

- Iron Law #10 (line 12): String.to_atom/1 detected — atom exhaustion DoS.
  Use String.to_existing_atom/1 or a whitelist map

Fix these before proceeding.
```

Comment lines are skipped, so an Iron Law quoted in a `#` comment does not
trip the check. Law #10 is skipped in `*_test.exs`, where `String.to_atom` on
fixture data is not a DoS vector.

---

## `debug-statement-warning.sh`

Catches debug leftovers in production code: `IO.inspect`, `dbg(`, and `IO.puts`
outside `@doc` / `@moduledoc` blocks. Up to 3 matches per kind, with line
numbers.

Scoped to `*.ex` only, and explicitly skips `*_test.exs` and anything under
`test/` — `IO.inspect` in a test is a legitimate debugging tool, not a leak.

```text
DEBUG STATEMENTS in accounts.ex:
  IO.inspect:
42:    |> IO.inspect(label: "changeset")

Remove before committing. Use Logger for intentional logging.
```

Unlike the Iron Law verifier this one scans the **whole file**, not just the
edit, since a stale `IO.inspect` anywhere in a file you are actively working on
is worth surfacing.

---

## `security-reminder.sh`

When you edit a file whose name suggests security, this re-states the four
security Iron Laws most often violated in that kind of code.

Trigger tokens: `auth`, `session`, `password`, `token`, `permission`, `admin`,
`payment`, `login`, `credential`, `secret`.

```text
SECURITY FILE DETECTED: user_auth.ex
Iron Laws — verify these apply:
  - AUTHORIZE in EVERY LiveView handle_event (don't trust mount auth)
  - NO String.to_atom with user input (atom exhaustion DoS)
  - NEVER use raw/1 with untrusted content (XSS)
  - Pin values with ^ in Ecto queries (no user input interpolation)
Consider: /phx:review security for full security audit
```

Three gates keep it quiet:

1. `mix.exs` must exist — no firing in non-Elixir projects (issue #55).
2. The extension must be `.ex`, `.exs`, `.heex`, `.eex`, or `.leex`. The laws
   are about code patterns, so a `token.json` is not interesting.
3. The token must match on the **basename** with word-boundary separators
   (`^`, `_`, `.`, `-`, `$`). Without this, `tokenizer.cpp` matched on `token`,
   and any file under an `admin_panel/` directory matched via its parent path.

## Related

- [Safety Gates](safety-gates.md) — the `PreToolUse` hooks that block
- [Failure Recovery](failure-recovery.md) — what fires when a `mix` command fails
- [Context Injection](context-injection.md) — how Iron Laws reach subagents
