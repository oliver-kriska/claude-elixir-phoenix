# Input Validation Patterns Reference

## Ecto Changesets (Primary Defense)

```elixir
def registration_changeset(user, attrs) do
  user
  |> cast(attrs, [:email, :username, :password])
  |> validate_required([:email, :username, :password])
  |> validate_format(:email, ~r/^[^\s]+@[^\s]+\.[^\s]+$/)
  |> validate_length(:username, min: 3, max: 30)
  |> validate_format(:username, ~r/^[a-zA-Z0-9_]+$/)
  |> validate_exclusion(:username, @reserved_usernames)
  |> validate_length(:password, min: 12, max: 72)
  |> unique_constraint(:email)
  |> unique_constraint(:username)
  |> hash_password()
end
```

## File Upload Validation

```elixir
@max_file_size 10_000_000
@allowed_extensions ~w(.jpg .jpeg .png .gif .pdf)
@magic_bytes %{
  ".jpg" => <<0xFF, 0xD8, 0xFF>>,
  ".png" => <<0x89, 0x50, 0x4E, 0x47>>,
  ".gif" => <<0x47, 0x49, 0x46>>,
  ".pdf" => <<0x25, 0x50, 0x44, 0x46>>
}

def validate_upload(%Plug.Upload{} = upload) do
  with :ok <- validate_extension(upload.filename),
       :ok <- validate_file_size(upload.path),
       :ok <- validate_magic_bytes(upload.path, upload.filename),
       {:ok, safe_name} <- sanitize_filename(upload.filename) do
    {:ok, %{original_name: upload.filename, safe_name: safe_name}}
  end
end

defp sanitize_filename(filename) do
  # Generate random filename to prevent path traversal
  ext = Path.extname(filename) |> String.downcase()
  {:ok, "#{Ecto.UUID.generate()}#{ext}"}
end
```

## Path Traversal Prevention

```elixir
def safe_path(base_dir, user_path) do
  case Path.safe_relative(user_path, base_dir) do
    {:ok, safe_path} -> {:ok, Path.join(base_dir, safe_path)}
    :error -> {:error, :path_traversal}
  end
end
```

## SQL Injection Prevention

```elixir
# ✅ SAFE: Parameterized queries
from(u in User, where: u.name == ^user_input)

# ✅ SAFE: Fragment with placeholders
from(u in User, where: fragment("lower(?) = lower(?)", u.email, ^email))

# ❌ VULNERABLE: String interpolation
from(u in User, where: fragment("name = '#{user_input}'"))

# ❌ VULNERABLE: Raw SQL
Repo.query("SELECT * FROM users WHERE name = '#{user_input}'")
```

## XSS Prevention

### Template Escaping

```elixir
# ✅ SAFE: Auto-escaped
<%= @user_content %>

# ❌ VULNERABLE: Raw output
<%= raw @user_content %>
```

### HTML Sanitization

```elixir
# For user-generated HTML (comments, posts)
defmodule MyApp.ContentScrubber do
  require HtmlSanitizeEx.Scrubber.Meta
  alias HtmlSanitizeEx.Scrubber.Meta

  Meta.remove_cdata_sections_before_scrub()
  Meta.strip_comments()

  # Allow safe tags only
  for tag <- ~w(p br strong em ul ol li h1 h2 h3 blockquote code pre) do
    Meta.allow_tag_with_these_attributes(tag, [])
  end

  # Allow links with safe protocols only
  Meta.allow_tag_with_uri_attributes("a", ["href"], ["https", "mailto"])

  Meta.strip_everything_not_covered()
end

# Usage
HtmlSanitizeEx.Scrubber.scrub(user_html, MyApp.ContentScrubber)
```

## Anti-patterns

```elixir
# ❌ String.to_atom with user input
String.to_atom(user_input)  # Atom table exhaustion!

# ✅ Use existing atoms
String.to_existing_atom(user_input)

# ❌ User-provided filenames directly
File.write(user_filename, content)  # Path traversal!

# ❌ :erlang.binary_to_term with untrusted data
:erlang.binary_to_term(user_input)  # Code execution!
```
