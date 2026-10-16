# ADR-013: Files — keep Active Storage tables and disk layout; libvips hardening; no direct uploads

**Status**: proposed (auto; needs approval). Behavior change DV-11.
**Date**: 2026-10-09 · **Bar**: ADR-000 (ASSUMED) Data: "Active Storage disk layout, tables and signed URLs are kept"

## Context

- Disk service `local` at `storage/files`, path `<key[0..1]>/<key[2..3]>/<key>`, base64 MD5 checksum, JSON `metadata`, variant records keyed by a Marshal-derived `variation_digest` (C-11, R-28).
- Upload processing (analyze, thumbnail `thumb` 1200×800, video preview webp via ffmpeg) runs synchronously in the request (M-44, R-34). Avatars `square` 512 webp, logo `large` 512 / `small` 192 png.
- libvips hardening: `block_untrusted`, Openslide blocked, bmp/ico/psd not variable (M-45). Direct uploads were exploitable and are unused (M-46).
- `has_one_attached` purges files later through an implicit `PurgeJob` (R-33).

## Decision

- **`Campfire.Files`** owns `active_storage_blobs`, `active_storage_attachments`, `active_storage_variant_records` and the files. Schemas keep table names, polymorphic strings (C-06) and `service_name = "local"`.
- **Upload path**: write the file to its final key path and compute the MD5 **before** opening the writer transaction; the transaction inserts blob and attachment rows with the message (ADR-005). Analyze and thumbnail/preview stay synchronous in the request (parity, R-34) but outside the writer transaction.
- **Variants** via `image` 0.72.0 / `vix` 0.42.0 (KB, verified 2026-10-09). Existing variant records are reused by computing the Rails `variation_digest` (ADR-011). Loader policy: an explicit content-type allow-list before decode plus Vix untrusted-loader blocking (`verify` the API in vix 0.42.0). ffmpeg for video posters as an external port under `tini`.
- **Serving**: blob redirect `/rails/active_storage/blobs/redirect/<signed_id>/<filename>` unauthenticated (C-27), disk-service download with `max-age=3600, public` (C-46), avatars and logos with their legacy cache headers.
- **No direct-upload or disk `PUT` routes** exist; a negative route test pins it (M-46 DELETE).
- **Purge**: `Files.PurgeBlob` Oban job inserted in the transaction that deletes the attachment row (ADR-006). It deletes files first, then rows, treats `:enoent` as success, and **skips blobs still attached elsewhere** (DV-11).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| C-11 legacy files and variants readable; port uploads readable by Rails | kept | every attachment |
| C-27 unauthenticated, non-expiring download links; anonymous upload impossible | kept | shared links |
| Untrusted decoders never run | kept (loader policy test) | all uploads |
| Purge after delete | **changed (strengthened)**: durable, retried, skips shared blobs (DV-11) | storage |

## Alternatives

- Move media processing to Oban (async thumbnails). Not adopted: changes when a thumbnail appears (redesign, needs approval).
- New storage layout. Rejected by the bar.

## Consequences

- Requests that upload hold a scheduler-dirty libvips/ffmpeg call; measured in the upload workload of the baseline.

## Validation

- Resolve five legacy blobs to paths and compare MD5; serve a legacy variant record without regeneration; Rails reads a port upload.
- Ported `vips_loader_policy_test` and `active_storage_authentication_test` (anonymous direct upload → 401/404).
- Variation-digest vectors (security consult vector 8).

## Ledger IDs

M-14, M-44, M-45, M-46, R-28, R-33, R-34, C-06, C-11, C-27
