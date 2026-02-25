# Plan JSON Sidecar Format

Machine-readable representation of plan state for validation
and recovery in long-running sessions.

## Overview

Every plan.md can have a companion plan.json that mirrors the
task state. This enables:

- **Validation**: Detect plan corruption after context compaction
- **Recovery**: Restore state if plan.md is accidentally modified
- **Tooling**: Machine-parseable plan state for hooks and scripts

## Schema

```json
{
  "version": "1.0.0",
  "source": "plan.md",
  "generated": "2026-02-24T10:30:00Z",
  "tasks": [
    {
      "task_id": "P1-T1",
      "agent": "ecto",
      "status": "pending|in_progress|completed|blocked",
      "description": "Create users migration",
      "implementation_note": "",
      "metadata": {
        "locations": ["lib/my_app/accounts/user.ex"],
        "retry_count": 0
      }
    }
  ]
}
```

## Source of Truth Rules

1. **plan.md is ALWAYS the source of truth** during execution
2. plan.json is a shadow copy for validation
3. Sync is async (doesn't block execution)
4. On mismatch, user chooses: "trust markdown" or "trust JSON"

## Lifecycle

| Event | Action |
|-------|--------|
| Plan created (Write) | `generate-plan-json.sh` creates plan.json |
| Task completed (Edit) | `sync-plan-state.sh` updates plan.json status |
| Plan edited (Edit) | `validate-plan-integrity.sh` checks consistency |
| Resume (`/phx:work`) | Compare plan.md vs plan.json, warn on mismatch |

## Migration

Old plans without plan.json get one auto-generated on first
`/phx:work` run. The generate script parses existing checkboxes
to create an accurate initial JSON state.

## Integrity Checks

The validation hook checks:

- Task ID format: `[Pn-Tm]` where n and m are integers
- No duplicate task IDs
- Checkbox count matches JSON completed count
- Phase status matches task completion state
