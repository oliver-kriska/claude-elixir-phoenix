---
description: Plan a small two-context feature. The plan must be a checkbox task list with DB-level dedupe, LiveView list handling and a verification step, and nothing may be implemented.
expected_outcome: plans/favorites/plan.md with - [ ] tasks, a unique index on (user_id, product_id), streams or assign_async for the list, mix test/compile verification, and no writes under lib/, priv/ or test/.
tags: [quality, plan]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Write, Edit]
---

/phx:plan Let signed-in users favorite products and see their favorites on a LiveView page at /favorites.
Write the plan to plans/favorites/plan.md (the .claude directory is read-only in this environment). mix is not
available here.
