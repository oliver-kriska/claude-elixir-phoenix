# Inventory: $S/testbeds/django-realworld

- git: `29c9d42831fa` on `master`, 1 commits, 2017-04-27 → 2017-04-27, 1 contributors
- tree fingerprint: `de077c0df95ad117`
- stacks: django (file:manage.py; dep:django)
- stack packs to read: `stacks/django.md`
- shape hints (confirm in code): http-api
- size: 48 files; LOC python 1778

## Infrastructure signals

- **api-serialization** (api): djangorestframework

## Entry points

- callbacks: 2 — conduit/apps/articles/signals.py, conduit/apps/authentication/signals.py
- config: 1 — conduit/settings.py
- controllers: 3 — conduit/apps/articles/views.py, conduit/apps/authentication/views.py, conduit/apps/profiles/views.py
- migrations: 10 — conduit/apps/articles/migrations/0001_initial.py, conduit/apps/articles/migrations/0002_comment.py, conduit/apps/articles/migrations/0003_auto_20160828_1656.py, conduit/apps/articles/migrations/__init__.py, conduit/apps/authentication/migrations/0001_initial.py …
- models: 4 — conduit/apps/articles/models.py, conduit/apps/authentication/models.py, conduit/apps/core/models.py, conduit/apps/profiles/models.py
- routes: 4 — conduit/urls.py, conduit/apps/articles/urls.py, conduit/apps/authentication/urls.py, conduit/apps/profiles/urls.py

## Mechanism hints (pattern counts — leads, not conclusions)

- events-and-observers: 6 in 2 files — conduit/apps/articles/signals.py, conduit/apps/authentication/signals.py
- metaprogramming: 2 in 1 files — conduit/apps/authentication/serializers.py

## Agent-steering files

- none found in SOURCE, TARGET or `--steering` roots; files elsewhere (e.g. above a `reference/` checkout) need `--steering DIR`

## Git hotspots (top 10)

- history too shallow (1 commits); hotspots suppressed (shallow repository)

## Coverage and limits

- files walked: 48; skipped oversized/binary source files: 0
- why-comments: returned 13 of 13 (round-robin by file); TODO/FIXME/HACK: 0
- git commits scanned: 1
- regex hints are leads; absence of a hint is not absence of the mechanism
- tests, SQL, triggers and stored procedures are not scanned for mechanism hints
- dynamic dispatch, metaprogramming and generated routes need manual tracing
- history too shallow (1 commits); hotspots suppressed (shallow repository)
