from __future__ import annotations

from decimal import Decimal

from scripts.coin_optimization_cycle import candidate_catalog, choose_training_candidate


def test_coin_optimization_catalog_is_bounded_and_contains_current() -> None:
    for symbol in ("BTCUSDC", "ETHUSDC", "ADAUSDC", "DOTUSDC", "LINKUSDC"):
        candidates = candidate_catalog(symbol)
        names = {candidate.name for candidate in candidates}
        assert "current" in names
        assert len(candidates) >= 10
        assert len(candidates) <= 24
        assert len({(candidate.parameters, candidate.policy) for candidate in candidates}) == len(
            candidates
        )


def test_training_choice_prefers_current_on_exact_tie() -> None:
    scores = {
        "current": (Decimal("10"), Decimal("5"), Decimal("20")),
        "other": (Decimal("10"), Decimal("5"), Decimal("20")),
    }
    assert choose_training_candidate(scores) == "current"


def test_training_choice_maximizes_worst_training_window_before_sum() -> None:
    scores = {
        "current": (Decimal("20"), Decimal("-10"), Decimal("15")),
        "balanced": (Decimal("6"), Decimal("7"), Decimal("18")),
        "high_sum_bad_worst": (Decimal("30"), Decimal("-9"), Decimal("10")),
    }
    assert choose_training_candidate(scores) == "balanced"
