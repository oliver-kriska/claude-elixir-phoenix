defmodule HealthRouterTest do
  use ExUnit.Case, async: true
  import Plug.Test

  test "C-01 returns public process liveness, not downstream readiness" do
    result = HealthRouter.call(conn(:get, "/health"), HealthRouter.init([]))
    assert result.status == 200
    assert result.resp_body == ~s({"status":"ok"})
    assert [type] = Plug.Conn.get_resp_header(result, "content-type")
    assert String.starts_with?(type, "application/json")
  end

  test "C-02 rejects unknown routes and unsupported methods" do
    for {method, path} <- [{:get, "/private"}, {:post, "/health"}] do
      assert HealthRouter.call(conn(method, path), HealthRouter.init([])).status == 404
    end
  end
end
