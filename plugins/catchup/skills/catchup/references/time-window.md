# Time Window Resolution

Turn `--since` into an unambiguous instant, then derive everything else
from it. **Epoch seconds is the single pivot** — it is timezone-free,
and both GNU (`date -d`) and BSD/macOS (`date -v`/`-r`) can read and
write it. Never resolve calendar words straight to UTC; that is the
timezone bug.

- `SINCE_EPOCH` — Unix seconds. The one source of truth.
- `SINCE_ISO` — `date -u` of `SINCE_EPOCH`, e.g. `2026-05-12T22:00:00Z`
  (for `gh api` / MCP filters; compares on absolute time).
- `SINCE_DATE` — UTC `YYYY-MM-DD` of `SINCE_EPOCH` (for `gh search`).
- `SINCE_LABEL` — human, with the anchor TZ shown so it is
  unambiguous: `since Fri May 13 00:00 CEST (3 days)`.

## The timezone model (read this)

The person running `/catchup` is on their own machine, so the machine's
**local timezone is the user's timezone**. Calendar words resolve in
that local TZ:

- `--since "friday"` → the user's most recent Friday, **00:00 local**.
- `--since "yesterday"` → start of yesterday, **local**.
- `--since "2026-05-13"` → that date **00:00 local**.

That local wall-clock is converted **once** to `SINCE_EPOCH` (an
absolute instant). Every source (git author/commit time, GitHub API
UTC timestamps, Linear/Calendar) is then compared on that absolute
instant. Consequence — and this is the desired behaviour:

> A colleague in another timezone whose own "Friday" begins at a
> different absolute moment is included **iff their event's absolute
> timestamp ≥ the user's Friday instant**. "Since Friday" means *since
> the user's Friday started*, not "since each author's local Friday".
> Their Friday-morning commit counts only if it happened at/after the
> user's Friday 00:00 in real time — which is exactly right.

Relative durations (`2h`, `3d`) are TZ-agnostic deltas: `now - N`.

## Grammar for `--since`

| Input              | Resolution                                          |
|--------------------|-----------------------------------------------------|
| `last-session`     | (default) newest Claude session mtime, this repo    |
| `2h`, `90m`, `3d`  | `now - duration` (TZ-agnostic delta)                |
| `yesterday`        | yesterday 00:00 **local TZ**                         |
| `friday`, `monday` | most recent past occurrence, 00:00 **local TZ**      |
| `"2026-05-13"`     | that date 00:00 **local TZ**                         |
| `"last week"`      | `now - 7d`                                           |

Validate `--since` against this grammar **before** it touches a shell.
No match → fall back to 24h and note the assumption in the brief's
Risks block.

## Resolving each form to `SINCE_EPOCH`

```bash
LOCAL_TZ=$(date +%Z)                       # user's TZ abbrev, for the label
NOW=$(date +%s)

# relative duration: now - N (TZ-agnostic)
#   parse 2h/90m/3d -> seconds, SINCE_EPOCH=$((NOW - secs))

# yesterday / explicit date: local midnight -> epoch
#   GNU : date -d 'yesterday 00:00' +%s
#         date -d '2026-05-13 00:00:00' +%s
#   BSD : date -v-1d -v0H -v0M -v0S +%s
#         date -j -f '%Y-%m-%d %H:%M:%S' '2026-05-13 00:00:00' +%s

# weekday name: most-recent-past occurrence at local 00:00.
# Use day-of-week arithmetic (do NOT rely on `date -d 'last friday'` —
# GNU/BSD disagree, and behaviour on the named day itself differs):
TARGET=5                                   # Mon=1..Sun=7 (here: Friday)
DOW=$(date +%u)
BACK=$(( (DOW - TARGET + 7) % 7 ))         # 0 if today IS that weekday
#   GNU : date -d "$BACK days ago 00:00" +%s
#   BSD : date -v-"${BACK}"d -v0H -v0M -v0S +%s
# BACK=0 ⇒ today 00:00 local ("since friday" said on a Friday = today).
```

Then derive the rest from the pivot (portable both ways):

```bash
SINCE_ISO=$(date -u -d "@$SINCE_EPOCH" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
         || date -u -r "$SINCE_EPOCH"  +%Y-%m-%dT%H:%M:%SZ)
SINCE_DATE=${SINCE_ISO%%T*}
```

- **git**: pass the absolute instant — `git log --since="$SINCE_ISO"`
  (UTC `…Z`). Git filters on each commit's own absolute timestamp, so
  cross-timezone colleagues are handled correctly. Do **not** pass a
  bare `--since="friday"` to git: git would re-resolve it in the
  machine's local TZ *and* with its own weekday quirks — exactly the
  inconsistency this pivot removes.
- **`gh api` / notifications / MCP**: use full `SINCE_ISO` (exact,
  timestamp-granular).
- **`gh search` / `gh pr list --search`**: `updated:>=$SINCE_DATE`
  only — GitHub search is **UTC, date-granular**. Near a TZ/midnight
  boundary this can be off by up to a day, so treat search hits as a
  coarse pre-filter and confirm precise inclusion with the
  `SINCE_EPOCH`/`SINCE_ISO` timestamp on each item before it enters the
  brief.

## `last-session` auto-detect (default)

Goal: "since I last had a Claude Code session in this project". File
mtimes are already absolute instants — read them straight to epoch, no
TZ handling needed.

1. Derive the per-project session dir:

   ```bash
   SLUG=$(pwd | sed 's@/@-@g')           # /Users/x/Projects/foo -> -Users-x-Projects-foo
   SDIR="$HOME/.claude/projects/$SLUG"
   ```

2. Newest session activity → epoch directly:

   ```bash
   LAST=$(ls -t "$SDIR"/*.jsonl 2>/dev/null | head -1)
   SINCE_EPOCH=$(date -r "$LAST" +%s 2>/dev/null \
              || stat -c %Y "$LAST")        # BSD -r / GNU stat
   ```

   If the newest file's mtime is within ~5 min of now it is the live
   session (empty window) — step to the second-newest. One file only →
   fall back to 24h.

3. No signal → `SINCE_EPOCH=$((NOW - 86400))`, and add to the brief
   Risks block: *"No prior session for this repo — defaulted to 24h."*

4. Optional: if ccrider MCP is present, its last-session-for-cwd
   timestamp can cross-check step 2. Not required.

## Producing `SINCE_LABEL`

```
days = round((NOW - SINCE_EPOCH) / 86400)
SINCE_LABEL = "since {Www Mmm DD} {HH:MM} {LOCAL_TZ} ({days}d)"
```

Sub-day windows use hours: `since 09:12 CEST today (5h)`. Always show
the anchor **in the user's local TZ with the TZ abbrev** — the reader
must see which Friday the brief means. Goes in the brief's **Intent**
line and **Timeline** block.
