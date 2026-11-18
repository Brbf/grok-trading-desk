from pathlib import Path
from types import SimpleNamespace

import pytest

from scanner.feeds.mt5 import MT5ReadOnlyFeed
from scanner.guards import LiveOrderRefused, install_order_guard
from scanner.paper import PaperBroker
from scanner.config import load_config


class FakeMT5:
    def __init__(self, mode: int, server: str):
        self.mode = mode
        self.server = server
        self.orders = []
        self.logins = []
        self.shutdown_called = False
        self.init_kwargs = None
        self.TIMEFRAME_H1 = 16385

    def initialize(self, **kwargs):
        self.init_kwargs = kwargs
        return True

    def shutdown(self):
        self.shutdown_called = True

    def last_error(self):
        return (1, "ok")

    def account_info(self):
        return SimpleNamespace(trade_mode=self.mode, server=self.server, login=123, currency="EUR")

    def order_send(self, request):
        self.orders.append(request)
        return "sent"

    def login(self, *args, **kwargs):
        self.logins.append((args, kwargs))
        return True


def test_demo_connect_disables_order_send_and_login():
    fake = FakeMT5(0, "MetaQuotes-Demo")
    feed = MT5ReadOnlyFeed()
    account = feed.connect(module=fake, terminal_path=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    assert account["trade_mode"] == "demo"
    assert fake.init_kwargs == {"path": r"C:\Program Files\MetaTrader 5\terminal64.exe"}
    assert "login" not in fake.init_kwargs
    with pytest.raises(LiveOrderRefused):
        fake.order_send({"action": "deal"})
    with pytest.raises(LiveOrderRefused):
        fake.login(1, "secret", "Live-Server")
    with pytest.raises(LiveOrderRefused):
        feed.order_send({"action": "deal"})
    assert fake.orders == []
    assert fake.logins == []
    assert fake.shutdown_called is False


def test_real_account_is_refused_and_shut_down():
    fake = FakeMT5(2, "ICMarkets-Live")
    feed = MT5ReadOnlyFeed()
    with pytest.raises(LiveOrderRefused):
        feed.connect(module=fake)
    assert fake.shutdown_called is True
    assert fake.orders == []


def test_demo_mode_on_a_non_demo_server_is_refused():
    fake = FakeMT5(0, "Broker-Live")
    feed = MT5ReadOnlyFeed()
    with pytest.raises(LiveOrderRefused):
        feed.connect(module=fake)
    assert fake.shutdown_called is True


def test_paper_broker_refuses_order_send():
    cfg = load_config()
    broker = PaperBroker(cfg["risk"], cfg["costs"], cfg["strategy"])
    with pytest.raises(LiveOrderRefused):
        broker.order_send({"action": "deal"})


def test_guard_replaces_existing_callable():
    module = SimpleNamespace(order_send=lambda *_a, **_k: "sent", login=lambda: "in")
    install_order_guard(module)
    with pytest.raises(LiveOrderRefused):
        module.order_send({})
    with pytest.raises(LiveOrderRefused):
        module.login()


def test_sources_do_not_call_order_send():
    root = Path(__file__).resolve().parents[1]
    for path in list((root / "scanner").rglob("*.py")) + list((root / "agents").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ".order_send(" not in text, path.name
        assert "TRADE_ACTION" not in text, path.name
