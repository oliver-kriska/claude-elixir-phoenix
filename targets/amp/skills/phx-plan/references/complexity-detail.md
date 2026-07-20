# Complexity-Based Depth Levels

## Depth Level Configuration

| Depth Level | Phases | Tasks per Phase | Includes |
|--------------|--------|-----------------|----------|
| `quick` | 2-3 | 2-4 | Basic structure |
| `standard` | 3-5 | 3-6 | Code examples, patterns |
| `deep` | 5-8 | 5-10 | Full specs, edge cases |

## Auto-Detect Complexity

When `--depth` is not specified, detect from scope:

| Indicators | Recommended Depth |
|------------|-------------------|
| 1 context, <5 files | `quick` |
| 2-3 contexts, 5-10 files | `standard` |
| 4+ contexts, >10 files | `deep` |

## Input Source Affects Depth

| Input | Typical Depth |
|-------|---------------|
| Review blockers (simple fixes) | `quick` |
| Brainstorm file (researched feature) | `standard` or `deep` |
| Feature description (new feature) | `standard` |
| Review blockers (architectural) | `standard` |
