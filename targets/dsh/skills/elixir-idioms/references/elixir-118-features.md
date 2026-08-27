# Elixir 1.18 Features Reference

> **Official changelog**: <https://github.com/elixir-lang/elixir/blob/main/CHANGELOG.md>
> **HexDocs**: <https://hexdocs.pm/elixir/> — Use `hexdocs-fetcher` for latest API docs.

## Duration Module (Elixir 1.18+)

Native duration representation without external dependencies.

### Creating Durations

```elixir
# From keyword list
Duration.new!(hour: 2, minute: 30)
#=> %Duration{hour: 2, minute: 30}

# Common units
Duration.new!(day: 7)
Duration.new!(week: 1)
Duration.new!(second: 3600)

# Negative durations
Duration.new!(hour: -1)
```

### Duration Arithmetic

```elixir
# Adding durations
Duration.add(Duration.new!(hour: 1), Duration.new!(minute: 30))
#=> %Duration{hour: 1, minute: 30}

# Adding to DateTime/NaiveDateTime
DateTime.add(DateTime.utc_now(), Duration.new!(hour: 24))

# Subtracting
DateTime.add(DateTime.utc_now(), Duration.negate(Duration.new!(day: 7)))
```

### Duration in Oban Jobs

```elixir
# Schedule job for specific duration from now
defmodule MyApp.Workers.ReminderWorker do
  use Oban.Worker

  def schedule_reminder(user_id, delay_duration) do
    scheduled_at = DateTime.add(DateTime.utc_now(), delay_duration)

    %{user_id: user_id}
    |> new(scheduled_at: scheduled_at)
    |> Oban.insert()
  end
end

# Usage
ReminderWorker.schedule_reminder(user.id, Duration.new!(day: 3))
```

### Duration in Cache TTLs

```elixir
# With Cachex or similar
def get_user_with_cache(user_id) do
  Cachex.fetch(:users_cache, user_id,
    ttl: Duration.to_milliseconds(Duration.new!(hour: 1))
  )
end

# Convert to different units
Duration.to_seconds(Duration.new!(hour: 2))
#=> 7200

Duration.to_milliseconds(Duration.new!(minute: 5))
#=> 300_000
```

### Anti-patterns

```elixir
# AVOID: Magic numbers for time
Process.send_after(self(), :timeout, 3600_000)  # What unit? Confusing!

# PREFER: Duration makes intent clear
Process.send_after(self(), :timeout,
  Duration.to_milliseconds(Duration.new!(hour: 1)))

# AVOID: Manual arithmetic
scheduled_at = DateTime.add(now, 7 * 24 * 60 * 60, :second)

# PREFER: Readable duration
scheduled_at = DateTime.add(now, Duration.new!(week: 1))
```

## Enhanced dbg/2 (Elixir 1.18+)

### Pipeline Debugging

```elixir
# dbg shows each pipeline step
users
|> Enum.filter(&(&1.active))
|> dbg()  # Shows filter result
|> Enum.map(&(&1.name))
|> dbg()  # Shows map result
|> Enum.sort()
```

### Customizing Output

```elixir
# In IEx or tests, customize dbg behavior
# config/dev.exs
config :elixir, :dbg_callback, {MyApp.Debug, :custom_dbg, []}

# Custom module
defmodule MyApp.Debug do
  def custom_dbg(code, options, env) do
    # Custom formatting, logging, etc.
    Macro.dbg(code, options, env)
  end
end
```

## Calendar.strftime/2 Improvements

```elixir
# ISO week numbers
Calendar.strftime(~D[2026-02-05], "%G-W%V")
#=> "2026-W06"

# 12-hour format with AM/PM
Calendar.strftime(~T[14:30:00], "%I:%M %p")
#=> "02:30 PM"

# Full datetime formatting
Calendar.strftime(DateTime.utc_now(), "%Y-%m-%d %H:%M:%S %Z")
#=> "2026-02-05 10:30:45 UTC"
```

## Deprecations in 1.18

### `unless/2` Deprecated

`unless` is soft-deprecated in Elixir 1.18. The formatter
automatically rewrites `unless condition` to `if !condition`.

```elixir
# Deprecated — formatter will rewrite
unless valid?(input) do
  {:error, :invalid}
end

# Current — what the formatter produces
if !valid?(input) do
  {:error, :invalid}
end
```

**Rule**: Never write `unless` — always use `if !` or
pattern match instead. This avoids unnecessary formatter churn.

## Compatibility Notes

- Duration requires Elixir 1.18+
- For projects on 1.17 or earlier, use Timex or manual arithmetic
- Check version in mix.exs: `{:elixir, "~> 1.18"}`
