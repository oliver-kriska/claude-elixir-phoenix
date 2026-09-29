---
description: Review a branch with five obvious and four subtle seeded defects. Score is the share the final review names.
expected_outcome: The review names the N+1, String.to_atom on a param, float money, missing authorization, the unguarded mount query, the missing @external_resource, the unsupervised Task, the locale lost in it and the unpreloaded order.user, and edits nothing.
tags: [quality, review]
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write]
---

/phx:review the orders feature on this branch (compare against main). mix is not available in this
environment, so don't try to compile or run tests.
