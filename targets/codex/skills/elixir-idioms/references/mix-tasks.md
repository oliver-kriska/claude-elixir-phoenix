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

## Chaining Tasks

```elixir
# Run another mix task from within a task
def run(args) do
  # Ensure app is started (needed for DB access)
  Mix.Task.run("app.start")

  # Run another task
  Mix.Task.run("ecto.migrate")

  # Your logic here
end
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
