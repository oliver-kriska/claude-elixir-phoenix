# Elixir Documentation Best Practices

## @moduledoc

- First line: One sentence summary
- Include `## Usage` with iex examples
- Include `## Options` if configurable
- Link to related modules with `See also`

## @doc

- First line: What it does (imperative)
- `## Parameters` with types
- `## Returns` with tagged tuples
- `## Examples` with iex

## Typespecs

Always pair @doc with @spec:

```elixir
@doc "Creates a magic token for the given user."
@spec create_magic_token(User.t()) :: {:ok, MagicToken.t()} | {:error, Ecto.Changeset.t()}
def create_magic_token(%User{} = user) do
  # ...
end
```
