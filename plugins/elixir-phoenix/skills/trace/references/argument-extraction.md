# Argument Extraction

Techniques for extracting argument patterns from call sites.

## Why Arguments Matter

Knowing "who calls" isn't enough. **HOW** they call reveals:

- Data flow through the system
- Where nil values originate
- Pattern mismatches (string vs atom keys)
- Missing validations

## Basic Extraction

### From Call Site Line

```elixir
# Call site: lib/web/controllers/user_controller.ex:45
Accounts.update_user(user, attrs)

# Extract:
# Arg 1: `user` - variable
# Arg 2: `attrs` - variable

# Need to trace where these variables come from in the same function
```

### Trace Variable Origins

```elixir
def update(conn, %{"id" => id, "user" => user_params}) do
  user = Accounts.get_user!(id)         # <- user comes from DB query
  attrs = sanitize_params(user_params)  # <- attrs comes from params + transform

  case Accounts.update_user(user, attrs) do  # <- call site
    {:ok, user} -> redirect(conn, to: ~p"/users/#{user}")
    {:error, changeset} -> render(conn, :edit, changeset: changeset)
  end
end

# Full trace:
# user = Accounts.get_user!(id) where id = params["id"] (string!)
# attrs = sanitize_params(user_params) where user_params = params["user"]
```

## Common Argument Patterns

### Direct from Params (Controller)

```elixir
def create(conn, %{"user" => user_params}) do
  Accounts.create_user(user_params)
  #                    ^^^^^^^^^^^
  # Source: conn.params["user"] (STRING KEYS!)
end
```

### From Socket Assigns (LiveView)

```elixir
def handle_event("save", %{"user" => params}, socket) do
  Accounts.update_user(socket.assigns.current_user, params)
  #                    ^^^^^^^^^^^^^^^^^^^^^^^^^   ^^^^^^
  # Source 1: socket.assigns (set in mount)
  # Source 2: event params (STRING KEYS from form!)
end
```

### From Job Args (Oban)

```elixir
def perform(%Oban.Job{args: %{"user_id" => user_id}}) do
  user = Accounts.get_user!(user_id)
  Accounts.sync_user(user)
  #                  ^^^^
  # Source: DB query using job.args["user_id"]
end
```

### Piped/Transformed

```elixir
users
|> Enum.map(&Accounts.update_user(&1, %{status: :active}))
#                                 ^^
# Source: element from `users` list (need to trace where users comes from)
```

## AST-Based Extraction (Advanced)

Using Sourceror for precise extraction:

```elixir
defmodule ArgumentExtractor do
  def extract_call_args(file_path, line, {target_mod, target_fun, _arity}) do
    file_path
    |> File.read!()
    |> Sourceror.parse_string!()
    |> find_call_at_line(line, target_mod, target_fun)
    |> extract_args()
  end

  defp find_call_at_line(ast, target_line, target_mod, target_fun) do
    {_ast, result} = Macro.prewalk(ast, nil, fn
      # Remote call: Module.function(args)
      {{:., meta, [{:__aliases__, _, mod_parts}, fun_name]}, _, args} = node, acc ->
        if meta[:line] == target_line and
           Module.concat(mod_parts) == target_mod and
           fun_name == target_fun do
          {node, args}
        else
          {node, acc}
        end

      node, acc ->
        {node, acc}
    end)

    result
  end

  defp extract_args(nil), do: []
  defp extract_args(args), do: Enum.map(args, &arg_to_string/1)

  defp arg_to_string({var, _, nil}) when is_atom(var), do: "#{var}"
  defp arg_to_string({{:., _, [Access, :get]}, _, [base, key]}), do: "#{arg_to_string(base)}[#{inspect(key)}]"
  defp arg_to_string({:@, _, [{name, _, _}]}), do: "@#{name}"
  defp arg_to_string(literal) when is_binary(literal), do: inspect(literal)
  defp arg_to_string(literal) when is_atom(literal), do: inspect(literal)
  defp arg_to_string(literal) when is_number(literal), do: inspect(literal)
  defp arg_to_string(_), do: "<complex expression>"
end
```

## Grep-Based Extraction (Simpler)

When AST parsing is overkill:

```bash
# Get the line with context
sed -n '43,47p' lib/web/controllers/user_controller.ex

# Output:
#   user = Accounts.get_user!(id)
#
#   case Accounts.update_user(user, params) do
#     {:ok, user} -> redirect(conn, to: ~p"/users/#{user}")
```

Then parse visually or with simple regex.

## Documenting Arguments in Call Tree

Format for clarity:

```markdown
## Call Site: lib/web/controllers/user_controller.ex:45

**Call:** `Accounts.update_user(user, attrs)`

**Arguments:**
1. `user` - Variable
   - Defined at line 42: `user = Accounts.get_user!(id)`
   - Origin: Database query using `params["id"]`

2. `attrs` - Variable
   - Defined at line 43: `attrs = params["user"]`
   - Origin: Request params (string keys!)

**Data Flow:**
```

HTTP Request → params["id"] → DB Query → user
→ params["user"] → attrs
→ update_user(user, attrs)

```
```

## Key Patterns to Flag

### String vs Atom Key Mismatch

```elixir
# Controller receives string keys
def update(conn, %{"user" => params}) do
  # But internal function might expect atom keys
  Accounts.update_user(user, params)  # ⚠️ params has string keys!
end
```

### Nil Propagation Risk

```elixir
# get_user returns nil on not found
user = Accounts.get_user(id)  # might be nil!
Accounts.update_user(user, attrs)  # ⚠️ passing nil?

# vs safe version
user = Accounts.get_user!(id)  # raises on nil
```

### Unvalidated External Data

```elixir
def perform(%Oban.Job{args: args}) do
  # args comes from untrusted source (whoever enqueued the job)
  Accounts.delete_user!(args["user_id"])  # ⚠️ no validation!
end
```

## Integration with Call Tracer

When building call tree, for each call site:

1. Read 10 lines before call site (variable definitions)
2. Extract argument expressions from call
3. Trace each argument to its origin
4. Note any transformations
5. Flag potential issues (nil, string keys, unvalidated)

```markdown
├─► MyAppWeb.UserController.update/2
│   └── lib/my_app_web/controllers/user_controller.ex:45
│       **Arguments:**
│       - `user`: from `Accounts.get_user!(params["id"])` ✓
│       - `attrs`: from `params["user"]` ⚠️ string keys
```
