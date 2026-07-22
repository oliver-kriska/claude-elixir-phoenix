# JavaScript Interoperability Reference

LiveView uses morphdom for DOM patching. Third-party JS libraries that manage their own DOM state conflict with this. This reference covers resolution patterns.

## Contents

- [The Core Problem](#the-core-problem)
- [Solution 1: phx-update="ignore"](#solution-1-phx-updateignore)
- [Solution 2: Hooks with Lifecycle Management](#solution-2-hooks-with-lifecycle-management)
- [Solution 3: Server-Driven Updates via pushEvent](#solution-3-server-driven-updates-via-pushevent)
- [Common Library Patterns](#common-library-patterns)
- [Anti-Patterns](#anti-patterns)
- [Decision Tree](#decision-tree)
- [Multi-Locale DOM Safety](#multi-locale-dom-safety)

## The Core Problem

```
LiveView Server                    Browser DOM
     │                                  │
     │  sends diff ──────────────────►  │
     │                                  │
     │                            morphdom patches
     │                                  │
     │                            ✗ DESTROYS JS state
     │                            ✗ TipTap loses content
     │                            ✗ Alpine loses x-data
     │                            ✗ Chart.js resets
```

## Solution 1: phx-update="ignore"

Tell LiveView to skip DOM diffing for a subtree.

```heex
<div id="editor-wrapper" phx-hook="TipTapEditor">
  <div id="editor-content" phx-update="ignore">
    <!-- JS library manages everything inside here -->
    <!-- LiveView will NEVER touch this subtree -->
  </div>
</div>
```

### Rules

1. **Must have unique ID** - Required for morphdom tracking
2. **Initial content preserved** - Whatever is rendered on mount stays
3. **No LiveView updates** - Assigns changes won't affect this element
4. **Hook still works** - Parent can have phx-hook for JS initialization

### When to Use

| Library Type | Use phx-update="ignore"? |
|--------------|-------------------------|
| Rich text editors (TipTap, Quill, ProseMirror) | Yes |
| Charts (Chart.js, D3, Plotly) | Yes |
| Maps (Leaflet, Mapbox, Google Maps) | Yes |
| Date pickers (Flatpickr) | Yes |
| Alpine.js components | Sometimes |
| Simple JS animations | Usually not needed |

## Solution 2: Hooks with Lifecycle Management

```javascript
// assets/js/hooks/tiptap_editor.js
const TipTapEditor = {
  mounted() {
    // Initialize when element enters DOM
    this.editor = new Editor({
      element: this.el.querySelector('[data-editor]'),
      content: this.el.dataset.content || '',
      onUpdate: ({ editor }) => {
        // Push changes to server
        this.pushEvent("editor-update", {
          content: editor.getHTML()
        })
      }
    })

    // Listen for server events
    this.handleEvent("set-content", ({ content }) => {
      this.editor.commands.setContent(content)
    })
  },

  updated() {
    // Called when LiveView updates the element
    // Usually no-op with phx-update="ignore"
  },

  destroyed() {
    // Cleanup when element leaves DOM
    this.editor?.destroy()
  }
}

export default TipTapEditor
```

### Hook Registration

```javascript
// assets/js/app.js
import TipTapEditor from "./hooks/tiptap_editor"
import ChartHook from "./hooks/chart_hook"

let Hooks = { TipTapEditor, ChartHook }

let liveSocket = new LiveSocket("/live", Socket, {
  hooks: Hooks,
  params: { _csrf_token: csrfToken }
})
```

### HEEx Template

```heex
<div
  id={"editor-#{@post.id}"}
  phx-hook="TipTapEditor"
  data-content={@post.content}
>
  <div data-editor phx-update="ignore"></div>
</div>
```

## Solution 3: Server-Driven Updates via pushEvent

When server needs to update JS state without DOM patching:

### LiveView

```elixir
def handle_event("load-template", %{"id" => id}, socket) do
  template = Templates.get!(id)
  # Push event to JS instead of assigning
  {:noreply, push_event(socket, "set-content", %{content: template.body})}
end

def handle_event("editor-update", %{"content" => content}, socket) do
  # Receive updates from JS
  {:noreply, assign(socket, draft_content: content)}
end
```

### JavaScript Hook

```javascript
mounted() {
  this.handleEvent("set-content", ({ content }) => {
    // Server tells JS to update, not via DOM
    this.editor.commands.setContent(content, false)
  })
}
```

## Common Library Patterns

### Chart.js

```heex
<div
  id={"chart-#{@chart_id}"}
  phx-hook="ChartHook"
  data-type={@chart_type}
  data-datasets={Jason.encode!(@datasets)}
>
  <canvas phx-update="ignore"></canvas>
</div>
```

```javascript
const ChartHook = {
  mounted() {
    const ctx = this.el.querySelector('canvas')
    this.chart = new Chart(ctx, {
      type: this.el.dataset.type,
      data: JSON.parse(this.el.dataset.datasets)
    })

    this.handleEvent("update-data", ({ datasets }) => {
      this.chart.data = datasets
      this.chart.update()
    })
  },
  destroyed() {
    this.chart?.destroy()
  }
}
```

### Leaflet Maps

```heex
<div
  id="map-container"
  phx-hook="LeafletMap"
  data-lat={@center.lat}
  data-lng={@center.lng}
>
  <div id="map" phx-update="ignore" style="height: 400px;"></div>
</div>
```

### Alpine.js

```heex
<%!-- Option 1: phx-update="ignore" for Alpine-only sections --%>
<div id="dropdown" phx-update="ignore" x-data="{ open: false }">
  <button @click="open = !open">Toggle</button>
  <div x-show="open">Content</div>
</div>

<%!-- Option 2: Alpine for UI state, LiveView for data --%>
<div x-data="{ expanded: false }">
  <button @click="expanded = !expanded"><%= @item.title %></button>
  <div x-show="expanded">
    <%!-- LiveView can update this content --%>
    <%= @item.description %>
  </div>
</div>
```

## Anti-Patterns

### Forget unique IDs

```heex
<%!-- BAD: No ID means morphdom can't track it --%>
<div phx-update="ignore"><canvas></canvas></div>

<%!-- GOOD: Unique ID for tracking --%>
<div id="chart-1" phx-update="ignore"><canvas></canvas></div>
```

### Put phx-update on hook element

```heex
<%!-- BAD: Hook won't receive updated() callback --%>
<div id="editor" phx-hook="Editor" phx-update="ignore"></div>

<%!-- GOOD: Separate hook from ignored content --%>
<div id="editor" phx-hook="Editor">
  <div id="editor-content" phx-update="ignore"></div>
</div>
```

### Forget cleanup in destroyed()

```javascript
// BAD: Memory leak
mounted() {
  this.chart = new Chart(...)
}

// GOOD: Proper cleanup
mounted() {
  this.chart = new Chart(...)
},
destroyed() {
  this.chart?.destroy()
}
```

### Use assigns for JS-managed content

```elixir
# BAD: LiveView tries to update, conflicts with JS
def handle_event("save", _, socket) do
  {:noreply, assign(socket, content: new_content)}
end

# GOOD: Push event to JS
def handle_event("save", _, socket) do
  {:noreply, push_event(socket, "content-saved", %{})}
end
```

## Decision Tree

```
Is your JS library managing DOM state?
│
├─ NO → Normal LiveView, no special handling
│
└─ YES → Does LiveView need to update that DOM area?
         │
         ├─ NO → Use phx-update="ignore"
         │       JS owns it completely
         │
         └─ YES → Use Hook + pushEvent pattern
                  Server sends events, JS updates itself
```

## Multi-Locale DOM Safety

Translated text can change DOM structure (different word count, RTL, different element wrapping). JS hooks that rely on DOM position break across locales.

### Rules

1. **NEVER use positional selectors** (`children[0]`, `firstChild`, `nth-child`) in JS hooks
2. **ALWAYS use `querySelector` with `data-*` attributes** for stable element targeting
3. **Test with longest locale** — German/Finnish strings are often 30-50% longer than English

### Anti-Pattern

```javascript
// BAD: Position changes when translation adds/removes elements
mounted() {
  this.target = this.el.children[0]
  this.label = this.el.querySelector('span:first-child')
}
```

### Correct Pattern

```javascript
// GOOD: data attributes survive translation changes
mounted() {
  this.target = this.el.querySelector('[data-role="content"]')
  this.label = this.el.querySelector('[data-role="label"]')
}
```

```heex
<div id="my-hook" phx-hook="MyHook">
  <span data-role="label"><%= gettext("Status") %></span>
  <div data-role="content"><%= @content %></div>
</div>
```
