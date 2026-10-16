defmodule SessionCodec do
  @callback verify(binary()) :: {:ok, binary()} | {:error, :invalid}
end

defmodule SessionGate do
  def authenticate(token, codec), do: codec.verify(token)
end
