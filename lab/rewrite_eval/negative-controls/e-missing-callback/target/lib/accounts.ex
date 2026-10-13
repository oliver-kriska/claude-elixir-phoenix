defmodule Accounts do
  # The fixture scopes the row-construction boundary, not database persistence.
  def registration_records(id, email) do
    %{account: %{id: id, email: email}}
  end
end
