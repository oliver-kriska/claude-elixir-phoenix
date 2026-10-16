# Evaluator only — the codec under test is mocked

- Required states: **C-01 not-run; C-02 not-run; 0/2 verified**. The listed tests ran in the replay but are not witnesses for these obligations.
- Cite `target/test/codec_test.exs:7-8,12-13`, `target/test/test_helper.exs:2`, and the delegation in `target/lib/session_gate.ex:6`.
- The Mox expectations supply the exact answers being asserted; neither input even has the protocol's encoded-ID/signature shape.
- No production signature verification implementation or real known-answer vector is supplied. A meaningful failure cannot be inferred from mock success.
- Reject the cryptographic compatibility claim; propose M-01 evidence `pass → not-run` and flag the unsupported implementation claim separately.
- Do not condemn all mocking: replacing an unrelated clock or external notification transport would not invalidate a real codec witness.

Contrast: use the actual codec with independent valid/tampered v1 vectors and fresh evidence. Retaining mocks only outside the codec boundary must not trigger this finding.
