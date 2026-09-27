from __future__ import annotations

import os
import socket
import threading
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import uvicorn

from hixton.config import ProjectConfig
from hixton.live.credentials import BinanceCredentials
from hixton.live.reconciliation import AccountSnapshot
from hixton.paper.storage import PaperStore
from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app

pytestmark = pytest.mark.skipif(
    os.environ.get("HIXTON_BROWSER_E2E") != "1",
    reason="browser E2E is reserved for the A04 UI gate",
)

_KEY = "TESTONLY" * 8
_SECRET = "NOTAREAL" * 8
_PASSWORD = "local-browser-test-password"


class MemoryVault:
    def __init__(self) -> None:
        self.records: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.records.get(name)

    def write(self, name: str, value: str) -> None:
        self.records[name] = value

    def delete(self, name: str) -> None:
        self.records.pop(name, None)


class BrowserSupervisor(RuntimeSupervisor):
    def start(self) -> None:
        self.state.set_status(
            health="HEALTHY",
            message="Browser-E2E: Marktdaten bereit",
            last_sync_utc=datetime.now(UTC),
            last_error=None,
            sync_in_progress=False,
            feed_mode="E2E",
        )

    async def stop(self) -> None:
        return None


class FakeReadOnlyClient:
    def __init__(self, credentials: BinanceCredentials) -> None:
        assert credentials.api_key == _KEY

    def inspect(
        self,
        notional: Decimal,
        *,
        minimum_free_quote: Decimal | None = None,
    ) -> dict[str, object]:
        assert notional in {Decimal("50"), Decimal("250")}
        return {
            "account_checks_passed": True,
            "blockers": [],
            "warnings": [],
            "checked_trade_notional": str(notional),
            "minimum_free_quote": str(minimum_free_quote or notional),
            "free_usdc": "1100.00",
            "free_bnb": "0.03",
        }


def _config(tmp_path: Path, port: int) -> ProjectConfig:
    return ProjectConfig(
        strategy_key="v6",
        database_path=tmp_path / "hixton.sqlite3",
        run_output_root=tmp_path / "backtests" / "v6" / "runs",
        binance_base_url="https://api.binance.com",
        starting_usdc_per_symbol=Decimal("250"),
        target_notional_usdc=Decimal("250"),
        run_baseline_and_stress=True,
        paper_poll_seconds=30,
        paper_starting_cash_usdc=Decimal("250"),
        paper_slot_count=2,
        paper_target_notional_usdc=Decimal("125"),
        paper_max_capital_usdc=Decimal("250"),
        daily_audit_utc="00:05",
        ui_bind="127.0.0.1",
        ui_port=port,
        ui_timezone="Europe/Berlin",
        ui_default_range="1m",
        sha256="browser-e2e",
    )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_real_browser_settings_and_trial_user_flow(tmp_path: Path) -> None:
    from playwright.sync_api import expect, sync_playwright

    port = _free_port()
    config = _config(tmp_path, port)
    supervisor = BrowserSupervisor(config)

    # Reproduce the real UI failure: editable settings exist, while the Paper/soak
    # dashboard is intentionally incomplete. Trading controls must remain usable.
    with PaperStore(config.database_path) as store:
        store.initialize(
            strategy_key="v6",
            strategy_version=supervisor.strategy.version,
            starting_cash_usdc=Decimal("250"),
        )

    app = create_app(config, supervisor, live_vault=MemoryVault())
    service = app.state.live_preparation
    service.client_factory = FakeReadOnlyClient
    service._account_snapshot = lambda: AccountSnapshot(
        service.credentials.load().fingerprint,
        datetime.now(UTC),
        {"USDC": (Decimal("1100"), Decimal("0")), "BNB": (Decimal("0.03"), Decimal("0"))},
        (),
    )

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", lifespan="on")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            page.get_by_role("button", name="Einstellungen").click()

            expect(page.locator("#settings-saved")).to_contain_text("Gespeichert: Max. 250,00 USDC")
            expect(page.locator("#entry-pause-input")).to_be_enabled()
            expect(page.locator("#settings-button")).to_be_enabled()

            page.locator("#entry-pause-input").check()
            page.locator("#settings-button").click()
            expect(page.locator("#settings-saved")).to_contain_text("Gespeichert: Max. 250,00 USDC")

            page.locator("#entry-pause-input").uncheck()
            page.locator("#settings-button").click()
            expect(page.locator("#settings-saved")).to_contain_text("Gespeichert: Max. 250,00 USDC")

            page.locator("#live-password").fill(_PASSWORD)
            page.locator("#live-password-repeat").fill(_PASSWORD)
            page.locator("#live-unlock").click()
            expect(page.locator("#live-auth-result")).to_contain_text("Entsperrt")

            page.locator("#live-api-key").fill(_KEY)
            page.locator("#live-api-secret").fill(_SECRET)
            page.locator("#live-save-key").click()
            expect(page.locator("#live-credentials-status")).to_contain_text(
                "Binance-Zugangsschlüssel lokal gespeichert"
            )

            expect(page.locator("#live-trial-start")).to_be_enabled()
            page.locator("#live-trial-start").click()
            expect(page.locator("#live-trial-status")).to_contain_text("WAITING_SIGNAL")
            expect(page.locator("#live-trial-result")).to_contain_text("Echtgeldtest scharf")

            # Normal 250-USDC live stays locked until the real roundtrip is completed.
            expect(page.locator("#live-request")).to_be_disabled()
            expect(page.locator("#live-blockers")).to_contain_text("1x50-Roundtrip")

            supervisor.state.set_status(
                health="DEGRADED",
                message="Browser-E2E: Warmup/Marktdaten unvollständig",
                last_error="warmup pending",
            )
            page.wait_for_timeout(5500)
            expect(page.locator("#live-trial-status")).to_contain_text(
                "Order-Ausführung derzeit blockiert"
            )
            expect(page.locator("#live-trial-status")).to_contain_text("HEALTHY")
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
