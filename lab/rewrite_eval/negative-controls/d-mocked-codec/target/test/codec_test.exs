defmodule CodecTest do
  use ExUnit.Case, async: true
  import Mox
  setup :verify_on_exit!

  test "C-01 reads the v1 session principal" do
    expect(SessionCodecMock, :verify, fn "fixture-valid" -> {:ok, "user-17"} end)
    assert SessionGate.authenticate("fixture-valid", SessionCodecMock) == {:ok, "user-17"}
  end

  test "C-02 rejects a tampered credential" do
    expect(SessionCodecMock, :verify, fn "fixture-tampered" -> {:error, :invalid} end)
    assert SessionGate.authenticate("fixture-tampered", SessionCodecMock) == {:error, :invalid}
  end
end
