# Requirements Detection

Use this order and stop at the first usable source:

| Priority | Source | Detection | Fetch |
|---|---|---|---|
| 1 | Explicit path | User input ends in `.md` and the file exists | Read the file |
| 2 | Explicit issue ID | Input matches `^[A-Z]+-\d+$` or `^#?\d+$` | Available Linear integration or `gh issue view` |
| 3 | Conversation context | Requirements already appear in the session | Reuse them |
| 4 | Branch name | Branch contains an issue-like identifier | Available integration or `gh` |
| 5 | Commit subjects | Recent subjects contain an identifier | Available integration or `gh` |
| 6 | Latest plan | Relevant `.claude/plans/*/plan.md` exists | Read the file |
| 7 | None | No source found | Mark `NOT AVAILABLE` and continue |

Never let a missing Linear, GitHub, MCP, hook, or network integration block the
review. Record the selected requirements source and any fetch failure. Do not
silently substitute guessed requirements.

## Coverage Output

For each acceptance criterion, report `MET`, `PARTIAL`, `UNMET`, or `UNCLEAR`
with changed-file evidence. Put requirements coverage before code-quality
findings. Any `UNMET` criterion requires a `REQUIRES CHANGES` verdict; `PARTIAL`
without `UNMET` downgrades `PASS` to `PASS WITH WARNINGS`.
