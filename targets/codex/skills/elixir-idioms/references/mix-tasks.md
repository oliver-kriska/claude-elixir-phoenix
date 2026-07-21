# Mix Task Patterns

> **Official docs**: <https://hexdocs.pm/mix/Mix.Task.html>
> **Mix guides**: <https://github.com/elixir-lang/elixir/tree/main/lib/mix/lib/mix>

## Module Naming Convention

Mix task module names map directly to the CLI command:

```elixir
# mix my_app.validate → Mix.Tasks.MyApp.Validate
defmodule Mix.Tasks.MyApp.Validate do
  @shortdoc "Validate configuration"
  @moduledoc "Detailed description..."
  use Mix.Task

  @impl Mix.Task
  def run(args) do
    # Parse args, do work
  end
end
```

**Rules:**

- Module name segments map to `.`-separated CLI words
- `CamelCase` in module → `snake_case` in CLI
- `@shortdoc` is REQUIRED (shows in `mix help`)
- `@moduledoc` for detailed `mix help my_app.validate`

## Option Parsing

```elixir
@impl Mix.Task
def run(args) do
  {opts, _rest, _invalid} =
    OptionParser.parse(args,
      strict: [
        dry_run: :boolean,
        type: :string,
        format: :string,
        verbose: :boolean
      ],
      aliases: [d: :dry_run, t: :type, f: :format, v: :verbose]
    )

  # Access with Keyword.get
  dry_run? = Keyword.get(opts, :dry_run, false)
  format = Keyword.get(opts, :format, "text")
end
```

## Shell Output

```elixir
# Prefer Mix.shell() for testability
Mix.shell().info("Processing #{count} items...")
Mix.shell().error("Failed: #{reason}")

# For colored output
Mix.shell().info([:green, "✓ ", :reset, "All checks passed"])

# Progress reporting
Enum.each(items, fn item ->
  Mix.shell().info("  #{item.name}... #{status}")
end)
```

## App Startup (Iron Law #10)

NEVER `Mix.Task.run("app.start")` — it boots the FULL supervision tree:
the endpoint binds its port and Oban starts consuming jobs, inside what
should be a one-off task. Start only what the task needs:

```elixir
def run(args) do
  # Load config without starting the app
  Mix.Task.run("app.config")

  # Start only the dependency apps + repo this task uses
  {:ok, _} = Application.ensure_all_started(:ecto_sql)
  {:ok, _} = MyApp.Repo.start_link()

  # Your logic here
end
```

## Chaining Tasks

```elixir
# Run another task (after the startup above)
Mix.Task.run("ecto.migrate")

# Re-run a task that already ran this VM session
Mix.Task.rerun("ecto.migrate")
```

## Credo Complexity

Mix tasks often trigger Credo complexity warnings because the
`run/1` function handles arg parsing + logic. Split into:

```elixir
def run(args) do
  args |> parse_opts() |> validate_opts() |> execute()
end

defp parse_opts(args), do: ...
defp validate_opts(opts), do: ...
defp execute(opts), do: ...
```

## Testing Mix Tasks

```elixir
defmodule Mix.Tasks.MyApp.ValidateTest do
  use ExUnit.Case, async: true

  test "runs successfully with valid args" do
    Mix.Tasks.MyApp.Validate.run(["--type", "full"])
  end

  test "handles missing args gracefully" do
    assert_raise Mix.Error, fn ->
      Mix.Tasks.MyApp.Validate.run(["--invalid"])
    end
  end
end
```
