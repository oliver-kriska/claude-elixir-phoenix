---
type: llm
---

The text is the final message of a code review of an Elixir/Phoenix branch. `OrderLive.mount/3` calls
`Orders.list_recent_orders/1` directly, so the query runs on both the disconnected (dead/static) render and the
connected render.

PASS if the review points out that the orders query in `mount` runs twice (dead render and connected render), or
recommends moving it behind `connected?/1`, into `assign_async`/`start_async`, or into `handle_params` because of
that double execution.

FAIL if the query in `mount` is not mentioned, or is mentioned only for a different reason (for example sorting or
the `params` shape) without the double execution.
