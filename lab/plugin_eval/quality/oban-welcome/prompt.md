---
description: Add an Oban worker and enqueue it. Iron Laws 7-9 cover idempotency, string-key args and IDs rather than structs.
expected_outcome: perform/1 matches %{"user_id" => id}, create_user/1 enqueues with the user id, the worker is unique or otherwise safe to retry, and a deleted user cancels the job instead of retrying.
tags: [quality, oban, quick]
max_turns: 25
timeout_seconds: 420
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit]
---

/phx:quick Send a welcome email in the background after a user signs up: add MyApp.Workers.WelcomeEmailWorker
in lib/my_app/workers/welcome_email_worker.ex and enqueue it from Accounts.create_user/1.
MyApp.Mailer.deliver_welcome/1 takes a %User{} and sends the email. mix is not available here, so don't
compile.
