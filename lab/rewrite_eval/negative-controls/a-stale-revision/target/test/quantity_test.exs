defmodule QuantityTest do
  use ExUnit.Case, async: true

  test "C-01 rejects negative units" do
    assert Batch.validate_quantity(-3) == {:error, :invalid_quantity}
  end
end
