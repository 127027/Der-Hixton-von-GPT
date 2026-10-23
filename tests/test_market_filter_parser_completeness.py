"""Active market-filter omissions must never certify unlimited capacity."""

from copy import deepcopy
from decimal import InvalidOperation

import pytest

from hixton.domain.market_rules import market_filter_values
from tests.test_market_execution_filters import filter_fixture


@pytest.mark.parametrize("value", ["missing", None])
@pytest.mark.parametrize(
    "kind,field",
    [
        ("MIN_NOTIONAL", "minNotional"),
        ("NOTIONAL", "minNotional"),
        ("NOTIONAL", "maxNotional"),
        ("MIN_NOTIONAL", "avgPriceMins"),
        ("NOTIONAL", "avgPriceMins"),
    ],
)
def test_explicit_active_bounds_and_windows_must_be_complete(kind, field, value):
    raw = filter_fixture()
    if value == "missing":
        del raw[kind][field]
    else:
        raw[kind][field] = value
    with pytest.raises((ValueError, InvalidOperation)):
        market_filter_values(raw)


def test_explicit_disabled_bounds_may_be_absent_without_disabling_other_filters():
    raw = filter_fixture()
    raw["MIN_NOTIONAL"] = {"applyToMarket": False}
    raw["NOTIONAL"] = {"applyMinToMarket": False, "applyMaxToMarket": False}
    result = market_filter_values(raw)
    assert result["market_limits_known"] is True
    assert result["min_notional"] == 0 and result["max_notional"] == 0
    assert result["max_qty"] == 100 and result["market_max_qty"] == 10


def test_legacy_missing_application_flags_are_readable_but_never_known():
    raw = filter_fixture()
    for kind, flags in (
        ("MIN_NOTIONAL", ("applyToMarket",)),
        ("NOTIONAL", ("applyMinToMarket", "applyMaxToMarket")),
    ):
        for flag in flags:
            legacy = deepcopy(raw)
            del legacy[kind][flag]
            assert market_filter_values(legacy)["market_limits_known"] is False


def test_explicit_active_zero_maximum_is_not_an_unlimited_market_order():
    raw = filter_fixture()
    raw["NOTIONAL"]["maxNotional"] = "0"
    with pytest.raises(ValueError, match="maximum"):
        market_filter_values(raw)
