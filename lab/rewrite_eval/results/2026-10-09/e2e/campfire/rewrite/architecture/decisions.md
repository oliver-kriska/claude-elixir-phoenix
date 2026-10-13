# Decision Index — ONCE Campfire → Elixir/Phoenix

All decisions were made in `--auto` mode on 2026-10-09. **None is accepted.** `ASSUMED` means a default the bar or a consult forced, which still needs approval. `proposed` means an architect choice awaiting review.

| ADR | Title | Status | Kind | Divergences | Ledger IDs (main) |
|-----|-------|--------|------|-------------|-------------------|
| ADR-000 | Compatibility bar | ASSUMED | bar | C-59, C-60 retired/changed | all |
| ADR-001 | App shape and framework defaults | proposed | framework defaults (UI constraint) | — | M-26, M-31, M-61, C-40, C-41, C-48, C-49 |
| ADR-002 | Context map drawn from invariants | proposed | structure | DV-01, DV-18, DV-19 | M-05, M-06, M-48, C-13 |
| ADR-003 | SQLite topology and legacy column types | proposed | data layer (corrects KB `:text_datetime`) | — | M-15, M-54, R-26, C-01..C-06, C-12, C-14, C-16 |
| ADR-004 | DDL authority: Rails-ledger migrator plus Ecto for port-only DDL | ASSUMED | data authority | — | M-57, R-03, C-01, C-55 |
| ADR-005 | One transaction per message write; broadcasts after commit | proposed | changed guarantee (strengthened) | DV-01, DV-12 | M-01..M-04, R-27, C-09, C-13 |
| ADR-006 | Oban Lite jobs; delivery semantics; 10-minute stale cancel | ASSUMED | changed guarantee | DV-02, DV-03, DV-13 | M-17, M-20..M-22, M-25, R-08, R-24, R-30..R-33, C-59, C-60 |
| ADR-007 | In-memory room presence (Registry) | ASSUMED | changed guarantee | DV-05 | M-27, M-28, R-05 |
| ADR-008 | Action Cable protocol SHIM at `/cable` | proposed | SHIM (owner + deletion trigger) | DV-16 | M-26, M-27, M-29..M-31, M-33, R-20, C-41 |
| ADR-009 | Forced socket disconnect after commit | ASSUMED | changed guarantee (strengthened) | DV-04 | M-07, M-16, R-21, C-28, C-43 |
| ADR-010 | Identity: Rails-format `session_token`; Plug CSRF; `_campfire_session` not read | ASSUMED | kept contract with cost + changed contract C-21 | DV-06, DV-08, DV-09 | M-09, M-18, M-36, R-29, C-07, C-08, C-20..C-22, C-26 |
| ADR-011 | Rails-format signed capability codecs | ASSUMED | SHIM / permanent adapter | — | M-29, M-37, M-38, C-10, C-23, C-24, C-27 |
| ADR-012 | Rich text stays Action Text HTML; pure `Content` pipeline | proposed | kept contract | — | M-39..M-41, M-62, M-67, M-68 |
| ADR-013 | Files: Active Storage tables and layout kept | proposed | kept contract with cost | DV-11 | M-44..M-46, R-28, R-33, R-34, C-11, C-27 |
| ADR-014 | Web Push continuity | proposed | kept contract | — | M-21..M-24, M-64, M-65, C-15, C-37..C-39 |
| ADR-015 | Outbound HTTP via Req/Finch; `Net.Guard` | proposed | framework default + port of shared policy | — | M-20, M-23, M-42, M-43 |
| ADR-016 | Abuse controls without Redis | ASSUMED | changed guarantee | DV-10 | M-17, M-47, R-23, C-42 |
| ADR-017 | No fragment or response cache | proposed | DELETE with consumers checked | DV-15 | M-34, M-35, R-22, C-46 |
| ADR-018 | Release, container and operator surface | ASSUMED | kept contracts + operational change | DV-07 | M-53, M-55, M-57..M-59, R-01, R-03, R-04, R-06, R-07, R-10, C-47, C-50..C-54, C-57, C-58, C-60 |
| ADR-019 | TLS edge: keep pinned Thruster | ASSUMED | KEEP (non-BEAM component) | — | M-56, R-02, C-56 |
| ADR-020 | Bot API and webhooks byte-compatible | proposed | kept contract with cost | — | M-18..M-20, M-60, C-30..C-36 |
| ADR-021 | DM identity in one IMMEDIATE txn; `(created_at, id)` keyset | proposed | changed behavior | DV-14, DV-17 | M-12, M-13, M-60, C-05 |

## Three decisions most needing review

1. **ADR-000 + ADR-008: keep the Hotwire UI behind an Action Cable shim.** The project would own another framework's wire protocol indefinitely. The alternative is a LiveView or `<turbo-stream-source>` UI that retires C-41, C-48 and C-49 (only open tabs are affected) and deletes the shim.
2. **ADR-010 + ADR-011: Rails-format crypto for sessions and every durable capability.** This means no forced logout, working rollback, and links that stay valid. The cost is permanent compat codecs gated on test vectors from the pinned image, plus documented weak capabilities: blob and avatar URLs never expire, and transfer links can be reused.
3. **ADR-006: delivery semantics under Oban.** It keeps at-most-once webhooks and push, adds a durable enqueue, and adds a new 10-minute stale cancel (DV-03). Webhook retries and per-device durable push (T-12 "strengthen") are rejected.
