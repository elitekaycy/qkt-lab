"""Gates are the only thing between the model and the account. Every one of these
tests is a way someone gets hurt if the gate is wrong.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lab.gates import Book, check
from tests.conftest import cfg_with

NOW = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)
FLAT = Book(
    open_positions=0, open_lots=0.0, open_risk_currency=0.0, realized_today=0.0, floating=0.0
)


def proposal(**kw):
    base = dict(side="BUY", entry_price=2609.9, sl=2606.2, tp=2621.4, expected_rr=3.1)
    base.update(kw)
    return base


def gates_of(r):
    return {x.gate for x in r}


def test_clean_proposal_passes(cfg):
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=FLAT, lots=0.13, events=[], now=NOW
    )
    assert r == []


def test_no_stop_loss_is_refused(cfg):
    r = check(
        cfg,
        cfg.instruments[0],
        proposal(sl=None),
        equity=10000,
        book=FLAT,
        lots=0.13,
        events=[],
        now=NOW,
    )
    assert "require_sl" in gates_of(r)


def test_min_rr_recomputed_from_prices_not_from_the_models_claim(cfg):
    """The model claims 5.0. The actual prices say 0.5. We trust the prices."""
    p = proposal(entry_price=2600.0, sl=2590.0, tp=2605.0, expected_rr=5.0)
    r = check(cfg, cfg.instruments[0], p, equity=10000, book=FLAT, lots=0.1, events=[], now=NOW)
    assert "min_rr" in gates_of(r)
    detail = next(x.detail for x in r if x.gate == "min_rr")
    assert "0.50" in detail and "model claimed 5.00" in detail


def test_buy_with_stop_above_entry_is_refused(cfg):
    """A mis-specified order the venue might well accept."""
    p = proposal(side="BUY", entry_price=2600.0, sl=2610.0, tp=2650.0)
    r = check(cfg, cfg.instruments[0], p, equity=10000, book=FLAT, lots=0.1, events=[], now=NOW)
    assert "sl_direction" in gates_of(r)


def test_sell_with_stop_below_entry_is_refused(cfg):
    p = proposal(side="SELL", entry_price=2600.0, sl=2590.0, tp=2500.0)
    r = check(cfg, cfg.instruments[0], p, equity=10000, book=FLAT, lots=0.1, events=[], now=NOW)
    assert "sl_direction" in gates_of(r)


def test_kill_switch_refuses_everything(cfg, tmp_path):
    c = cfg_with(cfg, kill_switch=tmp_path / "KILL")
    (tmp_path / "KILL").touch()
    r = check(
        c, c.instruments[0], proposal(), equity=10000, book=FLAT, lots=0.13, events=[], now=NOW
    )
    assert "kill_switch" in gates_of(r)


def test_max_open_positions_counts_lab_tickets_only(cfg):
    book = Book(
        open_positions=3, open_lots=0.3, open_risk_currency=100, realized_today=0, floating=0
    )
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=book, lots=0.1, events=[], now=NOW
    )
    assert "max_open_positions" in gates_of(r)


def test_daily_loss_limit_halts_new_orders(cfg):
    # 2% limit on 10k equity = -200. Realized -150 + floating -60 = -210.
    book = Book(
        open_positions=1,
        open_lots=0.1,
        open_risk_currency=50,
        realized_today=-150.0,
        floating=-60.0,
    )
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=book, lots=0.1, events=[], now=NOW
    )
    assert "max_daily_loss_pct" in gates_of(r)


def test_daily_loss_limit_not_breached_when_within(cfg):
    book = Book(
        open_positions=1, open_lots=0.1, open_risk_currency=50, realized_today=-50.0, floating=-20.0
    )
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=book, lots=0.1, events=[], now=NOW
    )
    assert "max_daily_loss_pct" not in gates_of(r)


def test_high_impact_event_inside_window_blocks(cfg):
    ev = [
        {
            "event": "US CPI",
            "at": (NOW + timedelta(minutes=20)).isoformat(),
            "impact": "high",
            "affects": ["EXNESS:XAUUSD"],
        }
    ]
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=FLAT, lots=0.13, events=ev, now=NOW
    )
    assert "news_blackout" in gates_of(r)


def test_event_outside_window_does_not_block(cfg):
    ev = [
        {
            "event": "US CPI",
            "at": (NOW + timedelta(minutes=90)).isoformat(),
            "impact": "high",
            "affects": ["EXNESS:XAUUSD"],
        }
    ]
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=FLAT, lots=0.13, events=ev, now=NOW
    )
    assert "news_blackout" not in gates_of(r)


def test_event_for_another_symbol_does_not_block(cfg):
    ev = [
        {
            "event": "NZD rate decision",
            "at": (NOW + timedelta(minutes=10)).isoformat(),
            "impact": "high",
            "affects": ["NZDUSD"],
        }
    ]
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=FLAT, lots=0.13, events=ev, now=NOW
    )
    assert "news_blackout" not in gates_of(r)


def test_low_impact_event_does_not_block(cfg):
    ev = [
        {"event": "minor survey", "at": NOW.isoformat(), "impact": "low", "affects": ["EXNESS:XAUUSD"]}
    ]
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=FLAT, lots=0.13, events=ev, now=NOW
    )
    assert "news_blackout" not in gates_of(r)


def test_unreadable_calendar_FAILS_CLOSED(cfg):
    """The whole point. A false positive costs one missed trade. A false negative
    means being long gold into a CPI print we didn't know about."""
    r = check(
        cfg,
        cfg.instruments[0],
        proposal(),
        equity=10000,
        book=FLAT,
        lots=0.13,
        events=[],
        now=NOW,
        calendar_ok=False,
        calendar_reason="cache stale by 40h",
    )
    assert "calendar_unavailable" in gates_of(r)


def test_zero_size_is_refused(cfg):
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=FLAT, lots=0.0, events=[], now=NOW
    )
    assert "size" in gates_of(r)


def test_over_max_lots_is_refused(cfg):
    r = check(
        cfg, cfg.instruments[0], proposal(), equity=10000, book=FLAT, lots=5.0, events=[], now=NOW
    )
    assert "max_lots" in gates_of(r)
