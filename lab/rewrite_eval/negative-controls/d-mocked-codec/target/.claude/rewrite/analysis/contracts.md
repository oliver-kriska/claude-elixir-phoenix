# Contracts — S-01

- C-01 (wire, keep): decode and verify a real v1 credential and return its original user ID.
- C-02 (wire, keep): reject a v1 credential whose encoded user ID changed while its original signature stayed unchanged.

Source: `SOURCE/PROTOCOL.md:3-4`. This slice is about the codec itself, not a caller's handling of a codec result.
Candidate witness file: `test/codec_test.exs`. Both obligations are required.
