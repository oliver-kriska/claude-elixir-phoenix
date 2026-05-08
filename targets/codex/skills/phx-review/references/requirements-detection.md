# Requirements Detection Reference

How `/phx:review` finds the task / issue / spec whose requirements should be
checked against the diff. Referenced by Step 1c of the review skill.

## Detection Priority

Try sources in order, stop at the first match. If none match, emit
`NOT AVAILABLE` in the coverage block (do not silently skip).

| # | Source | How to detect | Fetch via |
|---|--------|---------------|-----------|
| 1 | Explicit `$ARGUMENTS` path | arg ends in `.md` and file exists | Read |
| 2 | Explicit `$ARGUMENTS` ID | arg matches `^[A-Z]+-\d+$` or `^#?\d+$` | Linear MCP / gh |
| 3 | Conversation context | a `mcp__linear__get_issue` or `gh issue view` call already in this session | Reuse the fetched body — do NOT re-fetch |
| 4 | Branch regex | `git rev-parse --abbrev-ref HEAD` matches `[A-Za-z][A-Za-z0-9_]+-\d+` | Linear MCP / gh (by ID) |
| 5 | Commit subjects | `git log main..HEAD --pretty=%s` mentions `[A-Z]+-\d+` or `#\d+` | Linear MCP / gh (by ID) |
| 6 | Latest plan file | `ls -t .claude/plans/*/plan.md \| head -1` exists | Read (extract `- [x]` items) |
| — | None of the above | — | emit `NOT AVAILABLE` |

## Regexes

Match these case-sensitively; Linear IDs are always uppercase, but branch
names often lowercase them:

- **Issue ID (upper)**: `([A-Z][A-Z0-9_]+-\d+)` — matches `ENA-8931`, `DOV-42`, `WED-1`
- **Branch form (lower)**: `^([a-z][a-z0-9_]+-\d+)` — matches `ena-8931-description`,
  uppercase it before calling Linear
- **GitHub ref**: `#(\d+)` — matches `#42`, `fix #1234`
- **Pure number** (as arg): `^#?(\d+)$` — default to GitHub when length ≤ 5

## Fetch Mapping

| Source type | Command | Output |
|-------------|---------|--------|
| `linear` | `mcp__linear__get_issue(id=ID)` | issue title + description + acceptance criteria |
| `github` | `gh issue view NNN --json title,body --jq '.title + "\n\n" + .body'` | title + body markdown |
| `file` | `Read(path)` | full file |
| `plan` | `Read(path)` filtered to lines matching `^- \[x\]` | completed tasks only |

## Fetch Failure Handling

Any fetch can fail (MCP not installed, network, auth). On failure:

1. Do NOT abort the review. The code-quality review still runs.
2. Write the source + failure reason to the agent's input stub
   (`.claude/plans/{slug}/reviews/.requirements-input.md`) so the verifier
   can include it in output:

   ```text
   SOURCE: Linear ENA-8931
   STATUS: FETCH_FAILED
   REASON: mcp__linear tool not available in this session
   ```

3. Verifier emits `NOT AVAILABLE — {reason}` instead of a table.

## Conversation-Context Reuse

If the same session already called `mcp__linear__get_issue(ENA-8931)` (for
example during `/phx:plan` or user exploration), the tool result is still
in context. Prefer reusing that over re-fetching:

- Scan the last N messages for a `mcp__linear__get_issue` response whose
  issue identifier matches the detected TASK_ID
- If found, pass its body as `REQUIREMENTS_TEXT` directly
- Saves a round-trip and preserves whatever was visible to the user

## Plan-File Special Case

When the source is a local plan, only `- [x]` items count as claimed
requirements. `- [ ]` items are known-deferred and should not be reported
as UNMET (that's just current progress, not a regression).

For Linear / GitHub / spec markdown, ALL listed AC items count — the user
expected the feature done.

## NOT AVAILABLE Output Shape

When detection fails completely, the verifier (or skill itself if the
verifier was not spawned) writes:

```markdown
## Requirements Coverage

**NOT AVAILABLE** — no task ID or requirements source detected.

Sources tried:
- $ARGUMENTS: empty
- Branch `main`: no issue ID pattern
- Commits since main: none
- `.claude/plans/`: no plan files present

To force a source: `/phx:review ENA-8931`, `/phx:review #42`, or
`/phx:review path/to/spec.md`.
```

This is the "we looked and couldn't find anything" alternative to silence
— users see we tried.
