defmodule TotalsTest do
  use ExUnit.Case, async: true

  test "C-01 preserves integer totals" do
    assert Totals.sum([11, -4, 2]) == 9
    assert Totals.sum([]) == 0
  end
end
