# Visual Explainer Integration

When a plan's complexity exceeds what terminal-based briefings handle
well, consider generating a visual HTML artifact using the
[visual-explainer](https://github.com/nicobailon/visual-explainer)
skill.

## When to Suggest Visual Output

Suggest visual rendering when ANY of these apply:

- Plan has **5+ phases** with cross-phase dependencies
- Plan has **4+ key decisions** with competing trade-offs
- Plan includes a **System Map** with 3+ pages and wiring
- Post-work briefing shows **mixed completion** (some phases
  blocked, others done) — progress burndown is clearer visually

## What Visual-Explainer Provides

| Cognitive Issue | Terminal Brief | Visual-Explainer |
|----------------|---------------|-----------------|
| Phase sequencing | Flat table | Mermaid flowchart with dependencies |
| Decision trade-offs | Linear text per decision | CSS Grid constraint cards (pros/cons/rejected) |
| Data model connections | Prose description | Entity diagrams with phase annotations |
| Post-work progress | Text table with counts | Chart.js burndown / progress bars |
| System Map wiring | Flat page list | Interactive Mermaid sequence diagram |

## How to Suggest

At the end of Section 3 (Solution Shape / How It Was Built), if
complexity thresholds are met, add:

```
This plan has {N} phases with cross-dependencies.
Want a visual diagram? Try: `/generate-visual-plan`
(requires visual-explainer skill)
```

Keep it as a **suggestion only** — never block the briefing flow.
The terminal briefing remains the primary output; visual rendering
is a complement for complex cases.

## Key Commands from Visual-Explainer

- `/generate-visual-plan` — Render plan as styled HTML with Mermaid
  phase flow diagrams and decision cards
- `/generate-slides` — Magazine-quality slide deck of the briefing
- `/diff-review --slides` — Visual diff analysis (pairs well with
  post-work brief)
- `/project-recap` — Context-switching snapshot (useful when
  resuming work on a plan after time away)

## Installation

```bash
# Via Claude Code
# Clone to ~/.claude/skills/visual-explainer
git clone https://github.com/nicobailon/visual-explainer ~/.claude/skills/visual-explainer
```

See the [visual-explainer README](https://github.com/nicobailon/visual-explainer)
for full setup instructions.
