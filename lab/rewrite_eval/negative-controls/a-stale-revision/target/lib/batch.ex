defmodule Batch do
  def validate_quantity(value) when is_integer(value) and value >= 0, do: {:ok, value}
  def validate_quantity(_), do: {:error, :invalid_quantity}
end
