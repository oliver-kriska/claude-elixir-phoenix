# History Saving

After generating `report.md` and `findings-merged.json`, the scan skill saves
a timestamped copy for future comparison via `/xray:compare`.

## Steps (added to scan Step 5)

After writing `report.md` (and `detailed-report.md` for deep mode):

1. Create the history directory:

   ```bash
   mkdir -p .claude/xray/history/
   ```

2. Copy the merged findings with a date stamp:

   ```bash
   cp .claude/xray/findings-merged.json \
      .claude/xray/history/scan-$(date +%Y-%m-%d).json
   ```

3. If a scan already exists for today's date, overwrite it (latest scan wins).

## Directory Layout

```
.claude/xray/history/
├── scan-2026-03-01.json
├── scan-2026-03-15.json
└── scan-2026-03-21.json    # Most recent
```

## Notes

- History files are plain copies of `findings-merged.json` — same schema
- `/xray:compare` reads these files by glob-sorting on filename date
- Keep history files in `.gitignore` (they contain project-specific analysis)
- Gate mode (`--gate measure`) writes to `baseline.json`, NOT to history
  (baselines serve a different purpose: CI pass/fail thresholds)
