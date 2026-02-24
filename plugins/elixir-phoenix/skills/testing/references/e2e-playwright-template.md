# Playwright E2E Test Template

Template for generating PhoenixTest.Playwright-based E2E tests.

## Setup Detection

```bash
grep -q "playwright" mix.exs && echo "Playwright available"
grep -q "phoenix_test" mix.exs && echo "PhoenixTest available"
```

## Basic LiveView E2E Test

```elixir
defmodule MyAppWeb.Features.UserRegistrationPlaywrightTest do
  use MyAppWeb.PlaywrightCase  # or E2ECase

  @moduletag :e2e

  test "user can register with valid data", %{page: page} do
    page
    |> navigate("/register")
    |> fill("input[name='user[email]']", "test@example.com")
    |> fill("input[name='user[password]']", "password123!")
    |> click("button[type='submit']")
    |> assert_text("Welcome")
  end

  test "user sees validation errors", %{page: page} do
    page
    |> navigate("/register")
    |> click("button[type='submit']")
    |> assert_text("can't be blank")
  end
end
```

## LiveView-Specific Patterns

### Waiting for Async Content

```elixir
page
|> navigate("/dashboard")
|> wait_for_selector(".data-loaded", timeout: 5_000)
|> assert_text("Dashboard loaded")
```

### File Upload

```elixir
page
|> navigate("/upload")
|> set_input_files("input[type='file']", ["test/fixtures/photo.jpg"])
|> click("button[type='submit']")
|> assert_text("Upload complete")
```

## Running Playwright Tests

```bash
# Ensure Playwright browsers are installed
npx playwright install chromium

# Run tests
mix test test/e2e/ --trace --include e2e
```
