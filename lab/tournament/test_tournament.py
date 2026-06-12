"""Tests for tournament core: Borda scoring, parsing, convergence."""

from lab.tournament.tournament import (
    TournamentState,
    aggregate_borda,
    check_convergence,
    parse_ranking,
    randomize_for_judge,
)


class TestRandomizeForJudge:
    def test_returns_all_versions(self):
        versions = {"A": "text a", "B": "text b", "AB": "text ab"}
        text, order_map = randomize_for_judge(versions)

        assert len(order_map) == 3
        assert set(order_map.values()) == {"A", "B", "AB"}
        assert "PROPOSAL 1:" in text
        assert "PROPOSAL 2:" in text
        assert "PROPOSAL 3:" in text

    def test_contains_all_content(self):
        versions = {"A": "alpha content", "B": "beta content", "AB": "merged content"}
        text, _ = randomize_for_judge(versions)

        assert "alpha content" in text
        assert "beta content" in text
        assert "merged content" in text

    def test_independent_randomization(self):
        """Multiple calls should produce different orderings (probabilistic)."""
        versions = {"A": "a", "B": "b", "AB": "ab"}
        orderings = set()
        for _ in range(20):
            _, order_map = randomize_for_judge(versions)
            orderings.add(tuple(order_map.values()))
        # With 3! = 6 permutations, 20 trials should hit at least 2
        assert len(orderings) >= 2

    def test_two_versions(self):
        versions = {"A": "text a", "B": "text b"}
        text, order_map = randomize_for_judge(versions)

        assert len(order_map) == 2
        assert set(order_map.values()) == {"A", "B"}


class TestParseRanking:
    def test_standard_format(self):
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "Some analysis...\n\nRANKING: 2, 1, 3"
        result = parse_ranking(text, order_map)
        assert result == ["B", "A", "AB"]

    def test_bottom_up_scan(self):
        """Should find the last RANKING line, not the first."""
        order_map = {"1": "AB", "2": "A", "3": "B"}
        text = "RANKING: 1, 2, 3\nMore text\nRANKING: 3, 1, 2"
        result = parse_ranking(text, order_map)
        assert result == ["B", "AB", "A"]

    def test_with_markdown_bold(self):
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "Analysis...\n**RANKING: 1, 3, 2**"
        result = parse_ranking(text, order_map)
        assert result == ["A", "AB", "B"]

    def test_with_heading_prefix(self):
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "Analysis...\n### RANKING: 2, 1, 3"
        result = parse_ranking(text, order_map)
        assert result == ["B", "A", "AB"]

    def test_no_ranking_line(self):
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "I think proposal 2 is best, followed by 1 and 3."
        result = parse_ranking(text, order_map)
        assert result is None

    def test_partial_ranking(self):
        """Two digits should still parse (minimum viable ranking)."""
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "RANKING: 2, 1"
        result = parse_ranking(text, order_map)
        assert result == ["B", "A"]

    def test_no_spaces(self):
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "RANKING: 312"
        result = parse_ranking(text, order_map)
        assert result == ["AB", "A", "B"]

    def test_brackets_format(self):
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "RANKING: [2], [3], [1]"
        result = parse_ranking(text, order_map)
        assert result == ["B", "AB", "A"]

    def test_lowercase_ranking(self):
        order_map = {"1": "A", "2": "B", "3": "AB"}
        text = "ranking: 1, 2, 3"
        result = parse_ranking(text, order_map)
        assert result == ["A", "B", "AB"]


class TestAggregateBorda:
    def test_unanimous_winner(self):
        """All judges agree: B is best."""
        rankings = [["B", "A", "AB"], ["B", "A", "AB"], ["B", "A", "AB"]]
        winner, scores, valid = aggregate_borda(rankings)

        assert winner == "B"
        assert scores["B"] == 9  # 3 judges × 3 pts
        assert scores["A"] == 6  # 3 judges × 2 pts
        assert scores["AB"] == 3  # 3 judges × 1 pt

    def test_tiebreak_favors_incumbent(self):
        """When A and B tie, A (incumbent) wins."""
        rankings = [["A", "B", "AB"], ["B", "A", "AB"]]
        winner, scores, _ = aggregate_borda(rankings)

        assert scores["A"] == scores["B"]  # Both get 5 pts
        assert winner == "A"  # Incumbent wins tie

    def test_three_way_tie(self):
        """Each wins once in first, second, third — all tie at 6."""
        rankings = [["A", "B", "AB"], ["B", "AB", "A"], ["AB", "A", "B"]]
        winner, scores, _ = aggregate_borda(rankings)

        assert scores["A"] == 6
        assert scores["B"] == 6
        assert scores["AB"] == 6
        assert winner == "A"  # Incumbent wins

    def test_none_rankings_filtered(self):
        """None entries (failed parses) are excluded."""
        rankings = [None, ["B", "A", "AB"], None, ["B", "AB", "A"]]
        winner, scores, valid = aggregate_borda(rankings)

        assert winner == "B"
        assert len(valid) == 2

    def test_all_none(self):
        """All rankings failed — tiebreak winner takes it."""
        rankings = [None, None, None]
        winner, scores, valid = aggregate_borda(rankings)

        assert winner == "A"
        assert len(valid) == 0

    def test_custom_tiebreak(self):
        """Custom tiebreak winner."""
        rankings = [["A", "B", "AB"], ["B", "A", "AB"]]
        winner, _, _ = aggregate_borda(rankings, tiebreak_winner="B")

        assert winner == "B"  # B wins tie instead of A

    def test_two_candidate_borda(self):
        """Works with 2 candidates (2 pts for 1st, 1 for 2nd)."""
        rankings = [["A", "B"], ["B", "A"], ["B", "A"]]
        winner, scores, _ = aggregate_borda(rankings)

        assert winner == "B"
        assert scores["B"] == 5  # 1×1 + 2×2
        assert scores["A"] == 4  # 1×2 + 2×1


class TestConvergence:
    def test_not_converged_initially(self):
        state = TournamentState(incumbent="test", consecutive_a_wins=0)
        assert not check_convergence(state)

    def test_converged_at_k2(self):
        state = TournamentState(incumbent="test", consecutive_a_wins=2)
        assert check_convergence(state, k=2)

    def test_not_converged_at_1(self):
        state = TournamentState(incumbent="test", consecutive_a_wins=1)
        assert not check_convergence(state, k=2)

    def test_custom_k(self):
        state = TournamentState(incumbent="test", consecutive_a_wins=3)
        assert not check_convergence(state, k=4)
        assert check_convergence(state, k=3)

    def test_state_history(self):
        state = TournamentState(incumbent="v1")
        state.pass_number = 5
        state.consecutive_a_wins = 2
        state.history.append({"pass": 4, "winner": "AB"})
        state.history.append({"pass": 5, "winner": "A"})

        assert state.pass_number == 5
        assert len(state.history) == 2
