# ADR-012: Operator surface — release tasks replace manage.py; Django admin retired; backups are a new duty

**Status**: ASSUMED (admin retirement inherited from ADR-000's C-52 relaxation; operator use unknown) · **Date**: 2026-10-09

## Context
Operators bootstrap with `manage.py migrate`, `runserver`, `createsuperuser` (C-43). `/admin/` exists but no app model is registered; only
`auth.Group` is manageable; nobody is known to use it (M-33 purpose `unknown`, C-52, R-41, R-11). Legacy has no backup duty; the DB is one file.

## Decision
- `bin/conduit eval "Conduit.Release.migrate()"` (with the ADR-004 preflight), `bin/conduit start`, and
  `bin/conduit eval 'Conduit.Release.create_operator_user("email", "username", "password")'` (creates user + profile atomically; sets
  `is_staff`/`is_superuser` true to mirror `create_superuser`, though no Phoenix behaviour reads them — C-55).
- Django admin, sessions, messages and static assets are retired (DV-14). **The retirement rests on an unknown purpose**: OD-5 asks whether any
  operator uses `/admin/`; if yes, a back office (backpex 0.22.0, KB) is scoped as a new slice. Until answered, this ADR stays ASSUMED.
- `is_staff`, `is_superuser`, `last_login` columns are kept and written with legacy defaults; no behaviour (DV-17).
- New duty: online backup with `VACUUM INTO` (or the SQLite backup API), never `cp` of a live WAL database (ADR-003).
- Dev shell: `iex -S mix`, `bin/conduit remote`, `mix phx.routes` replace django_extensions (M-35).

## Guarantees
- Kept: C-43 as equivalents.
- Changed: C-52 (admin retired, DV-14), C-55 (DV-17). Consumers: unknown operators (OD-5).

## Alternatives
Keep the Django admin running read-only beside Phoenix: a second runtime on the file with the leaked `SECRET_KEY` signing its sessions; rejected.

## Consequences
The runbook documents each command once and tests it once.

## Validation
Empty DB → migrate → create operator user → API registration and login work.

## Ledger IDs
M-41, R-03, C-43, M-33, C-52, R-11, R-41, C-55, M-14, M-35
