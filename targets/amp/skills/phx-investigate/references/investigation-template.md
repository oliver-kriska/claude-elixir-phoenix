# Investigation Output Template

Return this structure in the current session; do not write a report file unless the user explicitly asks for one:

````markdown
# Bug Investigation: <bug description>

## Error

```
{exact error message}
```

## Reproduction

```bash
{command to reproduce}
```

## Ralph Wiggum Checklist

- [x] File saved? YES
- [x] Compiled? YES
- [ ] Correct key type? **NO - FOUND IT**
- [ ] Data exists? Not checked

## Root Cause

**What's wrong**: Using string key "user_id" but map has atom :user_id

**Where**: lib/my_app_web/controllers/user_controller.ex:45

**Why missed**: External API returns string keys, internal code uses atoms

## Fix

```elixir
# Before
def show(conn, %{"user_id" => id}) do
  user = Accounts.get_user(params["user_id"])  # params has string keys!

# After
def show(conn, %{"user_id" => id}) do
  user = Accounts.get_user(id)  # Already extracted
```

## Prevention

- Add test with external API mock
- Add typespec to catch at compile time
````
