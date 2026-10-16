defmodule Batch do
  def validate_quantity(value) when is_integer(value), do: {:ok, value}
  def validate_quantity(_), do: {:error, :invalid_quantity}
end
