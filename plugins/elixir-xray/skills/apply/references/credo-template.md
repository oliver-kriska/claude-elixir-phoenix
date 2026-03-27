# Credo Check Template

Use this template when generating custom Credo checks.

## Standard Check Structure

```elixir
defmodule MyApp.Credo.Check.Warning.EnforceGettextInHeex do
  @moduledoc """
  Checks that user-facing strings in HEEX templates use gettext.

  Hardcoded strings bypass the translation pipeline and create
  maintenance burden when adding new locales.

  ## Configuration

      # .credo.exs
      {MyApp.Credo.Check.Warning.EnforceGettextInHeex, []}
  """

  @explanation [
    check: @moduledoc,
    params: []
  ]

  use Credo.Check, base_priority: :high, category: :warning

  @doc false
  def run(%SourceFile{} = source_file, params \\\\ []) do
    issue_meta = IssueMeta.for(source_file, params)

    source_file
    |> SourceFile.source()
    |> String.split("\\n")
    |> Enum.with_index(1)
    |> Enum.reduce([], fn {line, line_no}, issues ->
      if violation?(line) do
        [issue_for(issue_meta, line_no, line) | issues]
      else
        issues
      end
    end)
  end

  defp violation?(line) do
    # Check logic here
    false
  end

  defp issue_for(issue_meta, line_no, trigger) do
    format_issue(
      issue_meta,
      message: "Hardcoded string found. Use gettext/1 instead.",
      trigger: trigger,
      line_no: line_no
    )
  end
end
```

## .credo.exs Configuration Snippet

```elixir
# Add to your .credo.exs under checks:
{MyApp.Credo.Check.Warning.EnforceGettextInHeex, []},
{MyApp.Credo.Check.Warning.NoRepoCallsInWeb, []},
```

## Naming Convention

- Module: `MyApp.Credo.Check.{Category}.{CheckName}`
- File: `lib/my_app/credo/check/{category}/{check_name}.ex`
- Categories: `Warning`, `Design`, `Consistency`, `Readability`

## Key Rules

1. Always include `@moduledoc` with usage instructions
2. Always include `@explanation` for `mix credo` output
3. Use `base_priority: :high` for critical checks, `:normal` for others
4. Pattern match on `%SourceFile{}` — don't read files directly
5. Return list of issues (empty list = check passes)
