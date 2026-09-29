---
type: llm
---

The text is the final message of a code review of an Elixir/Phoenix branch. The branch adds
`MyAppWeb.OrderLive`, whose `handle_event("cancel", %{"id" => id}, socket)` loads any order by id and cancels
it without checking who the current user is.

PASS if the review flags that the cancel event (or `Orders.cancel_order/1`) performs no authorization or
ownership check, so any connected user can cancel any order by sending an arbitrary id.

FAIL if authorization, ownership or permission checks are not mentioned, or are mentioned only as a generic
reminder that is not tied to the cancel event.
