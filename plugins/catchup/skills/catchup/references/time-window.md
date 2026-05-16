# Time Window Resolution

Turn `--since` into two values used everywhere downstream:

- `SINCE_ISO` — RFC3339 UTC, e.g. `2026-05-13T00:00:00Z` (for `gh api`,
  `gh search`, MCP filters).
- `SINCE_LABEL` — human string for the brief, e.g.
  `3 days (since Fri May 13)`.

Always compute the window first. Every source query depends on it.

## Grammar for `--since`

| Input            | Meaning                                              |
|------------------|------------------------------------------------------|
| `last-session`   | (default) newest Claude session mtime for this repo  |
| `2h`, `90m`, `3d`| relative duration before now                         |
| `yesterday`      | start of yesterday, local TZ                          |
| `friday`, `monday` | most recent past occurrence of that weekday, 00:00 |
| `"2026-05-13"`   | explicit date, 00:00 local TZ                         |
| `"last week"`    | 7 days ago                                            |

Validate the input against this grammar **before** it touches a shell.
If it does not match, do not interpolate it into `git`/`gh` — fall back
to 24h and record the assumption in the brief's Risks block.

`git` accepts most of these natively (`git log --since="friday"`), but
`gh` needs an ISO date. Resolve once with `date`:

```bash
# relative duration (portable enough for macOS/Linux GNU date)
SINCE_ISO=$(date -u -d "3 days ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
         || date -u -v-3d +%Y-%m-%dT%H:%M:%SZ)        # BSD/macOS fallback
SINCE_DATE=${SINCE_ISO%%T*}                            # gh search wants a date
```

`gh search` / `gh pr list --search` use `updated:>=YYYY-MM-DD`; `gh api`
endpoints use the full `SINCE_ISO`.

## `last-session` auto-detect (default)

Goal: "since I last had a Claude Code session in this project".

1. Derive the session dir slug. Claude stores per-project sessions in
   `~/.claude/projects/-<path-with-slashes-as-dashes>/`. Compute it from
   the current working directory:

   ```bash
   SLUG=$(pwd | sed 's@/@-@g')          # /Users/x/Projects/foo -> -Users-x-Projects-foo
   SDIR="$HOME/.claude/projects/$SLUG"
   ```

2. Newest session activity = newest `*.jsonl` mtime in that dir:

   ```bash
   LAST=$(ls -t "$SDIR"/*.jsonl 2>/dev/null | head -1)
   [ -n "$LAST" ] && SINCE_ISO=$(date -u -r "$LAST" +%Y-%m-%dT%H:%M:%SZ)
   ```

   Use the **second-newest** file if the newest is the current live
   session (its mtime is "now", which would yield an empty window).
   Heuristic: if newest mtime is within the last 5 minutes, step to the
   next file; if only one file exists, fall back to 24h.

3. No `*.jsonl` and no signal → `SINCE_ISO = now - 24h`, and add to the
   brief Risks block: *"No prior session found for this repo — defaulted
   to a 24h window."*

4. Optional cross-check: if ccrider MCP is available, its
   last-session-for-cwd timestamp can confirm step 2. Not required;
   mtime is sufficient and dependency-free.

## Producing `SINCE_LABEL`

```
days = round((now - SINCE_ISO) / 86400)
SINCE_LABEL = "{days} day(s) (since {Www Mmm DD})"
```

For sub-day windows use hours: `"5h (since 09:12 today)"`. The label
goes in the brief's **Intent** line and **Timeline** block so the
reader instantly knows how much ground the brief covers.
