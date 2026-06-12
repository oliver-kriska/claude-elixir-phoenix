# Async and Streams Reference

## Lifecycle Execution Order

```
[Initial HTTP Request]
     ↓
mount/3 (disconnected) → handle_params/3 → render/1
     ↓
[WebSocket Connection]
     ↓
mount/3 (connected) → handle_params/3 → render/1
     ↓
[Stateful Loop]
handle_event/3, handle_info/2, handle_async/3
```

**Critical**: Code in mount runs TWICE unless you use `assign_async` or check `connected?/1`

## Async Assigns (LiveView 1.0+)

**CRITICAL**: Extract variables BEFORE closure to avoid copying socket:

```elixir
def mount(%{"slug" => slug}, _session, socket) do
  # Extract needed values BEFORE the closure
  scope = socket.assigns.current_scope

  {:ok,
   socket
   |> assign(:page_title, "Dashboard")
   |> assign_async(:org, fn -> {:ok, %{org: fetch_org(scope, slug)}} end)
   |> assign_async([:posts, :comments], fn ->
     {:ok, %{posts: list_posts(slug), comments: list_comments(slug)}}
   end)}
end

# In template - handle loading state
~H"""
<.async_result :let={org} assign={@org}>
  <:loading>Loading <.spinner /></:loading>
  <:failed :let={_failure}>Error loading</:failed>
  {org.name}
</.async_result>
"""
```

### Cancel Async Operations

```elixir
def handle_event("cancel_search", _, socket) do
  {:noreply, cancel_async(socket, :search_results)}
end
```

### Testing Async Operations

```elixir
test "loads data asynchronously", %{conn: conn} do
  {:ok, view, html} = live(conn, ~p"/dashboard")
  assert html =~ "Loading..."

  html = render_async(view)  # Wait for async to complete
  assert html =~ "Dashboard Data"
end
```

## stream_async (LiveView 1.1+)

```elixir
def mount(%{"slug" => slug}, _, socket) do
  {:ok, stream_async(socket, :posts, fn -> {:ok, list_posts!()} end)}
end
```

## Streams (for Lists)

### Basic Stream Operations

```elixir
# Mount - initialize stream
def mount(_params, _session, socket) do
  {:ok, stream(socket, :items, Items.list_items())}
end

# Insert item (at beginning)
def handle_event("create", params, socket) do
  {:ok, item} = Items.create_item(params)
  {:noreply, stream_insert(socket, :items, item, at: 0)}
end

# Update item
def handle_event("update", %{"id" => id} = params, socket) do
  item = Items.get_item!(id)
  {:ok, updated} = Items.update_item(item, params)
  {:noreply, stream_insert(socket, :items, updated)}
end

# Delete item
def handle_event("delete", %{"id" => id}, socket) do
  item = Items.get_item!(id)
  {:ok, _} = Items.delete_item(item)
  {:noreply, stream_delete(socket, :items, item)}
end
```

### Stream Pagination with Limit

```elixir
# Append new items, prune from top (keep last 30)
stream(socket, :posts, new_posts, at: -1, limit: -30)

# Prepend items, prune from bottom (keep first 30)
stream(socket, :posts, Enum.reverse(posts), at: 0, limit: 30)
```

### Empty Stream Handling (Use CSS)

Cannot use `Enum.empty?` on streams. Use `:only-child`:

```elixir
~H"""
<tbody id="songs" phx-update="stream">
  <tr id="songs-empty" class="only:table-row hidden">
    <td colspan="3">No songs found</td>
  </tr>
  <tr :for={{dom_id, song} <- @streams.songs} id={dom_id}>
    <td>{song.title}</td>
  </tr>
</tbody>
"""
```

### Stream Template

```elixir
~H"""
<div id="items" phx-update="stream">
  <div :for={{dom_id, item} <- @streams.items} id={dom_id}>
    {item.name}
  </div>
</div>
"""
```

## SEO Dead-Render Pattern (cache-backed disconnected branch)

The disconnected mount renders the HTML that Googlebot, GPTBot, ChatGPT-User,
PerplexityBot, ClaudeBot, and JS-disabled clients see. For SEO-visible routes
(marketing pages, articles, product listings, public catalogs) it IS correct
to populate that render with real content. The wrong way is `Repo.all/1` on
every dead render — that doubles DB load. The right way is cache-backed:

```elixir
def mount(_params, _session, socket) do
  products =
    if connected?(socket),
      do: Catalog.list_products(),
      else: Cache.get_products() || []

  {:ok, assign(socket, products: products)}
end
```

Cache backends that work well:

- `:persistent_term.put/2` for content updated by an Oban cron (sitemap-style)
- ETS for sub-microsecond lookups (Cachex, ConCache, hand-rolled GenServer)
- Edge cache (Cloudflare, Fly.io edge) — set `cache-control: public` on the route

Empty fallback is also acceptable when the page renders a skeleton via CSS:

```elixir
else: []  # template shows skeleton with `:only-child` rows
```

What NOT to do:

```elixir
# ❌ Doubles DB load — runs on dead render AND connect
def mount(_params, _session, socket) do
  products = Catalog.list_products()
  {:ok, assign(socket, products: products)}
end

# ❌ Empty assign on private/authed routes — flicker, no SEO benefit
# (use assign_async for private dashboards instead)
```

This pattern satisfies Iron Law #1 because the disconnected branch does NOT
hit the database. The cache is populated by a background job, not the request.

## Anti-patterns

```elixir
# ❌ Database queries when disconnected (runs TWICE)
def mount(_params, _session, socket) do
  data = Repo.all(User)  # ← HTTP render + WebSocket connect
  {:ok, assign(socket, data: data)}
end

# ✅ Use assign_async (runs only when connected)
def mount(_params, _session, socket) do
  {:ok, assign_async(socket, :data, fn -> {:ok, %{data: Repo.all(User)}} end)}
end

# ❌ Copying socket to async closure
assign_async(socket, :org, fn -> {:ok, %{org: fetch_org(socket.assigns.slug)}} end)

# ✅ Extract before closure
slug = socket.assigns.slug
assign_async(socket, :org, fn -> {:ok, %{org: fetch_org(slug)}} end)

# ❌ Not using streams for lists (memory hog)
{:ok, assign(socket, items: Items.list_items())}

# ✅ Use streams (O(1) memory)
{:ok, stream(socket, :items, Items.list_items())}
```
