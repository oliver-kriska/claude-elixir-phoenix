defmodule RegistrationTest do
  use ExUnit.Case, async: true

  test "C-01 creates the account record with the requested identity" do
    records = Accounts.registration_records(17, "reader@example.invalid")
    assert records.account == %{id: 17, email: "reader@example.invalid"}
  end
end
