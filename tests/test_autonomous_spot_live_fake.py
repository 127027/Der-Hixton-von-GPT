"""Key-free fake-exchange proof: real-money path never budgets more than fresh USDC."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from pathlib import Path

from hixton.backtest.models import ExecutionRules
from hixton.domain.versions import V6_COIN_STRATEGY as V6
from hixton.live.production import (
    LiveBalanceReconciler, LiveOrderExecutor, LiveOrderJournal,
    LivePortfolioController,
)
from tests.test_live_production import Account, ApplyingExchange, universe

NOW = datetime.now(UTC).replace(second=0, microsecond=0)


def _case(tmp_path: Path, initial_usdc: str):
    db=tmp_path/"fake.sqlite3"
    account=Account()
    account.balances["USDC"]=(D(initial_usdc), D("0"))
    exchange=ApplyingExchange(account)
    journal=LiveOrderJournal(db)
    reconciler=LiveBalanceReconciler(journal)
    holder={}
    executor=LiveOrderExecutor(journal,exchange,lambda intent: holder["bot"].pre_submit(intent))
    points_holder={"points": universe(NOW-timedelta(hours=1))}
    rules={symbol:ExecutionRules(step_size=D("0.000001"),min_qty=D("0.000001"),min_notional=D("5")) for symbol in V6.symbols}
    bot=LivePortfolioController(
        db,journal,executor,reconciler,account.snapshot,
        lambda:(D("250"),False),lambda:rules,V6,lambda:True,
        autonomous_spot=lambda:True,
        market_points=lambda:points_holder["points"],
        execution_source_sha256="autonomy-test-sha",
    )
    holder["bot"]=bot
    snap=account.snapshot()
    bot.enable(snap.account,points_holder["points"],snap,now=snap.observed_at)
    return bot,account,exchange,points_holder


def test_autonomous_live_uses_all_1100_even_if_saved_plan_is_250(tmp_path: Path):
    bot,account,exchange,holder=_case(tmp_path,"1100")
    p=universe(NOW,enter=("BTCUSDC",))
    holder["points"]=p
    for _ in range(4):
        bot.advance(p,now=NOW,healthy=True)
    assert len(exchange.submits)==1
    assert exchange.submits[0].quote_budget==D("1100.00")
    assert exchange.submits[0].side=="BUY"
    assert account.balances["USDC"][0]==D("0")
    assert bot.report()["state"]=="LIVE_ENABLED"


def test_manual_balance_change_never_silently_spent(tmp_path: Path):
    bot,account,exchange,holder=_case(tmp_path,"1100")
    account.balances["USDC"]=(D("1400"),D("0")) # external deposit is unverified
    p=universe(NOW,enter=("BTCUSDC",))
    holder["points"]=p
    for _ in range(3):
        bot.advance(p,now=NOW,healthy=True)
    assert not exchange.submits
    assert bot.report()["state"]!="LIVE_ENABLED"


def test_autonomous_order_revalidated_on_new_snapshot_before_submit(tmp_path: Path):
    bot,account,exchange,holder=_case(tmp_path,"1100")
    p=universe(NOW,enter=("BTCUSDC",))
    holder["points"]=p
    bot.advance(p,now=NOW,healthy=True) # persistent pending, not submitted
    assert not exchange.submits
    # A manual balance change between signal and order *must* block execution.
    account.balances["USDC"]=(D("1000"),D("0"))
    bot.advance(p,now=NOW,healthy=True)
    assert not exchange.submits
