"""Role-specific prompt factories for skill description tournament.

Adapted from autoreason's role isolation principle. Each role gets a fresh
context with only what it needs — no shared conversation history.

Domain adaptation: autoreason targets long-form proposals (4000+ words).
We target skill descriptions (10-25 words, 250-char plugin budget target —
CC hard cap is 1,536 as of v2.1.105, but the listing budget is shared across
~40 skills). Prompts are redesigned for routing effectiveness rather than
content quality.
"""


def critic_prompt(
    skill_name: str,
    incumbent: str,
    all_descriptions: dict[str, str],
    trigger_prompts: list[str],
) -> tuple[str, str]:
    """Generate critic system + user prompt.

    The critic finds routing weaknesses — which user prompts would fail
    to route to this skill? Does NOT propose fixes.
    """
    other_skills = "\n".join(
        f"- {name}: {desc}"
        for name, desc in sorted(all_descriptions.items())
        if name != skill_name
    )

    system = (
        "You are a routing accuracy analyst. Your only job is to find problems "
        "with a skill description that cause incorrect routing. Be specific "
        "and concrete. Do NOT suggest fixes or rewrites — only identify weaknesses."
    )

    user = f"""Skill being evaluated: {skill_name}
Current description: "{incumbent}"

These user prompts SHOULD trigger this skill but may not route correctly:
{chr(10).join(f'- "{p}"' for p in trigger_prompts)}

Other skills competing for routing:
{other_skills}

Find routing weaknesses in this description. Focus on:
- Which test prompts would NOT match this description's keywords?
- What's ambiguous — could another skill's description capture these prompts instead?
- What keywords are missing that would help routing?
- Does the description differentiate from similar skills?

Do NOT propose fixes. Just the problems."""

    return system, user


def author_prompt(
    skill_name: str,
    incumbent: str,
    critique: str,
    trigger_prompts: list[str],
) -> tuple[str, str]:
    """Generate author B system + user prompt.

    The author rewrites the description targeting specific critique points.
    """
    system = (
        "You are a skill description writer optimizing for routing accuracy. "
        "Rewrite descriptions to be concise, keyword-rich, and unambiguous. "
        "Address each criticism directly. Do not make changes that aren't "
        "motivated by an identified problem."
    )

    user = f"""Skill: {skill_name}
Current description: "{incumbent}"

User prompts that should trigger this skill:
{chr(10).join(f'- "{p}"' for p in trigger_prompts)}

PROBLEMS FOUND:
---
{critique}
---

Rewrite the description to address these problems. For each change, state
which problem it fixes.

CONSTRAINTS:
- Maximum 250 characters
- Must start with a verb or action phrase
- Include "Use when..." or "Use proactively when..." phrasing
- No vague words (various, general, comprehensive, etc.)

Respond with ONLY the new description text (no quotes, no explanation).
Then on a new line starting with "FIXES:", list which problems each change addresses."""

    return system, user


def synthesizer_prompt(
    skill_name: str,
    version_x: str,
    version_y: str,
    trigger_prompts: list[str],
) -> tuple[str, str]:
    """Generate synthesizer system + user prompt.

    Versions are presented as neutral X/Y — no information about
    which is incumbent or revision.
    """
    system = (
        "You are given two versions of a skill description as equal inputs. "
        "You have no preference between them. Take the strongest routing "
        "elements from each and produce a coherent synthesis. This is not "
        "a compromise — pick the best phrasing per aspect."
    )

    user = f"""Skill: {skill_name}

User prompts that should trigger this skill:
{chr(10).join(f'- "{p}"' for p in trigger_prompts)}

VERSION X: "{version_x}"

VERSION Y: "{version_y}"

Produce a synthesis that keeps the strongest routing elements from both.
Pick the best keyword coverage, the clearest differentiation, the most
accurate trigger phrasing.

CONSTRAINTS:
- Maximum 250 characters
- Must start with a verb or action phrase
- Include "Use when..." or "Use proactively when..." phrasing

Respond with ONLY the synthesized description text (no quotes, no explanation)."""

    return system, user


def judge_prompt(
    skill_name: str,
    proposals_text: str,
    trigger_prompts: list[str],
    all_descriptions: dict[str, str],
) -> tuple[str, str]:
    """Generate judge system + user prompt.

    Judges evaluate routing effectiveness — given user prompts,
    which description would they route to?
    """
    other_skills = "\n".join(
        f"- {name}: {desc}"
        for name, desc in sorted(all_descriptions.items())
        if name != skill_name
    )

    system = (
        "You are an independent routing evaluator. You have no authorship "
        "stake in any version. You have never seen these descriptions before. "
        "Your job is to determine which description would most accurately "
        "route user prompts to this skill."
    )

    user = f"""Skill being evaluated: {skill_name}

User prompts that SHOULD route to this skill:
{chr(10).join(f'- "{p}"' for p in trigger_prompts)}

Other skills competing for routing:
{other_skills}

Three proposed descriptions for {skill_name}:

{proposals_text}

For each proposal, evaluate:
1. How many of the test prompts would be correctly routed to this description?
2. Does the description clearly differentiate from competing skills?
3. Is the description concise and keyword-rich?

Then rank all three from best to worst. Respond with your ranking in this
exact format at the end:

RANKING: [best], [second], [worst]

Where each slot is 1, 2, or 3 corresponding to the proposal numbers above."""

    return system, user
