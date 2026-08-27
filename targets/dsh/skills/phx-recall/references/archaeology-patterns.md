# Archaeology Patterns

## Git recipes (Layer 2)

| Question shape | Recipe |
|----------------|--------|
| "When did we change/add X?" (code symbol) | `git log -S "X" --oneline` — pickaxe finds commits where the count of X changed |
| "Why does this line exist?" | `git log -L {start},{end}:{file}` or `git blame -w -C {file}` |
| "What happened to this file?" | `git log --follow --oneline -- {file}` (survives renames) |
| "What did we do about {topic}?" | `git log --grep="{topic}" -i --oneline` |
| "What changed between releases?" | `git log v2.10.0..v2.11.0 --oneline` |
| Inspect a candidate | `git show {hash} --stat`, then `git show {hash} -- {file}` for the diff |

Prefer `--oneline` + targeted `git show` over dumping full diffs into
context — same delta-only discipline as the watch-pr skill.

## ccrider query patterns (Layer 3)

- Lead with the concrete noun: `"form save silent changeset"` beats
  `"debugging problem form"`
- Search returns ranked hits with session IDs + snippets — that's usually
  enough to pick ONE session worth fetching
- `list_recent_sessions` when the user says "last week" / "yesterday"
  rather than describing content

## Subagent prompt template (Iron Law 2)

One session per subagent — `get_session_messages` responses are 3–15KB
and batching floods the parent context:

```
Fetch session {SESSION_ID} via mcp__ccrider__get_session_messages.
The question is: "{QUESTION}"
Extract ONLY content that answers it: the problem, the fix/decision,
file paths, and the outcome. Ignore everything else.
Write at most 30 lines of markdown to .claude/recall/{SESSION_ID}.md
and reply with just "done" — the file is the output.
```

Note: ccrider messages use `type` (not `role`) and content is plain
string — tool usage must be inferred from assistant text.

## When all three layers miss

Say so explicitly: "No prior work found on {topic} in solution docs, git
history, or indexed sessions." A clean miss is a valid answer — do not
pad it with speculation. Suggest `/phx-compound` after the user solves it
fresh, so the next recall hits Layer 1.
