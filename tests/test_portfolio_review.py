from decimal import Decimal

from hixton.backtest.portfolio_review import policy_catalog, training_choice
from hixton.domain.versions import V6_COIN_STRATEGY


def test_fixed_catalog_preserves_active_strategy():
    before = V6_COIN_STRATEGY.config_payload()
    catalog = policy_catalog()
    assert len(catalog) == 10
    assert catalog["current"] == V6_COIN_STRATEGY.policy_map()
    for policies in catalog.values():
        assert tuple(policies) == V6_COIN_STRATEGY.symbols
    assert catalog["slope24"]["BTCUSDC"].cmo_floor == 0.2
    assert catalog["cmo20"]["ETHUSDC"].slope_bars == 24
    assert V6_COIN_STRATEGY.config_payload() == before


def test_choose_training_worst_window_and_prefer_current_ties():
    assert (
        training_choice(
            {
                "current": (Decimal(2), Decimal(2)),
                "boom_bust": (Decimal(300), Decimal(-10)),
                "steady": (Decimal(4), Decimal(3)),
            }
        )
        == "steady"
    )
    assert (
        training_choice({"current": (Decimal(2), Decimal(2)), "trial": (Decimal(2), Decimal(2))})
        == "current"
    )
