# UI strategy for a rewrite

The UI decision sets which contracts the backend must keep: HTML, JSON, or a realtime wire protocol. `[U]` marks an unverified detail.
Make it per surface (public site, app, admin, mobile API), not once for the whole product. The stack files in `stacks/` cover the
backend side of each option; the verdict vocabulary (MAP, REPLACE, KEEP, SHIM, DELETE, UNDECIDED) is defined in the elixir-way SKILL.md.

## Options

| Option | When it fits | Cost | Risk | What the legacy UI becomes |
|---|---|---|---|---|
| **Keep the legacy server-rendered frontend and its protocol behind a SHIM** (Turbo/Hotwire + Stimulus + Action Cable) | A Rails/Hotwire app whose HTML and Stimulus layer work, and the rewrite is about the backend. Phase 1 of most strangler migrations. Valian's Campfire port kept Turbo and Action Cable on Phoenix controllers + HEEx | Controllers + HEEx reproduce the HTML. Turbo Drive needs only HTML; Frames need a matching `<turbo-frame id>` in the response; HTTP Turbo Streams are a response format (`text/vnd.turbo-stream.html`). Action Cable needs a WebSock 0.6 handler speaking `actioncable-v1-json` (welcome, ping, subscribe, confirm, message) fed by Phoenix.PubSub. `turbo_stream_from` names are signed with the Rails secret, so the shim must verify that signature [U exact format] | The shim stays by default rather than by decision, and core code bends toward Rails semantics (once-campfire-elixir hand-rolled Cable with Redis on the hot path) | Unchanged at first. Later, Turbo Streams move to `<turbo-stream-source>` over a Phoenix Channel or SSE endpoint and the Cable shim is deleted, or pages move to LiveView one by one |
| **Proxy server-component frontends; never re-implement their protocol** (Livewire, Blazor Server, Vaadin) | Laravel Livewire or Blazor Server apps | Unported pages stay on the legacy app behind reverse_proxy_plug. Each component is rewritten as a LiveView or LiveComponent, which is the same model (server state, events, re-render) | Re-implementing Livewire's snapshot + checksum protocol or a Blazor circuit means maintaining another framework's internals forever | Served by the legacy app until its page is ported, then deleted |
| **LiveView (default)** | CRUD, admin, back office, dashboards, forms, workflows; realtime notifications, collaboration and presence; SEO pages through the dead render; an Elixir-capable team | Templates rewritten in HEEx. One socket per tab. Server memory per connection (streams for lists, Iron Law 2) | Every event round-trips: high-RTT users on interaction-heavy screens need regional nodes, JS commands and `phx-debounce`. No offline mode | Templates rewritten. API/BFF, client router, client cache and duplicated validation deleted |
| **LiveView + JS hooks or islands** (colocated hooks, LiveSvelte, LiveReact, LiveVue) | Mostly LiveView, plus a few rich widgets (rich-text editor, charts, maps, drag-and-drop, canvas) or a component library worth reusing | Colocated hooks (LiveView 1.1+) and `phx-update="ignore"` containers. Island libraries pass assigns as props and push events back. SSR needs a Node runtime (live_svelte: Node 19+) | Two component models. All three island libraries are single-maintainer with no KB verdict. Pin `nodejs` at 3.1.4 or later for SSR | Complex widgets kept as islands; page shells, routing and data loading become LiveView |
| **Inertia-Phoenix** | Page-oriented React/Vue/Svelte apps (Next.js Pages Router, Remix, Laravel + Inertia) whose pages are server props plus forms; a React-centric team | Controllers call `render_inertia` with the props that loaders or `getServerSideProps` returned. Server validation errors come back as props. SSR is optional (Node adapter) | inertia 3.0.0 shipped 2026-10-08, a brand-new major: pin it and watch patch releases. Realtime needs Channels added by hand. Native apps still need a JSON API | Page components kept; API layer, client router and fetch/cache layer deleted |
| **Keep the SPA with a JSON or GraphQL API** | Offline or PWA requirements; native apps or partners reuse the API; heavy client state (editors, canvases, maps); a separate frontend team with its own CDN deploys | The API stays a product: open_api_spex golden tests, CORS or a same-site cookie session, duplicated validation, two pipelines | Contract drift (key casing, `null` vs missing, decimal encoding). The SPA remains a second codebase | Unchanged. Phoenix serves the same contract behind the strangler. Realtime moves to Channels via phoenix.js once clients can change |
| **Mobile clients that cannot be force-updated** | Shipped iOS/Android builds, embedded devices, partner integrations | The current API, auth and realtime contracts become KEEP: a permanent supported adapter (owner, support policy, conformance tests) unless ADR-000 sets an end. Add app-version telemetry and a minimum-version endpoint now, so the next contract change can be forced. Existing JWTs and refresh tokens must keep validating | The old contract lives for years. A Socket.io or SignalR protocol shim is the most expensive part | Old builds keep the legacy contract, now served by Phoenix. New builds move to a versioned API, Channels, or a native shell over LiveView (KB: Enaia's Expo single-WebView shell) |
| **Do not plan around:** LiveView Native; local-first sync | LiveView Native is dormant (0.3.1 from 2024-10, 0.4.0-rc.1 from 2025-03). phoenix_sync 0.6.1 is early: spike it only when offline is a hard requirement and Phoenix stays the authority | Spike time | Abandonment; early-stage API | n/a |

## Decision questions

1. Must any surface work offline or local-first? Why: LiveView needs the socket. Offline means an SPA (or phoenix_sync after
   a spike). If the answer is yes, that surface is decided.
2. Who else consumes the backend (native apps, partners, other frontends)? Why: their API survives in every option, but it
   does not force the web UI to stay an SPA, because LiveView and the API share the same contexts.
3. Can every client be force-updated, and by when? Why: it decides whether each protocol or contract shim is migration-only
   (a removal milestone) or a permanent supported adapter (owner, support policy, conformance tests).
4. Does the legacy frontend depend on a server-side protocol (Action Cable, Socket.io, SignalR, Livewire, Blazor circuits,
   STOMP, graphql-ws)? Why: each one needs a decision between a shim, a proxy and a client migration.
5. How much of the UI is heavy client state? Why: a few widgets point to islands; most of the UI points to keeping the SPA.
6. What does the team write today, and who maintains the UI after the rewrite? Why: a React team on page-style apps lands
   faster on Inertia; a full-stack Elixir team lands faster on LiveView.
7. What is the p95 RTT from the main user regions, and how interaction-dense are the screens? Why: above roughly 150 ms
   [U rule of thumb], plan regional nodes, JS commands or islands for those screens.
8. Which routes need SEO or link previews? Why: their content and metadata must be in the disconnected HTTP response, from a
   synchronous read, a cache or a controller-rendered page. `assign_async` starts only on a connected socket, so it never fills
   that render; use it for connected-only enhancements.
9. How many users are connected at once, and how much state does each screen hold? Why: LiveView memory scales with
   connections, so streams and temporary assigns are design inputs, not later tuning.
10. Is the legacy frontend wanted, or is replacing it part of the goal? Why: if it works, keep it first and change only the
    backend; UI changes then happen page by page.
11. Are thin native apps candidates for a WebView shell over LiveView? Why: new builds then need no separate mobile API
    (KB pattern: a navigation shim calling `liveSocket.js().navigate`).

## Migration order

1. **Record the contract.** For each route and event, capture the HTML, JSON and WebSocket frames the legacy app emits
   (golden vectors), plus the client-version distribution.
2. **Put Phoenix in front.** Proxy unported HTTP routes with reverse_proxy_plug 3.0. Route WebSocket paths at the load
   balancer, because reverse_proxy_plug is HTTP-only (reverse_proxy_plug_websocket 0.2 exists but is young).
3. **Port backend slices behind the unchanged frontend.** Serve the same HTML from controllers + HEEx, or the same JSON
   from controllers + views. The frontend must not notice.
4. **Swap the transport.** Realtime moves onto Phoenix.PubSub at the core. Clients you control switch to Phoenix Channels
   (phoenix.js) or to `<turbo-stream-source>` over a Phoenix endpoint. Clients you do not control get a shim: migration-only
   with a removal milestone, or a permanent supported adapter.
5. **Swap the UI page by page** where the chosen option says so: LiveView or Inertia for CRUD and admin first, islands for
   latency-critical widgets, and the SPA kept where the decision questions point there.
6. **Delete.** Remove shims, BFF routes, client caches and legacy assets, each gated by access logs, client-version
   telemetry and a parity run.

Change one side of a contract per slice. A slice either keeps the frontend and swaps the backend, or replaces both with
LiveView. It never swaps the backend and edits the client protocol at the same time.

## Traps

- **Reimplementing a frontend framework's server protocol without a decision.** Action Cable, Engine.IO/Socket.io, SignalR,
  Livewire snapshots, Blazor circuits, STOMP and graphql-ws are other projects' internals. A port that keeps one owns its
  bugs, versions and security fixes with no upstream. once-campfire-elixir hand-rolled Action Cable with Redis on the hot
  path; Valian's port kept the same wire protocol as a thin WebSock layer over local PubSub. A protocol shim is acceptable
  only when all of these hold:
  - it lives in one namespace (for example `MyAppWeb.Compat.ActionCable`) and only translates to and from PubSub; core
    code never calls it;
  - recorded frame-level conformance tests cover it;
  - a migration-only shim has an owner and a removal milestone (a client-version share or a date) in the divergence ledger;
    a permanent supported adapter, when ADR-000 keeps the protocol for clients that cannot update, has an owner, a version
    and security support policy and review conditions instead, with no forced client update;
  - new clients ship on the idiomatic transport from day one.
- Moving to LiveView but keeping the JSON API and BFF that only your own UI used.
- Keeping SPA + API for CRUD and admin screens only because the legacy app had one.
- Forcing LiveView onto offline or canvas-heavy surfaces.
- Mirroring a Redux or React Query cache in socket assigns, or holding large lists in plain assigns (Iron Law 2).
- Repeating the same DB work in the disconnected and the connected mount (Iron Law 1). Required HTTP content still loads in
  the disconnected render; avoid only the duplicate. Authorization in `mount` only instead of in every `handle_event`
  (Iron Law 11).
- Keeping localStorage JWTs after the move to LiveView, or disabling CSRF because "the SPA used JWT".
- "Cleaning up" JSON that non-updatable mobile clients parse (`null` vs missing, key casing, number vs string decimals).
- Round-tripping pure UI state (toggles, tabs, modals) through the server instead of `Phoenix.LiveView.JS` commands, and
  inputs without `phx-debounce`.
- Shipping socket.io-client or the SignalR JS client against Phoenix: neither speaks the Channels protocol.
- Adopting Inertia 3.0 (a one-day-old major) or a single-maintainer island library as a default without
  `/phx:research --library`.
- Planning a mobile strategy around LiveView Native.

## Libraries

| Need | Package | Version | Notes |
|---|---|---|---|
| Server UI (default) | phoenix_live_view | 1.2.12 | Colocated hooks since 1.1, colocated CSS since 1.2 |
| Server-rendered HTML for a kept frontend | phoenix | 1.8.15 | Controllers + HEEx serve Turbo/Stimulus pages unchanged |
| Raw protocol shims | websock_adapter / bandit | 0.6.0 / 1.12.5 | Action Cable or legacy WebSocket protocols, isolated in one namespace |
| Core fan-out | phoenix_pubsub | 2.4.1 | Every shim translates to and from PubSub |
| HTTP strangler proxy | reverse_proxy_plug | 3.0.4 | HTTP only |
| WebSocket proxy | reverse_proxy_plug_websocket | 0.2.0 | Young, low adoption: evaluate before use |
| Page-style React/Vue/Svelte | inertia | 3.0.1 | 3.0.0 shipped 2026-10-08; pin and watch |
| Islands | live_svelte / live_react / live_vue | 0.18.0 / 2.0.0 / 1.2.3 | Single-maintainer; SSR needs Node |
| SSR worker pool | nodejs | 3.1.4 | 3.1.4 fixes CVE-2026-33872 |
| Kept SPA or mobile contract | open_api_spex | 3.22.4 | Golden contract tests against the legacy spec |
| GraphQL API | absinthe / absinthe_phoenix | 1.12.0 / 2.0.5 | Subscriptions over Channels |
| Apollo `graphql-ws` clients | absinthe_graphql_ws | 0.3.6 | Dormant since 2022: fork, replace, or migrate clients |
| CORS for a cross-origin SPA | cors_plug / corsica | 3.0.3 / 2.1.3 | Dormant but stable |
| Existing mobile tokens | joken / joken_jwks | 2.7.0 / 1.8.0 | Same keys, issuer and audience |
| Push notifications | pigeon | 2.1.0 | APNs and FCM for native apps |
| Static content (replaces SSG) | nimble_publisher | 2.1.0 | Compiled into the release |
| Local-first (spike only) | phoenix_sync | 0.6.1 | Early-stage |
| Native UI | live_view_native | 0.3.1 | Dormant; do not plan around it |
