"""The join is the load-bearing piece: get it wrong and every belief is scored
against corrupt data. These tests encode the failure modes that would be silent.
"""

from __future__ import annotations

import pytest

from lab.join import aggregate, r_multiple


def deal(ticket, entry, lots, price, profit=0.0, commission=0.0, swap=0.0, t=0):
    return {
        "dealTicket": 50000 + t,
        "positionTicket": ticket,
        "symbol": "XAUUSDm",
        "side": "BUY",
        "entry": entry,
        "lots": lots,
        "price": price,
        "profit": profit,
        "commission": commission,
        "swap": swap,
        "fee": 0.0,
        "timeMs": 1752480000000 + t * 1000,
        "comment": None,
    }


def test_commission_on_the_in_deal_is_counted():
    """MT5 books commission on the IN deal. Summing only OUT rows under-counts
    cost and makes every trade look more profitable than it was — forever."""
    deals = [
        deal(88412, "IN", 0.13, 2609.94, commission=-0.91, t=0),
        deal(88412, "OUT", 0.13, 2621.40, profit=148.98, swap=-0.22, t=22229),
    ]
    got = aggregate(88412, deals)
    assert got is not None
    assert got.gross_pnl == pytest.approx(148.98)
    assert got.commission == pytest.approx(-0.91)  # NOT 0.0
    assert got.swap == pytest.approx(-0.22)
    assert got.net_pnl == pytest.approx(147.85)


def test_partial_closes_are_aggregated_not_take_first():
    """A partial close produces several OUT deals sharing one positionTicket."""
    deals = [
        deal(9001, "IN", 0.20, 2600.0, commission=-1.40, t=0),
        deal(9001, "OUT", 0.10, 2610.0, profit=100.0, t=100),
        deal(9001, "OUT", 0.10, 2620.0, profit=200.0, swap=-0.50, t=200),
    ]
    got = aggregate(9001, deals)
    assert got is not None
    assert got.gross_pnl == pytest.approx(300.0)
    assert got.net_pnl == pytest.approx(300.0 - 1.40 - 0.50)
    assert got.lots_closed == pytest.approx(0.20)
    # Volume-weighted close, not a naive mean (here both legs are equal so it is
    # the midpoint — but the weighting is what matters when they are not).
    assert got.close_price == pytest.approx(2615.0)


def test_volume_weighted_close_price_with_uneven_partials():
    deals = [
        deal(9002, "IN", 0.30, 2600.0, t=0),
        deal(9002, "OUT", 0.20, 2610.0, profit=200.0, t=10),
        deal(9002, "OUT", 0.10, 2640.0, profit=400.0, t=20),
    ]
    got = aggregate(9002, deals)
    assert got is not None
    # (2610*0.2 + 2640*0.1) / 0.3 = 2620.0 — a naive mean would say 2625.0
    assert got.close_price == pytest.approx(2620.0)


def test_out_by_and_inout_count_as_exits():
    """qkt collapses MT5's INOUT/OUT_BY into 'OUT'. Any non-IN row is an exit."""
    deals = [
        deal(9003, "IN", 0.10, 2600.0, t=0),
        deal(9003, "OUT", 0.10, 2590.0, profit=-100.0, t=50),
    ]
    got = aggregate(9003, deals)
    assert got is not None
    assert got.net_pnl == pytest.approx(-100.0)


def test_still_open_returns_none():
    """No OUT deal yet — the position is open. Must not fabricate an outcome."""
    deals = [deal(9004, "IN", 0.10, 2600.0, commission=-0.70, t=0)]
    assert aggregate(9004, deals) is None


def test_other_tickets_are_ignored():
    """History returns every deal on the account, including other strategies'."""
    deals = [
        deal(7777, "IN", 5.00, 100.0, t=0),
        deal(7777, "OUT", 5.00, 90.0, profit=-5000.0, t=1),
        deal(9005, "IN", 0.10, 2600.0, t=2),
        deal(9005, "OUT", 0.10, 2610.0, profit=100.0, t=3),
    ]
    got = aggregate(9005, deals)
    assert got is not None
    assert got.net_pnl == pytest.approx(100.0)  # NOT -4900


def test_duration_spans_first_in_to_last_out():
    deals = [
        deal(9006, "IN", 0.10, 2600.0, t=0),
        deal(9006, "OUT", 0.05, 2610.0, profit=50.0, t=100),
        deal(9006, "OUT", 0.05, 2620.0, profit=100.0, t=250),
    ]
    got = aggregate(9006, deals)
    assert got is not None
    assert got.duration_s == 250


def test_r_multiple():
    assert r_multiple(147.85, 48.62) == pytest.approx(3.041, rel=1e-3)
    assert r_multiple(-48.62, 48.62) == pytest.approx(-1.0)


def test_r_multiple_without_risk_is_none_not_zero():
    """A missing denominator must not silently become 0R — that would drag every
    belief's mean_R toward zero and look like 'no edge'."""
    assert r_multiple(100.0, None) is None
    assert r_multiple(100.0, 0.0) is None
