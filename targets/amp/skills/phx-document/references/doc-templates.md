# Documentation Templates

## @moduledoc Template

```elixir
@moduledoc """
{Brief description of module purpose}.

## Usage

    iex> MyApp.Module.function(arg)
    :result

## Options

  * `:option` - Description of option

## Examples

    # Example usage
    MyApp.Module.do_thing()

"""
```

## @doc Template

```elixir
@doc """
{Brief description}.

## Parameters

  * `param` - Description

## Returns

  * `{:ok, result}` - On success
  * `{:error, reason}` - On failure

## Examples

    iex> function(:arg)
    {:ok, :result}

"""
```

## README Section Template

For features users interact with:

````markdown
## {Feature Name}

{Brief description}

### Configuration

```elixir
# config/config.exs
config :my_app, :feature,
  option: value
```

### Usage

{How to use the feature}
````

## ADR Template

Create `docs/adr/{number}-{title}.md`:

```markdown
# ADR-{n}: {Title}

**Date**: {date}
**Status**: Accepted
**Context**: {Why this decision was needed}

## Decision

{What was decided}

## Consequences

### Positive

- {benefit}

### Negative

- {tradeoff}

## Alternatives Considered

### {Alternative 1}

- Rejected because: {reason}
```
