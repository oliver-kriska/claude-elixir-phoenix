# OTP Advisor Consult: presence, supervision, Action Cable shim, TLS, ephemeral channels

**Scope**: answers only. This is not a plan and not an implementation.
**Bar**: ADR-000 (ASSUMED). Replacement cutover in one ONCE container. The Hotwire UI stays and talks to an isolated `Compat.ActionCable` shim. The schema stays, including `memberships.connections` and `connected_at`. C-56 mechanism is open.
**Evidence read**: ADR-000; analysis/runtime.md (all); mechanisms.md M-07, M-27, M-28, M-29, Q4, Q5; contracts.md C-28, C-41, C-43, C-47, C-50..C-56; features.md F-08, F-12, F-13; kb/infrastructure.md, kb/ui-strategy.md, kb/sqlite-on-beam.md.
**SOURCE anchors**: `app/channels/**`, `app/models/membership/connectable.rb`, `app/models/user.rb:34-63`, `app/models/membership.rb:7`, `app/models/room.rb:80`, `app/models/room/message_pusher.rb:59`, `app/controllers/concerns/authentication.rb:70-81`, `app/javascript/controllers/{presence,refresh_room,typing_notifications}_controller.js`, `app/javascript/models/typing_tracker.js`, `bin/boot`, `bin/start-app`, `Procfile`, `Dockerfile`, `config/puma.rb:51`, `config/cable.yml`, `hooks/*`.

---

## Answers

### Q1. Presence and connected state: DB counters vs in-memory

**Verdict**: keep the columns in the schema, but stop reading and writing them. Hold "is looking at the room" in memory, in a process-linked `Registry` (`keys: :duplicate`) behind a project-owned facade (`Campfire.RoomPresence`). Keep a 60 s refresh-driven expiry in memory, so a half-open socket cannot claim presence forever. `Phoenix.Presence` is acceptable but not the best fit here (reasons below).

**What the semantics actually are** (from source, not from the column names):
- A membership counts as "connected" when a `PresenceChannel` subscription for that room exists **and** the tab is visible. The JS sends `absent` 5 s after the tab is hidden and `present` 5 s after it becomes visible again (`presence_controller.js:9,47-64`). It sends `refresh` every 50 s while visible. The server treats a row as connected if `connected_at >= now - 60 s` (`connectable.rb:4-9`).
- Only two code paths read this state, and both are in the app: unread marking (`room.rb:80`, `memberships.visible.disconnected...update_all(unread_at:)`) and push recipient selection (`room/message_pusher.rb:59`, same scope). Nothing in `script/admin/*`, `hooks/*`, views, jbuilder or the bot API reads `connections` or `connected_at` (grep over app, lib, config, script, hooks). No contract in contracts.md exposes them.
- `present` also does a **business write**: it sets `unread_at = nil` (mark read) and broadcasts `{room_id}` on `user_<id>_reads` (`presence_channel.rb:5-9`, `connectable.rb:16-18`). That write must stay. Only the counter and heartbeat writes are platform workarounds.

**Why in-memory wins under the single SQLite writer.** Today every visible room tab costs one `BEGIN IMMEDIATE` write every 50 s, on the same single writer as message posts and every Oban fetch and ack (sqlite-on-beam rules 1, 9; Oban Lite caveat "writer contention"). For example, 500 visible tabs means about 10 writer transactions per second of pure bookkeeping. The counter is also read-modify-write in Ruby (`present` computes `connections + 1` client-side), so concurrent tabs lose updates, and only the TTL heals it. A process-linked registry gives an exact count per subscription, with no writes, no TTL drift and no boot reset.

**Why `Registry` over `Phoenix.Presence`**:
- `Registry.register/3` is synchronous. Once the `subscribe` handler returns, `Registry.lookup` sees the entry. The `confirm_subscription` frame therefore means "present" with no propagation window. Phoenix.Presence goes through `Phoenix.Tracker` shards and broadcasts `presence_diff` messages that no client consumes, because the Hotwire UI shows no presence list.
- Entries disappear when the connection process dies, because Registry links to registered processes. That replaces `disconnect_all` at boot.
- If the app is ever clustered, swap the facade's implementation to Phoenix.Presence. SQLite pins ONCE to a single node anyway (sqlite-on-beam "When to Move to Postgres").

**Keep the 60 s window in memory, not just "socket alive"**. This is the main pitfall. A laptop that sleeps or loses its network leaves a half-open TCP socket. The server only notices when a write fails, which on Linux can take about 15 minutes of retransmits even with 3 s cable pings. Without a TTL that user would suppress their own unread marking and push for minutes. Two ways to model it, both inside the connection process:
- Store `last_refresh_at` (monotonic) in the registry value and filter on it at read time.
- Or (preferred) keep a per-subscription `Process.send_after(self(), {:presence_expired, identifier}, 60_000)` timer, reset it on every `present` and `refresh`, and unregister when it fires. On a late `refresh`, re-register. This matches `refresh_connection`'s "increment unless connected?".

**Registry key shape**: key `{:room, room_id}`, value `{user_id, identifier}`. Unregister with `Registry.unregister_match/4` on the identifier. A plain `Registry.unregister/2` would drop every entry for that room from the process, which is wrong if one connection holds two presence subscriptions for the same room (Turbo preview and navigation races can cause this). Readers call `RoomPresence.user_ids(room_id)`, which returns a `MapSet` of user ids.

**Query shape**: `memberships visible, user_id NOT IN ^present_ids, user_id != creator`. The SQL stays index-friendly, and the present set is small.

**Sampling time (mechanisms Q4)**. Keep legacy parity:
- Unread is sampled at commit. Read the registry inside `Repo.transact`, immediately before the `update_all`. The registry read is ETS and needs no DB.
- Push is sampled when the Oban job runs, by calling the same facade inside the worker.

Do not freeze present ids into job args. A restored backup replaying an old job should use current presence, and legacy also samples push late. Both run on the same node, so run-time sampling is valid.

**External and rollback readers.** Nothing external reads the columns. The rollback path is safe without the port ever writing them, because the pinned Rails image runs `Membership.disconnect_all` at Puma boot (`config/puma.rb:51`), which clears every row still inside the 60 s window. Rows the port leaves stale (`connections > 0`, old `connected_at`) already count as `disconnected` for Rails, and its `present` resets them to 1. ONCE restore (`hooks/post-restore`) runs with the app stopped, and Rails resets on boot. Result: no compatibility reason to keep writing the columns. Keep them in the schema because ADR-000 forbids destructive DDL during the rollback window, and record them as "retire after rollback window" in the divergence ledger.

**Acceptance probes from F-12, rechecked against this design**:
- Two tabs, close one → still present: holds, one registry entry per subscription.
- Tab closed 61 s ago without a clean unsubscribe → unread: holds, either because the socket died (immediate) or because the TTL fired.
- Server restart → nobody present: holds, the registry starts empty.
- Membership removed → connections reset: the forced disconnect kills the process, which drops its entries.

### Q2. Release supervision tree and startup ordering

See the sketch below. The rules behind it:

1. **Create directories, then the writer, then migrations, then everything else.** `File.mkdir_p!` for `storage/db` and `storage/files` runs in `Application.start/2` before `Supervisor.start_link`. This mirrors `config/initializers/storage_paths.rb`. Next comes the writer `Campfire.Repo` (pool 1, `:immediate`, WAL, busy_timeout 5000). Then `{Ecto.Migrator, repos: [Campfire.Repo], skip: ...}` runs pending migrations synchronously in `init` and returns `:ignore`. That reproduces `db:prepare`: Exqlite creates a missing file on open, and Rails' `schema_migrations` is kept (C-55). The reader `Campfire.Repo.Read` starts only after migrations, because a read-only connection cannot create the DB or switch it to WAL (sqlite-on-beam "Config Example" note).
2. **Boot-time resets run as `:ignore` children between Migrator and Endpoint.** With the in-memory presence from Q1 there is nothing to reset. If the team overrides Q1 and keeps DB counters, add a `Campfire.Boot.ResetConnections` child whose `start_link` runs the `UPDATE` and returns `:ignore`. It sits after the Migrator and before the Endpoint, so no socket can register before the reset.
3. **PubSub comes before anything that subscribes or broadcasts**: Oban workers broadcast, and the shim subscribes.
4. **Oban comes before the Endpoint**, because `Oban.insert` inside request transactions needs the Oban instance registered. Oban uses `Campfire.Repo` (writer), `Oban.Engines.Lite`, `Oban.Notifiers.PG`. Queues: `webhooks` (limit 2-5, `max_attempts: 1`, per M-20/Q5), `push` (limit 2; fan-out happens inside the job), `default`.
5. **HTTP clients and helpers** sit together under a `:one_for_one` sub-supervisor:
   - three named Finch instances: `Campfire.Finch.Webhook` with a 7 s connect and receive budget (C-35/C-36), `Campfire.Finch.Push` with sized pools for vendor hosts, and `Campfire.Finch.Opengraph`;
   - `Campfire.TaskSupervisor` for push fan-out (`Task.Supervisor.async_stream_nolink`, `max_concurrency: 50`, parity with `WebPush::Pool`) and for off-socket writes from the shim (Q3);
   - the rate limiter, which is Hammer with the ETS backend (`use Hammer, backend: :ets`, started as a child), for C-42.

   Set `pool_max_idle_time` on the webhook and opengraph Finch instances. Their origins are arbitrary hosts, and Finch creates a pool per origin lazily, so without reaping they accumulate. Separate instances isolate pool exhaustion: a stuck bot cannot starve push.
6. **The Action Cable shim is not a separate endpoint or listener.** It is a plug at `/cable` inside `CampfireWeb.Endpoint` that calls `WebSockAdapter.upgrade/4`. Bandit (ThousandIsland) supervises each connection process. The only shim-owned child is `Campfire.RoomPresence` (Registry), and it must start **before** the Endpoint.
7. **The Endpoint starts last**, so the port opens only once migrations are applied and every dependency is up. `GET /up` (C-47) then becomes true only after a full boot. With in-release ACME (Q4 option B), the Endpoint is wrapped by the ACME library's child, which also starts last.
8. **Strategy: top level `:rest_for_one`**, inner service groups `:one_for_one`. Why `rest_for_one`:
   - If PubSub restarts, every existing shim process is silently subscribed to nothing.
   - If the Repo restarts, the Migrator should re-check and Oban should reconnect.
   - Restarting everything after the failed child forces sockets to drop. The JS reconnects and resubscribes, which re-authorizes (M-07) and re-registers presence.

   `:ignore` children (Migrator, resets) are re-attempted on restart. That is cheap and correct. Keep the defaults `max_restarts: 3, max_seconds: 5`. When intensity is exceeded, the permanent application stops, the VM halts and the container exits for Docker's restart policy. That is the same "any fatal failure restarts the container" behavior `bin/boot` gives today by trapping `CLD` (runtime.md R-01).
9. **Shutdown inside Docker's 10 s stop window.** SIGTERM triggers `init:stop`, and children stop in reverse order:
   - Endpoint first. Use the `drainer` option. Sockets close with 1001 and the JS reconnects to the next container.
   - Then Oban, with `shutdown_grace_period` of about 5 s. Ruby lost queued jobs here because Redis had no persistence. Oban keeps them, which is the durability upgrade noted in R-24.
   - Then the Repo.

   Use `tini` as PID 1 (`ENTRYPOINT ["/usr/bin/tini","--"]`). The release spawns `ffmpeg`/vips helpers, and the BEAM does not reap orphaned grandchildren. `bin/boot` was a Ruby PID 1 that reaped through `Process.wait`.
10. **Admin scripts** (C-54) that touch the DB on a running container, especially `prepare-backup`, must use `bin/campfire rpc` so the write goes through the live writer Repo. `eval` would boot a second VM with its own writer, which breaks sqlite-on-beam rules 1 and 11. `reset-password` can use `rpc` too. `generate-secrets` needs no DB and can use `eval`.

### Q3. Action Cable shim process design

**Process model: one process per WebSocket connection** (the Bandit WebSock handler), and nothing else. Subscriptions are entries in that process's state, as they are in Action Cable, where channels are objects inside the connection, not threads. Per-subscription processes would add no runtime property: no isolation need, no separate state lifetime. Name it `CampfireWeb.Compat.ActionCable.{Plug, Socket, Protocol, Channels.*}`. Core contexts never call it (ADR-000, ui-strategy "Traps").

**Handshake (in the plug, before upgrade)**:
- **Origin check**: compare the `Origin` header to the request host, as Rails does with `allow_same_origin_as_host`. Cookie-authenticated WebSockets are open to cross-site WebSocket hijacking without it.
- **Subprotocol**: the client offers `actioncable-v1-json, actioncable-unsupported`. Put `sec-websocket-protocol: actioncable-v1-json` on the conn before `WebSockAdapter.upgrade`, otherwise `@rails/actioncable` treats the server as unsupported and never reaches `welcome`.
- **Auth**: resolve the user from the signed `session_token` cookie through the same session reader as HTTP (C-20/C-08). Load `{user_id, name, session_id}` once into state. That matches `identified_by :current_user`, which is also loaded once per connection.
- **Unauthenticated**: upgrade anyway, send `{"type":"disconnect","reason":"unauthorized","reconnect":false}`, then close. That is Rails' behavior, and it stops the client's reconnect loop. Answering 401 at the HTTP level makes the client retry with backoff forever.
- **WebSock options**:
  - `timeout: :infinity`. The Action Cable client never sends heartbeats; only the server pings. The default 60 s idle timeout would kill every socket outside a room page, which has no 50 s `refresh` traffic.
  - Set a `max_frame_size` (for example 64 KB) and `fullsweep_after` (through `websocket_options`), because long-lived processes that touch large binaries otherwise hold memory.

**Protocol loop**:
- On `init`, push `{"type":"welcome"}` and schedule `{"type":"ping","message":<unix seconds>}` every 3 s. The client's ConnectionMonitor treats about 6 s without a ping as stale and reconnects.
- Commands are `subscribe`, `unsubscribe` and `message`. The `identifier` is a **JSON string**. Keep it verbatim as the map key and echo it **byte-for-byte** in `confirm_subscription`, `reject_subscription` and every `{"identifier":..., "message":...}`. Re-encoding it can reorder keys, and the client then drops frames because the identifier no longer matches.
- Dispatch on the `channel` string through a fixed map of the 7 names to modules. Unknown names are rejected. Never use `String.to_atom`.
- A duplicate subscribe for an identifier that is already active must be ignored, as Rails does, not double-subscribed.

**Subscriptions to PubSub topics** (topic names are core-owned; the shim only maps them):

| Channel | Authorize at subscribe | Topic(s) | Actions |
|---|---|---|---|
| `HeartbeatChannel` | authenticated connection | none | none; confirm only |
| `PresenceChannel{room_id}` | membership via `Repo.Read` (M-27) | none needed (nobody broadcasts on it) | `present`, `absent`, `refresh` (Q1) |
| `TypingNotificationsChannel{room_id}` | membership | `"typing:room:<id>"` | `start`, `stop` → broadcast `{action, user:{id,name}}` |
| `ReadRoomsChannel` | authenticated connection | `"user:<id>:reads"` | none |
| `UnreadRoomsChannel` | authenticated connection | `"user:<id>:unreads"` | none |
| `RoomMessagesChannel{signed_stream_name}` | verify signature, parse `gid://campfire/Room/<id>:messages`, check membership (M-29) | `"room:<id>:messages"` | none |
| `Turbo::StreamsChannel{signed_stream_name}` | verify signature; **reject any `*:messages` name** (C-28) | stream name → topic (`rooms`, `<user gid>:rooms`) | none |

**Topic bookkeeping**: `Phoenix.PubSub.subscribe/2` is per process per topic. Subscribing twice makes every broadcast arrive twice. Keep `topics: %{topic => MapSet(identifiers)}` in state. Subscribe on the first reference and unsubscribe on the last.

**Fan-out cost**:
- Render the turbo-stream HTML **once** per event in the web layer and broadcast it pre-encoded as a binary. Binaries over 64 bytes are reference-counted, not copied per subscriber.
- In the connection, build the frame as iodata: `["{\"identifier\":", Jason.encode!(identifier), ",\"message\":", payload_json, "}"]`.
- Do not render once per subscriber.

**Forced disconnect (M-07, C-28, C-43)**:
- Each connection subscribes at `init` to a core-owned per-user topic, for example `"user:<id>"`. Core broadcasts domain events on it: `{:sockets_revoked, reconnect: true | false}`. The shim translates the event into `{"type":"disconnect","reason":"remote","reconnect":...}` and `{:stop, :normal, ...}`.
- Callers and flags, matching `user.rb`:
  - membership destroy: `reconnect: true`, after commit;
  - logout: `reconnect: true` for **all** of the user's connections, as `terminate_current_session` → `reset_remote_connections` does today; other devices re-authenticate with their own cookies;
  - deactivate and ban: `reconnect: false`.
- **Broadcast after commit everywhere.** Legacy deactivate and ban disconnect *inside* the transaction (M-07), so a fast client could reconnect and authenticate before the commit lands. Post-commit is strictly safer. Record it as an intended divergence.
- Action Cable v1 has no server-initiated per-subscription unsubscribe. Dropping the whole connection is the only way to revoke one room, which is parity.
- C-43 "logout still works when realtime is unreachable" holds trivially, because a local `PubSub.broadcast` cannot fail like the Redis call could.

**Pitfalls**:
1. **Blocking the socket process blocks pings.** If a `present` write (`unread_at = nil`) waits behind the single writer for close to `busy_timeout` (5 s), no ping goes out. The client declares the connection stale at about 6 s and reconnects, which triggers another `present` write, a feedback loop. Fixes:
   - Do authorization reads on `Repo.Read` (fast).
   - Run the `present` write and the reads broadcast in `Task.Supervisor.start_child(Campfire.TaskSupervisor, ...)`. Capture `user_id` and `room_id` first; never pass the conn.
   - Registry register and unregister stay inline (ETS).
2. **Slow consumers.** WebSock pushes are synchronous socket writes, so a stalled client lets its mailbox grow with broadcasts. Check `Process.info(self(), :message_queue_len)` on the ping tick and close with 1013 when it exceeds a threshold (for example 1,000). Set a ThousandIsland `send_timeout`.
3. **Identifier re-encoding**, the subprotocol header and the WebSock idle timeout (above). These are the three failures that look like "connected but nothing arrives".
4. **Signed stream names.**
   - Verification must match Turbo's `MessageVerifier` format (key derived from `SECRET_KEY_BASE`, digest, serializer). That needs test vectors from the pinned Rails image (ADR-000 Identity), but only for tabs that stay open across cutover. The port mints every name it renders afterwards.
   - The global `turbo_stream_from :rooms` stream (`users/sidebars/show.html.erb:2`) is unscoped by design. Keep parity and do not invent scoping in the shim.
5. **Typing amplification.** Each `start` fans out to every room member. The client throttles but the server does not. Optionally drop a `start` that arrives less than 1 s after the previous one from the same connection, and log the divergence if you do.
6. **Do not use Phoenix.Socket or Channels for this.** Their wire format (`phx_join`, ...) is not Action Cable's. Raw WebSock is the right layer (kb/ui-strategy row "Raw protocol shims").
7. **Conformance tests.** Record frame transcripts from the pinned Rails image (welcome, ping, confirm and reject for each channel, the disconnect variants) and replay them against the shim with a real WebSocket client (`Mint.WebSocket`). This is a precondition for the shim (ui-strategy "Traps"), together with an owner and a deletion trigger.

### Q4. TLS (C-56): keep Thruster vs Bandit plus ACME in the release

**Recommendation for the cutover release: keep Thruster** as a pinned, standalone Go binary (multi-arch release asset, no Ruby needed) in front of Bandit. Move to in-release TLS in a later ADR, once certificate migration and a staging-ACME rehearsal exist.

**Why keep it for now**:
- **Certificate continuity.** Thruster's autocert cache lives under its `STORAGE_PATH`, which runtime.md infers as `/rails/storage/thruster`. Not verified, so confirm it in the pinned image. Reusing that cache means an upgrade issues no new certificate. An in-release ACME client cannot read Go autocert's cache format without custom import code. Every fresh install, and any crash-looping container, re-issues against Let's Encrypt's duplicate-certificate limit (5 per week per identical name set). A boot loop could lock an operator out of HTTPS for a week.
- **Env contract.** `TLS_DOMAIN`, `HTTP_IDLE/READ/WRITE_TIMEOUT` and any Thruster vars ONCE may set (runtime.md Q1 is open) keep their exact meaning, with zero re-implementation.
- **Process model.** `thrust <cmd>` spawns one child, forwards signals and exits when the child exits. With Redis and Resque gone there is only one app process, so `bin/boot` is deleted. Use `CMD ["thrust", "/rails/bin/campfire", "start"]` under `tini` as PID 1. "Any crash restarts the container" still holds: the VM halts, Thruster exits, the container exits.
- **Bandit side**:
  - bind `127.0.0.1:${PORT:-3000}`;
  - mirror `assume_ssl` (treat the scheme as https unless `DISABLE_SSL`) plus `Plug.SSL` HSTS and redirect;
  - trust `X-Forwarded-For` **only from loopback** (`remote_ip`-style plug). Otherwise every client appears as 127.0.0.1, and the C-42 login limit (10 per 3 min per IP) throttles all users together.
- **WebSockets** proxy through Thruster today, so the shim needs nothing new.

**What option B (Bandit TLS plus an ACME library such as `site_encrypt`) would require**:
- Bandit listens on 80 (ACME http-01 plus redirect) and 443 (HTTP/1.1 and HTTP/2). The ACME child wraps the Endpoint and owns a renewal timer.
- Certificate storage explicitly under `/rails/storage/<acme>/` (C-52), owned by uid 1000.
- An importer from the Thruster autocert cache, run on first boot.
- ACME failures must not crash the Endpoint. Isolate renewal under its own supervisor, serve the cached certificate, and log the error.
- `DISABLE_SSL` and "no TLS_DOMAIN" modes reproduced: HTTP-only on 80 with or without `force_ssl`.
- Check the library's maintenance status before committing. It has a small user base, and the team would own its ACME edge cases.

The benefit is one fewer process and binary, which is the idiomatic end state (kb/infrastructure "Reverse Proxies").

**Ports 80/443 as uid 1000 (both options)**: the legacy image already binds low ports as a non-root user. It relies on Docker's default `net.ipv4.ip_unprivileged_port_start=0` inside the container namespace. Bandit, or Thruster, gets the same behavior, so the port has parity and no new requirement. Do **not** add `setcap cap_net_bind_service` to `beam.smp`. It sits inside the release's `erts-*` directory, breaks on every ERTS bump, and file capabilities make the loader ignore `LD_*` variables. Document the same Docker-default dependency the legacy image has. Keep `USER 1000:1000`, `WORKDIR /rails` (Thruster's relative storage path depends on it) and `EXPOSE 80 443` (C-50).

### Q5. Typing indicator and heartbeat: ephemeral PubSub only?

**Yes. Neither needs a process, a table or Presence.**

- **TypingNotificationsChannel**:
  - Membership is checked at subscribe (F-13 negative probe).
  - `start` and `stop` from the client call `Phoenix.PubSub.broadcast(Campfire.PubSub, "typing:room:<id>", payload)` with `{action, user: %{id, name}}`, using the `name` cached at connect. That is parity, since Rails also uses the connection's `current_user`.
  - Broadcast to everyone, including the sender's other tabs. The JS filters `user.id !== Current.user.id` (`typing_notifications_controller.js:40`), so `broadcast_from` is unnecessary.
  - Expiry is purely client-side: a 5 s purge in `typing_tracker.js`. Nothing is persisted, and losing events on restart is acceptable.
- **HeartbeatChannel**: an empty channel (`heartbeat_channel.rb`). Its only job is to give `refresh_room_controller.js` `connected` and `disconnected` callbacks, which drive the catch-up `GET /rooms/:id/refresh?since=` and the offline banner after 5 s. In the shim, confirm the subscription and do nothing else. No topic, no state, no DB. Liveness comes from the protocol-level 3 s pings.
- **PresenceChannel `refresh`** is the only "heartbeat" with server state. Under Q1 it only resets an in-memory timer and writes nothing to the DB.

---

## Supervision tree sketch

```elixir
# lib/campfire/application.ex  (sketch, not a plan)
def start(_type, _args) do
  Campfire.Storage.ensure_dirs!()            # storage/db, storage/files (C-52)

  children = [
    CampfireWeb.Telemetry,
    Campfire.Repo,                           # writer: pool_size 1, :immediate, WAL, busy_timeout 5_000
    {Ecto.Migrator, repos: [Campfire.Repo], skip: System.get_env("SKIP_MIGRATIONS") == "true"},
    # Campfire.Boot.ResetConnections,        # :ignore child; ONLY if DB presence counters are kept (Q1 says no)
    Campfire.Repo.Read,                      # read-only pool, after migrations (WAL already set)
    {Phoenix.PubSub, name: Campfire.PubSub},
    {Registry, keys: :duplicate, name: Campfire.RoomPresence,
     partitions: System.schedulers_online()},
    {Supervisor, name: Campfire.Services, strategy: :one_for_one, children: [
      {Finch, name: Campfire.Finch.Webhook,   pools: %{default: [size: 5, pool_max_idle_time: 60_000]}},
      {Finch, name: Campfire.Finch.Push,      pools: %{default: [size: 25, count: 2]}},
      {Finch, name: Campfire.Finch.Opengraph, pools: %{default: [size: 5, pool_max_idle_time: 60_000]}},
      {Task.Supervisor, name: Campfire.TaskSupervisor},
      {Campfire.RateLimit, clean_period: :timer.minutes(1)}   # Hammer ETS backend
    ]},
    {Oban, Application.fetch_env!(:campfire, Oban)},          # Lite engine, writer repo
    CampfireWeb.Endpoint                     # Bandit on 127.0.0.1:$PORT behind Thruster;
                                             # /cable -> Compat.ActionCable.Plug (WebSockAdapter.upgrade)
    # option B: {SiteEncrypt.Phoenix.Endpoint, endpoint: CampfireWeb.Endpoint} instead
  ]

  Supervisor.start_link(children, strategy: :rest_for_one, name: Campfire.Supervisor)
end
```

Container process tree (option A): `tini (PID 1) → thrust → bin/campfire start (BEAM)`. Thruster listens on 80/443 and proxies to Bandit at 127.0.0.1:3000.

---

## Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Half-open sockets keep a user "present", suppressing their unread marking and push for minutes | high (business rule F-12, F-15) | Expire presence 60 s after the last `present`/`refresh` in memory (Q1) |
| R2 | The shim socket process blocks on the writer, misses 3 s pings, and the client reconnect storm adds more writes | high | Off-socket Task for the `present` write; authorize on `Repo.Read`; measure writer checkout queue time (performance-gates) |
| R3 | Identifier re-encoding, a missing subprotocol header or WebSock's 60 s idle timeout make sockets "connected but silent" | high | Frame-level conformance replay from the pinned Rails image |
| R4 | In-release ACME re-issues certificates on upgrade or boot loop and hits Let's Encrypt limits | high (operator outage) | Keep Thruster for cutover; option B only with an autocert-cache importer and staging rehearsal |
| R5 | `remote_ip` = loopback behind Thruster collapses the per-IP login limit (C-42) and banned-IP checks | med | Trust `X-Forwarded-For` from 127.0.0.1 only |
| R6 | PubSub restart leaves live sockets subscribed to nothing | med | Top-level `:rest_for_one` so the Endpoint restarts after PubSub |
| R7 | Admin `eval` scripts open a second writer on the live DB file | med | `prepare-backup` and `reset-password` via `rpc` |
| R8 | Thruster `STORAGE_PATH` default is inferred, not verified | med | Inspect the pinned image's Thruster version and default before choosing A or B |
| R9 | Docker stop (10 s) kills mid-drain; Oban jobs left `executing` | low | Endpoint drainer plus Oban `shutdown_grace_period` ≤ 5 s; Oban rescues orphans on boot |
| R10 | The shim becomes permanent ("Traps" in kb/ui-strategy) | med | Owner plus deletion trigger in the divergence ledger (a later LiveView or `turbo-stream-source` ADR) |

## Recommendations

1. **Presence**: a `Campfire.RoomPresence` facade over a duplicate-key `Registry`, with a 60 s refresh-driven in-memory TTL. No DB writes for `refresh` or counters; `present` still writes `unread_at = nil` (off-socket) and broadcasts reads. Columns stay, unused, and are ledgered for retirement after the rollback window. No boot reset needed. Rollback-safe because Rails resets them at Puma boot.
2. **Sampling**: unread at commit inside `Repo.transact`; push at Oban job run time. Both read the same facade (mechanisms Q4, legacy parity).
3. **Supervision**: top-level `:rest_for_one` in the order Telemetry → Repo → Migrator → Repo.Read → PubSub → RoomPresence → Services (`:one_for_one`: 3×Finch, TaskSupervisor, Hammer) → Oban → Endpoint. Default restart intensity, so fatal failures still exit the container.
4. **Shim**: one WebSock process per connection, subscriptions as state, a fixed channel map, verbatim identifiers, `timeout: :infinity`, 3 s pings, an Origin check, Rails-style `unauthorized` disconnect, refcounted PubSub topics, pre-encoded payloads, a mailbox cap, and a per-user core topic for post-commit forced disconnects.
5. **TLS**: keep a pinned Thruster binary as the front process for the cutover release (`tini → thrust → release`). Delete `bin/boot`. Bandit on loopback with loopback-only proxy trust. Open a follow-up ADR for Bandit TLS plus ACME with a certificate importer.
6. **Typing and heartbeat**: ephemeral PubSub only; heartbeat confirms and holds no state.
7. **Before the realtime slice**: record legacy Action Cable frame transcripts, plus Turbo signed-stream-name and session-cookie test vectors, from the pinned Rails image.
