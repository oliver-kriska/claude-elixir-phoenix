# Quick Debug Commands & Common Fixes

## Quick Debug Commands

Common debug commands:

- Clean rebuild: `rm -rf _build deps && mix deps.get && mix compile`
- Check module exports: `mix run -e "IO.inspect MyModule.__info__(:functions)"`
- Interactive debugging: `iex -S mix phx.server` (then `recompile()`)
- Run single test with output: `mix test test/file_test.exs:42 --trace`

## Common Fixes

### String vs Atom Keys

```elixir
# External data (JSON, params) = strings
params["key"]

# Internal data = atoms
struct.field
map.key
```

### Missing Preload

```elixir
# Before
user = Repo.get(User, id)
user.posts  # BOOM

# After
user = Repo.get(User, id) |> Repo.preload(:posts)
```

### Nil Propagation

```elixir
# Before
user.profile.name  # Crashes if profile nil

# After
case user.profile do
  nil -> nil
  profile -> profile.name
end
# Or use get_in/2
```

## Telemetry-Based Debugging

When Tidewave is unavailable, use telemetry to diagnose
performance and behavior issues:

```elixir
# Attach a temporary handler to see all Ecto queries
:telemetry.attach(
  "debug-queries",
  [:my_app, :repo, :query],
  fn _event, measurements, metadata, _config ->
    IO.puts("Query: #{metadata.query}")
    IO.puts("  Time: #{measurements.total_time / 1_000_000}ms")
  end,
  nil
)
# Detach when done: :telemetry.detach("debug-queries")
```

### Common Telemetry Events to Attach

| Event | What It Shows |
|-------|---------------|
| `[:my_app, :repo, :query]` | All Ecto queries with timing |
| `[:phoenix, :endpoint, :stop]` | Request duration |
| `[:phoenix, :router_dispatch, :stop]` | Per-route timing |
| `[:oban, :job, :stop]` | Oban job execution time |
| `[:oban, :job, :exception]` | Oban job failures |

### LiveDashboard in Dev

Add to router for real-time metrics visualization:

```elixir
if Mix.env() in [:dev, :test] do
  import Phoenix.LiveDashboard.Router

  scope "/" do
    pipe_through :browser
    live_dashboard "/dashboard",
      metrics: MyAppWeb.Telemetry
  end
end
```
