"""Store integration against a real Postgres.

Run with a live DB (docker: postgres:16, user/pass/db = lab) and
LAB_TEST_DSN set; skipped otherwise so the unit suite stays hermetic.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lab.store import Decision, Store

DSN = os.environ.get("LAB_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="LAB_TEST_DSN not set")

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store():
    s = Store(DSN)
    s.migrate(ROOT / "db" / "schema.sql")
    with s._conn() as c:
        c.execute("TRUNCATE outcome, decision RESTART IDENTITY CASCADE")
        c.commit()
    return s


def trade_decision(ticket=88412):
    return Decision(
        as_name="lab-xau", symbol="ICM:XAUUSD", action="TRADE", side="BUY",
        lots=0.13, sl=2606.2, tp=2621.4, conviction=0.6,
        setup="vwap pullback", factors=["trend:1h-up", "level:vwap-touch"],
        regime={"session": "london", "atr14": 4.12},
        thesis="t", rationale_md="r", charts=["state/charts/x.png"],
        ticket=ticket, fill_price=2609.94, accepted=True,
        risk_at_entry=48.62, equity_at_entry=10000.0,
    )


def test_full_round_trip(store):
    did = store.record(trade_decision())
    assert did == 1

    assert len(store.open_tickets()) == 1

    store.record_outcome(
        ticket=88412, closed_at=datetime.now(UTC), close_price=2621.4,
        gross_pnl=148.98, commission=-0.91, swap=-0.22, net_pnl=147.85,
        r_multiple=3.04, lots_closed=0.13, duration_s=22229,
        deals=[{"dealTicket": 51199}],
    )
    assert store.open_tickets() == []  # joined -> no longer open

    # Idempotent: the joiner running twice must be a no-op, not a crash or a dupe.
    store.record_outcome(
        ticket=88412, closed_at=datetime.now(UTC), close_price=2621.4,
        gross_pnl=148.98, commission=-0.91, swap=-0.22, net_pnl=147.85,
        r_multiple=3.04, lots_closed=0.13, duration_s=22229, deals=[],
    )
    rows = store.query("SELECT count(*) AS n FROM outcome")
    assert rows[0]["n"] == 1

    # The episode view joins decision to outcome — this is what beliefs score on.
    ep = store.query("SELECT * FROM episode")
    assert len(ep) == 1
    assert float(ep[0]["r_multiple"]) == pytest.approx(3.04)
    assert ep[0]["factors"] == ["trend:1h-up", "level:vwap-touch"]


def test_jsonb_predicates_work(store):
    """The whole reason the store is typed: belief predicates are SQL."""
    store.record(trade_decision(ticket=1001))
    store.record_outcome(
        ticket=1001, closed_at=datetime.now(UTC), close_price=2620.0,
        gross_pnl=100.0, commission=-1.0, swap=0.0, net_pnl=99.0,
        r_multiple=2.0, lots_closed=0.13, duration_s=100, deals=[],
    )
    rows = store.query(
        """
        SELECT ticket FROM episode
        WHERE regime->>'session' = %s
          AND (regime->>'atr14')::numeric BETWEEN 3 AND 5
          AND factors ? %s
        """,
        ("london", "level:vwap-touch"),
    )
    assert [r["ticket"] for r in rows] == [1001]


def test_no_trade_and_gated_rows_are_first_class(store):
    store.record(Decision(as_name="lab-xau", symbol="ICM:XAUUSD",
                          action="NO_TRADE", conviction=0.1))
    store.record(Decision(as_name="lab-xau", symbol="ICM:XAUUSD", action="GATED",
                          conviction=0.8,
                          gate_rejects=[{"gate": "min_rr", "detail": "0.5 < 1.5"}]))
    rows = store.query("SELECT action, count(*) AS n FROM decision GROUP BY action")
    got = {r["action"]: r["n"] for r in rows}
    assert got == {"NO_TRADE": 1, "GATED": 1}

    assert store.realized_today() == 0.0
