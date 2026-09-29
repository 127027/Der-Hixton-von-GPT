from __future__ import annotations

from decimal import Decimal

from hixton.domain.models import StrategyParameters
from hixton.domain.trade_policy import TradePolicy
from scripts.coin_optimization_cycle import (
    _runner_profile_hashes,
    aggregate_promotion_gate,
    candidate_catalog,
    choose_training_candidate,
    freeze_distinct_training_shortlist,
    rank_training_candidates,
)


def test_coin_optimization_catalog_is_bounded_and_contains_current() -> None:
    for symbol in ("BTCUSDC", "ETHUSDC", "ADAUSDC", "DOTUSDC", "LINKUSDC"):
        candidates = candidate_catalog(symbol)
        names = {candidate.name for candidate in candidates}
        assert "current" in names
        assert len(candidates) >= 10
        assert len(candidates) <= 128
        assert len({(candidate.parameters, candidate.policy) for candidate in candidates}) == len(
            candidates
        )


def test_coin_optimization_catalog_contains_fine_neighbourhood() -> None:
    names = {candidate.name for candidate in candidate_catalog("BTCUSDC")}
    assert {"band_plus_01", "band_plus_02", "band_plus_04", "band_plus_05"} <= names
    assert {"vidya7", "vidya9", "momentum18", "momentum22", "atr75", "atr105"} <= names
    assert {
        "vidya3_band_m0_1",
        "vidya7_band_0_1",
        "momentum18_band_0_2",
        "momentum22_band_0_1",
    } <= names


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


def test_runner_profile_hashes_are_independent_and_sensitive_to_inputs() -> None:
    symbols = ("BTCUSDC", "ETHUSDC")
    parameters = {
        symbol: StrategyParameters(
            vidya_length=5,
            momentum_length=20,
            smoothing_length=8,
            atr_length=120,
            band_multiplier=4.4,
            warmup_bars=400,
        )
        for symbol in symbols
    }
    policies = dict.fromkeys(symbols, TradePolicy())
    first = _runner_profile_hashes(parameters, policies)
    second = _runner_profile_hashes(dict(parameters), dict(policies))
    assert first == second

    changed = dict(parameters)
    changed["ETHUSDC"] = StrategyParameters(
        vidya_length=7,
        momentum_length=20,
        smoothing_length=8,
        atr_length=120,
        band_multiplier=4.4,
        warmup_bars=400,
    )
    third = _runner_profile_hashes(changed, policies)
    assert third["BTCUSDC"] == first["BTCUSDC"]
    assert third["ETHUSDC"] != first["ETHUSDC"]

def test_distinct_training_shortlist_skips_current_equivalent_behaviour() -> None:
    ordered = ("same_as_current", "current", "first", "same_as_first", "second")
    behavior = {
        "current": ("current-behaviour",),
        "same_as_current": ("current-behaviour",),
        "first": ("first-behaviour",),
        "same_as_first": ("first-behaviour",),
        "second": ("second-behaviour",),
    }
    selected, skipped = freeze_distinct_training_shortlist(
        ordered,
        behavior,
        limit=2,
    )
    assert selected == ("first", "second")
    assert skipped == ("same_as_current", "same_as_first")


def test_profit_first_hypothesis_pack_is_bounded_and_present() -> None:
    def has_profile(
        symbol: str,
        *,
        momentum: int | None = None,
        smoothing: int | None = None,
        band: float | None = None,
        cmo: float | None = None,
        slope: int | None = None,
        stop: float | None = None,
        trail: float | None = None,
    ) -> bool:
        for candidate in candidate_catalog(symbol):
            p = candidate.parameters
            policy = candidate.policy
            if momentum is not None and p.momentum_length != momentum:
                continue
            if smoothing is not None and p.smoothing_length != smoothing:
                continue
            if band is not None and p.band_multiplier != band:
                continue
            if cmo is not None and policy.cmo_floor != cmo:
                continue
            if slope is not None and policy.slope_bars != slope:
                continue
            if stop is not None and policy.stop_atr != stop:
                continue
            if trail is not None and policy.trail_atr != trail:
                continue
            return True
        return False

    assert has_profile("ETHUSDC", momentum=18, cmo=0.15, slope=0)
    assert has_profile("ETHUSDC", momentum=18, cmo=0.15, slope=72)
    assert has_profile("BTCUSDC", band=4.2, cmo=0.15)
    assert has_profile("BTCUSDC", band=4.6, cmo=0.25)
    assert has_profile("SOLUSDC", momentum=18, smoothing=12, cmo=0.15)
    assert has_profile("LINKUSDC", momentum=18, cmo=0.15, slope=24)
    assert has_profile("XRPUSDC", momentum=18, cmo=0.10, stop=3.5)
    assert has_profile("AVAXUSDC", band=5.0)
    assert has_profile("AVAXUSDC", band=5.4)
    assert has_profile("DOGEUSDC", momentum=18, band=4.2, cmo=0.15)
    assert has_profile("BNBUSDC", band=4.8)
    assert has_profile("BNBUSDC", stop=2.0)

    for symbol in (
        "BTCUSDC",
        "ETHUSDC",
        "BNBUSDC",
        "SOLUSDC",
        "XRPUSDC",
        "LINKUSDC",
        "AVAXUSDC",
        "DOGEUSDC",
    ):
        catalog = candidate_catalog(symbol)
        assert len(catalog) <= 128
        assert len({(candidate.parameters, candidate.policy) for candidate in catalog}) == len(
            catalog
        )

def test_coin_optimization_catalog_contains_training_led_second_stage_neighbourhoods() -> None:
    expected = {
        "BTCUSDC": {"local_smooth10_band_p20", "local_atr135_band_p03"},
        "ETHUSDC": {"local_smooth7_mom18", "local_slope0_smooth6_mom20"},
        "BNBUSDC": {"local_vidya9_mom18", "local_atr135_mom19"},
        "SOLUSDC": {"local_mom18_smooth12", "local_mom19_smooth13"},
        "XRPUSDC": {"local_mom21", "local_mom22_band_p05"},
        "ADAUSDC": {"local_vidya9_mom14", "local_vidya8_band_m05"},
        "LINKUSDC": {"local_mom21", "local_vidya9_mom22"},
        "AVAXUSDC": {"local_mom21", "local_vidya9_band_p10"},
        "DOTUSDC": {"local_vidya5_band_p15", "local_vidya8_cmo20"},
        "DOGEUSDC": {"local_smooth16_mom16", "local_smooth17_mom15"},
    }
    for symbol, names in expected.items():
        catalog = candidate_catalog(symbol)
        found = {candidate.name for candidate in catalog}
        assert names <= found
        assert len(catalog) <= 128
        assert len({(candidate.parameters, candidate.policy) for candidate in catalog}) == len(
            catalog
        )

