# ADR-012: Rich text stays Action Text HTML; one pure `Campfire.Content` rendering pipeline

**Status**: proposed (auto; needs approval)
**Date**: 2026-10-09 · **Bar**: ADR-000 (ASSUMED) Data and Clients sections

## Context

- Message bodies live in `action_text_rich_texts.body` as HTML with `<action-text-attachment>` mentions (sgid) and opengraph embeds, in Trix and Lexxy forms (C-10, M-39, M-40).
- Rendering is a three-layer XSS defense: remove-solo-unfurled-link, SanitizeTags (remove, not unwrap), SanitizeAttributes with a fresh scrubber per call (thread race in rails-html-sanitizer), an Action Text allowed-tags patch, `auto_link` re-sanitize, and fail-soft "unrenderable" output with a Sentry capture (M-41).
- `to_plain_text` feeds FTS (C-09), the push body (C-37) and the webhook `plain` (C-35), so its output is a cross-contract value.
- Admin custom CSS is injected raw into `<style>` (M-68, T-03 triaged `preserve` ASSUMED).

## Decision

- **Storage format unchanged.** `Campfire.Chat.RichText` maps `action_text_rich_texts` (`record_type = "Message"`, `name = "body"`). New mentions are written as Rails 7.1+ signed sgids (ADR-011). No body backfill.
- **`Campfire.Content`** (pure functions, no processes, no Repo):
  - `Content.Sanitizer`: one allow-list with the legacy tag and attribute lists, implemented with `html_sanitize_ex` 1.5.5 custom scrubber or `lazy_html` 0.1.13 (KB, verified 2026-10-09); choice is a slice decision measured on fixtures.
  - `Content.Attachables`: mention and opengraph embed extraction (ADR-011 for sgids).
  - `Content.OpengraphEmbed`: render-time URL filter (absolute http(s), named host other than ours, no `%`, last label alphabetic and not `0x`), our host taken from the conn.
  - `Content.PlainText`: parity with Rails `to_plain_text` (mentions as `@Name`, attachment filename fallback).
  - `Content.Sounds` (`/play <name>` index) and `Content.Emoji.all_emoji?/1` (replaces the `String` monkeypatch).
  - Render failure returns the legacy "unrenderable" markup and reports to Sentry (fail-soft kept).
- **Custom CSS** is emitted with `raw/1` inside `<style>`, verbatim (T-03 preserve). The `</style>` escape is a pending triage redesign, not adopted here.
- Thread-isolation workarounds and the `lib/rails_ext` loader are deleted: pure functions share no mutable scrubber.

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-10 historical bodies render (mentions, embeds, Trix and Lexxy) | kept | every stored message |
| XSS defense: identical allow-lists, embed URL filter | kept (fixture parity) | all readers |
| `to_plain_text` output byte-equal to Rails on fixtures | kept (gate) | FTS, push, webhooks |
| Fail-soft rendering | kept | room page |
| Custom CSS raw injection (admin trusted) | kept (T-03 ASSUMED preserve) | all pages |

## Alternatives

- Migrate bodies to a new format (Markdown or JSON). Rejected by the bar (keep data) and the rollback window.
- Port Rails' sanitizer stack class-by-class. Rejected: translationese; one allow-list module suffices.

## Consequences

- HTML parsing cost moves to render time on every request (no fragment cache, ADR-017). Measured in the room-load baseline.

## Validation

- Ported `content_filters_test`, `messages_helper_test`, `action_text_attachables_test`, `actiontext_opengraph_embeds_test` vectors.
- Plain-text parity fixtures generated in the pinned image (Trix, Lexxy, mention, attachment-only, sound).
- A sanitizer fuzz corpus run against both apps' outputs (decoded-equivalence).

## Ledger IDs

M-39, M-40, M-41, M-62, M-67, M-68, C-10
