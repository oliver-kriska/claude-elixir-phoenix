# Wallaby E2E Test Template

Template for generating Wallaby-based E2E tests for LiveView features.

## Setup Detection

Check for Wallaby in the project:

```bash
grep -q "wallaby" mix.exs && echo "Wallaby available"
ls config/int_test.exs 2>/dev/null && echo "Custom MIX_ENV: int_test"
```

## Basic LiveView E2E Test

```elixir
defmodule MyAppWeb.Features.UserRegistrationTest do
  use MyAppWeb.IntegrationCase  # or FeatureCase

  @moduletag :e2e

  feature "user can register with valid data", %{session: session} do
    session
    |> visit("/register")
    |> fill_in(Query.text_field("Email"), with: "test@example.com")
    |> fill_in(Query.text_field("Password"), with: "password123!")
    |> click(Query.button("Register"))
    |> assert_has(Query.text("Welcome"))
  end

  feature "user sees validation errors", %{session: session} do
    session
    |> visit("/register")
    |> click(Query.button("Register"))
    |> assert_has(Query.text("can't be blank"))
  end
end
```

## LiveView-Specific Patterns

### Waiting for Async Operations

```elixir
session
|> visit("/dashboard")
|> assert_has(Query.css(".loading-spinner"))
|> refute_has(Query.css(".loading-spinner"))  # Waits for async
|> assert_has(Query.css(".data-loaded"))
```

### Form with Live Validation

```elixir
session
|> visit("/settings")
|> fill_in(Query.text_field("Name"), with: "")
|> send_keys([:tab])  # Trigger blur validation
|> assert_has(Query.text("can't be blank"))
|> fill_in(Query.text_field("Name"), with: "Valid Name")
|> refute_has(Query.text("can't be blank"))
```

### PubSub-Driven Updates

```elixir
feature "real-time notification appears", %{session: session} do
  session
  |> visit("/dashboard")

  # Trigger update from another process
  Phoenix.PubSub.broadcast(MyApp.PubSub, "user:1", {:new_notification, %{text: "Hello"}})

  session
  |> assert_has(Query.text("Hello"))
end
```

## Running E2E Tests

```bash
# With custom MIX_ENV
MIX_ENV=int_test mix test test/features/ --trace

# Standard
mix test test/features/ --trace --include e2e
```
