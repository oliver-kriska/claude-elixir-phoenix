# Mox Patterns Reference

## Setup

```elixir
# 1. Define behaviour
defmodule MyApp.WeatherAPI do
  @callback get_temperature(String.t()) :: {:ok, float()} | {:error, term()}

  def get_temperature(city), do: impl().get_temperature(city)
  defp impl, do: Application.get_env(:my_app, :weather_api, MyApp.OpenWeatherAPI)
end

# 2. Define mock in test/support/mocks.ex
Mox.defmock(MyApp.MockWeatherAPI, for: MyApp.WeatherAPI)

# 3. Configure in test_helper.exs
Application.put_env(:my_app, :weather_api, MyApp.MockWeatherAPI)
```

## Usage

```elixir
import Mox

setup :verify_on_exit!

test "fetches temperature" do
  expect(MockWeatherAPI, :get_temperature, fn "Chicago" ->
    {:ok, 72.0}
  end)

  assert {:ok, temp} = Weather.current_temp("Chicago")
  assert temp == 72.0
end

# Stub for default behavior (not verified)
stub(MockWeatherAPI, :get_temperature, fn _ -> {:ok, 70.0} end)

# Multiple calls
expect(MockWeatherAPI, :get_temperature, 3, fn _ -> {:ok, 70.0} end)
```

## Async Tests with Mox

```elixir
# For spawned processes - allow parent's expectations
test "task uses parent's mock" do
  expect(MockAPI, :fetch, fn _ -> {:ok, "data"} end)
  parent = self()

  Task.async(fn ->
    Mox.allow(MockAPI, parent, self())
    # Now can use mock
  end)
  |> Task.await()
end

# For GenServers - use global mode (requires async: false!)
setup do
  set_mox_global()
  verify_on_exit!()
  :ok
end
```

## expect vs stub

| Function | Verification | Use When |
|----------|--------------|----------|
| `expect/4` | Verified on exit | Testing specific call with specific args |
| `stub/3` | NOT verified | Default behavior, not testing the call |

## Anti-patterns

```elixir
# ❌ Missing verify_on_exit!
setup do
  expect(MockAPI, :call, fn _ -> :ok end)
  :ok  # Missing verify_on_exit!()
end

# ❌ async: true with Mox global mode
use MyApp.DataCase, async: true
setup do
  set_mox_global()  # Race conditions!
end

# ❌ Mocking internal modules
Mox.defmock(MockRepo, for: Ecto.Repo)  # Never mock the database!
```
