#!/usr/bin/env bash
# Minimal Phoenix-shaped project so routing sees a realistic workspace:
# mix.exs (gates route-intent/check-resume hooks), a context, a schema,
# a LiveView, a test, and one uncommitted change for "verify my changes".
set -euo pipefail

mkdir -p lib/my_app/accounts lib/my_app_web/live test/my_app config priv/repo/migrations

cat > mix.exs <<'MIX'
defmodule MyApp.MixProject do
  use Mix.Project

  def project do
    [app: :my_app, version: "0.1.0", elixir: "~> 1.17", deps: deps()]
  end

  def application, do: [mod: {MyApp.Application, []}, extra_applications: [:logger]]

  defp deps do
    [
      {:phoenix, "~> 1.8"},
      {:phoenix_live_view, "~> 1.1"},
      {:phoenix_ecto, "~> 4.6"},
      {:ecto_sql, "~> 3.13"},
      {:postgrex, ">= 0.0.0"},
      {:oban, "~> 2.19"}
    ]
  end
end
MIX

cat > lib/my_app/accounts.ex <<'EX'
defmodule MyApp.Accounts do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User

  def list_users, do: Repo.all(from u in User, order_by: u.inserted_at)
  def get_user!(id), do: Repo.get!(User, id)

  def create_user(attrs) do
    %User{} |> User.changeset(attrs) |> Repo.insert()
  end
end
EX

cat > lib/my_app/accounts/user.ex <<'EX'
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    timestamps()
  end

  def changeset(user, attrs) do
    user |> cast(attrs, [:email, :name]) |> validate_required([:email])
  end
end
EX

cat > lib/my_app_web/live/user_live.ex <<'EX'
defmodule MyAppWeb.UserLive do
  use MyAppWeb, :live_view
  alias MyApp.Accounts

  def mount(_params, _session, socket) do
    {:ok, assign(socket, users: Accounts.list_users())}
  end

  def render(assigns) do
    ~H"""
    <ul><li :for={u <- @users}>{u.email}</li></ul>
    """
  end
end
EX

cat > test/my_app/accounts_test.exs <<'EX'
defmodule MyApp.AccountsTest do
  use MyApp.DataCase, async: true
  alias MyApp.Accounts

  test "create_user/1 requires email" do
    assert {:error, _} = Accounts.create_user(%{})
  end
end
EX

git init -q -b main
git -c user.email=eval@example.com -c user.name=eval add -A
git -c user.email=eval@example.com -c user.name=eval commit -q -m "Initial app"

# One uncommitted change so "verify/review my changes" prompts have a diff.
sed -i.bak 's/validate_required(\[:email\])/validate_required([:email, :name])/' lib/my_app/accounts/user.ex
rm -f lib/my_app/accounts/user.ex.bak
