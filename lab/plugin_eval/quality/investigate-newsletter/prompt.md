---
description: Silent failure from an atom/string key mismatch that the test suite hides. Graded on root cause, why the test missed it, whether the fix avoids the "false"-string trap, and whether the prior solution doc in .claude/solutions/ is used.
expected_outcome: Root cause is attrs[:newsletter] on string-keyed form params; the test passes atom keys; the fix reads the cast boolean (user.newsletter or the changeset), not attrs["newsletter"], which is the truthy string "false" when unticked.
tags: [quality, investigate]
max_turns: 30
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash]
---

/phx:investigate Users who tick "Subscribe to newsletter" on their profile page never get subscribed. The
profile saves fine, the checkbox is still ticked after a reload, there is nothing in the error logs, and the
newsletter test in test/my_app/accounts_test.exs passes. mix is not available in this environment, so work
from the code. Don't change any files: report the root cause and the fix you would make.
