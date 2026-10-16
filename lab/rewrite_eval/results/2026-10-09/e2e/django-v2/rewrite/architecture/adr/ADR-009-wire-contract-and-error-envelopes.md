# ADR-009: Wire contract — explicit JSON modules, legacy error envelopes, relaxed incidentals

**Status**: proposed (kept parts) / ASSUMED (relaxations inherited from ADR-000) · **Date**: 2026-10-09

## Context
ADR-000 keeps C-17..C-30 and freezes C-26 by golden files; relaxes C-45..C-51, C-54, C-56; changes C-34. The legacy shapes come from DRF renderers and
a custom exception handler (M-08, M-09) and are partly inferred from library reading (contracts "(lib)"; VO-10).

## Decision
- Explicit JSON modules per resource; Jason encoding; no `@derive Jason.Encoder` on schemas.
- `ConduitWeb.LegacyErrors` is the single place that knows the envelope rules: 400 field map with `error` for non-field; bare list for self-follow;
  per-route NotFound key (model-keyed vs `detail`); label-wrapped `detail` for every other error, bare where legacy used DRF's default renderer
  (architecture.md section 4 table). Each controller declares its label. Validation stays 400, not 422.
- Router: explicit slashless routes; trailing slash accepted (widening ADR-000 relaxed, DV-19). One slug matcher for all article routes (DV-18).
- Relaxed (no SHIM, each with a pending divergence): no API root or format suffixes (DV-07), no browsable API (DV-08), OPTIONS only as CORS preflight
  (DV-09), JSON 404 for unknown routes (DV-10), timestamps always `.ffffff+00:00` (DV-11), Jason bytes (DV-12), Phoenix secure headers (DV-13),
  PUT only on `/api/user` (DV-16).
- C-34: no debug pages outside dev; 500 → JSON with no stack, headers or route list (DV-05).
- UNDECIDED rows stay open and block their slices: C-16, C-35, C-36, C-39, C-40, C-41.

## Guarantees
- Kept: C-17 (slashless forms), C-18, C-19, C-20, C-21, C-22, C-23, C-24, C-25, C-26, C-27, C-28, C-29, C-30.
- Changed: C-34 (DV-05) and the incidental relaxations listed above. Consumers: none identified for the incidentals (contracts "Incidental Behaviour").

## Alternatives
- Spec-conformant errors (422, 401, uniform `errors`): changes a kept contract (C-26); needs a new ADR and user approval.
- Byte-identical Python JSON and timestamps: incidental per ADR-000; not built.

## Consequences
Golden files recorded from an isolated legacy run are the acceptance oracle (needs permission, contracts Q7). Until then the per-route table is a
code-reading inference and is marked "verify".

## Validation
VO-08, VO-10, VO-11; one golden file per endpoint and per error class (duplicate username, bad login, unknown article retrieve vs favorite, unknown
profile retrieve vs follow, self-follow, malformed JSON).

## Ledger IDs
M-08, C-19, M-09, C-26, M-13, C-30, M-23, C-21, M-28, C-17, M-29, C-24, M-38, C-20, C-18, C-22, C-23, C-25, C-34, M-34, C-46, C-45, C-47, C-48, C-49, C-50, C-51, C-54, C-56, M-32, R-31
