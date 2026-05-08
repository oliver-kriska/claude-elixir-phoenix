# Components Reference

## Function Components

```elixir
# In core_components.ex or separate file
attr :user, :map, required: true
attr :class, :string, default: ""
attr :rest, :global, include: ~w(disabled)

slot :inner_block
slot :actions

def user_card(assigns) do
  ~H"""
  <div class={["card", @class]} {@rest}>
    <h3>{@user.name}</h3>
    <p>{@user.email}</p>
    {render_slot(@inner_block)}
    <div :if={@actions != []}>
      {render_slot(@actions)}
    </div>
  </div>
  """
end

# Usage
~H"""
<.user_card user={@user} class="mb-4">
  <:actions>
    <.button phx-click="edit">Edit</.button>
  </:actions>
</.user_card>
"""
```

## LiveComponents (Stateful)

**Key rule**: DON'T update local state - notify parent to avoid sync issues

```elixir
defmodule MyAppWeb.Components.SearchBox do
  use MyAppWeb, :live_component

  @impl true
  def mount(socket) do
    {:ok, assign(socket, query: "", results: [])}
  end

  @impl true
  def handle_event("search", %{"query" => query}, socket) do
    results = search(query)
    {:noreply, assign(socket, query: query, results: results)}
  end

  # Notify parent instead of updating shared state
  @impl true
  def handle_event("select", %{"id" => id}, socket) do
    send(self(), {:item_selected, id})
    {:noreply, socket}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div>
      <form phx-change="search" phx-target={@myself}>
        <input type="text" name="query" value={@query} />
      </form>
      <ul>
        <li :for={result <- @results} phx-click="select" phx-value-id={result.id} phx-target={@myself}>
          {result.name}
        </li>
      </ul>
    </div>
    """
  end

  defp search(query), do: # Search implementation
end

# Usage
~H"""
<.live_component module={SearchBox} id="search" />
"""
```

## Colocated Hooks (LiveView 1.1+)

```elixir
def phone_input(assigns) do
  ~H"""
  <input type="text" id="phone" phx-hook=".PhoneNumber" />
  <script :type={Phoenix.LiveView.ColocatedHook} name=".PhoneNumber">
    export default {
      mounted() {
        this.el.addEventListener("input", e => {
          // Format phone number
        })
      }
    }
  </script>
  """
end
```

## JS Commands (No Server Round-trip)

```elixir
# Chained commands
def hide_modal(js \\ %JS{}) do
  js
  |> JS.hide(transition: "fade-out", to: "#modal")
  |> JS.hide(transition: "fade-out-scale", to: "#modal-content")
end

# In template
<button phx-click={hide_modal()}>Close</button>

# Push with loading indicator
<button phx-click={JS.push("save", loading: "#form")}>Save</button>

# Focus management
<button phx-click={JS.focus(to: "#input")}>Focus Input</button>

# Toggle visibility
<button phx-click={JS.toggle(to: "#details")}>Toggle Details</button>
```
