# ExUnit Patterns Reference

## Setup Chain

```elixir
describe "admin actions" do
  setup [:create_user, :make_admin, :authenticate]

  test "admin can delete user", %{conn: conn, user: user, admin: admin} do
    # All context from setup chain available
  end
end

defp create_user(_context), do: %{user: insert(:user)}
defp make_admin(%{user: user}), do: %{admin: insert(:user, role: :admin)}
defp authenticate(%{conn: conn, admin: admin}), do: %{conn: log_in_user(conn, admin)}
```

## Module Setup vs Test Setup

```elixir
# setup_all - once per module, SEPARATE PROCESS
setup_all do
  # For expensive operations that can be shared
  # CAUTION: Can't use Sandbox in async tests
  :ok
end

# setup - before each test, SAME PROCESS
setup do
  %{user: insert(:user)}
end
```

## Tags

```elixir
@moduletag :integration
@tag :slow
@tag timeout: 120_000
@tag :skip

# Run only tagged tests
# mix test --only integration
# mix test --exclude slow
```

## Assertions

```elixir
# Pattern matching (preferred)
assert {:ok, %User{name: name}} = create_user(attrs)
assert name == "Jane"

# Guards in pattern
assert match?({:ok, %{id: id}} when is_integer(id), result)

# Messages - waits up to timeout
assert_receive {:user_created, user}, 5000

# Messages - must already be in mailbox
assert_received {:notification, _}

# Refute (prefer assert with negation for clarity)
refute User.admin?(user)

# Exceptions
assert_raise ArithmeticError, fn -> 1 / 0 end
assert_raise Ecto.NoResultsError, ~r/could not find/, fn -> Repo.get!(User, -1) end

# Numeric with delta
assert_in_delta 1.1, 1.15, 0.1
```

## DataCase Template

```elixir
defmodule MyApp.DataCase do
  use ExUnit.CaseTemplate

  using do
    quote do
      alias MyApp.Repo
      import Ecto
      import Ecto.Changeset
      import Ecto.Query
      import MyApp.DataCase
      import MyApp.Factory
    end
  end

  setup tags do
    MyApp.DataCase.setup_sandbox(tags)
    :ok
  end

  def setup_sandbox(tags) do
    pid = Ecto.Adapters.SQL.Sandbox.start_owner!(MyApp.Repo, shared: not tags[:async])
    on_exit(fn -> Ecto.Adapters.SQL.Sandbox.stop_owner(pid) end)
  end

  def errors_on(changeset) do
    Ecto.Changeset.traverse_errors(changeset, fn {msg, opts} ->
      Regex.replace(~r"%{(\w+)}", msg, fn _, key ->
        opts |> Keyword.get(String.to_existing_atom(key), key) |> to_string()
      end)
    end)
  end
end
```

## ConnCase Template

```elixir
defmodule MyAppWeb.ConnCase do
  use ExUnit.CaseTemplate

  using do
    quote do
      import Plug.Conn
      import Phoenix.ConnTest
      import MyAppWeb.ConnCase
      import MyApp.Factory
      @endpoint MyAppWeb.Endpoint
      use MyAppWeb, :verified_routes
    end
  end

  setup tags do
    MyApp.DataCase.setup_sandbox(tags)
    {:ok, conn: Phoenix.ConnTest.build_conn()}
  end

  def log_in_user(conn, user) do
    token = MyApp.Accounts.generate_user_session_token(user)
    conn
    |> Phoenix.ConnTest.init_test_session(%{})
    |> Plug.Conn.put_session(:user_token, token)
  end
end
```

## CI Partitioning

Split tests across CI machines for faster runs:

```bash
# CI config — run with 4 partitions
MIX_TEST_PARTITION=1 mix test --partitions 4
MIX_TEST_PARTITION=2 mix test --partitions 4
# etc.
```

Database per partition in `config/test.exs`:

```elixir
config :my_app, MyApp.Repo,
  database: "my_app_test#{System.get_env("MIX_TEST_PARTITION")}",
  pool: Ecto.Adapters.SQL.Sandbox
```

## Seed-Based Flaky Test Debugging

ExUnit randomizes test order by default. When tests fail
intermittently, re-run with the specific seed:

```bash
# Failed run shows seed
mix test  # "Randomized with seed 401472"

# Reproduce exact order
mix test --seed 401472
```

If tests pass with `--seed` but fail randomly, you have
state leakage between tests. Check:

- Shared ETS tables or Application env
- Global Mox mode without cleanup
- Missing Sandbox ownership

## Running Test Subsets

```bash
mix test test/file_test.exs         # Single file
mix test test/file_test.exs:42      # Single test at line
mix test test/my_app_web/           # Directory
mix test --only integration         # Tagged tests
mix test --exclude slow             # Exclude tagged
mix test --failed                   # Re-run failures only
```

## Filtering Verbose Test Output

When `--trace` or E2E test output (Playwright, Wallaby) is too
noisy, filter for signal:

```bash
# ExUnit --trace: show only test names and summary
mix test test/file_test.exs --trace 2>&1 | \
  grep -E '(^\s+\* test|^\s+\d+\) test|\d+ tests|failures)'

# Playwright (via phoenix_test_playwright): filter results
MIX_ENV=int_test mix test test/features/file_test.exs --trace 2>&1 | \
  grep -E '(test |Finished|failure|✓|✗|success|Failed|assert|Error|PASS|FAIL|\d+ tests)' | \
  tail -20
```

**Rule**: When running E2E tests, always pipe through a filter
to extract pass/fail signal. Raw output is too noisy to read
in Claude Code.
