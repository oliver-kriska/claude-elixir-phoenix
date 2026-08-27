# PR Splitting Strategy + Scratch Layout

## Default grouping (override with `--pr-per`)

| Update class | Default grouping | Rationale |
|--------------|------------------|-----------|
| Patch (x.y.Z) | ONE bundled PR ("Bump N patch deps") | Low risk; reviewer skims the lock diff |
| Minor (x.Y.z) | Grouped by area | Back-compatible features; area grouping keeps review coherent |
| Major (X.y.z) | ONE PR each, changelog excerpt in body | Breaking; each needs focused review and its own revert unit |
| Coupled group | ONE PR for the whole group, regardless of class | Must move together (Iron Law 4) |

`--pr-per area` (default) · `--pr-per major` (majors separate, all minors
bundled) · `--pr-per none` (single branch, no split — solo repos).

## Area buckets (heuristic by package name)

`web` (phoenix*, plug*, bandit, cowboy) · `data` (ecto*, postgrex,
decimal) · `json` (jason, poison) · `test` (`:only` test — ex_machina,
mox, wallaby) · `obs` (telemetry*, opentelemetry*) · `bg` (oban*) ·
`auth` (guardian, bcrypt*, argon2*) · `misc` (rest).

## PR body template

Built from the scratch changelog deltas:

```markdown
## Dependency update: <pkg> <old> → <new>  [<class>]

<changelog delta excerpt — the CHANGELOG hunk from hex.package diff>

- Full diff: https://diff.hex.pm/diff/<pkg>/<old>..<new>
- Verification: mix compile + mix test PASS
- Security: /phx-deps-audit risk band <band>
```

## Commit discipline

Per commit: `mix.lock` + any `mix.exs` edit + (Phoenix-family)
`assets/package-lock.json` — never a lock alone (Iron Law 5). Stage
specific files; never `git add -A`.

## Scratch layout

`.claude/deps-update/{YYYY-MM-DD}/` — per-run, never committed:

```
inventory.md              # parsed hex.outdated table, classified
before/<pkg>-CHANGELOG.md # snapshot of the current changelog (pre-update)
<pkg>-<old>-<new>.md      # per-package changelog delta + notes
lock-diff.patch           # git diff mix.lock for the whole run
pr-plan.md                # grouping decisions + PR bodies
```

PR bodies are the only content that leaves the dir (into `gh pr create`).
