# Mechanisms — onboarding (accounts)

Source: source/ @ 3333333333333333333333333333333333333333 (from current-state.json; git not run, no history read) · Scope: whole source (4 py files + README, listed from source/) · Mechanisms: 5 · Evidence: documented 2 / observed 0 / inferred 3 / unknown 0

Existing analysis (target/.claude/rewrite/analysis/) complete? **NO.** It claims "No callbacks or implicit record creation were found" and "Coverage: complete onboarding application". source/accounts/signals.py:6-9 is a `post_save` receiver on Account that does `Profile.objects.create(account=instance)` when `created`, wired by `AccountsConfig.ready()` (apps.py:7-8) and described in source/README.md:3-4. The analysis covers only models.py:4-5 (Account) and never mentions Profile, signals.py or apps.py. Its `contracts.md` ("No other construction or lifecycle obligations exist") and `features.md` ("no secondary effects exist") are therefore contradicted by source.

## Draft Ledger
| ID | Mechanism (anchor) | Purpose | Evidence | Tags | Guarantees | Consumers now | Candidate verdict → target | Conf |
|----|--------------------|---------|----------|------|------------|---------------|----------------------------|------|
| M-01 | Account model, models.py:4-5 | Hold identity and unique email | inferred | business | uniqueness of email (DB unique index) | registration | MAP → schema + `unique_constraint/3` (in existing analysis, but uniqueness is not stated there) | high |
| M-02 | `create_profile` post_save receiver, signals.py:6-9 | Every newly created Account gets an editable Profile before registration returns | documented (README.md:3-4) | business | atomicity: not guaranteed by the signal itself (same transaction only if caller/ATOMIC_REQUESTS wraps `save()`; not verified); ordering: after Account row insert; visibility: Profile exists when `save()` returns; idempotence: `created` flag only, so re-save creates nothing | profile editing (bio) | MAP → one `Ecto.Multi`/`Repo.transact` in the registration context inserting Account then Profile; no signal bus | med |
| M-03 | `if created:` guard, signals.py:8 | Ordinary later saves must not create a second Profile or overwrite bio | documented (README.md:4) | business | negative guarantee: re-save is a no-op for Profile | any account update path | MAP → Profile insert only in the registration function; update changesets never touch Profile; test it | high |
| M-04 | `AccountsConfig.ready()` imports signals, apps.py:7-8 | Registers the receiver at startup; without it M-02 silently never fires | inferred | platform | none beyond wiring | none (implicit) | DELETE the wiring (replaced by explicit call in M-02); consumer check: only M-02 depends on it | med |
| M-05 | `Profile.account` OneToOneField CASCADE + `bio` default "", models.py:8-10 | At most one Profile per Account; deleting an Account removes its Profile; new Profile has empty bio | inferred | business | uniqueness (unique index on account_id); cascade delete; default "" | profile editing, account deletion | MAP → `unique_constraint/3`, FK `on_delete: :delete_all`, schema default "" | med |

## High-Risk Mechanisms
### M-02 / M-03 Profile auto-creation
**Anchor**: source/accounts/signals.py:6-9, source/accounts/apps.py:7-8. **Purpose**: registration returns with an editable Profile in place; ordinary saves leave Profile alone (evidence: README.md:3-4, documented).
**Guarantees**: Profile exists after Account creation; no duplicate and no bio overwrite on re-save. **Failure history**: not investigated, no git history read (git not run in this replay). **Candidate**: MAP → explicit, transactional pipeline. **Why not REPLACE/DELETE**: a current product rule (the README states it), and the existing ledger would drop it silently.
**Implicit-path note**: Django `bulk_create`/`QuerySet.update`/raw SQL skip `post_save`; I found none in source (4 files), but only these files exist in the scope.

## Implicit Framework Behavior
- Signal registration depends on `ready()` running at app load (M-04).
- Receiver runs synchronously inside `save()`; atomicity relative to the Account insert depends on the enclosing transaction (unverified; no settings file in source, so `ATOMIC_REQUESTS` unknown).
- `OneToOneField` implies a unique index; `on_delete=CASCADE` is explicit; `email` unique creates an index (M-01).

## Questions
- Q1 (M-02 atomicity): Is Account+Profile creation wrapped in one transaction (ATOMIC_REQUESTS or atomic block)? Needs settings/views, absent from source/. If not, partial states (Account without Profile) are possible today; decide whether the port keeps that or tightens it. Confidence on M-02 is med until settled.
- Q2: Are there other writers of Account (admin, import, bulk paths) that bypass the signal? Needs the rest of the app, absent from source/.

## Coverage
| Area | Investigated | Not investigated (why) |
|------|--------------|------------------------|
| Django probes (signals, ready, receivers, constraints) | all 4 py files + README read in full | settings, views, urls, admin, tests, migrations: not present in source/ |
| Caches, locks, jobs, raw SQL, middleware | grep-level: none present in the 4 files | nothing else exists to search |
| Git history | not investigated | git not run per replay rules; no fix commits or purpose history |
