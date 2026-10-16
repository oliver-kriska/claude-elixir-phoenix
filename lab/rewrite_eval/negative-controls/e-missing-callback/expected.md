# Evaluator only — callback missing from analysis

- Required review verdict: **incomplete mechanism/contract inventory**, not full parity.
- Recover automatic profile creation from `source/accounts/signals.py:6-9`, its registration through `source/accounts/apps.py:7-8`, and the consumer promise in `source/README.md:3-4`.
- Explain its purpose: immediate editable profile availability, one profile per account, no recreation/overwrite on ordinary updates.
- Cite `source/accounts/models.py:8-10` for the one-to-one relationship. Do not invent after-commit or transaction guarantees from a synchronous post_save receiver.
- The current target record builder returns no profile, and its test checks only account identity. Flag this omission instead of treating the absence of a ledger row as an exclusion.
- Retain C-01's limited replay result, add the omitted creation and update-preservation obligations as **not-run**, and reject the broad completion claim.
- Suggest an explicit target operation/record plan, not a requirement to recreate Django signals. Persistence remains a separate untested boundary.

Contrast: if analysis records the profile mechanism and both lifecycle obligations, and target witnesses cover them with matching fresh evidence,
the omission finding must disappear. Merely adding the word `post_save` to the inventory without its purpose/consumers does not resolve it.
