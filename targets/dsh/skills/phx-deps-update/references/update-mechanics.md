# Update Mechanics

Verified against Hex 2.4.2 / Elixir 1.20 (2026-06).

## Parsing `mix hex.outdated`

There is NO JSON output — parse the fixed-width text table (split on 2+
spaces), tolerating the trailing "Run `mix hex.outdated APP`..." footer:

```
Dependency  Only  Current  Latest  Status
decimal           2.4.1    3.1.1   Update not possible
jason             1.4.5    1.4.5   Up-to-date
```

- **Exit 1 = some dep is outdated. This is the NORMAL signal, not an
  error** — always `|| true`. `--within-requirements` flips exit semantics
  to in-range updates only.
- `--all` includes transitive deps; `--pre` includes pre-releases;
  `--only <env>` filters by `:only`.
- `Update not possible` = newer version exists but the `mix.exs`
  requirement blocks it — the blocked-major signal.

Classify by semver delta Current→Latest: patch (x.y.Z), minor (x.Y.z),
major (X.y.z).

## Why is a bump blocked? (per-package mode)

```
$ mix hex.outdated decimal
There is newer version of the dependency available 3.1.1 > 2.4.1!
Source   Requirement                 Up-to-date
mix.exs  ~> 2.0                      No
jason    ~> 1.0 or ~> 2.0 or ~> 3.0  Yes
```

This shows WHICH constraint to edit (`mix.exs`) AND whether transitive
consumers already allow the new major. If a consumer row says `No`, you
need `override: true` on the `mix.exs` dep tuple; if all consumers say
`Yes`, a plain constraint edit suffices.

## Update commands

| Goal | Command |
|------|---------|
| Named deps + their children, within requirements | `mix deps.update <pkg> [<pkg2>...]` |
| Single dep, NO children | `mix deps.unlock <pkg> && mix deps.get` |
| Everything (destructive) | `mix deps.update --all` |
| Cross a major | Edit `mix.exs` constraint FIRST, then `mix deps.update <pkg>` |

`mix deps.update` can never cross a constraint boundary — a blocked major
always needs the `mix.exs` edit first.

## Reading the lock diff (authoritative result)

`mix.lock` is a map literal, one line per package:

```elixir
"jason": {:hex, :jason, "1.4.5", "<hash>", [:mix], [<deps>], "hexpm", "<hash>"},
```

After every update step, `git diff mix.lock` and parse element 3 (the
version string) of old vs new lines to build the real `{pkg, old, new}`
set. `hex.outdated` says what COULD change; the lock diff says what DID —
transitive bumps appear here that the inventory never listed.

## Release metadata

- `mix hex.info <pkg>` — locked version, recent releases with dates,
  GitHub link (the source for `gh` fallbacks)
- `mix hex.info <pkg> <version>` — release date, deps, publisher
