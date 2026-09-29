#!/usr/bin/env bash
# Accounts context + Swoosh mailer + Oban config; no workers yet.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR source=../_shared/base.sh
source "$(dirname "${BASH_SOURCE[0]}")/../_shared/base.sh"

cat > lib/my_app/mailer.ex <<'EX'
defmodule MyApp.Mailer do
  use Swoosh.Mailer, otp_app: :my_app
  import Swoosh.Email
  alias MyApp.Accounts.User

  def deliver_welcome(%User{} = user) do
    new()
    |> to(user.email)
    |> from({"MyApp", "hello@example.com"})
    |> subject("Welcome to MyApp")
    |> text_body("Hi #{user.name}, thanks for signing up!")
    |> deliver()
  end
end
EX

cat > config/config.exs <<'EX'
import Config

config :my_app, Oban,
  repo: MyApp.Repo,
  queues: [default: 10, mailers: 20]

import_config "#{config_env()}.exs"
EX

commit "Add mailer and Oban config"
