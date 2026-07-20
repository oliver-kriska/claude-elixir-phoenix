# Documentation Patterns

## Contents

- [@moduledoc Templates](#moduledoc-templates)
- [@doc Templates](#doc-templates)
- [ADR Template](#adr-template)
- [README Section Template](#readme-section-template)

## @moduledoc Templates

### Context Module

```elixir
defmodule MyApp.Accounts do
  @moduledoc """
  The Accounts context manages user registration, authentication, and profile management.

  This context is the public API for all user-related operations. Controllers and
  LiveViews should call functions here rather than accessing schemas directly.

  ## Functions

  ### Registration

    * `register_user/1` - Creates a new user account
    * `confirm_user/1` - Confirms email address

  ### Authentication

    * `authenticate_user/2` - Validates credentials
    * `create_session/1` - Creates a new session

  ## Examples

      iex> Accounts.register_user(%{email: "user@example.com", password: "secret123"})
      {:ok, %User{}}

      iex> Accounts.authenticate_user("user@example.com", "wrong")
      {:error, :invalid_credentials}

  """
end
```

### Schema Module

```elixir
defmodule MyApp.Accounts.User do
  @moduledoc """
  Schema representing a user account.

  ## Fields

    * `email` - User's email address (unique, required)
    * `password_hash` - Argon2 hashed password
    * `confirmed_at` - When email was confirmed (nil if unconfirmed)
    * `role` - User role: `:member` | `:admin`

  ## Changesets

    * `registration_changeset/2` - For new user registration
    * `password_changeset/2` - For password changes
    * `email_changeset/2` - For email changes

  ## Associations

    * `posts` - Has many posts
    * `comments` - Has many comments

  """
end
```

### LiveView Module

```elixir
defmodule MyAppWeb.UserRegistrationLive do
  @moduledoc """
  LiveView for user registration.

  ## Assigns

    * `form` - The registration form changeset
    * `trigger_submit` - Whether to trigger form submission

  ## Events

    * `"save"` - Submits registration form
    * `"validate"` - Validates form on change

  ## Example

      live "/users/register", UserRegistrationLive, :new

  """
end
```

### GenServer Module

```elixir
defmodule MyApp.RateLimiter do
  @moduledoc """
  GenServer that tracks request rates per IP address.

  ## Why a GenServer?

  This uses a GenServer (rather than ETS or Agent) because:
  - Needs periodic cleanup of expired entries (handle_info)
  - Coordinates with external rate limit service
  - Requires atomic check-and-increment operations

  ## State

  Map of IP addresses to request counts and timestamps:

      %{
        {192, 168, 1, 1} => %{count: 5, window_start: ~U[...]},
        ...
      }

  ## Configuration

      config :my_app, MyApp.RateLimiter,
        max_requests: 100,
        window_seconds: 60

  ## Usage

      case RateLimiter.check("192.168.1.1") do
        :ok -> proceed()
        {:error, :rate_limited} -> return_429()
      end

  """
end
```

### Oban Worker

```elixir
defmodule MyApp.Workers.SendEmailWorker do
  @moduledoc """
  Oban worker for sending emails asynchronously.

  ## Idempotency

  Uses `email_id` as idempotency key. Safe to retry - checks if email
  already sent before processing.

  ## Args

    * `"email_id"` - ID of the Email record to send
    * `"template"` - Email template name

  ## Queues

  Runs on `:mailers` queue with rate limiting.

  ## Example

      %{email_id: 123, template: "welcome"}
      |> SendEmailWorker.new()
      |> Oban.insert()

  """
end
```

## @doc Templates

### Context Function

```elixir
@doc """
Creates a magic link token for passwordless authentication.

Generates a secure random token, stores it in the database with an expiration
time, and returns the token for inclusion in an email link.

## Parameters

  * `user` - The user to create a token for
  * `opts` - Options
    * `:expires_in` - Token lifetime in seconds (default: 86400)

## Returns

  * `{:ok, token}` - The magic link token string
  * `{:error, changeset}` - If token creation fails

## Examples

    iex> Auth.create_magic_token(user)
    {:ok, "abc123..."}

    iex> Auth.create_magic_token(user, expires_in: 3600)
    {:ok, "def456..."}

"""
@spec create_magic_token(User.t(), keyword()) :: {:ok, String.t()} | {:error, Ecto.Changeset.t()}
def create_magic_token(user, opts \\ [])
```

### Query Function

```elixir
@doc """
Lists users matching the given criteria.

## Parameters

  * `criteria` - Keyword list of filters
    * `:role` - Filter by role
    * `:confirmed` - Filter by confirmation status
    * `:search` - Search in email/name
  * `opts` - Pagination options
    * `:page` - Page number (default: 1)
    * `:per_page` - Items per page (default: 20)

## Returns

A list of users (may be empty).

## Examples

    iex> Accounts.list_users(role: :admin)
    [%User{role: :admin}, ...]

    iex> Accounts.list_users(search: "john", page: 2)
    [%User{}, ...]

"""
```

### LiveView Event Handler

```elixir
@doc """
Handles the "save" event from the registration form.

Attempts to register the user. On success, redirects to confirmation page.
On failure, re-renders form with errors.

## Parameters

  * `params` - Form parameters with "user" key
  * `socket` - LiveView socket

## Returns

Updated socket, either:
  * Redirected to confirmation page on success
  * Re-rendered with form errors on failure

"""
def handle_event("save", %{"user" => params}, socket)
```

## ADR Template

```markdown
# ADR-{number}: {Title}

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Deprecated | Superseded by ADR-X
**Deciders**: {who made the decision}
**Technical Story**: {link to issue/PR if applicable}

## Context and Problem Statement

{Describe the context and problem in 2-3 sentences. What forces are at play?
What decision needs to be made?}

## Decision Drivers

* {driver 1, e.g., performance requirement}
* {driver 2, e.g., team familiarity}
* {driver 3, e.g., maintenance burden}

## Considered Options

1. {Option 1}
2. {Option 2}
3. {Option 3}

## Decision Outcome

Chosen option: **"{Option X}"**, because {justification}.

### Positive Consequences

* {positive consequence 1}
* {positive consequence 2}

### Negative Consequences

* {negative consequence 1}
* {mitigation for negative consequence}

## Pros and Cons of the Options

### {Option 1}

{Description}

* Good, because {argument a}
* Good, because {argument b}
* Bad, because {argument c}

### {Option 2}

{Description}

* Good, because {argument a}
* Bad, because {argument b}
* Bad, because {argument c}

## Links

* {Link to related ADR}
* {Link to relevant documentation}
* {Link to discussion/issue}
```

## README Section Template

````markdown
## {Feature Name}

{One paragraph description of what this feature does and why it exists.}

### Configuration

```elixir
config :my_app, :feature_name,
  option_a: "value",
  option_b: 123
```

### Usage

```elixir
MyApp.Feature.do_thing()
```

### Troubleshooting

**Problem**: {Common issue}
**Solution**: {How to fix}
````
