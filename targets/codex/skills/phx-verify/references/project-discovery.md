# Project Discovery for Verification

How to analyze `mix.exs` and adapt the verification sequence to what the project actually has.

## Reading mix.exs

Read the project's `mix.exs` file. Extract three sections:

1. **`deps/0`** — list of dependencies (what tools are available)
2. **`aliases/0`** — custom mix task aliases (composite commands, test variants)
3. **`cli/0`** — `preferred_envs` mapping (newer Elixir pattern for custom MIX_ENV)

Also check for:

- `project/0 [:preferred_cli_env]` — older pattern for custom MIX_ENV
- `project/0 [:dialyzer]` — dialyzer config (paths, ignore files)
- `project/0 [:test_coverage]` — coverage tool config
- `project/0 [:test_paths]` — per-env test paths (E2E tests may be in separate dirs)
- `.check.exs` — ex_check configuration file

### cli/0 vs project/0 preferred_cli_env

Modern Elixir projects use `cli/0` with `preferred_envs`:

```elixir
def cli do
  [
    preferred_envs: [
      check: :test,
      credo: :test,
      sobelow: :test,
      coveralls: :test,
      "playwright.test": :int_test,
      "playwright.run": :int_test
    ]
  ]
end
```

Older projects use `project/0 [:preferred_cli_env]` instead. Check both.

## Dependency Detection

Search the deps list for these tool dependencies:

| Dependency | Enables | Verification Command |
|------------|---------|---------------------|
| `:credo` | Static analysis | `mix credo --strict` |
| `:dialyxir` | Type checking | `mix dialyzer` |
| `:sobelow` | Security scan | `mix sobelow --config` |
| `:ex_check` | Composite checker | `mix check` (orchestrates all) |
| `:excoveralls` | Test coverage | Coverage-enabled test alias |
| `:boundary` | Context boundaries | `mix compile` with `:boundary` compiler |
| `:mix_audit` | Dependency audit | `mix deps.audit` |
| `:phoenix_test_playwright` | E2E Playwright | `mix playwright.test` (custom env) |
| `:phoenix_test` | Integration tests | Often paired with E2E setup |

### Detection patterns in deps

Dependencies can appear in several forms:

```elixir
# Standard with env restriction
{:credo, "~> 1.7", only: [:dev, :test], runtime: false}

# Available in custom env too
{:credo, "~> 1.7", only: [:dev, :test, :int_test], runtime: false}

# E2E deps often restricted to custom env
{:phoenix_test_playwright, "~> 0.13", only: :int_test}
```

Search for the atom name (`:credo`, `:dialyxir`, etc.) in the deps function body.

## ex_check + .check.exs (Priority Path)

If `:ex_check` is installed, check for `.check.exs` at the project root.
This file defines the full verification pipeline:

```elixir
[
  retry: false,
  tools: [
    {:dialyzer, "mix dialyzer", order: -1},
    {:ex_unit, command: "mix test.with_coverage", retry: "mix test.with_coverage --failed"},
    {:credo, "mix credo --strict", detect: [{:package, :credo}]},
    {:check_translation, "mix gettext.extract --check-up-to-date"},
    {:prettier, order: 3, command: "npx --prefix assets prettier -c ."},
    {:sobelow, "mix sobelow --config .sobelow-conf"},
    {:compile_connected_dependency, "mix xref graph --label=compile-connected"}
  ]
]
```

Key observations:

- **`mix check` replaces individual steps** — it handles compile, format, credo,
  tests, dialyzer, sobelow in configured order
- **Custom tools** — may include prettier, gettext checks, xref analysis
- **Custom test command** — may use coverage alias instead of bare `mix test`
- **Retry config** — `retry: "mix test --failed"` for re-running only failures

When `.check.exs` exists: run `mix check` instead of individual steps.
Only add steps NOT covered by `.check.exs` (typically E2E tests).

## Test Command Discovery

Projects often have multiple test commands for different purposes.
Discover ALL of them from aliases and deps:

### Common test alias patterns

```elixir
defp aliases do
  [
    # Unit tests (standard or with coverage)
    test: ["ecto.create --quiet", "ecto.migrate --quiet", "test"],
    "test.with_coverage": [...],  # Unit tests + ExCoveralls report

    # E2E / Integration tests (different MIX_ENV)
    "playwright.test": [          # Full E2E: seeds + assets + tests
      fn _ -> System.put_env("MIX_ENV", "int_test") end,
      "ecto.create --quiet", "ecto.migrate --quiet",
      "assets.build", "test --only playwright"
    ],
    "playwright.run": [           # Fast E2E: skip seeds/assets
      fn _ -> System.put_env("MIX_ENV", "int_test") end,
      "test --only playwright"
    ],
    "playwright.reset": [...]     # Full DB reset for E2E

    # CI-specific
    "test.ci": ["ecto.create --quiet", "ecto.migrate --quiet", "test"],
  ]
end
```

### Categorize discovered test commands

| Category | Examples | Auto-run? |
|----------|----------|-----------|
| Unit | `mix test`, `mix test.with_coverage` | Yes (core verification) |
| E2E | `mix playwright.test`, `mix cypress.run` | Ask user first |
| Fast E2E | `mix playwright.run` | Offer as faster alternative |
| Coverage | `mix coveralls`, `mix test --cover` | Offer after unit pass |

### Detecting custom MIX_ENV for tests

Check both `cli/0` and aliases for env switching:

```elixir
# In cli/0
preferred_envs: ["playwright.test": :int_test]

# In aliases (anonymous function pattern)
"playwright.test": [
  fn _ -> System.put_env("MIX_ENV", "int_test") end,
  ...
]
```

When running these commands, ensure the correct `MIX_ENV` is used.

## Decision Logic

### IMPORTANT: Validate before adopting

Before using ANY discovered alias or composite command:

1. **Check `mix.lock`** — dependency must be fetched, not just in `mix.exs`
2. **Try running it** — if exit code != 0 with "not found" or dep error, fall back
3. **Log fallback**: "mix check failed (not installed locally), using individual steps"

Common failure: `mix.exs` has `{:ex_check, ...}` but user hasn't run `mix deps.get`
or the dep is only available in CI (`only: :ci`).

### Priority 1: ex_check + .check.exs

1. Verify `:ex_check` is in `mix.lock` (not just `mix.exs`)
2. Try `mix check` — if it fails, fall back to Priority 3
3. Check if E2E test commands exist
4. Ask user if they want to run E2E tests

### Priority 2: Composite alias (mix ci, mix precommit)

1. Map which steps the alias covers
2. Try running the alias — if it fails, fall back to Priority 3
3. Run uncovered steps individually
4. Offer E2E tests

### Priority 3: Individual steps

Run in order, skipping unavailable:

1. `mix compile --warnings-as-errors` — always
2. `mix format --check-formatted` — always
3. `mix credo --strict` — if `:credo` in deps
4. `mix test --trace` — always (use project alias if exists)
5. `mix dialyzer` — if `:dialyxir` in deps, pre-PR
6. `mix sobelow --config` — if `:sobelow` in deps

### Step 7: Additional test offer (always)

After core verification passes, present discovered test commands:

```
Core verification passed. Additional test commands available:
1. mix playwright.test (E2E, MIX_ENV=int_test)
2. mix test.with_coverage (unit + coverage report)
Run any of these? [1/2/both/skip]
```

### Skipped tool reporting

When a tool is not available, report once:

```
Credo: ⏭ Not installed (add {:credo, "~> 1.7", only: [:dev, :test]} to deps)
Dialyzer: ⏭ Not installed (add {:dialyxir, "~> 1.4", only: :dev} to deps)
```

## Real-World Examples

### Minimal Phoenix project (no extras)

```
Discovery: compile ✓ | format ✓ | credo ✗ | dialyzer ✗ | sobelow ✗ | ex_check ✗
Test commands: mix test (unit only)
Strategy: compile → format → test (3 steps). No additional tests to offer.
```

### Full-featured project with ex_check

```
Discovery: compile ✓ | format ✓ | credo ✓ | dialyzer ✓ | sobelow ✓ | ex_check ✓
Test commands: mix test.with_coverage (unit) | mix playwright.test (E2E, int_test)
.check.exs: compiler, formatter, credo, dialyzer, sobelow, tests, prettier, xref
Strategy: mix check (covers all core). Then ask: "Run E2E? mix playwright.test"
```

### Project with CI alias, no ex_check

```
Discovery: compile ✓ | format ✓ | credo ✓ | dialyzer ✓ | sobelow ✗ | ex_check ✗
Test commands: mix test (unit) | mix test.ci (unit + DB setup)
Aliases: ci ["compile --warnings-as-errors", "format --check-formatted", "credo --strict", "test"]
Strategy: mix ci → mix dialyzer (not covered by alias). No E2E found.
```

### Project with custom test env only

```
Discovery: compile ✓ | format ✓ | credo ✓ | dialyzer ✗
Test commands: mix test (unit) | MIX_ENV=int_test mix test --only integration
preferred_envs: ["test.integration": :int_test]
Strategy: compile → format → credo → test. Offer: "Run integration tests?"
```
