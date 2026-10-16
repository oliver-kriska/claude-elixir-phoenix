# Inventory: ~/Projects/campfire-bench/once-campfire-elixir/reference

- git: `90b330024dec` on `HEAD`, 259 commits, 2025-08-15 → 2026-09-26, 33 contributors
- tree fingerprint: `455ff1ef81a4f46d`
- stacks: rails (file:config/routes.rb; dep:rails)
- shape hints (confirm in code): web-ui, web-app, realtime, worker/consumer, cli
- size: 694 files; LOC ruby 10159, javascript 3886, css 3378, erb 2247, html 579

## Infrastructure signals

- **redis** (datastore): kredis, redis, redis-client, redis-namespace
- **resque** (jobs): resque, resque-pool
- **actioncable/anycable** (realtime) _(transitive only)_: actioncable
- **turbo/hotwire** (ui): stimulus-rails, turbo-rails
- **file-storage** (storage) _(transitive only)_: activestorage
- **image-processing** (media): image_processing, mini_magick, ruby-vips
- **mail** (mail) _(transitive only)_: actionmailer, mail
- **inbound-mail** (mail) _(transitive only)_: actionmailbox
- **auth** (auth): bcrypt
- **api-serialization** (api): jbuilder
- **web-push** (integration): web-push
- **observability** (ops): sentry-rails, sentry-ruby
- **orm** (data) _(transitive only)_: activerecord
- **sqlite** (datastore): sqlite3
- **rich-text** (ui) _(transitive only)_: actiontext
- **proxy/server** (ops): puma, thruster
- **cli** (shape) _(transitive only)_: thor

## Entry points

- concerns: 13 — app/controllers/concerns/active_storage_authentication.rb, app/controllers/concerns/allow_browser.rb, app/controllers/concerns/authentication.rb, app/controllers/concerns/authorization.rb, app/controllers/concerns/block_banned_requests.rb …
- config: 35 — config/application.rb, config/boot.rb, config/bundler-audit.yml, config/cable.yml, config/ci.rb …
- controllers: 34 — app/controllers/accounts_controller.rb, app/controllers/application_controller.rb, app/controllers/first_runs_controller.rb, app/controllers/messages_controller.rb, app/controllers/pwa_controller.rb …
- deployment: 3 — Dockerfile, Dockerfile-export, Procfile
- frontend: 70 — app/javascript/application.js, app/javascript/controllers/application.js, app/javascript/controllers/auto_submit_controller.js, app/javascript/controllers/autocomplete_controller.js, app/javascript/controllers/badge_dot_controller.js …
- helpers: 27 — app/helpers/accounts_helper.rb, app/helpers/application_helper.rb, app/helpers/broadcasts_helper.rb, app/helpers/cable_helper.rb, app/helpers/clipboard_helper.rb …
- jobs: 4 — app/jobs/application_job.rb, app/jobs/remove_banned_content_job.rb, app/jobs/bot/webhook_job.rb, app/jobs/room/push_message_job.rb
- lib: 11 — lib/assets/.keep, lib/rails_ext/action_text_allowed_tags.rb, lib/rails_ext/action_text_attachables.rb, lib/rails_ext/actiontext_opengraph_embeds.rb, lib/rails_ext/filter.rb …
- migrations: 15 — db/migrate/20231215043540_create_initial_schema.rb, db/migrate/20231220143106_add_bio_to_users.rb, db/migrate/20240110071740_create_sessions.rb, db/migrate/20240115124901_remove_owner_role.rb, db/migrate/20240130003150_create_webhooks.rb …
- models: 40 — app/models/account.rb, app/models/application_platform.rb, app/models/application_record.rb, app/models/ban.rb, app/models/boost.rb …
- realtime: 10 — app/channels/heartbeat_channel.rb, app/channels/presence_channel.rb, app/channels/read_rooms_channel.rb, app/channels/room_channel.rb, app/channels/room_messages_channel.rb …
- routes: 1 — config/routes.rb
- schema: 1 — db/schema.rb
- tasks: 3 — lib/tasks/.keep, lib/tasks/generate.rake, lib/tasks/resque.rake
- tests: 105 — test/application_system_test_case.rb, test/test_helper.rb, test/channels/presence_channel_test.rb, test/channels/room_messages_channel_test.rb, test/channels/unread_rooms_channel_test.rb …
- views: 89 — app/views/accounts/_help_contact.html.erb, app/views/accounts/_invite.html.erb, app/views/accounts/edit.html.erb, app/views/accounts/bots/_bot.html.erb, app/views/accounts/bots/_form.html.erb …

## Mechanism hints (pattern counts — leads, not conclusions)

- request-globals: 74 in 43 files — app/helpers/application_helper.rb, app/controllers/rooms_controller.rb, app/controllers/concerns/authentication.rb, app/controllers/searches_controller.rb
- controller-filters: 59 in 33 files — app/controllers/concerns/authentication.rb, app/controllers/rooms/closeds_controller.rb, app/controllers/rooms/opens_controller.rb, app/controllers/messages/by_bots_controller.rb
- realtime-broadcast: 56 in 16 files — app/models/message/broadcasts.rb, app/controllers/messages/boosts_controller.rb, app/controllers/rooms/closeds_controller.rb, app/controllers/rooms/opens_controller.rb
- external-http: 27 in 12 files — config/puma.rb, app/models/opengraph/fetch.rb, config/initializers/web_push.rb, app/models/webhook.rb
- derived-data: 7 in 6 files — app/models/membership/connectable.rb, app/models/boost.rb, app/models/membership.rb, app/models/message.rb
- caching: 6 in 5 files — config/environments/production.rb, app/controllers/messages_controller.rb, app/controllers/accounts/logos_controller.rb, app/controllers/users/avatars_controller.rb
- crypto-contracts: 6 in 6 files — app/controllers/concerns/authentication.rb, app/controllers/concerns/authentication/session_lookup.rb, app/controllers/users/avatars_controller.rb, app/models/user.rb
- model-callbacks: 5 in 5 files — app/models/message.rb, app/models/search.rb, app/models/session.rb, app/models/account/joinable.rb
- async-jobs: 5 in 4 files — lib/web_push/pool.rb, app/models/room.rb, app/models/user/bannable.rb, app/models/user/bot.rb
- concurrency: 4 in 1 files — lib/web_push/pool.rb
- timers-and-polling: 2 in 2 files — app/javascript/controllers/presence_controller.js, app/javascript/models/typing_tracker.js

## Agent-steering files

- none found

## Git hotspots (top 10)

- lib/rails_ext/actiontext_opengraph_embeds.rb: 11 changes, 1 fix commits
- lib/restricted_http/private_network_guard.rb: 10 changes, 0 fix commits
- test/controllers/messages/by_bots_controller_test.rb: 10 changes, 4 fix commits
- app/controllers/messages/by_bots_controller.rb: 8 changes, 2 fix commits
- app/controllers/rooms_controller.rb: 8 changes, 0 fix commits
- app/views/accounts/edit.html.erb: 8 changes, 2 fix commits
- test/lib/rails_ext/actiontext_opengraph_embeds_test.rb: 7 changes, 0 fix commits
- config/routes.rb: 7 changes, 0 fix commits
- app/models/account.rb: 7 changes, 0 fix commits
- lib/rails_ext/active_record_has_json.rb: 7 changes, 1 fix commits

## Co-change pairs (candidate shared boundaries)

- app/controllers/messages/by_bots_controller.rb ↔ test/controllers/messages/by_bots_controller_test.rb: 6× (J=0.5)
- lib/rails_ext/actiontext_opengraph_embeds.rb ↔ test/lib/rails_ext/actiontext_opengraph_embeds_test.rb: 6× (J=0.5)
- lib/restricted_http/private_network_guard.rb ↔ test/lib/restricted_http/private_network_guard_test.rb: 5× (J=0.5)
- app/controllers/rooms/closeds_controller.rb ↔ app/controllers/rooms/opens_controller.rb: 4× (J=0.67)
- app/controllers/rooms/closeds_controller.rb ↔ app/controllers/rooms_controller.rb: 4× (J=0.44)
- app/controllers/rooms/opens_controller.rb ↔ app/controllers/rooms_controller.rb: 4× (J=0.44)
- app/models/account.rb ↔ test/models/account_test.rb: 4× (J=0.44)
- app/controllers/messages/boosts/by_bots_controller.rb ↔ test/controllers/messages/boosts/by_bots_controller_test.rb: 3× (J=1.0)
- test/controllers/rooms/closeds_controller_test.rb ↔ test/controllers/rooms/opens_controller_test.rb: 3× (J=0.6)
- app/controllers/messages/boosts/by_bots_controller.rb ↔ config/routes.rb: 3× (J=0.43)

## Coverage and limits

- files walked: 694; skipped oversized/binary source files: 0
- why-comments: returned 21 of 21 (round-robin by file); TODO/FIXME/HACK: 1
- git commits scanned: 259
- regex hints are leads; absence of a hint is not absence of the mechanism
- tests, SQL, triggers and stored procedures are not scanned for mechanism hints
- dynamic dispatch, metaprogramming and generated routes need manual tracing
