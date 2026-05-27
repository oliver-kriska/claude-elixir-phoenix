# Proven Post Templates

Reference patterns extracted from 7 promotional posts (Feb-Apr 2026).
Analytics: 144 likes / 9.9K views at peak, 153 bookmarks on announcement.

## ASCII Card Template

Use Unicode box-drawing characters for a polished look. Every line must be **exactly
72 visual characters wide**. After writing, verify alignment with a Python script
(see Verification section below).

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Elixir/Phoenix Plugin vX.Y.Z — Short Title                         │
│  N files changed | +N lines | N skills | N agents                   │
│                                                                      │
╞═══════════════════════════════════╤══════════╤═══════════════════════╡
│  Change                           │  Before  │  After                │
╞═══════════════════════════════════╪══════════╪═══════════════════════╡
│  Row 1 description                │  val     │  val                  │
│  Row 2 description                │  val     │  val                  │
│  Row 3 description                │  val     │  val                  │
│  Row 4 description                │  val     │  val                  │
╞═══════════════════════════════════╧══════════╧═══════════════════════╡
│                                                                      │
│  Additional context line if needed                                   │
│                                                                      │
│  github.com/oliver-kriska/claude-elixir-phoenix                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Column widths

The table area between `╞` borders has 3 columns:
- Col 1 (Change): 35 chars
- Col 2 (Before): 10 chars
- Col 3 (After): 23 chars

### Verification

After writing the table, run this to verify all lines are 72 chars:

```python
import unicodedata
def vw(s):
    return sum(2 if unicodedata.east_asian_width(c) in ('F','W') else 1 for c in s)
lines = open('scratchpad/x-posts/{version}-table.txt').read().strip().split('\n')
target = vw(lines[0])
for i, line in enumerate(lines):
    w = vw(line)
    if w != target:
        print(f"L{i+1}: {w} chars (expected {target}): {line}")
```

If any line is off, add or remove spaces before the closing `│`.

### Alternatives

For releases without before/after data (new features only):

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  Elixir/Phoenix Plugin vX.Y.Z — Title                               │
│  N files changed | +N lines                                         │
│                                                                      │
│  What's new:                                                         │
│  · Feature 1 description                                             │
│  · Feature 2 description                                             │
│  · Feature 3 description                                             │
│                                                                      │
│  github.com/oliver-kriska/claude-elixir-phoenix                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Tweet Thread Patterns

### Pattern A: Changelog Audit (v2.7.0 — 4 tweets, 670 views early)

**Tweet 1**: Version + what prompted the release ("Claude Code shipped 46 releases since we last checked"). Headline stats. Repo link.

**Tweet 2**: Numbered list of what was found/fixed. Before/after where possible.

**Tweet 3**: Secondary feature with depth (Oban Pro rewrite, from real incident).

**Tweet 4**: CTA + release link. "If you're building Elixir/Phoenix with Claude Code, try it."

### Pattern B: Source-Informed (v2.6.1 — 3 tweets, 1.4K views)

**Tweet 1**: What triggered the work ("I asked Claude to go through TypeScript source"). Headline stats. Repo link.

**Tweet 2**: Numbered findings — each with concrete numbers. "80% of descriptions silently truncated" > "many descriptions were too long."

**Tweet 3**: Smaller changes as bullet list + eval scores + CTA.

### Pattern C: Metrics-Driven (v2.4.0 — standalone, 3.8K views)

**Single tweet**: Version + headline. Before/after metrics as formatted list. Brief explanation of changes. File stats. Repo link.

Best for releases with strong quantitative improvements. No thread needed.

### Pattern D: Deep-Dive (reply thread — 9.9K views, highest)

Reply to a relevant conversation in the Claude Code space. Share your experience and data. This gets the highest views because it piggybacks on existing engagement.

Best used opportunistically, not for every release.

### Pattern E: Long-Form (v2.6.0 — 150 likes, best overall)

**7-9 tweets** covering a major milestone. Data-heavy throughout. Works when the content is genuinely excellent (self-improving skills, 0/8 → 8/8 eval scores). Risk: longer threads lose casual readers. Only use for truly big releases.

## Top-Performing Elements (from analytics)

| Element | Impact | Example |
|---------|--------|---------|
| Before/after metrics | Highest engagement | "340K → 120K tokens (-65%)" |
| Concrete numbers | High trust signal | "32/40 descriptions rewritten under 200 chars" |
| Real incident stories | High bookmarks | "72k+ orphaned jobs before someone caught it" |
| Transparent methodology | Builds authority | "Validated across 75 real sessions" |
| Eval scores | Credibility closer | "All 40 skills pass eval (avg 0.988)" |

## Anti-Patterns (from analytics)

| What | Why it hurts |
|------|-------------|
| Back-to-back releases | v2.6.1 got 37 likes vs v2.6.0's 150 — diluted signal |
| Threads >6 tweets | Casual readers drop after 4-6 |
| Missing hashtags | Recent posts without #ElixirLang got lower discoverability |
| API cost mentions | User uses subscription — per-call costs are irrelevant |
| Hype language | "Game-changer" / fire emojis erode dev trust |
| Vague claims | "Improved performance" < "340K → 120K tokens (-65%)" |

## CodeSnap Rendering

**ALWAYS render via the config file, never inline color flags.**
Current `codesnap` ignores a single-color `--background` when a theme
gradient is set ("candy" theme → bright green gradient). The config's
structured `background.stops` is the only reliable override. This is
the canonical command (matches every prior correct card, e.g. v280):

```bash
codesnap \
  -f scratchpad/x-posts/{version}-table.txt \
  -o scratchpad/x-posts/{version}-card.png \
  --config scratchpad/x-posts/codesnap-claude-dark.json \
  --title "claude-elixir-phoenix {version}" \
  -l text
```

`codesnap-claude-dark.json` (committed in `scratchpad/x-posts/`) sets
the dark gradient (`#0f1115` → `#1a1f2b`), mac window bar, border,
JetBrains Mono, and an **empty watermark**. Default for all
releases. Always `Read` the output PNG to confirm: dark background,
no green, no watermark, table aligned.

> **Do NOT** use the old inline-flag form
> (`--background "#0f1115" --watermark … --shadow-radius …`). It
> rendered correctly in April but the current codesnap leaves the
> green "candy" gradient and adds an unwanted watermark. For a
> celebratory accent variant, copy the config to a `*-accent.json`
> and change `background.stops` + `title_config.color` there — keep
> it config-driven.
