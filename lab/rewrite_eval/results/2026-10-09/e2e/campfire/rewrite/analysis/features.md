# Features — ONCE Campfire

Source: `~/Projects/campfire-bench/once-campfire-elixir/reference` @ `90b330024dec3e757c79b6a7e6568f93da8e3148` (2026-09-26) · Stack: Rails 8.2 (Hotwire/Turbo + Stimulus, Action Cable on Redis, Resque, SQLite + FTS5, Active Storage disk, Web Push) · Shape: **mixed** — single-tenant web app + realtime + background worker + operator CLI scripts · Capabilities: **28**

Mode: `--auto`. All triage defaults are `preserve` and every triage default is **ASSUMED** (not approved by the user).
Paths below are relative to SOURCE. Line numbers are from the revision above.

## Actors

| Actor | How identified | Notes |
|-------|----------------|-------|
| Anonymous visitor | no `session_token` cookie | May reach: login, first run (only while no account), join link (with valid code), session transfer, QR code, logo, avatars, PWA manifest/service worker, `/up` (`app/controllers/*` `allow_unauthenticated_access`) |
| Member | signed permanent cookie `session_token` → `sessions.token` (`app/controllers/concerns/authentication.rb:93-95`, `authentication/session_lookup.rb:2-5`) | `users.role = member`, `status = active` |
| Administrator | same as member, `role = administrator` (`app/models/user/role.rb:5`) | `can_administer?` = admin, OR creator of the record, OR record is new (`app/models/user/role.rb:8-10`) |
| Record creator | `record.creator == Current.user` | Gains edit/delete rights on own messages and own rooms via `can_administer?(record)` |
| Bot (machine) | `:bot_key` path segment `"{id}-{token}"` (`config/routes.rb:66`, `app/models/user/bot.rb:20-23`) | `role = bot`; only bot-allowed endpoints; CSRF skipped (`authentication.rb:10,101-103`) |
| Bot webhook endpoint (machine, outbound) | `webhooks.url` set by admin | Receives JSON POST, may reply with text or a file (`app/models/webhook.rb`) |
| Browser push service (machine) | VAPID; endpoint host allow-list | FCM, Mozilla, Apple, WNS (`app/models/push/subscription.rb:4-10`) |
| Service worker (client machine) | `/service-worker` | Shows notifications, sets app badge, focuses/opens room (`app/views/pwa/service_worker.js`) |
| Operator | shell inside the container | `script/admin/*`, ONCE `hooks/pre-backup`, `hooks/post-restore`, env vars, `bin/boot` |
| Deactivated / banned user | `users.status` = `deactivated` / `banned` | Sessions deleted; cannot log in (`User.active.authenticate_by`, `sessions_controller.rb:11`) |

## Capability Map

| ID | Capability (goal) | Actors | Entry anchors | Side effects | Legacy tests | Triage |
|----|-------------------|--------|---------------|--------------|--------------|--------|
| F-01 | First person to open a fresh install becomes administrator of the single account and lands in "All Talk" | Anonymous | `config/routes.rb:4`, `app/controllers/first_runs_controller.rb:10-21`, `app/models/first_run.rb:5-15` | session started | `test/controllers/first_runs_controller_test.rb:10-34`, `test/models/first_run_test.rb:10-20` | preserve |
| F-02 | A person signs in with email+password and stays signed in on that device until sign-out; sign-out kills live connections and the device's push subscription | Member, Admin | `config/routes.rb:6-10`, `app/controllers/sessions_controller.rb:1-39`, `concerns/authentication.rb` | session row, cookie, cable disconnect | `test/controllers/sessions_controller_test.rb:7-83`, `test/channels/application_cable/connection_test.rb:4-16` | preserve (T-11, T-19) |
| F-03 | A person holding the account join link creates an account and is immediately a member of every open room | Anonymous | `config/routes.rb:32-33`, `app/controllers/users_controller.rb:2-33`, `app/models/account/joinable.rb` | memberships to open rooms | `test/controllers/users_controller_test.rb:14-43`, `test/models/user_test.rb:9` | preserve |
| F-04 | A user (or an admin on their behalf) obtains a time-limited sign-in link/QR to sign in on another device | Member, Admin | `config/routes.rb:8`, `app/controllers/sessions/transfers_controller.rb`, `app/models/user/transferable.rb`, `app/views/users/profiles/_transfer.html.erb:1`, `app/views/users/show.html.erb:49-52` | new session | `test/controllers/sessions/transfers_controller_test.rb:4-10` | preserve? (T-01, T-02) |
| F-05 | A member opens the app and lands in the last room they visited, with a sidebar of their visible rooms and DMs that stays current live | Member | `app/controllers/welcome_controller.rb`, `rooms_controller.rb:6-12`, `concerns/tracked_room_visit.rb`, `users/sidebars_controller.rb` | cookie `last_room` | `test/controllers/welcome_controller_test.rb:8-14`, `rooms_controller_test.rb:8-18`, `users/sidebars_controller_test.rb:8-24` | preserve |
| F-06 | Members create, rename, convert (open<->closed) and delete shared rooms; membership of closed rooms is curated; open rooms include everyone | Member, Admin, Creator | `config/routes.rb:62,82-84`, `rooms/opens_controller.rb`, `rooms/closeds_controller.rb`, `rooms_controller.rb:14-19`, `app/models/room.rb`, `rooms/open.rb` | sidebar broadcasts, cable reconnect on revoke | `rooms/opens_controller_test.rb`, `rooms/closeds_controller_test.rb`, `rooms_controller_test.rb:68-76`, `models/room_test.rb`, `rooms/open_test.rb` | preserve (T-14) |
| F-07 | Two or more people open a private direct conversation; the same set of people always gets the same room, and it can never be widened | Member | `config/routes.rb:85`, `rooms/directs_controller.rb`, `app/models/rooms/direct.rb` | sidebar broadcast per participant | `rooms/directs_controller_test.rb:8-53`, `models/rooms/direct_test.rb:4-17`, `rooms/opens_controller_test.rb:61-71`, `rooms/closeds_controller_test.rb:69` | preserve (T-10, T-14) |
| F-08 | A member posts a message (rich text, mentions, file, `/play` sound) and every member watching the room sees it within a second, in order | Member | `config/routes.rb:63`, `messages_controller.rb:20-28`, `app/models/message.rb`, `message/broadcasts.rb`, `channels/room_messages_channel.rb` | broadcast, unread, push job, bot webhooks, FTS index | `messages_controller_test.rb:51-68,142`, `system/sending_messages_test.rb:9`, `system/composer_test.rb`, `models/message_test.rb` | preserve |
| F-09 | A member reads room history: latest page, older/newer pages on scroll, a permalink to one message, and catch-up after being offline or hidden | Member | `messages_controller.rb:10-18,62-71`, `rooms_controller.rb:46-53`, `config/routes.rb:79`, `rooms/refreshes_controller.rb`, `message/pagination.rb` | — | `messages_controller_test.rb:12-43`, `rooms/refreshes_controller_test.rb:8` | preserve (T-08) |
| F-10 | The author or an admin edits or deletes a message and every viewer sees the change live | Creator, Admin | `messages_controller.rb:36-59`, `messages/edit.html.erb` | broadcast replace/remove, FTS update | `messages_controller_test.rb:79-131`, `system/sending_messages_test.rb:29-49`, `system/composer_test.rb:73-135,177` | preserve |
| F-11 | A member reacts to a message with a short boost and removes only their own boost; everyone sees it live | Member | `config/routes.rb:88-92`, `messages/boosts_controller.rb`, `app/models/boost.rb` | broadcast, message touch | `messages/boosts_controller_test.rb:9-18`, `system/boosting_messages_test.rb` | preserve (T-09) |
| F-12 | Rooms with activity the member hasn't seen show as unread; viewing a room clears it; presence is known per room | Member | `channels/presence_channel.rb`, `channels/unread_rooms_channel.rb`, `channels/read_rooms_channel.rb`, `models/membership/connectable.rb`, `room.rb:48-51,79-81`, `config/puma.rb:51` | DB writes on connect/disconnect | `models/membership_test.rb`, `channels/presence_channel_test.rb`, `channels/unread_rooms_channel_test.rb`, `system/unread_rooms_test.rb`, `users/sidebars_controller_test.rb:16-24` | preserve |
| F-13 | Members see who is typing in the room right now | Member | `channels/typing_notifications_channel.rb`, `app/javascript/models/typing_tracker.js:1-2` | ephemeral broadcast | none | preserve |
| F-14 | A member chooses per room how involved they are (hidden, nothing, mentions, everything), which drives visibility and notifications | Member | `config/routes.rb:76`, `rooms/involvements_controller.rb`, `membership.rb:9,14` | sidebar broadcast to that user | `rooms/involvements_controller_test.rb:8-47`, `models/room_test.rb:33`, `rooms/direct_test.rb:17` | preserve |
| F-15 | A member who is away gets an OS push notification for new messages they care about, on each registered device | Member, Push service, Service worker | `config/routes.rb:45-49`, `users/push_subscriptions_controller.rb`, `push_subscriptions/test_notifications_controller.rb`, `room/message_pusher.rb`, `lib/web_push/*`, `config/initializers/web_push.rb`, `models/push/subscription.rb` | outbound HTTPS, subscription cleanup | `models/room/push_test.rb`, `models/push/subscription_test.rb`, `users/push_subscriptions_controller_test.rb`, `lib/web_push/persistent_request_test.rb` | preserve (T-12) |
| F-16 | A member full-text searches every message they can reach and re-runs recent searches | Member | `config/routes.rb:94-96`, `searches_controller.rb`, `message/searchable.rb`, `models/search.rb`, `db/schema.rb:182` | FTS index, `searches` rows | `searches_controller_test.rb:9-41`, `message/searchable_test.rb` | preserve (T-13) |
| F-17 | Pasting a public URL produces a safe link preview; the server never fetches private-network addresses | Member | `config/routes.rb:98`, `unfurl_links_controller.rb`, `models/opengraph/*`, `lib/restricted_http/private_network_guard.rb`, `lib/rails_ext/actiontext_opengraph_embeds.rb` | outbound HTTP | `unfurl_links_controller_test.rb`, `models/opengraph/*_test.rb`, `lib/restricted_http/private_network_guard_test.rb`, `lib/rails_ext/actiontext_opengraph_embeds_test.rb`, `system/unfurling_links_test.rb` | preserve (T-18) |
| F-18 | While composing, a member @-mentions people via autocomplete, scoped to the room | Member | `config/routes.rb:54-56`, `autocompletable/users_controller.rb`, `user/mentionable.rb` | — | `autocompletable/users_controller_test.rb:8-31`, `system/composer_test.rb:61` | preserve |
| F-19 | A user edits their own profile (name, email, password, bio, avatar) and anyone can view a user's card and avatar | Member | `config/routes.rb:37-44`, `users/profiles_controller.rb`, `users/avatars_controller.rb`, `users_controller.rb:19-25`, `user/avatar.rb` | avatar variants | `users/profiles_controller_test.rb`, `users/avatars_controller_test.rb`, `users_controller_test.rb:8` | preserve |
| F-20 | An administrator manages the account: name, logo, room-creation policy, custom CSS, member roles, deactivation, join link reset | Admin | `config/routes.rb:12-26`, `accounts_controller.rb`, `accounts/users_controller.rb`, `accounts/custom_styles_controller.rb`, `accounts/logos_controller.rb`, `accounts/join_codes_controller.rb`, `user.rb:35-46` | cable disconnect on deactivate | `accounts_controller_test.rb`, `accounts/*_test.rb`, `models/user_test.rb:15-27`, `models/account_test.rb` | preserve? (T-03, T-05) |
| F-21 | An administrator bans an abusive user: they are logged out everywhere, their messages vanish, and their IPs can no longer write | Admin | `config/routes.rb:40`, `users/bans_controller.rb`, `user/bannable.rb`, `models/ban.rb`, `concerns/block_banned_requests.rb`, `jobs/remove_banned_content_job.rb` | job, broadcasts, IP block | `users/bans_controller_test.rb:8-75`, `concerns/block_banned_requests_test.rb:11-27` | preserve? (T-04) |
| F-22 | An administrator creates, edits, deactivates bots and rotates a bot's key | Admin | `config/routes.rb:16-20`, `accounts/bots_controller.rb`, `accounts/bots/keys_controller.rb`, `user/bot.rb` | webhook row | `accounts/bots_controller_test.rb`, `accounts/bots/keys_controller_test.rb`, `models/user/bot_test.rb` | preserve |
| F-23 | A bot holding a key reads, posts, edits, deletes its messages and adds/removes its boosts over HTTP in rooms it belongs to | Bot | `config/routes.rb:65-71`, `messages/by_bots_controller.rb`, `messages/boosts/by_bots_controller.rb`, `views/messages/*.json.jbuilder` | broadcasts, webhooks to other bots | `messages/by_bots_controller_test.rb`, `messages/boosts/by_bots_controller_test.rb`, `lib/rails_ext/log_scrubbing_formatter_test.rb` | preserve (T-07, T-20) |
| F-24 | When a bot is mentioned (or messaged directly) its webhook receives the message, and its reply is posted into the room as the bot | Bot endpoint | `messages_controller.rb:79-85`, `user/bot.rb:51-57`, `jobs/bot/webhook_job.rb`, `models/webhook.rb` | outbound POST, reply message | `models/webhook_test.rb:4-55`, `models/user/bot_test.rb:34`, `messages_controller_test.rb:142`, `messages/by_bots_controller_test.rb:29-37` | preserve? (T-06, T-07) |
| F-25 | Whatever a member writes, other readers never get executable markup, and old messages keep their mentions, embeds and formatting | Member | `helpers/content_filters.rb`, `helpers/content_filters/*`, `helpers/messages_helper.rb:58-73`, `lib/rails_ext/action_text_allowed_tags.rb`, `lib/rails_ext/action_text_attachables.rb` | — | `helpers/content_filters_test.rb`, `helpers/messages_helper_test.rb`, `lib/rails_ext/action_text_attachables_test.rb`, `helpers/rich_text_helper_test.rb`, `system/composer_test.rb:53,92-163` | preserve (T-17) |
| F-26 | Files posted to rooms are stored, thumbnailed/previewed safely and served to readers; anonymous callers cannot upload | Member | `models/message/attachment.rb`, `config/initializers/vips.rb`, `config/initializers/active_storage_authentication.rb`, `config/initializers/active_storage.rb`, `messages/attachment_presentation` | disk writes, variants | `models/message/attachment_test.rb`, `lib/vips_loader_policy_test.rb`, `controllers/active_storage_authentication_test.rb` | preserve |
| F-27 | The app installs as a PWA, refuses unsupported browsers, serves logo/QR assets and identifies its version | Anonymous, Member | `config/routes.rb:35,100-103`, `pwa_controller.rb`, `views/pwa/*`, `concerns/allow_browser.rb`, `qr_code_controller.rb`, `accounts/logos_controller.rb:7-17`, `concerns/version_headers.rb` | — | `sessions_controller_test.rb:20-25`, `qr_code_controller_test.rb:4`, `accounts/logos_controller_test.rb:9-33` | preserve (T-16) |
| F-28 | An operator deploys, backs up, restores, rotates secrets and resets a password without touching the UI | Operator | `Dockerfile`, `Procfile`, `bin/boot`, `bin/start-app`, `hooks/pre-backup`, `hooks/post-restore`, `script/admin/*`, `config/initializers/{vapid,sentry,version,resque}.rb`, `config/environments/production.rb:53-85` | files in `storage/` | `lib/rails_ext/log_scrubbing_formatter_test.rb` (only logs) | preserve |

---

## F-01 First-run bootstrap
**Goal**: The first visitor to an empty install creates the one account ("Campfire"), becomes its administrator, and lands in an open room "All Talk"; afterwards first run is unreachable.
**Sub-behaviors**: show form; create account + admin + first room; redirect away once any account exists.
**Invariants**:
- At most one account ever exists: unique index `accounts.singleton_guard` (`db/schema.rb:20-22`); a concurrent second create raises `RecordNotUnique` and is redirected to root (`app/controllers/first_runs_controller.rb:15-16`). Asserted by `test/controllers/first_runs_controller_test.rb:34` ("not vulnerable to race conditions").
- First run is blocked as soon as `Account.any?` (`first_runs_controller.rb:20-21`); `test/controllers/first_runs_controller_test.rb:15`.
- Login page redirects to first run when `User.none?` (`sessions_controller.rb:26-27`); `sessions_controller_test.rb:12`.
- First user is `administrator`, first room is `Rooms::Open` named "All Talk", creator = admin, admin has membership (`app/models/first_run.rb:2-14`); `test/models/first_run_test.rb:10-20`. Later users default to `member` (`test/models/user/role_test.rb:4`).
- `Current.account` is always `Account.first` (`app/models/current.rb:14-16`) — the app is single-tenant.
**Acceptance probes**:
- Given no account, when a visitor POSTs name/email/password, then one account, one admin user, one open room "All Talk" with that admin as member exist, and the visitor is signed in at `/`.
- Given no account and two concurrent first-run POSTs, then exactly one account exists and both requests redirect to `/` (no 500).
- Negative: Given an account exists, when anyone GETs `/first_run`, then they are redirected to `/`.
**Side effects**: session + cookie.

## F-02 Password sign-in, persistent session, sign-out
**Goal**: An active user signs in with email+password, stays signed in on that device indefinitely, and sign-out ends that device session, its live sockets and its push subscription.
**Sub-behaviors**: login form, login, logout, session resume, return-to-after-login.
**Invariants**:
- Only `status = active` users authenticate (`sessions_controller.rb:11`); bad credentials render the form with 401 and "Too many requests or unauthorized." (`:30-32`); `sessions_controller_test.rb:30-39`.
- Rate limit: 10 login attempts per 3 minutes, response 429 (`sessions_controller.rb:3`). Counter store is Rails cache = Redis in production (`config/environments/production.rb:72`). UNKNOWN: the rate-limit key — Rails default is `request.remote_ip`; confirm no custom `by:`.
- Session cookie: signed, permanent (20 y), `httponly`, `SameSite=Lax`, name `session_token` (`authentication.rb:93-95`); Rails session cookie `_campfire_session` also 20 y (`config/initializers/session_store.rb`). Server sessions have no expiry; `last_active_at`, IP and UA refresh at most hourly (`app/models/session.rb:2,14-17`).
- Unauthenticated requests store `return_to_after_authenticating` and redirect to login (`authentication.rb:50-52,89-91`).
- Sign-out: deletes the session row, resets the Rails session, deletes the cookie, disconnects the user's live connections with reconnect (`authentication.rb:70-81`); if the realtime service is unreachable sign-out still succeeds (`sessions_controller_test.rb:71`). Removes the push subscription whose endpoint the client sends (`sessions_controller.rb:35-38`; `sessions_controller_test.rb:83`).
- CSRF enforced on every non-bot request (`authentication.rb:10`).
- Realtime socket connects only with a valid session cookie (`app/channels/application_cable/connection.rb:12-17`; `test/channels/application_cable/connection_test.rb:4-16`).
- Already signed-in users visiting join pages are redirected to root (`authentication.rb:22-25,55-57`; `users_controller_test.rb:19`).
**Acceptance probes**:
- Given an active user, when they POST correct credentials, then a `sessions` row is created, cookie set, and they're redirected to the URL they originally requested.
- Negative: Given a deactivated or banned user with the right password, then 401 and no session.
- Negative: Given 10 failed POSTs from one IP within 3 minutes, then the 11th gets 429.
- Given a user with two devices, when device A signs out, then device B stays signed in, and A's sockets are closed.
**Side effects**: `sessions` row, cable disconnect, push subscription deletion.

## F-03 Join via invite link
**Goal**: Anyone with the current join link `/join/XXXX-XXXX-XXXX` creates a member account, is signed in, and is a member of every open room.
**Sub-behaviors**: join form; create user; duplicate-email handling.
**Invariants**:
- Join code = 12 alphanumerics in 3 groups of 4 joined by `-` (`app/models/account/joinable.rb:13-14`), generated on account create (`:5`), rotatable by admins (F-20). A wrong code is 404 (`users_controller.rb:27-29`; `users_controller_test.rb:26`).
- New users get memberships to all open rooms after commit (`app/models/user.rb:22,53-55`; `test/models/user_test.rb:9`), with the column default involvement `mentions` (`db/schema.rb:86`). Note `insert_all` here omits involvement, unlike `grant_to`.
- Duplicate email → redirect to login prefilled with that email (`users_controller.rb:15-16`; `users_controller_test.rb:43`). Email unique index (`db/schema.rb:158`).
- Password has no length validation and long passwords are accepted (`has_secure_password validations: false`, `user.rb:20`; `test/models/user_test.rb:4`). UNKNOWN: are blank passwords accepted at join? No validation is visible.
**Acceptance probes**:
- Given the current join code, when a visitor submits name/email/password, then they are a member of every open room and land at `/`.
- Negative: Given a stale join code (after reset), then 404.
- Negative: Given an existing email, then no user is created and the visitor is redirected to `/session/new?email_address=…`.

## F-04 Sign-in transfer link
**Goal**: A user signs in on another device via a link or QR valid for 4 hours; an admin can mint the same link for any active user to recover their access.
**Invariants**:
- Link = `/session/transfers/{signed_id(purpose: :transfer, expires_in: 4h)}` (`app/models/user/transferable.rb:4,12-13`); it depends on `SECRET_KEY_BASE` (wire/data contract).
- Only `User.active` can redeem it; an invalid or expired link gets 400 (`sessions/transfers_controller.rb:8-13`); `sessions/transfers_controller_test.rb:10`.
- The link can be reused within its 4 h window (no single-use marker). See T-02.
- Admins see the link for other active users (`app/views/users/show.html.erb:49-52`); everyone sees their own on the profile.
**Acceptance probes**:
- Given a transfer id minted 3 h ago, when PUT `/session/transfers/:id` is sent, then a new session starts and the caller is redirected.
- Negative: Given an id minted 5 h ago, then 400. Given the user is deactivated, then 400.

## F-05 Landing, last room and sidebar
**Goal**: A member opening the app lands in their last-visited room, or the oldest room they belong to, and sees a sidebar of rooms and DMs that updates live.
**Invariants**:
- `/` redirects to the last visited room (permanent cookie `last_room`) if the user is still a member, else to the user's oldest room by `created_at`; if they have no rooms, the welcome page is shown (`welcome_controller.rb:2-7`, `concerns/tracked_room_visit.rb:8-19`); `welcome_controller_test.rb:8-14`, `rooms_controller_test.rb:18`.
- `/rooms` redirects to `Current.user.rooms.last` (`rooms_controller.rb:6-7`).
- Sidebar: only `visible` memberships (not `invisible`); shared rooms sorted case-insensitively by name (`membership.rb:11,14`); DMs sorted by room `updated_at` desc (`users/sidebars_controller.rb:13-15`); room `updated_at` is touched by each new message (`message.rb:4`).
- Up to 20 DM placeholders: active users without a DM with me, oldest first (`users/sidebars_controller.rb:2,17-19`).
- Live updates: new open room → prepended for everyone on the global `:rooms` stream; closed room create/update → per member stream; room delete → removed on global stream; DM → per participant (`rooms/opens_controller.rb:49-55`, `rooms/closeds_controller.rb:63-80`, `rooms/directs_controller.rb:26-30`, `rooms_controller.rb:60-62`).
- Room display name for a DM is the other participants' names as a sentence, or my own name if alone (`helpers/rooms_helper.rb:55-61`).
**Acceptance probes**:
- Given I visited room B last and am still a member, when I GET `/`, then I'm redirected to B. Negative: if I was removed from B, I'm redirected to my oldest room.
- Given an admin creates an open room, then every connected member's sidebar shows it without reload.
- Negative: Given a closed room I'm not in is created, then my sidebar stream receives nothing about it.

## F-06 Shared rooms (open / closed) lifecycle
**Goal**: Members create rooms; open rooms include every active user automatically, closed rooms include an explicit list; the creator or an admin can rename, convert, revise membership and delete.
**Sub-behaviors**: new/create open, new/create closed (with picked users), edit, update (rename, convert type, grant/revoke), delete.
**Invariants**:
- When `settings.restrict_room_creation_to_administrators` is on, non-admins get 403 on new/create (`rooms_controller.rb:40-43`); `rooms/opens_controller_test.rb:27`, `rooms/closeds_controller_test.rb:32`. DMs are not restricted.
- Update and delete need `can_administer?(room)` (admin or creator) (`rooms_controller.rb:36-38`, `rooms/opens_controller.rb:3`, `rooms/closeds_controller.rb:3`); `rooms/opens_controller_test.rb:36`, `rooms/closeds_controller_test.rb:58`, `rooms_controller_test.rb:76`.
- Room lookups are always scoped to the user's own rooms; a non-member is redirected to `/` with "Room not found or inaccessible" (`rooms_controller.rb:22-27`).
- Open/closed endpoints can't reach DMs (`room_scope` = `without_directs`, `rooms/opens_controller.rb:45-47`, `rooms/closeds_controller.rb:47-49`). Model validation also forbids a type change away from Direct (`room.rb:73-77`).
- Converting to open grants membership to all active users (`rooms/open.rb:3-8`; `rooms/open_test.rb:9`). Converting to closed keeps current members, then applies the posted user list (`rooms/closeds_controller.rb:31-37`).
- Closed-room create = room + memberships in one transaction (`room.rb:35-41`); revise = grant + revoke in one transaction (`room.rb:12-17`); `models/room_test.rb:4-20`.
- Membership uniqueness `(room_id, user_id)` (`db/schema.rb:92`). UNKNOWN: `grant_to` uses `insert_all`, so a duplicate user id in the grant list (or granting an existing member) behaves per SQLite `INSERT … ON CONFLICT DO NOTHING`, which Rails `insert_all` uses by default. Confirm.
- Revoking a membership closes the revoked user's sockets with reconnect, so streams are re-authorized (`membership.rb:7`; `membership_test.rb:85`).
- The editor can remove themselves (`rooms/closeds_controller_test.rb:81`).
- New memberships get `involvement = mentions` for shared rooms (`room.rb:65-67`).
- Delete removes the room, memberships (`delete_all`) and messages (`destroy` → boosts, rich text, attachments) permanently (`room.rb:2,21`).
- Default name for new rooms is "New room" (`rooms/opens_controller.rb:8`).
**Acceptance probes**:
- Given a closed room with A, B and an admin, when the admin revises it to A, C, then B loses membership and B's open socket is reconnected and can no longer subscribe to the room's messages; C sees the room in the sidebar.
- Given a closed room is converted to open, then every active user is a member.
- Negative: Given the restriction setting is on, when a member POSTs `/rooms/opens`, then 403.
- Negative: Given a member who did not create room R, when they PATCH `/rooms/opens/R`, then 403.
- Negative: Given a DM id, when anyone PATCHes `/rooms/opens/:dm` or `/rooms/closeds/:dm`, then they're redirected (not found) and the room's type and members are unchanged.

## F-07 Direct messages
**Goal**: Picking one or more people opens the single DM room for exactly that set of people (me included); participants are notified of everything by default, and any participant can delete it.
**Invariants**:
- One room per exact user set: `find_or_create_for` compares member-id sets (`app/models/rooms/direct.rb:5-16`); `rooms/direct_test.rb:4-11`, `rooms/directs_controller_test.rb:17`. Not enforced in the DB, so concurrent creates can race. UNKNOWN whether duplicates exist in production data.
- The current user is always included (`rooms/directs_controller.rb:18-19`).
- Default involvement `everything` (`rooms/direct.rb:19-21`).
- Any participant may delete the DM (`rooms/directs_controller.rb:34-36`). The relaxation only reaches DMs: `room_scope = directs` (`:38-40`); `rooms/directs_controller_test.rb:24-53`.
- Never convertible to open or closed (`room.rb:73-77`; `rooms/opens_controller_test.rb:61-71`; `rooms/closeds_controller_test.rb:69`).
- Deactivating a user keeps their DM memberships (`user.rb:39`; `test/models/user_test.rb:15`).
**Acceptance probes**:
- Given A opens a DM with B twice, then exactly one room exists with members {A,B}.
- Given A opens a DM with {B}, and separately with {B,C}, then two distinct rooms exist.
- Negative: Given A is in a DM, when A sends DELETE `/rooms/directs/:closed_room_id` for a closed room A didn't create, then nothing is deleted.

## F-08 Post a message and deliver it live
**Goal**: A member posts text (rich text with mentions, tables, code), a file, or a `/play` sound into a room they belong to; all members currently viewing the room see it appended within a second, and the message is durable, searchable and triggers unread, push and bot side effects.
**Invariants**:
- Posting requires membership (`concerns/room_scoped.rb:9-12`). A non-member or a missing room gets the `room_not_found` view (`messages_controller.rb:26-27`).
- `client_message_id` comes from the client (optimistic rendering, DOM id `message_{client_message_id}` via `to_key`, `message.rb:27-29`; `app/javascript/models/client_message.js`); it defaults to a UUID for bots (`message.rb:11`). Not unique in the DB (`db/schema.rb:97-105`). UNKNOWN: duplicate submission (retry) creates duplicates; there is no dedup.
- Creator defaults to the current user (`message.rb:5`).
- After commit: memberships that are visible, disconnected and not the author get `unread_at = message.created_at`; a push job is enqueued (`message.rb:12`, `room.rb:48-51,79-81`); `models/message_test.rb:6`.
- Broadcasts after creation: append to the room's guarded message stream, and a per-member `user_{id}_unreads` signal `{roomId}` to every member, including the author (`message/broadcasts.rb:2-18`); `messages_controller_test.rb:51-68`.
- The room message stream can only be subscribed through `RoomMessagesChannel`, which checks current membership at subscribe time; the stock Turbo channel refuses `…:messages` streams (`channels/room_messages_channel.rb`, `channels/concerns/room_streams_are_authorized.rb`, `config/initializers/turbo_streams_authorization.rb`); `test/channels/room_messages_channel_test.rb:11-79`.
- Webhooks to bots: in a DM, every active bot member; otherwise active bots mentioned in the body; never the author (`messages_controller.rb:79-85`).
- Mentions = User attachables inside the rich text, filtered to room members (`message/mentionee.rb`); `models/message_test.rb:19`.
- Sound: body exactly `/play <name>` with a known name renders the sound (55 built-ins, `app/models/sound.rb:29-88`, `message.rb:39-43`).
- Emoji-only messages get the `message--emoji` presentation (`lib/rails_ext/string.rb`, `helpers/messages_helper.rb:34`; `models/message_test.rb:12`).
- Attachment-only messages use the filename as plain text (`message.rb:23-25`; `message/attachment_test.rb:17`).
- Rendering failures degrade to an "unrenderable" placeholder plus a Sentry report, never a 500 for the page (`helpers/messages_helper.rb:47-51,68-72`).
- Composer: Enter sends, Shift/rich mode newline, Meta+Enter sends, per-room drafts survive room hopping, reply quotes with attribution (`test/system/composer_test.rb:9-177`). These are UI contracts; see ui-strategy.
**Acceptance probes**:
- Given A and B viewing room R, when A posts "hi", then B's view shows "hi" within 1 s and in `created_at` order.
- Given C is a member not viewing R (disconnected), then C's membership gets `unread_at` and C's unread stream receives `{roomId: R}`.
- Negative: Given D is not a member of R, then D's unread stream gets nothing (`unread_rooms_channel_test.rb:14`), and D cannot subscribe to R's message stream even with a signed stream name harvested earlier (`room_messages_channel_test.rb:28`).
- Negative: Given a POST to a room the user isn't in, then no message is created.

## F-09 Read history, permalink and catch-up
**Goal**: A member sees the latest 40 messages, pages older/newer in 40s, opens a permalink centered on one message, and after being offline or hidden for 60 s gets the messages created and edited since.
**Invariants**:
- Page size 40; order by `created_at` asc (`message/pagination.rb:4-17`). `before`/`after` use strict `created_at` comparison (`:10-11`). See T-08.
- Empty page → 204 (`messages_controller.rb:13-17`); a non-empty page uses ETag/`fresh_when` (`:14`); `messages_controller_test.rb:12-35`.
- Permalink `/rooms/:room_id/@:message_id` renders `page_before + message + page_after` (`config/routes.rb:79`, `rooms_controller.rb:46-53`).
- Refresh: `GET /rooms/:id/refresh?since=<epoch ms>` returns up to 40 new messages (created after `since`), plus up to 40 messages updated after `since` that aren't new (`rooms/refreshes_controller.rb:6-14`); `rooms/refreshes_controller_test.rb:8`. The client triggers it on `online` or after being hidden for 60 s, and shows offline state after 5 s disconnected (`app/javascript/controllers/refresh_room_controller.js:6-7`). Epoch format = ms (`config/initializers/time_formats.rb`).
- History is membership-scoped (`room_scoped.rb`).
**Acceptance probes**:
- Given 100 messages, then GET index returns messages 61–100; `?before=61` returns 21–60; `?after=60` returns 61–100.
- Given a room with no messages, then 204.
- Given a client hidden for 2 minutes during which 3 messages were created and 1 edited, when it becomes visible, then refresh returns 3 new and 1 updated.
- Negative: Given a non-member, then index is 404.

## F-10 Edit and delete messages
**Goal**: The author or any admin edits or deletes a message; all viewers see the replacement or removal live.
**Invariants**:
- `can_administer?(message)` = admin or creator (`messages_controller.rb:57-59`, `user/role.rb:8-10`); `messages_controller_test.rb:79-131`.
- Update re-renders the presentation for all viewers with `maintain_scroll` (`messages_controller.rb:39`); the search index is updated after commit (`message/searchable.rb:6`).
- Delete destroys boosts and rich text, removes it from the index, and broadcasts the removal (`messages_controller.rb:47-50`, `message.rb:7`).
- Editing preserves mentions, embeds and Trix-era formatting (`system/composer_test.rb:73-135`, `helpers/rich_text_helper_test.rb`).
- Up-arrow in an empty composer edits my last message (`system/composer_test.rb:177`).
**Acceptance probes**:
- Given A's message, when an admin edits it, then all viewers see the new body and search finds the new text, not the old.
- Negative: Given B (non-admin) and A's message, then PATCH and DELETE return 403.

## F-11 Boosts
**Goal**: Members attach short reactions to messages they can reach and remove only their own; viewers see changes live.
**Invariants**:
- Message lookup through `reachable_messages` (rooms I belong to) (`messages/boosts_controller.rb:25-26`).
- Destroy only my own boost (`find_by!(id:, booster: Current.user)`, `:29-30`).
- Boost touches the message (`boost.rb:2`), so its `updated_at` changes and it appears in refresh "updated" lists and bot caches.
- Content: UI `maxlength: 16` (`views/messages/boosts/new.html.erb:11`) and `limit: 16` in the schema (`db/schema.rb:74`). SQLite does not enforce varchar limits and there is no model validation. See T-09.
- Broadcast append to `boosts_message_{client_message_id}`, and remove (`messages/boosts_controller.rb:37-44`).
- Ordered by `created_at` (`boost.rb:5`).
**Acceptance probes**:
- Given A boosts B's message with "🔥", then all viewers see it; A deletes it, and it disappears.
- Negative: Given A tries to DELETE B's boost, then 404.
- Negative: Given a message in a room A isn't in, then POST a boost → 404.

## F-12 Unread state and presence
**Goal**: Rooms with unseen activity are marked unread for the member; opening a room (on any device) marks it read on all their devices; a member counts as "present" in a room while a tab is subscribed, with a 60 s liveness window.
**Invariants**:
- Connection TTL 60 s; `connected` = `connected_at >= now-60s` (`membership/connectable.rb:4-9`). Client heartbeat refresh every 50 s; visibility changes debounce 5 s (`app/javascript/controllers/presence_controller.js:5,9`).
- Subscribing to presence: `connections += 1` (or reset to 1 if stale), `connected_at = now`, `unread_at = nil`, and broadcast `{room_id}` on `user_{id}_reads` (`channels/presence_channel.rb:5-9`, `connectable.rb:16-18,25-27`). Unsubscribe decrements and clears `connected_at` at 0 (`connectable.rb:34-37`); `membership_test.rb:36-75`, `presence_channel_test.rb:35-43`.
- Presence subscription is rejected for non-members, missing or nonexistent rooms (`channels/room_channel.rb:2-13`; `presence_channel_test.rb:17-29`).
- On server boot every membership is marked disconnected (`config/puma.rb:51`, `connectable.rb:12-14`).
- Unread is set only for `visible`, disconnected, non-author memberships (`room.rb:79-81`).
- Unread and read signals are per-user streams, never global (`channels/unread_rooms_channel.rb:2-11`, `channels/read_rooms_channel.rb`); `unread_rooms_channel_test.rb:4-25`.
- The push badge count = number of the user's unread memberships (`push/subscription.rb:19`).
- Removing a membership resets the user's connections (`membership_test.rb:85`).
**Acceptance probes**:
- Given B has room R open in a tab, when A posts, then B's membership stays read.
- Given B's tab closed 61 s ago without a clean unsubscribe, when A posts, then B's membership becomes unread.
- Given B has two tabs on R and closes one, then B is still connected (connections = 1).
- Negative: Given a server restart, then no membership claims to be connected until a client re-subscribes.

## F-13 Typing indicator
**Goal**: Room members see "X, Y" typing while others type, and it clears within 5 s of inactivity.
**Invariants**: subscription requires membership (`typing_notifications_channel.rb` < `room_channel.rb`); payload `{action: start|stop, user: {id, name}}` (`typing_notifications_channel.rb:2-12`); the client sorts names and purges after 5 s (`typing_tracker.js:1-2,25-40`). Not persisted.
**Acceptance probes**:
- Given A types in R, then B (member) receives `start` with A's id and name. Negative: a non-member's subscription is rejected.
- Given A stops sending events, then B's indicator clears after 5 s or less.

## F-14 Room involvement
**Goal**: A member sets their involvement per room: `invisible` hides the room from their sidebar and from unread/push, `nothing` = no push, `mentions` = push on mention, `everything` = push on every message.
**Invariants**:
- Enum values `invisible nothing mentions everything` stored as strings (`membership.rb:9`, `db/schema.rb:86`) — data contract.
- Only the membership of the current user is changed (`room_scoped.rb`); any member, not only admins, can change it (`rooms/involvements_controller_test.rb:47`).
- Sidebar broadcast: going invisible removes the room; leaving invisible prepends it; visible→visible and DMs send nothing (`rooms/involvements_controller.rb:16-25`; tests `:13-38`).
**Acceptance probes**:
- Given involvement `everything`, when set to `invisible`, then the room vanishes from that user's sidebar live and new messages don't mark it unread.
- Negative: Given a DM, when involvement changes, then no sidebar broadcast is sent.

## F-15 Web Push notifications
**Goal**: A member registers devices for push; when someone else posts in a room where the member is not currently connected and is involved, each device gets a notification within seconds (title, body, deep-link path, badge), and dead subscriptions are cleaned up.
**Sub-behaviors**: subscribe/refresh, list/delete devices, send test notification, deliver on message, invalidate expired, remove on sign-out.
**Invariants**:
- Endpoint must be HTTPS, port 443, and its host equal to or a subdomain of the allow-list (`push/subscription.rb:4-10,41-59`), and must resolve to a public IP (SSRF guard); `models/push/subscription_test.rb:8-135`, `users/push_subscriptions_controller_test.rb:33-54`.
- Re-registering an existing triple `(endpoint, p256dh, auth)` touches it if still valid, else 422 (`users/push_subscriptions_controller.rb:7-19`; tests `:21,54`).
- Recipients: memberships of the room that are `visible`, disconnected and not the author, joined to `everything` users, plus `mentions` users who are mentioned (`room/message_pusher.rb:40-60`); `models/room/push_test.rb:10-43`.
- Payload: DM → title = author name, body = plain text; shared → title = room name, body = "Author: text"; `path` = room path; icon = account logo; badge = unread count; urgency high; VAPID subject `mailto:support@37signals.com` (`room/message_pusher.rb:24-38`, `lib/web_push/notification.rb:7-30`). This is a wire contract with the service worker (`views/pwa/service_worker.js:1-30`).
- DNS is resolved at delivery time, and the connection is pinned to that IP with proxies ignored (anti-rebinding) (`push/subscription.rb:18-27`, `config/initializers/web_push.rb:18-60`); `lib/web_push/persistent_request_test.rb:10-30`.
- Expired subscription or TLS error → the subscription is destroyed (`lib/web_push/pool.rb:38-50`, `config/initializers/web_push.rb:6-13`); `room/push_test.rb:53`.
- Delivery guarantee today: a Resque job builds the payload, then delivery runs in an in-memory thread pool (50 threads, queue 10 000); overflow is silently dropped (`pool.rb:6,35`). At-most-once and non-durable. See T-12.
- Test notification: title "Campfire Test", random body (`push_subscriptions/test_notifications_controller.rb:5`).
- VAPID keys come from env `VAPID_PRIVATE_KEY`/`VAPID_PUBLIC_KEY` or credentials (`config/initializers/vapid.rb`). Operational contract: existing browser subscriptions are bound to the public key.
**Acceptance probes**:
- Given B (involvement `everything`, disconnected, 1 device) and A posts in R, then exactly one push to B's endpoint with title R's name and body "A: text".
- Negative: Given B is connected to R, then no push (`room/push_test.rb:33`). Given B is `invisible`, then no push (`:43`). Given B is `mentions` and not mentioned, then no push.
- Negative: Given an endpoint `https://fcm.googleapis.com.evil.com/…` or `:8443`, then subscribe returns 422.
- Given the push service answers 410, then the subscription row is deleted.

## F-16 Search
**Goal**: A member searches message text across all rooms they currently belong to and sees up to 100 most recent matches in chronological order; their last 10 distinct queries are remembered and clearable.
**Invariants**:
- Index: SQLite FTS5 virtual table `message_search_index(body, tokenize=porter)`, `rowid = messages.id`, body = plain text (mentions as `@Name`, attachment filename) (`db/schema.rb:182`, `message/searchable.rb`); `message/searchable_test.rb:4-23`. Data contract under the SQLite constraint.
- The index is maintained after commit on create, update and destroy (`message/searchable.rb:5-7`).
- Query sanitized: non-word chars → spaces before MATCH (`searches_controller.rb:29-31`), which prevents FTS syntax errors.
- Scope: `Current.user.reachable_messages` (`searches_controller.rb:23`); `searches_controller_test.rb:16-23`.
- Results: `.last(100)` of matches ordered by `created_at` (`searches_controller.rb:23`, `searchable.rb:9`).
- Recent searches: `find_or_create_by(query).touch`; keep the newest 10 by `updated_at` (`models/search.rb:4-17`); `searches_controller_test.rb:32-41`.
**Acceptance probes**:
- Given messages "deploying now" in R1 (member) and R2 (not a member), when searching "deploy", then only the R1 message is returned (porter stemming).
- Given 11 distinct searches, then 10 remain. Clear → 0.
- Negative: Given a query `"foo" OR bar*`, then no error and it's treated as words.

## F-17 Link unfurling
**Goal**: When a member pastes a public URL, the client gets OpenGraph title, description, canonical URL and safe image to embed; private, oversized, non-HTML or malicious targets yield nothing.
**Invariants**:
- Only `http(s)`; host must resolve to a public IP and the connection is pinned to that IP; redirects (max 10) are re-resolved and re-checked; 5 MB cap enforced while streaming; only `200 text/html`; URLs ending in media/archive extensions are not fetched (`opengraph/fetch.rb:5-78`, `opengraph/location.rb:14-51`); `opengraph/fetch_test.rb:10-107`, `opengraph/location_test.rb:5-65`.
- The private-network policy is shared with other 37signals apps via the `surfguard` gem (`lib/restricted_http/private_network_guard.rb:6-9`), covering IPv4/IPv6 private, CGNAT, NAT64, 6to4, Teredo and more (`test/lib/restricted_http/private_network_guard_test.rb:5-143`).
- Title and description are stripped of tags and must be present; image must be a valid public URL with content type jpeg, png, gif or webp, so SVG is refused (`opengraph/metadata.rb:13-25`, `metadata/fetching.rb:14,40-48`); `metadata_test.rb:4-173`.
- twitter.com/x.com status URLs are fetched via fxtwitter.com (`metadata/fetching.rb:12-13,50-66`); `unfurl_links_controller_test.rb:62-70`. See T-18.
- Response: 200 JSON `{title,url,image,description}` or 204 (`unfurl_links_controller.rb:5-9`).
- Stored embeds are re-validated at render time: href and image must be absolute http(s) on a named, non-IP host other than this Campfire's host (`lib/rails_ext/actiontext_opengraph_embeds.rb:48-89`); `actiontext_opengraph_embeds_test.rb:6-85`, `rooms_controller_test.rb:23-54`.
- A message that is only an unfurled URL hides the duplicate link text (`content_filters/remove_solo_unfurled_link_text.rb`); `content_filters_test.rb:5-64`.
**Acceptance probes**:
- Given `http://169.254.169.254/` or a host resolving to `10.0.0.5`, then 204 and no connection to that IP.
- Given a public page redirecting to `http://localhost`, then 204.
- Given a 6 MB HTML page with no Content-Length, then 204.
- Negative: Given a hand-written embed whose image points at `https://<this host>/rooms/1`, then the rendered message has no image/link.

## F-18 Mention autocomplete
**Goal**: While typing `@`, a member sees up to 20 matching active users, scoped to the room's members when a room is given, and inserts a mention that later resolves to that user.
**Invariants**: `filter` (editor) or `query` param; `name LIKE %q%` (`user.rb:25`); room scope through `Current.user.rooms.find(room_id)` (404 if not a member) (`autocompletable/users_controller.rb:26-28`); 20 per page, ordered by name; HTML response for the editor, JSON `{name (HTML-escaped), value, avatar_url, sgid}` (`views/autocompletable/users/_user.json.jbuilder`); `autocompletable/users_controller_test.rb:8-31`. Mention attachment content type `application/vnd.campfire.mention` (`user/mentionable.rb:4`) — data contract inside stored message HTML.
**Acceptance probes**:
- Given room R with {A,B} and account users {A,B,C}, when searching "" with `room_id=R`, then only A, B.
- Negative: Given a user named `<img onerror>`, then the JSON name is escaped.
- Negative: `room_id` of a room I'm not in → 404.

## F-19 Profile and avatars
**Goal**: A user edits their own name, email, password, bio and avatar; anyone signed in can view a user card; avatars are served from stable, cacheable, unguessable URLs.
**Invariants**:
- The profile always targets `Current.user` (`users/profiles_controller.rb:15-16`); `profiles_controller_test.rb:23`. Blank fields are dropped via `.compact` (`:20`). The notice says avatar changes take up to 30 minutes, matching the cache TTL (`:24`).
- Avatar URL `/users/{signed_id(purpose: :avatar)}/avatar?v={updated_at}` (`config/routes.rb:58-60`, `user/avatar.rb:11-18`). An invalid token gets 404 (`avatars_controller.rb:4`; `avatars_controller_test.rb:29`). The token has no expiry and depends on `SECRET_KEY_BASE` (wire contract).
- Served as webp 512 px square variant; bots without an avatar get the default bot SVG; others get an SVG of their initials; `Cache-Control: public, max-age=1800, stale-while-revalidate=1 week`, ETag by user (`avatars_controller.rb:6-19`; tests `:8-29`).
- Avatar delete removes only my own (`avatars_controller.rb:22`).
- User card: admins see email, sign-in link (F-04), ban button (not for self) (`views/users/show.html.erb:36-58`). `GET /users/:id` is reachable for any user id, including deactivated users (`users_controller.rb:23-25`).
**Acceptance probes**:
- Given A updates their bio, then A's card shows it. Negative: PATCH `/users/B/profile` still edits A (the route defaults to `me`).
- Given a tampered avatar token, then 404.

## F-20 Account administration
**Goal**: Admins rename the account, upload or remove the logo, toggle "only admins create rooms", set custom CSS, promote or demote members, deactivate members and rotate the join link; all members can see the member list and join link.
**Invariants**:
- Every mutation requires an administrator; non-admins get 403 (`concerns/authorization.rb:3-5`; `accounts_controller_test.rb:54`, `accounts/users_controller_test.rb:26`, `accounts/custom_styles_controller_test.rb:22`, `accounts/join_codes_controller_test.rb:15`).
- Member list: admins see active + banned, others only active; bots excluded; admins listed separately; 500 per page (`accounts_controller.rb:5-31`; `accounts_controller_test.rb:13`).
- Role change allows only `member` or `administrator`; any other value becomes `member` (`accounts/users_controller.rb:23-25`). There is no guard against removing the last admin. See T-05.
- Deactivate (`user.rb:35-46`, one transaction): close sockets, delete non-DM memberships, push subscriptions, searches and sessions, set `status=deactivated`, and rewrite the email to `local-deactivated-{uuid}@domain` so the address can re-join. Messages remain. `test/models/user_test.rb:15-27`, `accounts/users_controller_test.rb:17`.
- Settings JSON `{restrict_room_creation_to_administrators: bool}` with string coercion (`account.rb:9`; `test/models/account_test.rb:4-17`). UNKNOWN: where `has_json` is defined (no definition found in `lib/`; likely a gem or framework extension). The architect must confirm coercion and unknown-key handling.
- Logo variants: large 512 and small 192 PNG; public, ETag by account, `max-age=300, stale-while-revalidate=1 week`; stock icon fallback; `/account/logo?v=…&size=small` (`account.rb:4-7`, `accounts/logos_controller.rb:7-47`, `config/routes.rb:28-30`); `accounts/logos_controller_test.rb:9-40`.
- Custom styles are emitted raw (`html_safe`) inside `<style>` on every page (`helpers/application_helper.rb:15-18`). See T-03.
- Join code reset invalidates the old link immediately (`account/joinable.rb:8-10`; `account/joinable_test.rb:10`).
**Acceptance probes**:
- Given admin deactivates B, then B's sessions are gone, B's open sockets close, B is removed from shared rooms but stays in DMs, and B's email is freed for a new join.
- Negative: Given a member PATCHes `/account/users/:id` with role=administrator, then 403.
- Negative: Given an admin PATCHes role=bot, then the role becomes `member`.

## F-21 Ban and unban
**Goal**: An admin bans a user: the user is logged out everywhere, all their messages are deleted and vanish from viewers' screens, and every IP they had sessions from can no longer make write requests; unbanning restores the account (not the messages).
**Invariants**:
- Admin only (`users/bans_controller.rb:2`; `bans_controller_test.rb:51,75`). The target can be any user id, including admins and bots; the UI hides the button for self only (`views/users/show.html.erb:56`). See T-04.
- Ban (one transaction): create a `Ban` per distinct non-blank session IP; reject private/loopback/link-local IPs, and the validation raises and aborts the ban (`models/ban.rb:4-19`, `user/bannable.rb:4-10,31-35`). UNKNOWN: whether a user with a private-IP session (e.g. behind a LAN proxy without proper `remote_ip`) can be banned at all, since `create!` raises.
- Then close sockets, delete sessions, enqueue `RemoveBannedContentJob`, and set `status=banned` (`bannable.rb:37-41`); `bans_controller_test.rb:8-39`.
- Content removal: destroy each message and broadcast its removal (`bannable.rb:23-28`).
- Banned IPs: every non-GET/HEAD request from a banned `remote_ip` gets 429, including login POST (`concerns/block_banned_requests.rb:5-15`); `block_banned_requests_test.rb:11-27`.
- Unban: delete all ban rows and set active (`bannable.rb:12-17`); `bans_controller_test.rb:59`.
**Acceptance probes**:
- Given B had sessions from 203.0.113.5 and 198.51.100.7, when banned, then both IPs get 429 on POST, B's messages disappear from open viewers, and B cannot sign in.
- Negative: Given a non-admin, then POST `/users/B/ban` → 403.
- Given unban, then POST from those IPs succeeds and B can log in; deleted messages stay deleted.

## F-22 Bot management
**Goal**: Admins create bots (name, avatar, optional webhook URL), edit them, rotate their key and deactivate them.
**Invariants**:
- Admin only (`accounts/bots_controller.rb:2`, `bots/keys_controller.rb:2`).
- A bot is a `User` with `role=bot`, a 12-char alphanumeric `bot_token` (unique index `db/schema.rb:157`), and key = `"{id}-{token}"` (`user/bot.rb:11-27,38-44`); `models/user/bot_test.rb:4-29`.
- Reset key invalidates the old key immediately (`bot.rb:42-44`; `keys_controller_test.rb:8`).
- Update with a blank `webhook_url` deletes the webhook (`bot.rb:61-67`; `bots_controller_test.rb:39`).
- Deactivate uses the same path as users (F-20); only active bots are listed or editable (`bots_controller.rb:6,33`).
- Bots are excluded from the members list (`accounts_controller.rb:6`), and bots get open-room memberships on create like any user (`user.rb:22`).
**Acceptance probes**:
- Given an admin resets bot X's key, then requests with the old key get redirected to login (not authenticated) and requests with the new key work.
- Negative: a member GETs `/account/bots` → 403.

## F-23 Bot HTTP API (inbound)
**Goal**: A bot uses `/rooms/:room_id/:bot_key/messages[...]` to page through history (JSON + `Link`/`X-Total-Count`), post text (raw body) or a file, edit or delete its own messages, and add or remove its own boosts, only in rooms it is a member of.
**Invariants**:
- Auth: `bot_key` param, stripped, `active_bots.find_by(id, bot_token)` (`authentication.rb:43-48`, `user/bot.rb:20-23`). Bots are denied (403) on every non-bot endpoint (`authentication.rb:101-103`; `by_bots_controller_test.rb:147`). CSRF is skipped only for bot-key auth (`authentication.rb:10`).
- A regular session cannot use bot endpoints to impersonate (`by_bots_controller_test.rb:53,199`; `boosts/by_bots_controller_test.rb:74`).
- A room the bot isn't in → 404 (`by_bots_controller.rb:27-31`; tests `:135-140,189`).
- Create: raw UTF-8 request body becomes the rich-text body, or `attachment` multipart; neither → 422; success → `201 Location: /messages/:id` (`by_bots_controller.rb:16-19,33-37,57-63`); tests `:8-43`.
- Update and destroy only own messages (admin bots N/A), else 403; destroy → 204 (`by_bots_controller.rb:8,21-24`; tests `:152-220`).
- Index JSON per message: `{id, created_at (UTC), body:{plain_text, html}, creator:{id,name,role,avatar_url}, room:{id}, url}` (`views/messages/_message.json.jbuilder`, `views/users/_user.json.jbuilder`); oldest→newest; `X-Total-Count` = room message count; `Link: <…?before=id>; rel="next"` for older (or `after=` when paging forward) only if more exist (`by_bots_controller.rb:39-55`); tests `:64-121`. This is a wire contract.
- Boost API: raw body = content; blank → 422; `201` with JSON `{id, content, created_at, booster, message:{id,url}}`; destroy only own boost, else 404 (`messages/boosts/by_bots_controller.rb`, `views/messages/boosts/_boost.json.jbuilder`); `boosts/by_bots_controller_test.rb:10-105`.
- Bot posts go through the same create path as members: broadcast, unread, push, and webhooks to other mentioned bots excluding itself (`messages_controller.rb:20-25,79-85`; `by_bots_controller_test.rb:29-37`).
- The bot key is redacted from logs, including in the `Link` header (`lib/rails_ext/log_scrubbing_formatter.rb:5-15`; `log_scrubbing_formatter_test.rb:6-36`).
**Acceptance probes**:
- Given bot X in room R, when it POSTs body "héllo ✓", then 201, Location header set, and members see the message from X live.
- Given 45 messages, then GET index returns 40 with `Link rel=next ?before=<first id>` and `X-Total-Count: 45`.
- Negative: wrong key → not authenticated (redirect to login, per `request_authentication`). UNKNOWN: whether a JSON client receives 302 vs 401; the legacy test `by_bots_controller_test.rb:130` asserts the observable status. Check it before porting.
- Negative: X PATCHes a member's message → 403. X POSTs to a room it isn't in → 404.

## F-24 Bot webhooks (outbound)
**Goal**: When a message mentions a bot (or is posted in a DM containing the bot), the bot's webhook receives a JSON description within seconds; a 200 text reply or a file reply is posted into the room as the bot; a timeout posts an apology message.
**Invariants**:
- Trigger rules in F-08; never to the author; only bots with a webhook (`bot.rb:51-53`). Delivered by a background job (`jobs/bot/webhook_job.rb`), Resque, at-least-once per job retry policy. UNKNOWN: retry behaviour (ApplicationJob has retries commented out, `app/jobs/application_job.rb:2-6`), so effectively at-most-once.
- Payload (wire contract): `{user:{id,name}, room:{id,name,path:"/rooms/:id/:bot_key/messages"}, message:{id, body:{html, plain (recipient's @mention and surrounding whitespace removed)}, path:"/rooms/:room_id/@:message_id"}}` (`webhook.rb:41-46,76-80`); `webhook_test.rb:4`.
- POST JSON, 7 s open and read timeout (`webhook.rb:5,29-35`).
- Reply: status 200 + `text/html|text/plain` → text message by the bot; else if the content type maps to a known MIME → attachment message (`webhook.rb:9-16,57-74`); `webhook_test.rb:20-42`. A 500 with no content type → nothing (`webhook_test.rb:42`). Replies are broadcast but do NOT trigger further webhooks (`webhook.rb:61-62,72-73`).
- Timeout → message "Failed to respond within 7 seconds" from the bot (`webhook.rb:17-18`; `webhook_test.rb:49`).
- No private-network guard by design: admins may point bots at internal services (documented, `webhook.rb:27-28`).
**Acceptance probes**:
- Given bot X with a webhook, when A posts "@X ping" in R, then X's URL receives a JSON POST with `message.body.plain == "ping"`; a `200 text/plain "pong"` reply appears in R from X.
- Given the webhook hangs past 7 s, then R gets "Failed to respond within 7 seconds" from X.
- Negative: Given X posts a message mentioning itself via the API, then no webhook to X.
- Negative: Given a shared room where X is a member but not mentioned, then no webhook.

## F-25 Safe rendering of message content
**Goal**: Message HTML from any author or bot is rendered so that no reader runs script or is pointed at unsafe URLs, while editor formatting (strike, underline, mark, tables, code language) and legacy Trix and Lexxy content keep rendering.
**Invariants**:
- Three layers: tag allow-list filter (`content_filters/sanitize_tags.rb:2-4`), an isolated attribute sanitizer allowing `class` and stripping event handlers and unsafe schemes (`content_filters/sanitize_attributes.rb`), and `auto_link` re-sanitization with extended allow-lists (`helpers/messages_helper.rb:2-5,65-66`). Links open `target=_blank`. Tests: `content_filters_test.rb:73-179`, `messages_helper_test.rb:4-20`, `system/unfurling_links_test.rb:18`.
- The sanitizer instance is isolated per call to avoid cross-request races (`sanitize_attributes.rb:19-27`; `content_filters_test.rb:129`).
- Legacy mention SGIDs remain resolvable after `SECRET_KEY_BASE` rotation and from Rails-7 Marshal-format SGIDs, for `User` only (`lib/rails_ext/action_text_attachables.rb:9-40`); `action_text_attachables_test.rb:8-30`, `action_text_attachment_test.rb:8-26`. This is a data contract on stored `action_text_rich_texts.body`.
- Stored body formats include both Trix (`<div>`-wrapped, embed attributes on the node) and Lexxy (`<p>`, details in content markup) (`actiontext_opengraph_embeds.rb:18-46`, `remove_solo_unfurled_link_text.rb:43-57`); `rich_text_helper_test.rb:5-48`.
**Acceptance probes**:
- Given a body `<a href="javascript:alert(1)">x</a><img src=x onerror=alert(1)>`, then the rendered HTML has no `javascript:` href and no `onerror`.
- Given a Trix-era message with a mention whose SGID was signed with an old secret, then it still renders as a mention of that user.
- Negative: Given `<script>` or `<iframe>` in the body, then they're removed.

## F-26 Attachments and media processing
**Goal**: Files posted to rooms are stored, images get ≤1200×800 thumbnails and videos webp previews, dangerous image decoders are never invoked, and anonymous callers can't upload.
**Invariants**:
- Analyze + thumbnail synchronously on create (`message/attachment.rb:14-41`); `message/attachment_test.rb:7-17`.
- libvips untrusted loaders blocked; BMP, ICO and PSD are not variable; allowed: PNG, GIF, JPEG, TIFF, WebP, AVIF, HEIC; denied: SVG, BMP, PSD, ICO, OpenSlide, FITS, MAT, NIfTI, RAW, VIPS (`config/initializers/vips.rb`; `test/lib/vips_loader_policy_test.rb:18-83`).
- Direct-upload endpoints and disk PUT require a session; disk GET stays public (signed blob URLs) with `Cache-Control: max-age=3600, public` (`config/initializers/active_storage_authentication.rb`, `config/initializers/active_storage.rb`); `active_storage_authentication_test.rb:8-44`.
- Storage: Active Storage disk service under `storage/files` (`config/initializers/storage_paths.rb`, `config/storage.yml`). Data contract: blob keys and paths, `active_storage_*` tables.
- UNKNOWN: max upload size. No explicit limit was found in app code; thruster or proxy defaults may apply (`Dockerfile:61-63` timeouts only).
**Acceptance probes**:
- Given a JPEG upload 4000×3000, then a thumb variant ≤1200×800 exists and readers get it.
- Negative: Given an anonymous POST to the direct-upload endpoint, then 401 and no blob.
- Negative: Given a BMP or SVG upload, then no variant is produced via the blocked loaders, and the message still renders as a file.

## F-27 PWA shell, browser gate, public assets
**Goal**: The app installs as a PWA with a stable service worker and manifest at the root, refuses outdated browsers with a friendly page (except Apple Messages link previews), serves QR codes and logos publicly, and labels responses with version headers.
**Invariants**:
- `/webmanifest` and `/service-worker` at stable root URLs, unauthenticated, no CSRF (`pwa_controller.rb:2-11`, `config/routes.rb:100-101`).
- Minimum browsers: Safari 17.2, Chrome 120, Firefox 121, Opera 104, no IE (`concerns/allow_browser.rb:4-7`); `sessions_controller_test.rb:20-25`. Apple Messages UA spoof is detected (`application_platform.rb:30-35`). UNKNOWN: whether `apple_messages?` actually bypasses the gate; the reference is in views or helpers, not `allow_browser`.
- `/qr_code/:base64url` renders an SVG QR of any URL, public, cached 1 year (`qr_code_controller.rb:4-10`); `qr_code_controller_test.rb:4`.
- Every response carries `X-Version` (APP_VERSION or GIT_REVISION or "0") and `X-Rev` (`concerns/version_headers.rb`, `config/initializers/version.rb`). UNKNOWN: which client reads them (likely the JS for reload-on-deploy). Check before dropping.
- `/up` health check (`config/routes.rb:103`).
- Multilingual hint labels on auth pages (`helpers/translations_helper.rb`, used in `first_runs/show`, `sessions/new`, `sessions/incompatible_browser`).
**Acceptance probes**:
- Given Chrome 119, then the incompatible-browser page renders. Given Chrome 120, then login renders.
- Given GET `/service-worker`, then JS is served without login.
- Negative: Given a banned IP, GET `/up` still works (GET is never blocked).

## F-28 Operator operations
**Goal**: An operator runs the single container (web + realtime + workers), generates secrets, resets a user's password, and takes or restores consistent backups through ONCE hooks.
**Invariants**:
- `bin/boot` supervises the Procfile processes (web via thruster+puma, redis, resque-pool) and propagates INT/TERM (`bin/boot:6-54`, `Procfile`). `bin/start-app` runs `db:prepare` before serving.
- Backup: `hooks/pre-backup` → `script/admin/prepare-backup` writes an online SQLite backup to `storage/backups/<db>.sqlite3` (`script/admin/prepare-backup:6-23`). Restore: `hooks/post-restore` copies it over `storage/db/<env>.sqlite3` and deletes `-wal`/`-shm` (`hooks/post-restore:4-12`). Operational contract with the ONCE host.
- `script/admin/reset-password <email> <password>` exits -1 if not found (`script/admin/reset-password`).
- `script/admin/generate-secrets` prints `SECRET_KEY_BASE`, `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`; `create-vapid-key` prints a VAPID pair.
- Env contract: `SECRET_KEY_BASE` / `RAILS_MASTER_KEY`, `VAPID_*`, `REDIS_URL`, `SENTRY_DSN`, `SKIP_TELEMETRY`, `APP_VERSION`, `GIT_REVISION`, `DISABLE_SSL` (force_ssl unless set, `production.rb:84-85`), `RAILS_LOG_LEVEL`, `PORT`, `WEB_CONCURRENCY`, `JOB_CONCURRENCY`, `RAILS_MAX_THREADS`, `HTTP_IDLE/READ/WRITE_TIMEOUT` (thruster), ports 80/443 (`Dockerfile:61-79`). UNKNOWN: thruster TLS env (e.g. `TLS_DOMAIN`) is consumed by thruster, not app code. Confirm the operator-facing list from ONCE docs.
- Logs go to STDOUT, with bot keys scrubbed (F-23) and params filtered (`config/initializers/filter_parameter_logging.rb:6-8`: passw, email, secret, token, _key, crypt, salt, certificate, otp, ssn, cvv, cvc, endpoint, message.body).
- Sentry only in production and unless `SKIP_TELEMETRY`, `send_default_pii=false` (`config/initializers/sentry.rb`).
- Runs as non-root uid 1000 (`Dockerfile:56-58`).
**Acceptance probes**:
- Given a running instance with writes in flight, when pre-backup runs, then `storage/backups/production.sqlite3` is a consistent DB that opens and contains all committed messages.
- Given post-restore with a snapshot present, then the app boots on the snapshot with no stale WAL.
- Negative: reset-password for an unknown email exits non-zero and changes nothing.

## Triage Questions

All defaults are `preserve` (ASSUMED, `--auto`; none approved).

- **T-01 F-04 (preserve?)** Admins can mint a 4 h sign-in link for any active user, which lets them sign in as that user (`views/users/show.html.erb:49-52`). It works as account recovery, since there is no email reset. Keep, or require an audit trail?
- **T-02 F-04 (preserve?)** Transfer links are reusable until expiry (not single-use) (`user/transferable.rb:12-13`). Keep, or make single-use? Single-use would be a behavior change.
- **T-03 F-20 (preserve? security)** Custom CSS is injected raw with `html_safe` inside `<style>` (`helpers/application_helper.rb:15-18`); an admin can break out with `</style><script>`. Admins are trusted, but this is stored XSS against all members. Keep verbatim, or escape `</style>`? Suggest `redesign` (escape the closing tag) with no visible change for legitimate CSS.
- **T-04 F-21 (preserve?)** Ban IP-blocks every session IP of the user (a shared office NAT then blocks colleagues' writes, including login); admins can ban other admins; a private-IP session makes `Ban.create!` raise and aborts the whole ban (`ban.rb:11-18`, `bannable.rb:31-35`). Keep all three?
- **T-05 F-20 (preserve?)** No guard against demoting or deactivating the last administrator (`accounts/users_controller.rb:8-16`). Keep?
- **T-06 F-24 (preserve?)** A webhook reply with a non-200 status but a recognizable content type (e.g. 500 `application/json`) becomes an attachment message, because `extract_attachment_from` ignores status (`webhook.rb:65-70`). Looks accidental. Legacy test `webhook_test.rb:42` only covers 500 without a content type.
- **T-07 F-23/F-24 (preserve?)** A bot posting via the API that mentions another bot triggers that bot's webhook, and nothing stops two bots from looping (`messages_controller.rb:79-85` via `by_bots_controller.rb:16-18`). Webhook replies don't fan out, but API posts do. Keep, or add a loop guard?
- **T-08 F-09 (preserve?)** Pagination uses strict `created_at <`/`>` with no id tie-breaker (`message/pagination.rb:10-11`); messages sharing a timestamp at a page edge can be skipped. Suggest `redesign`: `(created_at, id)` keyset, which is invisible to clients.
- **T-09 F-11 (preserve?)** Boost length of 16 is enforced only by the UI `maxlength` and an unenforced SQLite column limit; the bot API accepts any length (`boosts/by_bots_controller.rb:36-38`). Enforce 16 server-side?
- **T-10 F-07 (redesign, perf)** DM lookup scans all DM rooms (FIXME, `rooms/direct.rb:10-16`) and isn't race-safe. Suggest a canonical member-set key with a unique index; behavior stays the same.
- **T-11 F-02 (preserve?)** Sessions never expire server-side; cookies last 20 years. Keep (product choice for chat apps)?
- **T-12 F-15 (preserve or strengthen)** Push delivery is at-most-once from an in-memory pool and drops on overflow or restart (`lib/web_push/pool.rb:6,35`). A durable per-subscription job is an upgrade, not a downgrade. Approve the upgrade, or keep best-effort?
- **T-13 F-16 (preserve)** Search returns only the newest 100 matches, and there is no pagination (`searches_controller.rb:23`). Keep?
- **T-14 F-06/F-07 (preserve)** Room deletion permanently destroys all messages; any DM participant can delete a DM for everyone. Keep?
- **T-15 F-20 (preserve)** Deactivated users keep their messages and DM memberships, and their cards stay viewable at `/users/:id`. Keep?
- **T-16 F-27 (preserve?)** `/qr_code/:id` is an unauthenticated QR generator for arbitrary URLs. Keep, or require sign-in? The login-page join flow may rely on it being public; UNKNOWN.
- **T-17 F-25 (preserve, contract)** The invalid-signature SGID fallback for User mentions (incl. Rails-7 Marshal format) must survive, as a permanent adapter: stored message HTML depends on it.
- **T-18 F-17 (preserve?)** Tweet unfurling depends on third-party fxtwitter.com. Keep?
- **T-19 F-02 (preserve)** Login rate limit (10 per 3 min) lives in the Redis cache. Redis is slated for removal (charter), so the limiter needs a BEAM-native store with the same per-IP window.
- **T-20 F-23 (preserve?)** The bot key travels in the URL path, and the token is compared via DB lookup (not constant-time). Keep the URL shape (wire contract with existing bots); log scrubbing must be carried over.

## Coverage

| Surface | Mapped | Not mapped (why) |
|---------|--------|------------------|
| `config/routes.rb` (all 104 lines) | All app routes → F-01…F-27 | — |
| Framework-generated routes: Action Cable `/cable`, Active Storage `/rails/active_storage/*` (blobs, representations, direct uploads, disk) | F-08/F-12/F-13 (cable), F-26 (storage) | Exact Active Storage URL formats are framework-defined; the archaeologist must list the signed blob URL shapes that are embedded in stored rich text (data contract) |
| Controllers (34) and concerns (13) | All | — |
| Channels (8 + connection + Turbo prepend) | F-05, F-08, F-12, F-13 | — |
| Jobs (3) | F-08 (push), F-21, F-24 | Retry semantics UNKNOWN (ApplicationJob retries commented out) |
| Models (40) | All, except `Purchaser` | `app/models/purchaser.rb` reads `config/purchased_by.yml`, but nothing in `app`/`lib` references `Purchaser`. Likely dead or used by views/licensing; UNKNOWN |
| `lib/rails_ext/*`, `lib/restricted_http`, `lib/web_push` | F-15, F-17, F-23, F-25 | — |
| `has_json` (account settings) | F-20 | Definition not found in SOURCE `lib/`; the inventory hotspot `lib/rails_ext/active_record_has_json.rb` no longer exists at HEAD. UNKNOWN origin (gem/framework) |
| Stimulus controllers / JS models (70 files) | Timers and behaviors cited in F-08, F-09, F-12, F-13, F-15 | Remaining UI interactions (drag/drop, clipboard, lightbox, sorted lists, maintain-scroll, sounds playback, composer toolbar) are UI contract; defer to ui-strategy and the system tests in `test/system/*` |
| Views (89) and helpers (27) | Behavior-bearing parts cited | CSS (3378 LOC) and layout markup not mapped; `translations_helper.rb` only noted (F-27) |
| `script/admin/*`, `hooks/*`, `bin/boot`, `bin/start-app`, Dockerfile, Procfile | F-28 | `bin/ci`, `bin/release`, `bin/setup`, `bin/dev`, `bin/brakeman`, `bin/rubocop` are dev/CI tooling, not product |
| `script/dev/*`, `lib/tasks/generate.rake`, `lib/tasks/resque.rake` | — | Dev data generation and Resque platform glue; no user or operator capability (`generate.rake` even references a "Lobby" room and a non-existent `user:` attribute, so it's likely stale) |
| `test/performance/*` (chatter.js, cookies) | — | Load-test harness; relevant to performance-gates, not features |
| `config/environments/performance.rb` | — | Perf environment only |
| Migrations (15) | via `db/schema.rb` | Migration history is for the data-compat analysis |
| Email / mailers | — | No mailers in the app (Action Mailer only transitive); no email capability exists. Password reset is operator-only (F-28) |

## Triage Decisions

Recorded by `/rewrite:analyze --auto` on 2026-10-09. Every answer is the default and **none is approved**.

| Question | Decision | Status | Analyst suggestion to weigh at approval |
|----------|----------|--------|------------------------------------------|
| T-01 | preserve | ASSUMED | consider an audit trail |
| T-02 | preserve | ASSUMED | — |
| T-03 | preserve | ASSUMED | redesign: escape `</style>` (security) |
| T-04 | preserve | ASSUMED | private-IP session aborts the ban (bug?) |
| T-05 | preserve | ASSUMED | — |
| T-06 | preserve | ASSUMED | looks accidental |
| T-07 | preserve | ASSUMED | consider a loop guard |
| T-08 | preserve | ASSUMED | redesign: `(created_at, id)` keyset |
| T-09 | preserve | ASSUMED | enforce 16 server-side |
| T-10 | preserve | ASSUMED | redesign: canonical member-set key + unique index |
| T-11 | preserve | ASSUMED | — |
| T-12 | preserve | ASSUMED | strengthen: durable push job |
| T-13 | preserve | ASSUMED | — |
| T-14 | preserve | ASSUMED | — |
| T-15 | preserve | ASSUMED | — |
| T-16 | preserve | ASSUMED | — |
| T-17 | preserve | ASSUMED | — |
| T-18 | preserve | ASSUMED | — |
| T-19 | preserve | ASSUMED | needs a BEAM-native store (Redis removed) |
| T-20 | preserve | ASSUMED | — |
