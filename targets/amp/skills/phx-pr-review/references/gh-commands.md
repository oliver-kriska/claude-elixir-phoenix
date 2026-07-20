# gh Command Reference — PR Review Threads

Verified against gh 2.94.0 and the live GitHub API (2026-06). Repo is
inferred from cwd, or parsed from a PR URL, or passed via `-R owner/repo`.

## The three comment surfaces

These are different endpoints with different reply mechanisms. Mixing them
up means replies silently land in the wrong place.

| Surface | Read | Resolvable? | Reply |
|---------|------|-------------|-------|
| Inline review comment (file/line) | GraphQL `reviewThreads` or REST `pulls/{n}/comments` | YES (thread) | REST `.../comments/{id}/replies` or GraphQL thread reply |
| Review summary ("Changes requested" body) | REST `pulls/{n}/reviews` | NO | Top-level conversation comment, or address inline and re-request review |
| Top-level conversation comment | REST `issues/{n}/comments` (a PR IS an issue) | NO | `POST repos/{o}/{r}/issues/{n}/comments -f body=...` |

## PR metadata

```bash
gh pr view "$PR" --json number,title,state,baseRefName,headRefName,url,author \
  --jq '{number,title,state,base:.baseRefName,head:.headRefName,url,author:.author.login}'
```

`gh pr view` accepts a number OR a URL and resolves the repo from the URL.

## Review threads with resolve state (GraphQL — the core query)

REST review comments have NO `isResolved` field and NO thread node ID.
The GraphQL query in SKILL.md Step 1 is the only way to get both. Key fields:

- `id` — `PRRT_...` thread node ID → used by resolve/unresolve and GraphQL reply
- `comments.nodes[].databaseId` — integer REST comment ID → used by REST reply
- `line` may be `null` on outdated threads → fall back to `originalLine`
- `--paginate` auto-follows `endCursor` because the query exposes
  `pageInfo { hasNextPage endCursor }` and accepts `$cursor`
- With `--paginate`, `--jq` runs PER PAGE. Add `--slurp` to merge pages into
  one array when counting/sorting across pages

## Reply

REST (preferred when `databaseId` is in hand — reply to the thread's ROOT comment):

```bash
gh api --method POST \
  "repos/$OWNER/$REPO/pulls/$PR/comments/$COMMENT_ID/replies" \
  -f body="$REPLY_TEXT" --jq '{reply_id: .id, in_reply_to: .in_reply_to_id}'
```

GraphQL (when only the thread ID is in hand):

```bash
gh api graphql \
  -f query='mutation($threadId:ID!,$body:String!){
    addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId, body:$body}){
      comment { id databaseId url } }}' \
  -F threadId="$THREAD_ID" -F body="$REPLY_TEXT"
```

## Resolve / unresolve

```bash
gh api graphql -f query='mutation($threadId:ID!){
  resolveReviewThread(input:{threadId:$threadId}){ thread { id isResolved } }}' \
  -F threadId="$THREAD_ID" --jq '.data.resolveReviewThread.thread'

gh api graphql -f query='mutation($threadId:ID!){
  unresolveReviewThread(input:{threadId:$threadId}){ thread { id isResolved } }}' \
  -F threadId="$THREAD_ID"
```

An invalid node ID returns a clean `NOT_FOUND` — safe to surface as an error.

## Review summaries + conversation comments

```bash
# Review summaries (incl. bot passes — Copilot/Codex post these)
gh api "repos/$OWNER/$REPO/pulls/$PR/reviews" \
  --jq '.[] | {reviewer: .user.login, isBot: (.user.type=="Bot"), state, body}'

# Top-level conversation: read + post (post = outward-facing, confirm first)
gh api "repos/$OWNER/$REPO/issues/$PR/comments" --jq '.[] | {user: .user.login, body}'
gh api --method POST "repos/$OWNER/$REPO/issues/$PR/comments" -f body="$SUMMARY"
```

## Bot detection

| Source | Field | Bot value |
|--------|-------|-----------|
| GraphQL | `author.__typename` | `"Bot"` |
| REST | `user.type` | `"Bot"` |
| REST | `user.login` suffix | `[bot]` — **NOT reliable**: `pulls/{n}/comments` reports `Copilot` (no suffix) while `pulls/{n}/reviews` reports `copilot-pull-request-reviewer[bot]` |

Use the type fields, not the login suffix.

## Edge cases

- **Outdated threads** (`isOutdated: true`): line moved or was deleted;
  `line` is often null → use `originalLine`. Default action: reply
  "addressed in {commit}, line has since moved" + resolve.
- **Multi-round reviews**: re-running is idempotent — the unresolved-only
  filter drops handled threads; GitHub's `isResolved` IS the state.
- **Summary-only feedback** (CHANGES_REQUESTED with no inline threads):
  can't be resolved; reply as conversation comment and/or change code —
  the review state flips on re-request.
- **No threads / all resolved**: report "No unresolved review threads on
  PR #N", but still surface CHANGES_REQUESTED summaries.
