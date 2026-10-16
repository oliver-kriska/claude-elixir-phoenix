# Mechanisms — Onboarding (accounts app)

Source: source/ @ 3333333333333333333333333333333333333333 (from current-state.json; no .git in source/, so no history was readable) · Scope: whole source (4 files: README.md, accounts/{apps,models,signals}.py), inventory derived by listing source/ · Mechanisms: 6 · Evidence: documented 2 / observed 3 / inferred 0 / unknown 1

Existing analysis (target/.claude/rewrite/analysis/) is NOT complete. mechanisms.md states "No callbacks or implicit record creation were found" and features.md/contracts.md state "no secondary effects exist" / "No other construction or lifecycle obligations exist". signals.py:6-9 contradicts this: a `post_save` receiver creates a Profile. The analysis covers only `accounts/models.py:4-5` (Account) and never mentions signals.py, apps.py, or Profile (models.py:8-10).

## Draft Ledger
| ID | Mechanism (anchor) | Purpose | Evidence | Tags | Guarantees | Consumers now | Candidate verdict → target | Conf |
|----|--------------------|---------|----------|------|------------|---------------|----------------------------|------|
| M-01 | Account model, `models.py:4-5` (unique email) | Hold identity and email; unique email is an identity rule | observed (code) | business, contract | uniqueness: unknown scope (DB constraint) | registration, Profile FK | MAP → Ecto schema + `unique_constraint(:email)` | high |
| M-02 | `post_save` receiver `create_profile`, `signals.py:6-9` | Create the editable Profile when an Account is first saved, before registration returns | documented (README:3) + observed (signals.py) | business | created exactly once per new Account; atomicity with the Account insert: unknown (depends on ATOMIC_REQUESTS/transaction settings, not in source); visibility: Profile present when registration returns (README) | registration flow, anything reading Profile | REPLACE → `Ecto.Multi` inserting Account then Profile in one `Repo.transact/2` | med |
| M-03 | `if created` guard, `signals.py:8` | A later ordinary Account save must not create a second Profile nor overwrite bio | documented (README:4) | business | idempotent on update; bio preserved | any code that re-saves Account | REPLACE → Profile insert only in the registration Multi; account updates never touch Profile | high |
| M-04 | `AccountsConfig.ready()` import of signals, `apps.py:7-8` | Registers the receiver at startup; without it M-02 never fires | observed (code); README:5 names the config as installed | platform | wiring only; INSTALLED_APPS/settings not in source, so activation is unconfirmed | M-02 | DELETE as wiring (explicit Multi step replaces it) after M-02 is covered | med |
| M-05 | `Profile.account` OneToOneField CASCADE, `models.py:9` | One Profile per Account; deleting an Account deletes its Profile (in Python) | observed (code) | business | uniqueness of Profile per Account; cascade delete | Account deletion paths | MAP → unique index on `account_id` + `on_delete: :delete_all` | med |
| M-06 | `Profile.bio` default `""`, `models.py:10` | Empty-string convention for bio | observed (code) | contract (data) | no NULL; Ecto `cast` turns "" into nil | Profile editing | MAP with explicit default `""` / `empty_values` handling | med |

## High-Risk Mechanisms
### M-02 post_save Profile creation
**Anchor**: source/accounts/signals.py:6-9. **Purpose**: README:3 "Saving a new account creates its editable profile before registration returns" (documented).
**Guarantees**: once per creation; atomicity with Account insert unknown; visibility before registration returns.
**Failure history**: none readable (no git history in source/).
**Candidate**: REPLACE → one `Repo.transact/2` with Account and Profile inserts. **Why not MAP**: a signal is implicit side-effect wiring; the effect must become an explicit step.
**Bypass note**: Django signals do not fire for `bulk_create`, `QuerySet.update()` or raw SQL; no such writers are visible in source/, but coverage of writers outside this tree is unknown.

### M-03 created-only guard
**Purpose**: README:4 (documented). Negative obligations: second save creates no second Profile; existing bio is not overwritten.

## Implicit Framework Behavior
- Signal dispatch inside `Model.save()` runs synchronously in the same call and, depending on settings, the same transaction; the port must provide this explicitly.
- Django applies `on_delete=CASCADE` in Python, not the DB.
- `OneToOneField` implies a unique constraint on `account_id`.
- Django stores `""` for text with default `""`; Ecto cast nils empty strings by default.
- Django adds an implicit `id` primary key to both models.

## Questions
- Q1: Is `ATOMIC_REQUESTS` set, and does the Profile insert share the Account's transaction? (settings.py not in source; would settle M-02 atomicity.)
- Q2: Does any writer outside source/ (admin, fixtures, bulk imports) create Accounts without signals, leaving Account rows with no Profile?
- Q3: Is `accounts.apps.AccountsConfig` actually in INSTALLED_APPS, so M-04 wiring is live? (README:5 asserts it.)

## Coverage
| Area | Investigated | Not investigated (why) |
|------|--------------|------------------------|
| Signals/apps.ready probe | signals.py, apps.py read in full | — |
| Models/Meta/on_delete/defaults probe | models.py read in full | — |
| Transactions, settings, middleware, urls, forms, admin, celery, channels | grep-equivalent by listing: no such files exist in source/ | settings.py absent, so global behavior is unknown rather than none |
| Git history | not available (no .git in source/) | purposes rest on README and code only |
| Whole source | 4 of 4 files | none |
