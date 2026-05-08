# Complexity-Based Detail Levels

## Detail Level Configuration

| Detail Level | Phases | Tasks per Phase | Includes |
|--------------|--------|-----------------|----------|
| `minimal` | 2-3 | 2-4 | Basic structure |
| `more` | 3-5 | 3-6 | Code examples, patterns |
| `comprehensive` | 5-8 | 5-10 | Full specs, edge cases |

## Auto-Detect Complexity

When `--detail` is not specified, detect from scope:

| Indicators | Recommended Detail |
|------------|-------------------|
| 1 context, <5 files | `minimal` |
| 2-3 contexts, 5-10 files | `more` |
| 4+ contexts, >10 files | `comprehensive` |

## Input Source Affects Detail

| Input | Typical Detail |
|-------|---------------|
| Review blockers (simple fixes) | `minimal` |
| Brainstorm file (researched feature) | `more` or `comprehensive` |
| Feature description (new feature) | `more` |
| Review blockers (architectural) | `more` |
