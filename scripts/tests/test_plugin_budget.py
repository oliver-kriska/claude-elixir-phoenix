import pytest

from scripts import plugin_budget

DETAILS = """phx 3.1.1
Projected token cost
  Always-on:   ~5,796 tok   added to every session
"""


def test_parse_always_on_reads_thousands_separator() -> None:
    assert plugin_budget.parse_always_on(DETAILS) == 5796


def test_parse_always_on_rejects_unknown_format() -> None:
    with pytest.raises(ValueError):
        plugin_budget.parse_always_on("Projected token cost\n")


def test_over_budget_uses_the_larger_of_percent_and_floor() -> None:
    assert not plugin_budget.over_budget(6086, 5796, 0.05, 50)
    assert plugin_budget.over_budget(6087, 5796, 0.05, 50)
    assert not plugin_budget.over_budget(114, 64, 0.05, 50)
    assert plugin_budget.over_budget(115, 64, 0.05, 50)
