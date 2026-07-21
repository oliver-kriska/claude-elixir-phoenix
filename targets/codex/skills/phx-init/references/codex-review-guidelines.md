# AGENTS.md Review Guidelines Block (Codex rubric)

Managed `## Review guidelines` block for the target project's `AGENTS.md`.
Codex honors this section in BOTH surfaces: the local CLI
(`codex exec review`) and the cloud GitHub reviewer apply "guidance from
the closest AGENTS.md to each changed file". This is the ONLY reliable
rubric injection point — `codex exec review` rejects a custom-instructions
prompt combined with `--base`/`--uncommitted`/`--commit`.

## Install rules

1. If `AGENTS.md` does not exist: create it with just the block below.
2. If it exists WITHOUT plugin markers but WITH a `## Review guidelines`
   section: show the existing section and STOP — ask before touching.
   User-authored guidelines win; offer to append missing rules only.
3. If plugin markers exist: replace content between markers only
   (same upsert convention as the `ELIXIR-PHOENIX-PLUGIN` CLAUDE.md block).
   **Exception**: carry over the project's existing `### Known non-issues`
   entries verbatim — they are project knowledge, not template content;
   wiping them resurrects the false positives they suppress.
4. Never modify anything outside the markers.

## Block to inject

```markdown
<!-- ELIXIR-PHOENIX-REVIEW-GUIDELINES:START -->
<!-- Last updated: {DATE} | Managed by $phx-init — edits inside markers are overwritten on --update -->

## Review guidelines

Elixir/Phoenix review priorities. Flag violations at the given priority.

- **P1** Money as float — monetary values must use `Decimal` or integer
  cents; flag any float arithmetic on prices/amounts.
- **P1** Unpinned query values — Ecto query values must use `^`; flag any
  interpolation of user input into queries.
- **P1** `String.to_atom/1` on user-controlled input — atom exhaustion DoS;
  require allowlist or validated `String.to_existing_atom/1`.
- **P1** Unconditional DB queries in LiveView `mount` — mount runs twice;
  expect `assign_async` or a `connected?/1`-guarded branch.
- **P1** Missing authorization in LiveView `handle_event` — every event
  handler must authorize; mount-time authorization is not sufficient.
- **P1** `raw/1` with untrusted content — XSS.
- **P1** Implicit cross join — `from(a in A, b in B)` without `on:` creates
  a Cartesian product.
- **P2** Lists over ~100 items in LiveView assigns — require streams.
- **P2** Oban worker hazards — non-idempotent `perform`, atom keys in args,
  structs stored in args (store IDs).
- **P2** Bare `{:error, _}` swallowing changesets — `{:error,
  %Ecto.Changeset{}}` must be matched explicitly or form errors never
  re-render.
- **P2** Unsupervised long-lived processes — no bare `GenServer.start_link`
  / `Agent.start_link` outside a supervision tree in production code.
- **P3** `has_many` preloads via JOIN — prefer separate queries for
  `has_many`, JOIN for `belongs_to` (row multiplication).

### Known non-issues (do NOT report these)

<!-- Add project-specific disproven findings here as reviewers repeat them.
     One line per pattern: what the reviewer keeps claiming + why it's wrong.
     Example:
- Ecto does NOT validate schema-declared generated columns used via
  fragment() in this codebase — verified {date}, do not report as a crash.
-->

<!-- ELIXIR-PHOENIX-REVIEW-GUIDELINES:END -->
```

## Notes

- Keep the block under ~35 lines — cloud reviews read the nearest AGENTS.md
  per changed file; a bloated rubric dilutes focus.
- Cloud reviews surface mainly P0/P1 per OpenAI docs (P2/P3 observed in
  practice) — putting a priority on each rule steers what Codex reports.
- Re-running `$phx-init --update` refreshes the block in place.
