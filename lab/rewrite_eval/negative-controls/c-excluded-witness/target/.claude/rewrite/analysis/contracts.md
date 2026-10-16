# Contracts — S-01

- C-01 (data, keep): -3 is rejected as invalid_quantity.
- C-02 (data, keep): 1.5 is rejected as invalid_quantity; units are indivisible.

Source: `SOURCE/quantity.py:1-4`. Both witnesses are in `test/quantity_test.exs`.
These two negative probes are the complete scored denominator; the positive test is ancillary.
