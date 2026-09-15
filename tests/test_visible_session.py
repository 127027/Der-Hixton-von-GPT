from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from hixton.runtime.supervisor import RuntimeSupervisor
from hixton.ui.api import create_app
from hixton.ui.instance import bind_local, remove_control, reserve_instance, write_control
from hixton.ui.lifecycle import BrowserLease, VisibleSession
from tests.test_ui_api import _config


def test_browser_start_deadline_and_reload_grace() -> None:
    lease = BrowserLease(now=0)
    assert lease.stop_reason(now=59) is None
    assert lease.stop_reason(now=60)
    lease.join("a")
    assert lease.stop_reason(now=1000) is None  # Background tabs need no JS heartbeat.
    lease.leave("a", now=1000)
    assert lease.stop_reason(now=1004) is None
    lease.join("reloaded")
    assert lease.stop_reason(now=1006) is None
    lease.leave("reloaded", now=1007)
    assert lease.stop_reason(now=1012)


def test_only_last_tab_closure_ends_lease() -> None:
    lease = BrowserLease(now=0)
    lease.join("a")
    lease.join("b")
    lease.leave("a", now=1)
    lease.leave("unknown", now=2)
    assert lease.stop_reason(now=1000) is None
    lease.leave("b", now=1000)
    assert lease.stop_reason(now=1005)


def test_no_trading_before_ui_and_authenticated_replacement(tmp_path, monkeypatch) -> None:
    config = _config(tmp_path)
    supervisor = RuntimeSupervisor(config)
    starts, exits = [], []
    monkeypatch.setattr(supervisor, "start", lambda: starts.append(1))
    session = VisibleSession(
        installation="test",
        token="secret",
        terminal_alive=lambda: True,
        request_exit=lambda: exits.append(1),
    )
    app = create_app(config, supervisor, session=session)
    with TestClient(app, base_url="http://127.0.0.1:8765") as client:
        assert not starts
        info = client.get("/api/session/info").json()
        assert "token" not in info
        assert (
            client.post("/api/session/shutdown", json={"instance": session.instance}).status_code
            == 403
        )
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(
                "ws://127.0.0.1:8765/api/session/presence", headers={"origin": "https://evil.test"}
            ),
        ):
            pass
        assert not starts
        with client.websocket_connect(
            "ws://127.0.0.1:8765/api/session/presence", headers={"origin": "http://127.0.0.1:8765"}
        ) as ws:
            assert ws.receive_json()["instance"] == session.instance
            assert starts == [1]
            assert (
                client.post(
                    "/api/session/shutdown",
                    headers={"X-Hixton-Session": "secret"},
                    json={"instance": "stale"},
                ).status_code
                == 409
            )
            assert not exits
            response = client.post(
                "/api/session/shutdown",
                headers={"X-Hixton-Session": "secret"},
                json={"instance": session.instance},
            )
            assert response.status_code == 200
            assert exits == [1]
            assert supervisor._stop.is_set()


def test_stop_button_and_terminal_watchdog(tmp_path, monkeypatch) -> None:
    config = _config(tmp_path)
    supervisor = RuntimeSupervisor(config)
    monkeypatch.setattr(supervisor, "start", lambda: None)
    exits = []
    session = VisibleSession(
        installation="test",
        token="secret",
        terminal_alive=lambda: True,
        request_exit=lambda: exits.append(1),
    )
    with TestClient(
        create_app(config, supervisor, session=session), base_url="http://127.0.0.1:8765"
    ) as client:
        with client.websocket_connect(
            "ws://127.0.0.1:8765/api/session/presence", headers={"origin": "http://127.0.0.1:8765"}
        ) as ws:
            ws.receive_json()
            ws.send_text("stop")
        assert exits == [1]
    assert session.stopping


def test_missing_terminal_stops_even_with_browser_lease(tmp_path) -> None:
    config = _config(tmp_path)
    exits = []
    session = VisibleSession(
        installation="test",
        token="secret",
        terminal_alive=lambda: False,
        request_exit=lambda: exits.append(1),
    )
    session.lease.join("tab")
    with TestClient(create_app(config, RuntimeSupervisor(config), session=session)):
        pass
    assert exits == [1]


def test_broken_terminal_probe_stops_instead_of_losing_watchdog(tmp_path) -> None:
    def broken():
        raise OSError("probe failure")

    exits = []
    session = VisibleSession(
        installation="test",
        token="secret",
        terminal_alive=broken,
        request_exit=lambda: exits.append(1),
    )
    config = _config(tmp_path)
    with TestClient(create_app(config, RuntimeSupervisor(config), session=session)):
        pass
    assert exits == [1]


def test_control_cleanup_never_deletes_successor(tmp_path: Path) -> None:
    session = VisibleSession(
        installation="test", token="secret", terminal_alive=lambda: True, request_exit=lambda: None
    )
    db = tmp_path / "paper.sqlite3"
    write_control(db, session)
    remove_control(db, "other-instance")
    assert (tmp_path / "runtime-session.json").exists()
    remove_control(db, session.instance)
    assert not (tmp_path / "runtime-session.json").exists()


def test_occupied_unknown_port_is_never_killed(tmp_path: Path) -> None:
    with bind_local(0) as listener:
        port = listener.getsockname()[1]
        with pytest.raises(RuntimeError, match="keine sicher ablösbare"):
            reserve_instance(tmp_path / "paper.sqlite3", port)
