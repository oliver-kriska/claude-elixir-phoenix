#!/usr/bin/env bash
# Atom/string key bug: update_profile/2 reads attrs[:newsletter], the LiveView
# passes string-keyed form params, and the only test passes atom keys. A
# /phx:compound doc from an earlier, related incident sits in .claude/solutions/.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=../_shared/base.sh
source "$(dirname "${BASH_SOURCE[0]}")/../_shared/base.sh"
mkdir -p test/support

cat > lib/my_app/accounts/user.ex <<'EX'
defmodule MyApp.Accounts.User do
  use Ecto.Schema
  import Ecto.Changeset

  schema "users" do
    field :email, :string
    field :name, :string
    field :newsletter, :boolean, default: false
    timestamps()
  end

  def changeset(user, attrs) do
    user |> cast(attrs, [:email, :name]) |> validate_required([:email])
  end

  def profile_changeset(user, attrs) do
    user |> cast(attrs, [:name, :newsletter]) |> validate_required([:name])
  end
end
EX

cat > lib/my_app/accounts.ex <<'EX'
defmodule MyApp.Accounts do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Newsletter
  alias MyApp.Accounts.User

  def list_users, do: Repo.all(from u in User, order_by: u.inserted_at)
  def get_user!(id), do: Repo.get!(User, id)

  def create_user(attrs) do
    %User{} |> User.changeset(attrs) |> Repo.insert()
  end

  def update_profile(%User{} = user, attrs) do
    with {:ok, user} <- user |> User.profile_changeset(attrs) |> Repo.update() do
      if attrs[:newsletter], do: Newsletter.subscribe(user.email)
      {:ok, user}
    end
  end
end
EX

cat > lib/my_app/newsletter.ex <<'EX'
defmodule MyApp.Newsletter do
  @moduledoc "Subscribes addresses with the mailing-list provider."

  def subscribe(email), do: adapter().subscribe(email)

  defp adapter, do: Application.get_env(:my_app, :newsletter_adapter, MyApp.Newsletter.HTTP)
end
EX

cat > test/support/newsletter_test_adapter.ex <<'EX'
defmodule MyApp.Newsletter.TestAdapter do
  def subscribe(email) do
    send(self(), {:newsletter_subscribed, email})
    :ok
  end
end
EX

cat > config/test.exs <<'EX'
import Config

config :my_app, :newsletter_adapter, MyApp.Newsletter.TestAdapter
EX

cat > lib/my_app_web/live/profile_live.ex <<'EX'
defmodule MyAppWeb.ProfileLive do
  use MyAppWeb, :live_view
  alias MyApp.Accounts
  alias MyApp.Accounts.User

  def mount(_params, _session, socket) do
    user = socket.assigns.current_user
    {:ok, assign(socket, form: to_form(User.profile_changeset(user, %{})))}
  end

  def handle_event("save", %{"user" => user_params}, socket) do
    case Accounts.update_profile(socket.assigns.current_user, user_params) do
      {:ok, user} ->
        {:noreply,
         socket
         |> assign(current_user: user, form: to_form(User.profile_changeset(user, %{})))
         |> put_flash(:info, "Profile updated")}

      {:error, %Ecto.Changeset{} = changeset} ->
        {:noreply, assign(socket, form: to_form(changeset))}
    end
  end

  def render(assigns) do
    ~H"""
    <.form for={@form} phx-submit="save">
      <.input field={@form[:name]} label="Name" />
      <.input field={@form[:newsletter]} type="checkbox" label="Subscribe to newsletter" />
      <button>Save</button>
    </.form>
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

  describe "update_profile/2" do
    test "subscribes to the newsletter when the user opts in" do
      {:ok, user} = Accounts.create_user(%{email: "ada@example.com", name: "Ada"})

      assert {:ok, %{newsletter: true}} = Accounts.update_profile(user, %{name: "Ada", newsletter: true})
      assert_received {:newsletter_subscribed, "ada@example.com"}
    end
  end
end
EX

mkdir -p .claude/solutions/liveview-issues
cat > .claude/solutions/liveview-issues/raw-form-params-in-side-effects.md <<'MD'
---
module: "Accounts"
date: "2026-06-14"
problem_type: logic_error
component: phoenix_context
symptoms:
  - "Users who unticked the marketing opt-in on signup still received marketing email"
root_cause: "side effect decided from raw form params: checkbox sends the string \"false\", which is truthy"
severity: medium
tags: [checkbox, params, string-keys, side-effects]
---

# Side effects decided from raw form params

## Problem

`Accounts.register_user/1` enqueued the marketing email when `attrs["marketing_opt_in"]`
was truthy. Phoenix checkboxes submit `"true"` or `"false"` (a hidden input sends
`"false"` when unticked), so every signup was opted in.

## Root cause

Contexts receive string-keyed, uncast params from LiveViews and controllers. Reading
them directly skips `cast/3`, so neither the key type nor the value type is what the
schema says.

## Solution

Decide side effects from the cast result, never from `attrs`: read the field on the
struct returned by `Repo.insert/update`, or `Ecto.Changeset.get_change/2`.

## Prevention

- Context tests must pass string-keyed params, the shape LiveView sends.
- Grep for `attrs[:` and `attrs["` in contexts during review.
MD

commit "Add profile page with newsletter opt-in"
