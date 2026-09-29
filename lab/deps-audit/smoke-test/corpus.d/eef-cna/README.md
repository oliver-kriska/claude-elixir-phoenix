# EEF CNA Real-World CVE Corpus

Regression fixtures derived from the 2026-05-12 virgil dogfood + the
broader EEF CNA Hex package CVE table (see
`.claude/research/2026-05-13-eef-cna-real-cve-corpus.md`).

Each fixture asserts the differential CVE pass (`diff_cves.py`)
correctly categorizes a real-world (OLD vulnerable, NEW patched)
package bump.

## Fixtures

| Fixture | Package | CVE | Disclosed |
|---------|---------|-----|-----------|
| `eef-cna-decimal` | `decimal 2.3.0 → 3.0.0` | CVE-2026-32686 (DoS) | 2026-05-07 |
| `eef-cna-bandit` | `bandit 1.10.3 → 1.11.0` | CVE-2026-39805 (HTTP smuggling) | 2026-05-01 |
| `eef-cna-phoenix` | `phoenix 1.8.5 → 1.8.7` | CVE-2026-32689 (long-poll DoS) | 2026-05-05 |
| `eef-cna-postgrex` | `postgrex 0.22.0 → 0.22.1` | CVE-2026-32687 (SQL injection) | 2026-05-12 |
| `eef-cna-cowlib` | `cowlib 2.13.0 → 2.15.0` | CVE-2026-43968 (CR injection) | 2026-05-11 |

## Running

```bash
FIXTURES_DIR=smoke-test/corpus.d/eef-cna \
  bash smoke-test/cve-diff-runner.sh
```

Or all together:

```bash
bash smoke-test/cve-diff-runner.sh   # runs fixtures.d/2x_cve_* by default
FIXTURES_DIR=smoke-test/corpus.d/eef-cna bash smoke-test/cve-diff-runner.sh
```

## Methodology

Real CVEs from EEF CNA. Mock `cves_old.json` / `cves_new.json`
synthesized to match the documented advisory shape (GHSA ID, CVE ID,
severity, disclosure_date, patched_versions). No real network calls
— the fixtures test the categorization layer, not `mix_audit` itself.

## Skipped

OTP-level CVEs (SSH, inets, public_key, kernel) — these aren't
Hex-tracked, so `mix_audit` doesn't see them. Phase 6+ will add a
separate OTP version detection layer.

## Future

The remaining ~30 EEF CNA CVEs (absinthe, plug_cowboy, hex,
ash, esaml, nerves_hub, etc.) are good follow-up fixtures. The
initial 5 prove the pipeline works end-to-end.
