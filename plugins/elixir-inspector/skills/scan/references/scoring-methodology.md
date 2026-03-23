# Scoring Methodology

How Inspector findings are scored, prioritized, and presented.

## Priority Score Formula

```
priority = severity_score × effort_score × automatable_bonus × confidence_bonus
```

### Severity Score

| Level | Score | Criteria |
|-------|-------|----------|
| critical | 4 | Security risk, data loss, blocks production |
| high | 3 | Recurring team pain, measurable CI/review cost |
| medium | 2 | Code quality, maintainability improvement |
| low | 1 | Nice-to-have, style preference |

### Effort Score (inverse — easier = higher)

| Level | Score | Time Estimate |
|-------|-------|---------------|
| tiny | 4 | < 30 minutes |
| small | 3 | 1-2 hours |
| medium | 2 | Half day |
| large | 1 | 1+ days |

### Automatable Bonus

| Level | Multiplier | Meaning |
|-------|------------|---------|
| yes | 1.5 | Can be fully automated (Credo check, CI step, hook) |
| partial | 1.0 | Needs human review but can be assisted |
| no | 0.5 | Manual only |

### Confidence Bonus

| Level | Multiplier | Criteria |
|-------|------------|----------|
| high | 1.5 | Finding corroborated by 3+ layers |
| medium | 1.0 | Found in 2 layers |
| low | 0.7 | Found in 1 layer only |

### Example Scores

| Finding | Severity | Effort | Auto | Conf | Priority |
|---------|----------|--------|------|------|----------|
| Missing gettext (3 layers) | high(3) | small(3) | yes(1.5) | high(1.5) | **20.25** |
| Repo in web layer (1 layer) | high(3) | tiny(4) | yes(1.5) | low(0.7) | **12.60** |
| Missing @moduledoc (1 layer) | medium(2) | small(3) | yes(1.5) | low(0.7) | **6.30** |
| Inconsistent naming (2 layers) | medium(2) | medium(2) | partial(1.0) | medium(1.0) | **4.00** |

## Deduplication Rules

Findings from different layers about the same pattern get merged:

1. **Title similarity**: 3+ significant words in common (excluding: "the", "a", "in", "for", "and", "or", "to", "is")
2. **Category match**: same category strengthens merge candidate
3. **When merged**:
   - Keep highest severity
   - Keep smallest effort (easiest fix wins)
   - Combine evidence arrays
   - Upgrade confidence: 1 layer = low, 2 = medium, 3+ = high
   - ID becomes: `L1-001+L2-003+L3-007`

## Dashboard Presentation

Findings are presented in a dashboard sorted by priority score:

```markdown
| # | Finding | Severity | Effort | Auto | Layers | Priority |
|---|---------|----------|--------|------|--------|----------|
| 1 | Missing gettext translations | high | small | yes | L1,L2,L3 | 20.25 |
| 2 | Repo calls from web layer | high | tiny | yes | L6 | 12.60 |
```

## Overall Project Score

The "improvement score" indicates how much the project would benefit:

```
improvement_score = sum(priority_scores) / max_possible_score × 100
```

Where `max_possible_score = finding_count × 36` (theoretical max per finding: 4×4×1.5×1.5 = 36).

| Score Range | Assessment |
|-------------|------------|
| 0-20% | Low improvement potential — project is well-maintained |
| 20-40% | Moderate — some automation opportunities |
| 40-60% | High — significant workflow improvements possible |
| 60%+ | Very high — many preventable patterns detected |
