# Codex CLI Review — Recipes and Gotchas

Verified against codex CLI **0.142.5** (2026-07-03). Re-verify flags with
`codex exec review --help` if behavior looks off — the CLI moves fast.

## Invocation recipes

```bash
# Diff vs a base branch (merge-base aware — only YOUR changes)
codex exec review --base main --ephemeral \
  -o /tmp/codex-out.md > /tmp/codex-out.log 2>&1

# Staged + unstaged + untracked
codex exec review --uncommitted --ephemeral \
  -o /tmp/codex-out.md > /tmp/codex-out.log 2>&1

# One commit
codex exec review --commit abc1234 --ephemeral \
  -o /tmp/codex-out.md > /tmp/codex-out.log 2>&1

# JSONL event stream (alternative capture)
codex exec review --base main --ephemeral --json \
  | jq -rs '[.[] | select(.item.type == "agent_message")] | last | .item.text'
```

- `--ephemeral` skips session persistence — always use it for loop rounds.
- Use ONE Bash call with a long timeout (up to 600000ms); reviews take
  1–5+ minutes. Never poll.
- **ALWAYS redirect stdout+stderr to a log file** (as above) — without
  `--json`, codex streams its entire agent transcript (10k+ lines) to the
  terminal. Only the `-o` last-message file is needed; letting the stream
  hit the tool result floods the session context. Read the `.log` only
  when the review fails.

## Gotchas (all verified live)

1. **`[PROMPT]` is mutually exclusive with `--base`/`--uncommitted`/
   `--commit`** — `error: the argument '--uncommitted' cannot be used with
   '[PROMPT]'`. You CANNOT pass custom review instructions together with a
   diff-mode flag. The rubric injection point is the project's `AGENTS.md`
   `## Review guidelines` section (honored by both the local CLI and the
   Codex cloud reviewer) — install the managed block via `phx-init`.
2. **Exit code is 0 even when findings exist** — parse the output, never
   branch on `$?`.
3. **Output format** (the `-o` file / final agent message):

   ```text
   {summary paragraph}

   Full review comments:

   - [P1] {title} — {absolute_path}:{start}-{end}
     {body paragraph}
   ```

   No `Full review comments:` section and no `- [P` bullets = clean pass.
   Paths are absolute — convert to repo-relative before displaying.
4. **Priorities**: P0/P1 = blocker-grade, P2 = warning, P3 = nit. Map to
   BLOCKER/WARNING/SUGGESTION in review artifacts.
5. **`review_model`** in `~/.codex/config.toml` pins a dedicated model for
   reviews (e.g. `review_model = "gpt-5-codex-max"`). Respect the user's
   config — do not override with `-c` unless asked.
6. **Codex plugin hooks do NOT fire under `codex exec`** — don't rely on
   codex-side plugins for review behavior; AGENTS.md is the only lever.
7. **Auth** rides the ChatGPT subscription login (`codex login`) — no API
   key. `codex doctor` diagnoses auth/config issues.
8. **Large diffs run 10+ minutes** (observed: big PR rewrite, session
   2026-07-10) — set Bash `timeout: 600000` explicitly. If it times out
   with the process alive, wait with ONE
   `until [ -f {out} ]; do sleep 5; done` call. NEVER `pkill` a running
   review — the round's quota is spent either way (observed: 5 poll
   commands then a pkill wasted a full round).
9. **codex review holds git locks** — it runs git internally (submodules
   included). A concurrent git command can fail with
   `index.lock: File exists` (observed live). Don't run git mutations
   while a review is in flight; don't delete the lock file — wait.

## Parse recipe (findings → table)

For each bullet matching `^- \[P([0-9])\] (.+) — (.+):([0-9]+)(-([0-9]+))?`:
capture priority, title, path, line range; the indented paragraph below is
the body. Keep the body verbatim — codex explanations reference concrete
runtime behavior and lose value when paraphrased.

## Related

- Cloud reviewer mechanics (triggers, 👀/👍 reactions, re-request loop):
  `watch-pr` skill, `references/watcher-mechanics.md`
- Cross-model panel review: `phx-review --codex` (codex-reviewer agent)
