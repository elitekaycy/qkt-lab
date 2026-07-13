"""End-to-end cycle tests with a fake venue, fake store, and fake agent.

This is the phase-1 acceptance, executable: gather -> propose -> gate -> size ->
execute -> record, and every branch lands as a decision row.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest
import yaml

from lab import agent as agent_mod
from lab import cycle
from lab.store import Decision
from tests.conftest import cfg_with


class FakeQkt:
    """A venue with a fixed quote, plausible bars, and a scripted fill."""

    def __init__(self, accept=True):
        self.accept = accept
        self.orders: list[dict] = []

    def account(self, broker=None):
        return {"ok": True, "equity": 10000.0, "currency": "USD"}

    def quote(self, symbol):
        return {"symbol": symbol, "bid": 2609.7, "ask": 2609.9, "spread": 0.2}

    def bars(self, symbol, tf, count=200):
        base = 2600.0
        return [
            {"t": 1752400000000 + i * 3600_000, "o": base + i * 0.1,
             "h": base + i * 0.1 + 2, "l": base + i * 0.1 - 2,
             "c": base + i * 0.1 + 1, "v": 100 + i}
            for i in range(count)
        ]

    def evaluate(self, expr, symbol, tf, count=500):
        return {"ok": True, "value": 4.12, "isReady": True}

    def positions(self, symbol=None):
        return []

    def buy(self, **kw):
        self.orders.append(kw)
        if not self.accept:
            return {"ok": False, "ticket": 0, "deal": 0, "fillPrice": None,
                    "retcode": 10013, "error": "market closed", "symbol": "XAUUSDm"}
        return {"ok": True, "ticket": 88412, "deal": 51199, "fillPrice": 2609.94,
                "retcode": 10009, "error": None, "symbol": "XAUUSDm",
                "qktVersion": "0.48.0"}

    sell = buy


class FakeStore:
    def __init__(self):
        self.decisions: list[Decision] = []

    def record(self, d: Decision) -> int:
        self.decisions.append(d)
        return len(self.decisions)

    def open_tickets(self):
        return []

    def realized_today(self):
        return 0.0


TRADE_JSON = {
    "action": "TRADE", "side": "BUY", "sl": 2606.2, "tp": 2621.4,
    "conviction": 0.6, "setup": "vwap pullback",
    "factors": ["trend:1h-up"], "regime": {"session": "london"},
    "thesis": "structure is the trade", "invalidation": "15m close below 2606",
    "rationale_md": "…", "map_nodes_used": [], "beliefs_used": [],
    "unexplained": None,
}


@pytest.fixture
def wired(cfg, tmp_path, monkeypatch):
    """A cfg with writable state, a fresh calendar, and no charts on disk needed."""
    from lab.config import Calendar

    cache = tmp_path / "upcoming.yaml"
    cache.write_text(yaml.safe_dump({
        "fetched_at": datetime.now(UTC).isoformat(),
        "events": [],
    }))
    c = cfg_with(
        cfg,
        state_dir=tmp_path / "state",
        calendar=Calendar(cache=cache, max_age_hours=30, min_sources=2, fail_closed=True),
    )
    # Charts: render for real (mplfinance) into tmp — proves the pipeline, slow-ish
    # but honest. Keep bar count small via instrument override.
    inst = dataclasses.replace(c.instruments[0], bars=60)
    c = cfg_with(c, instruments=[inst])
    return c


def agent_returns(monkeypatch, payload):
    monkeypatch.setattr(agent_mod, "run", lambda *a, **k: (payload, "sha16"))


def test_trade_end_to_end(wired, monkeypatch):
    agent_returns(monkeypatch, TRADE_JSON)
    qkt, store = FakeQkt(), FakeStore()
    r = cycle.run(wired, qkt, store, wired.instruments[0])

    assert r.action == "TRADE"
    d = store.decisions[-1]
    assert d.accepted and d.ticket == 88412
    # sizing by hand: 10000*0.5% = 50 ; stop = 2609.9-2606.2 = 3.7 ; /100 -> 0.135 -> 0.13
    assert d.lots == pytest.approx(0.13)
    assert qkt.orders[0]["lots"] == pytest.approx(0.13)
    # risk_at_entry from the ACTUAL fill (2609.94), not the quote
    assert d.risk_at_entry == pytest.approx((2609.94 - 2606.2) * 0.13 * 100, rel=1e-6)
    assert d.conviction == 0.6
    assert d.prompt_sha == "sha16"
    assert len(d.charts) == 2  # both timeframes rendered and archived


def test_no_trade_is_recorded_not_skipped(wired, monkeypatch):
    agent_returns(monkeypatch, {"action": "NO_TRADE", "conviction": 0.15,
                                "thesis": "no edge this hour"})
    store = FakeStore()
    r = cycle.run(wired, FakeQkt(), store, wired.instruments[0])
    assert r.action == "NO_TRADE"
    d = store.decisions[-1]
    assert d.action == "NO_TRADE"
    assert d.conviction == 0.15  # calibration needs these rows too


def test_bad_rr_is_gated_and_journaled(wired, monkeypatch):
    agent_returns(monkeypatch, {**TRADE_JSON, "sl": 2606.2, "tp": 2611.0})  # rr ~0.3
    store = FakeStore()
    qkt = FakeQkt()
    r = cycle.run(wired, qkt, store, wired.instruments[0])
    assert r.action == "GATED"
    d = store.decisions[-1]
    assert d.action == "GATED"
    assert any(g["gate"] == "min_rr" for g in d.gate_rejects)
    assert qkt.orders == []  # nothing reached the venue


def test_stale_calendar_gates_the_trade(wired, monkeypatch):
    wired.calendar.cache.write_text(yaml.safe_dump({
        "fetched_at": "2026-07-01T00:00:00Z", "events": [],
    }))
    agent_returns(monkeypatch, TRADE_JSON)
    store, qkt = FakeStore(), FakeQkt()
    r = cycle.run(wired, qkt, store, wired.instruments[0])
    assert r.action == "GATED"
    assert any(g["gate"] == "calendar_unavailable" for g in store.decisions[-1].gate_rejects)
    assert qkt.orders == []


def test_kill_switch_stops_the_order(wired, monkeypatch, tmp_path):
    c = cfg_with(wired, kill_switch=tmp_path / "KILL")
    (tmp_path / "KILL").touch()
    agent_returns(monkeypatch, TRADE_JSON)
    store, qkt = FakeStore(), FakeQkt()
    r = cycle.run(c, qkt, store, c.instruments[0])
    assert r.action == "GATED"
    assert any(g["gate"] == "kill_switch" for g in store.decisions[-1].gate_rejects)
    assert qkt.orders == []


def test_agent_garbage_is_a_journaled_decision(wired, monkeypatch):
    def boom(*a, **k):
        raise agent_mod.AgentError("model output is not valid JSON")

    monkeypatch.setattr(agent_mod, "run", boom)
    store = FakeStore()
    r = cycle.run(wired, FakeQkt(), store, wired.instruments[0])
    assert r.action == "NO_TRADE"
    assert store.decisions[-1].unexplained == "agent_error"


def test_venue_reject_is_recorded_with_the_reason(wired, monkeypatch):
    agent_returns(monkeypatch, TRADE_JSON)
    store = FakeStore()
    r = cycle.run(wired, FakeQkt(accept=False), store, wired.instruments[0])
    assert r.action == "TRADE_REJECTED"
    d = store.decisions[-1]
    assert not d.accepted
    assert "market closed" in (d.rationale_md or "")


def test_arm_assignment_is_deterministic(cfg):
    import copy

    c = cfg_with(cfg, raw={**copy.deepcopy(cfg.raw),
                           "experiment": {"ab_enabled": True,
                                          "arms": ["beliefs", "control"]}})
    t = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)
    a1 = cycle.assign_arm(c, "ICM:XAUUSD", t)
    a2 = cycle.assign_arm(c, "ICM:XAUUSD", t)
    assert a1 == a2  # cannot be re-rolled
    # and with the experiment off, always beliefs
    assert cycle.assign_arm(cfg, "ICM:XAUUSD", t) == "beliefs"
