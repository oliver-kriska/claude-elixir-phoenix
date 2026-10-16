# ADR-005: `Conduit.Ecto.LegacyDateTime` for legacy SQLite datetime text

**Status**: proposed · **Date**: 2026-10-09

## Context
C-03: Django 1.10 with `USE_TZ=True` stores naive UTC text `YYYY-MM-DD HH:MM:SS[.ffffff]`, omitting the fraction when microseconds are 0 (inferred; scan in ADR-013).
Lists sort by `created_at` text (M-12). ecto_sqlite3 `datetime_type` options: `:iso8601` writes `T…Z` (sorts after every legacy row of the same day),
`:text_datetime` drops microseconds; both are global app env (kb/data-compat.md; consult Q2 read 0.22.0, KB cites 0.25.0).

## Decision
A project-owned Ecto type (`type: :string`) on every legacy datetime column (timestamps on User, Profile, Article, Comment, Tag; `last_login`):
- `load/1`: `NaiveDateTime.from_iso8601/1` → `DateTime.from_naive!(…, "Etc/UTC")` → normalised to microsecond precision 6.
- `dump/1`: `Calendar.strftime(dt, "%Y-%m-%d %H:%M:%S.%f")` (space, 6 digits, no zone).
- `cast/1` delegates to `:utc_datetime_usec`; `utc_now/0` for autogenerate. Global `datetime_type` untouched.
- Query parameters on these columns go through the field type; never compare against an untyped `fragment`.

## Guarantees
- Kept: C-03 (legacy text round-trips unless the column is written; port rows sort correctly against legacy rows; Django can read the 6-digit form).
- Changed: newly written rows always carry 6 fraction digits where Django would omit `.000000` (DV-24; no reader depends on the width).

## Alternatives
`:text_datetime` (loses ordering within a second), `:iso8601` (breaks ordering against legacy rows): rejected.

## Consequences
`insert_all`/`update_all` must set timestamps explicitly with `LegacyDateTime.utc_now/0`.

## Validation
VO-04, VO-05: decode both widths; legacy row at `…:40.500000` vs port row 1 s later; ordering test in `GET /api/articles`.

## Ledger IDs
M-11, C-03
