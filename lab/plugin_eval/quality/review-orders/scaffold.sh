#!/usr/bin/env bash
# feature/orders branch, one commit ahead of main. Five defects vanilla Claude
# reliably finds: N+1 (Repo.get! per order), String.to_atom on a request param,
# :float money, no authorization in handle_event("cancel"), unguarded query in
# mount. Four subtler ones: compile-time File.read! without @external_resource,
# unsupervised Task.start, Gettext locale lost in that Task, and order.user not
# preloaded on the cancel path.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=../_shared/base.sh
source "$(dirname "${BASH_SOURCE[0]}")/../_shared/base.sh"
git checkout -q -b feature/orders
mkdir -p lib/my_app/orders

cat > lib/my_app/orders/order.ex <<'EX'
defmodule MyApp.Orders.Order do
  use Ecto.Schema
  import Ecto.Changeset

  schema "orders" do
    field :status, :string, default: "pending"
    field :total, :float
    belongs_to :user, MyApp.Accounts.User
    timestamps()
  end

  def changeset(order, attrs) do
    order
    |> cast(attrs, [:status, :total, :user_id])
    |> validate_required([:total, :user_id])
  end
end
EX

cat > lib/my_app/orders.ex <<'EX'
defmodule MyApp.Orders do
  import Ecto.Query
  alias MyApp.Repo
  alias MyApp.Accounts.User
  alias MyApp.Orders.Order

  def list_recent_orders(params \\ %{}) do
    sort = String.to_atom(Map.get(params, "sort", "inserted_at"))

    from(o in Order, order_by: [desc: field(o, ^sort)], limit: 50)
    |> Repo.all()
    |> Enum.map(fn order -> %{order | user: Repo.get!(User, order.user_id)} end)
  end

  def get_order!(id), do: Repo.get!(Order, id)

  def cancel_order(%Order{} = order) do
    order |> Order.changeset(%{status: "cancelled"}) |> Repo.update()
  end
end
EX

cat > priv/order_statuses.json <<'JSON'
{"pending": "Pending", "shipped": "Shipped", "cancelled": "Cancelled"}
JSON

cat > lib/my_app/orders/status_labels.ex <<'EX'
defmodule MyApp.Orders.StatusLabels do
  @labels "priv/order_statuses.json" |> File.read!() |> Jason.decode!()

  def label(status), do: Map.fetch!(@labels, status)
end
EX

cat > lib/my_app/orders/notifier.ex <<'EX'
defmodule MyApp.Orders.Notifier do
  use Gettext, backend: MyAppWeb.Gettext
  import Swoosh.Email

  def deliver_cancellation(order) do
    new()
    |> to(order.user.email)
    |> from({"MyApp", "orders@example.com"})
    |> subject(gettext("Your order #%{id} was cancelled", id: order.id))
    |> text_body(gettext("We have cancelled your order."))
    |> MyApp.Mailer.deliver()
  end
end
EX

cat > lib/my_app_web/live/order_live.ex <<'EX'
defmodule MyAppWeb.OrderLive do
  use MyAppWeb, :live_view
  alias MyApp.Orders
  alias MyApp.Orders.{Notifier, StatusLabels}

  def mount(params, session, socket) do
    Gettext.put_locale(MyAppWeb.Gettext, session["locale"] || "en")
    {:ok, assign(socket, orders: Orders.list_recent_orders(params))}
  end

  def handle_event("cancel", %{"id" => id}, socket) do
    order = Orders.get_order!(id)

    case Orders.cancel_order(order) do
      {:ok, order} ->
        Task.start(fn -> Notifier.deliver_cancellation(order) end)

        {:noreply,
         socket
         |> put_flash(:info, "Order cancelled")
         |> assign(orders: Orders.list_recent_orders())}

      {:error, _} ->
        {:noreply, put_flash(socket, :error, "Could not cancel order")}
    end
  end

  def render(assigns) do
    ~H"""
    <table>
      <tr :for={order <- @orders}>
        <td>{order.user.email}</td>
        <td>{order.total}</td>
        <td>{StatusLabels.label(order.status)}</td>
        <td><button phx-click="cancel" phx-value-id={order.id}>Cancel</button></td>
      </tr>
    </table>
    """
  end
end
EX

commit "Add orders list with cancel"
