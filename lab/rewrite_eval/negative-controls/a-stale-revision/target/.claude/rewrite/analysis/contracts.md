# Contracts — S-01

- C-01 (data, keep): the batch importer rejects a negative unit count with `invalid_quantity`.
  Witness: `test/quantity_test.exs`, input -3, no accepted quantity.
  Source: `SOURCE/quantity.py:1-4`. No other obligations are in this slice.
