# gh Commands — PR Review Threads

Use the exact outer and nested GraphQL queries in `SKILL.md`. Both queries use
`$endCursor`; the outer query includes `originalLine`, and the per-thread nested
query uses `gh api graphql --paginate -F threadId=...` with nested `pageInfo {
hasNextPage endCursor }`. Merge nested pages in API order, deduplicate comments by
GraphQL `id`, and do not begin triage until all comments are complete.

Reply only to the root review comment after exact-reply posting approval. Confirm
the API response, then separately request resolution approval. `--no-resolve`
always wins. Review summaries and issue comments are non-resolvable surfaces and
must not substitute for review threads.
