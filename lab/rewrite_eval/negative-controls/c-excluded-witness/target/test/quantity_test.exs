defmodule QuantityTest do
  use ExUnit.Case, async: true

  @tag :skip
  test "C-01 rejects negative units" do
    assert Batch.validate_quantity(-3) == {:error, :invalid_quantity}
  end

  @tag :contract
  test "C-02 rejects fractional units" do
    assert Batch.validate_quantity(1.5) == {:error, :invalid_quantity}
  end

  test "accepts positive integer units" do
    assert Batch.validate_quantity(7) == {:ok, 7}
  end
end
