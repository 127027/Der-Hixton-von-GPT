from __future__ import annotations

from decimal import Decimal

from scripts.coin_optimization_cycle import (
    aggregate_promotion_gate,
    candidate_catalog,
    choose_training_candidate,
    rank_training_candidates,
)


def test_coin_optimization_catalog_is_bounded_and_contains_current() -> None:
    for symbol in ("BTCUSDC", "ETHUSDC", "ADAUSDC", "DOTUSDC", "LINKUSDC"):
        candidates = candidate_catalog(symbol)
        names = {candidate.name for candidate in candidates}
        assert "current" in names
        assert len(candidates) >= 10
        assert len(candidates) <= 64
        assert len({(candidate.parameters, candidate.policy) for candidate in candidates}) == len(
            candidates
        )


def test_coin_optimization_catalog_contains_fine_neighbourhood() -> None:
    names = {candidate.name for candidate in candidate_catalog("BTCUSDC")}
    assert {"band_plus_01", "band_plus_02", "band_plus_04", "band_plus_05"} <= names
    assert {"vidya7", "vidya9", "momentum18", "momentum22", "atr75", "atr105"} <= names


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


def test_training_rank_freezes_multiple_candidates_before_validation() -> None:
    scores = {
        "current": (Decimal("5"), Decimal("5"), Decimal("10")),
        "a": (Decimal("9"), Decimal("8"), Decimal("12")),
        "b": (Decimal("8"), Decimal("7"), Decimal("9")),
        "c": (Decimal("7"), Decimal("6"), Decimal("8")),
    }
    ranked = rank_training_candidates(scores, limit=3)
    assert ranked == ("a", "b", "c")
    assert choose_training_candidate(scores) == ranked[0]


def test_training_rank_rejects_nonpositive_limit() -> None:
    scores = {"current": (Decimal("1"), Decimal("1"), Decimal("1"))}
    try:
        rank_training_candidates(scores, limit=0)
    except ValueError as error:
        assert "positive" in str(error)
    else:
        raise AssertionError("expected ValueError")


def test_aggregate_promotion_gate_requires_both_models_to_hold() -> None:
    batches = {
        "current_baseline": {"ending_equity": "100"},
        "candidate_baseline": {"ending_equity": "110"},
        "current_stress": {"ending_equity": "90"},
        "candidate_stress": {"ending_equity": "91"},
    }
    portfolios = {
        "current_baseline": {"ending_equity": "50"},
        "candidate_baseline": {"ending_equity": "49"},
        "current_stress": {"ending_equity": "40"},
        "candidate_stress": {"ending_equity": "41"},
    }
    rejected = aggregate_promotion_gate(batches, portfolios)
    assert rejected["promotable"] is False
    assert rejected["checks"]["portfolio_baseline"]["passes"] is False

    portfolios["candidate_baseline"]["ending_equity"] = "51"
    accepted = aggregate_promotion_gate(batches, portfolios)
    assert accepted["promotable"] is True
