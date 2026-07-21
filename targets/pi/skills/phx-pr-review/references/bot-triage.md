# Bot Review Triage

CI bots (Copilot, Codex, CodeRabbit, SonarCloud) post review passes as
inline review threads + a review summary. They produce volume — triage in
batch, but never bulk-resolve without replies (SKILL.md Iron Laws 6 + 9).

## Known bot logins

`copilot-*`, `codex`, `coderabbitai`, `sonarcloud`, `github-actions`,
`dependabot`, `*-ci`. Detect via `__typename == "Bot"` (GraphQL) or
`user.type == "Bot"` (REST) — see `gh-commands.md` for why the `[bot]`
login suffix is unreliable.

## Batch flow (`--bots-only`)

1. Fetch unresolved threads, filter `isBot == true`
2. Classify each finding:

| Verdict | Signal | Action |
|---------|--------|--------|
| **Real bug** | Reproducible, matches code behavior | Fix → reply with diff summary → resolve |
| **Real but deferred** | Valid, out of this PR's scope | Reply "tracked as follow-up: {ref}" → resolve |
| **False positive** | Bot misread the code | Reply with one-line explanation of why it's safe → resolve |
| **Iron Law conflict** | Bot suggests an Iron Law violation | Reply declining with the law + reasoning → resolve |

3. Present the verdict table to the user BEFORE posting anything
4. Post replies + resolve only after approval

## Codex thread anatomy (chatgpt-codex-connector)

Codex inline comments have a fixed shape — parse it, don't guess:

- Priority badge: `![P1 Badge](https://img.shields.io/badge/P1-orange...)`
  (P1 orange / P2 yellow / P3), then a **bold one-line title**, a detailed
  body, and a `Useful? React with 👍 / 👎.` footer.
- Mapping: P0/P1 → treat as code-change/blocker; P2 → verify-then-fix;
  P3 → nitpick. Codex P1s on Elixir code have proven accurate (Ecto
  schema-field crashes, tsquery guards) — verify, but don't dismiss.
- Reviews are per-commit (`Reviewed commit: <sha>` in the summary body) —
  after a force-push or big rebase, outdated codex threads are expected;
  handle via the standard outdated-thread rule.
- Reply + resolve works exactly like human threads. Optionally react 👍/👎
  on the finding itself — it trains the reviewer.
- A codex review summary with ZERO inline threads = clean pass (summary-only
  round); nothing to triage.
- A clean pass can also be a plain bot COMMENT ("Codex Review: Didn't find
  any major issues" + `Reviewed commit: <sha>`) or a 👍 reaction on the
  trigger comment / PR body — all three mean the same thing.

## Common false-positive patterns (Elixir)

- **`nil[:key]` flagged as crash risk** — Access protocol on nil returns
  nil; nil-safe by design. Reply: "Access lookup on nil is nil-safe in
  Elixir (`nil[:key]` → `nil`); no guard needed."
- **"Unused variable" on pattern-match bindings** — bindings used for
  match assertion, not value. Prefix with `_` only if truly unused.
- **"Missing error handling" on `!` functions** — `Repo.get!`/`File.read!`
  crash intentionally per let-it-crash; supervised recovery is the design.
- **Atom-vs-string key confusion in test fixtures** — bots often suggest
  atomizing external/JSON data; that violates Iron Law #10 territory
  (`String.to_atom` on input). Decline.

## What NOT to do

- Never auto-resolve a bot pass to "clean up the PR" — each thread gets a
  reply first, even one line.
- Never accept a bot's code suggestion verbatim without reading the
  surrounding code — bots see the diff hunk, not the module.
- Never let a bot summary (review body) block on "resolution" — summaries
  are not threads and cannot be resolved; address inline findings instead.
