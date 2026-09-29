---
type: llm
---

The text is the final message of a code review of an Elixir/Phoenix branch. In `OrderLive.handle_event("cancel", ...)`
the order returned by `Orders.get_order!/1` and `cancel_order/1` has no `:user` preloaded, and it is passed to
`Notifier.deliver_cancellation/1` inside `Task.start`, which reads `order.user.email`.

PASS if the review points out that the order sent to the cancellation email lacks its preloaded `:user`, so
`order.user.email` fails (Ecto.Association.NotLoaded) and the email is not sent.

FAIL if this is not mentioned. The N+1 in `list_recent_orders/1` (`Repo.get!(User, ...)` per order) is a different
finding and does not count.
