"""LLM call abstraction — wraps `claude -p` subprocess.

Same pattern as lab/eval/trigger_scorer.py for consistency.
Uses stdin for large prompts to avoid shell argument length limits.
Uses --system-prompt for role isolation (no project context bleed).
"""

import subprocess
import sys


def call_llm(
    system: str,
    user: str,
    model: str = "haiku",
    timeout: int = 60,
    max_budget: str = "0.50",
    verbose: bool = False,
) -> str | None:
    """Call Claude via CLI and return response text.

    Each call is context-isolated: --system-prompt overrides project
    context, ensuring fresh agent per role (autoreason's key property).

    Note: `claude -p` does not support a --temperature flag. Temperature
    differentiation is achieved via system prompt tone guidance instead
    (e.g., "Be creative and exploratory" for critic, "Be consistent" for judge).

    Args:
        system: System prompt for role isolation.
        user: User message with task details.
        model: Model name (haiku, sonnet, opus).
        timeout: Subprocess timeout in seconds.
        max_budget: Max USD per call (passed to --max-budget-usd).
        verbose: If True, print debug info to stderr.

    Returns:
        Response text, or None on failure.
    """
    try:
        result = subprocess.run(
            [
                "claude", "-p",
                "--model", model,
                "--output-format", "text",
                "--max-budget-usd", max_budget,
                "--no-session-persistence",
                "--system-prompt", system,
            ],
            input=user,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            if verbose:
                print(f"  LLM error (rc={result.returncode}): {result.stderr[:200]}", file=sys.stderr)
            return None

        return result.stdout.strip()

    except subprocess.TimeoutExpired:
        if verbose:
            print(f"  LLM timeout ({timeout}s)", file=sys.stderr)
        return None
    except FileNotFoundError:
        if verbose:
            print("  claude CLI not found", file=sys.stderr)
        return None
