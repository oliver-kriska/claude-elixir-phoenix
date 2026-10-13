# ADR-013: Cutover runbook, pre-cutover scans and rollback

**Status**: proposed (rollback method and window are OD-6) · **Date**: 2026-10-09

## Context
ADR-000: Replacement in one window; the pre-cutover `db.sqlite3` copy is the rollback point; valid until the first approved destructive DDL and at
most one release cycle; production data is assumed to exist (Q2 unanswered). Consult ecto-schema-designer Q5 lists the scans.

## Decision
Runbook (rehearsed in S8 on a copy):
1. Stop Django and disable its start. 2. `VACUUM INTO` a rollback copy; checksum it. 3. Run the read-only scans on the copy:
   orphans (`PRAGMA foreign_key_check` + explicit joins), users without a profile (C-05), self-follows (C-38), case-variant emails/usernames (C-04,
   informational), oversize values (C-07), `slug <> lower(tag)` drift, datetime format (C-03), non-`pbkdf2_sha256$` hashes (C-02), empty slugs (C-06).
   Each must be 0 or have a recorded decision; additive backfill of missing profiles only (`bio=''`, `image=''`).
4. `Conduit.Release.migrate()` (preflight; records the baseline, no DDL on legacy tables). 5. Start Phoenix (WAL set at first writer connection).
6. Smoke tests: login with a known legacy account, list, feed, create and delete a comment. 7. Announce the one-time re-login.
- **Fencing:** Django is stopped before Phoenix starts; Phoenix boot attempts `BEGIN IMMEDIATE` and refuses to continue on `SQLITE_BUSY` from a foreign holder.
- **Rollback (OD-6):** preferred = hand the live file back (stop Phoenix, `PRAGMA wal_checkpoint(TRUNCATE)`, `PRAGMA journal_mode=DELETE`, start
  Django). This keeps post-cutover writes, because the port writes only Django-readable values (ADR-005, ADR-007) and no DDL on legacy tables;
  clients log in again (different key). Fallback = restore the step-2 copy, which **loses post-cutover writes**; ADR-000 names it, but using it after
  writes have happened needs the user's explicit approval at that time.

## Guarantees
- Kept: no data loss on the forward path; C-01, C-02, C-03, C-42.
- Changed: forced re-login (DV-01).

## Alternatives
Start empty (if Q2 says no production data): skips scans and rollback copy; still runs the baseline migration.

## Consequences
Self-follow purge and orphan deletion are destructive; they need their own ADRs if chosen.

## Validation
Full rehearsal on a production copy with timings; rollback hand-back rehearsed once, verifying Django 1.10 reads port-written rows and hashes.

## Ledger IDs
R-10, C-05, C-38, C-04, C-07, C-03, C-02, C-06, M-26
