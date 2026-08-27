# OAuth Account Linking Patterns

## Progressive Resolution Pattern

When a user authenticates via OAuth, resolve their identity in order:

```elixir
def find_or_create_user_from_oauth(%Ueberauth.Auth{} = auth) do
  email = auth.info.email
  provider = to_string(auth.provider)
  uid = to_string(auth.uid)

  # 1. Check for existing identity (same provider + uid)
  case Repo.get_by(UserIdentity, provider: provider, uid: uid) do
    %UserIdentity{} = identity ->
      {:ok, Repo.preload(identity, :user).user}

    nil ->
      # 2. Check for existing user by email (link accounts)
      case Repo.get_by(User, email: email) do
        %User{} = user ->
          link_identity(user, auth)

        nil ->
          # 3. Create new user with identity
          create_user_with_identity(auth)
      end
  end
end
```

## Identity Linking

```elixir
defp link_identity(user, auth) do
  %UserIdentity{}
  |> UserIdentity.changeset(%{
    user_id: user.id,
    provider: to_string(auth.provider),
    uid: to_string(auth.uid),
    provider_token: auth.credentials.token,
    provider_refresh_token: auth.credentials.refresh_token,
    provider_token_expires_at: token_expiry(auth)
  })
  |> Repo.insert()
  |> case do
    {:ok, _identity} -> {:ok, user}
    {:error, changeset} -> {:error, changeset}
  end
end
```

## Schema Design

```elixir
defmodule MyApp.Accounts.UserIdentity do
  use Ecto.Schema

  schema "user_identities" do
    field :provider, :string
    field :uid, :string
    # Encrypt tokens at rest
    field :provider_token, MyApp.Encrypted.Binary
    field :provider_refresh_token, MyApp.Encrypted.Binary
    field :provider_token_expires_at, :utc_datetime

    belongs_to :user, MyApp.Accounts.User

    timestamps()
  end

  # Composite unique index
  # add_index :user_identities, [:provider, :uid], unique: true
end
```

## Token Refresh Pattern

```elixir
def refresh_token_if_expired(%UserIdentity{} = identity) do
  if token_expired?(identity) do
    case refresh_oauth_token(identity) do
      {:ok, new_token, new_refresh, new_expiry} ->
        identity
        |> UserIdentity.token_changeset(%{
          provider_token: new_token,
          provider_refresh_token: new_refresh,
          provider_token_expires_at: new_expiry
        })
        |> Repo.update()

      {:error, _reason} ->
        # Token refresh failed - user needs to re-authenticate
        {:error, :reauth_required}
    end
  else
    {:ok, identity}
  end
end

defp token_expired?(%{provider_token_expires_at: nil}), do: false
defp token_expired?(%{provider_token_expires_at: expires_at}) do
  DateTime.compare(expires_at, DateTime.utc_now()) == :lt
end
```

## Multiple Providers Per User

```elixir
# User can have multiple identities
def list_user_identities(user) do
  UserIdentity
  |> where(user_id: ^user.id)
  |> Repo.all()
end

def unlink_identity(user, provider) do
  case Repo.get_by(UserIdentity, user_id: user.id, provider: provider) do
    nil ->
      {:error, :not_found}

    identity ->
      # Ensure user has another way to log in
      if has_password?(user) or identity_count(user) > 1 do
        Repo.delete(identity)
      else
        {:error, :last_auth_method}
      end
  end
end
```

## Security Considerations

1. **Email verification** - Only link if OAuth provider verified the email
2. **Encrypt tokens** - Use Cloak or similar for tokens at rest
3. **GDPR consent** - May need explicit consent for new accounts
4. **Token scope** - Request minimal scopes needed
5. **Refresh token rotation** - Implement rotation if provider supports it

```elixir
# Check email verification from provider
defp email_verified?(%Ueberauth.Auth{} = auth) do
  case auth.provider do
    :google -> auth.extra.raw_info["email_verified"] == true
    :github -> auth.info.email != nil  # GitHub only returns verified emails
    _ -> false
  end
end

def find_or_create_user_from_oauth(auth) do
  if email_verified?(auth) do
    # Proceed with linking
    do_find_or_create(auth)
  else
    {:error, :email_not_verified}
  end
end
```

## Migration

```elixir
def change do
  create table(:user_identities) do
    add :provider, :string, null: false
    add :uid, :string, null: false
    add :provider_token, :binary  # Encrypted
    add :provider_refresh_token, :binary  # Encrypted
    add :provider_token_expires_at, :utc_datetime
    add :user_id, references(:users, on_delete: :delete_all), null: false

    timestamps()
  end

  create unique_index(:user_identities, [:provider, :uid])
  create index(:user_identities, [:user_id])
end
```
