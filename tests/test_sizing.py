"""Sizing: the model states conviction; code composes the size.

The tests that matter here are the ones proving conviction cannot scale size
until it has earned the right to — and that no path can breach a cap.
"""

from __future__ import annotations

import dataclasses

import pytest

from lab import sizing
from lab.config import Sizing
from tests.conftest import cfg_with


def test_vol_targeting_keeps_risk_constant_in_R(cfg):
    """A wider stop gets a smaller position, so the MONEY at risk is unchanged.
    That is volatility targeting, and it falls out of the arithmetic for free."""
    inst = cfg.instruments[0]  # gold, 100 oz/lot
    tight = sizing.size(cfg, inst, equity=10000, entry=2610.0, sl=2606.0, conviction=0.5)
    wide = sizing.size(cfg, inst, equity=10000, entry=2610.0, sl=2598.0, conviction=0.5)

    assert wide.lots < tight.lots
    # Both risk ~0.5% of 10k = $50, give or take the lot-step flooring.
    assert tight.risk_currency == pytest.approx(50, abs=6)
    assert wide.risk_currency == pytest.approx(50, abs=6)


def test_flat_stage_ignores_conviction(cfg):
    """Until calibration proves conviction predicts realized R, it must not move
    size. It is recorded, not obeyed."""
    assert cfg.sizing.stage == "flat"
    inst = cfg.instruments[0]
    low = sizing.size(cfg, inst, equity=10000, entry=2610.0, sl=2606.0, conviction=0.05)
    high = sizing.size(cfg, inst, equity=10000, entry=2610.0, sl=2606.0, conviction=0.99)
    assert low.lots == high.lots
    assert low.conviction_mult == 1.0 and high.conviction_mult == 1.0


def test_fitted_stage_lets_conviction_move_size(cfg):
    c = cfg_with(
        cfg,
        sizing=Sizing(
            stage="fitted",
            conviction_max_mult=2.0,
            kelly_fraction=0.5,
            fit={"slope": 1.0, "intercept": 0.5},
        ),
    )
    inst = c.instruments[0]
    low = sizing.size(c, inst, equity=10000, entry=2610.0, sl=2600.0, conviction=0.1)
    high = sizing.size(c, inst, equity=10000, entry=2610.0, sl=2600.0, conviction=0.9)
    assert high.lots > low.lots


def test_fractional_kelly_damps_the_fit(cfg):
    """Full Kelly is growth-optimal only if the edge estimate is exactly right,
    and catastrophically over-levered when it isn't. Half-Kelly halves the deviation
    from neutral."""
    full = cfg_with(cfg, sizing=Sizing("fitted", 5.0, 1.0, {"slope": 2.0, "intercept": 1.0}))
    half = cfg_with(cfg, sizing=Sizing("fitted", 5.0, 0.5, {"slope": 2.0, "intercept": 1.0}))
    # raw at conviction 1.0 = 1.0 + 2.0 = 3.0 -> deviation from neutral is 2.0
    assert sizing.conviction_multiplier(full, 1.0) == pytest.approx(3.0)
    assert sizing.conviction_multiplier(half, 1.0) == pytest.approx(2.0)  # 1 + 2*0.5


def test_conviction_multiplier_is_capped(cfg):
    c = cfg_with(cfg, sizing=Sizing("fitted", 2.0, 1.0, {"slope": 99.0, "intercept": 1.0}))
    assert sizing.conviction_multiplier(c, 1.0) == 2.0  # not 100


def test_max_lots_cap_binds(cfg):
    inst = cfg.instruments[0]  # max_lots 0.10
    got = sizing.size(cfg, inst, equity=10_000_000, entry=2610.0, sl=2609.0, conviction=1.0)
    assert got.lots == inst.max_lots
    assert got.capped_by == "max_lots"


def test_portfolio_heat_cap_blocks_the_next_correlated_position(cfg):
    """Long gold + short DXY + long silver is one trade wearing three hats.
    Once the heat budget is consumed, the next position gets nothing."""
    inst = cfg.instruments[0]
    # heat cap 2% of 10k = $200 already fully consumed
    got = sizing.size(
        cfg, inst, equity=10000, entry=2610.0, sl=2606.0, conviction=0.8, open_risk_currency=200.0
    )
    assert got.lots == 0.0
    assert got.correlation_haircut == 0.0


def test_heat_headroom_shrinks_size_gradually(cfg):
    inst = cfg.instruments[0]
    free = sizing.size(
        cfg, inst, equity=10000, entry=2610.0, sl=2606.0, conviction=0.5, open_risk_currency=0.0
    )
    tight = sizing.size(
        cfg, inst, equity=10000, entry=2610.0, sl=2606.0, conviction=0.5, open_risk_currency=175.0
    )  # $25 headroom
    assert 0 < tight.lots < free.lots


def test_lots_are_floored_never_rounded_up(cfg):
    """Rounding up would breach the very cap we just applied."""
    inst = cfg.instruments[0]
    got = sizing.size(cfg, inst, equity=10000, entry=2610.0, sl=2606.0, conviction=0.5)
    assert got.lots == round(got.lots, 2)
    assert (got.lots / sizing.LOT_STEP) == pytest.approx(round(got.lots / sizing.LOT_STEP))


def test_tiny_equity_yields_zero_not_a_sub_minimum_order(cfg):
    inst = cfg.instruments[0]
    got = sizing.size(cfg, inst, equity=10.0, entry=2610.0, sl=2606.0, conviction=1.0)
    assert got.lots == 0.0
    assert got.capped_by == "below_min_lot"


def test_zero_stop_distance_raises(cfg):
    with pytest.raises(ValueError):
        sizing.size(cfg, cfg.instruments[0], equity=10000, entry=2610.0, sl=2610.0, conviction=0.5)


def test_hand_computed_example(cfg):
    """The worked example from docs/SIZING.md, checked by hand.

    risk = 10142 * 0.5% = 50.71 ; stop = 3.70 ; contract = 100
    lots = 50.71 / (3.70 * 100) = 0.137 -> floored to 0.13
    """
    inst = cfg.instruments[0]
    got = sizing.size(cfg, inst, equity=10142.0, entry=2609.9, sl=2606.2, conviction=0.6)
    assert got.lots == pytest.approx(0.13)


def test_max_lots_below_typical_size_is_detected(cfg):
    """A cap that binds on every trade makes the risk model inert: every position
    becomes the same size regardless of stop distance, vol-targeting silently
    stops working, and nothing errors. This is the bug the test suite caught in
    the shipped lab.yaml (max_lots 0.10 vs a typical 0.137)."""
    inst = cfg.instruments[0]
    assert not sizing.cap_binds_at_typical_size(cfg, inst, equity=10000, stop_distance=3.7)

    tiny = dataclasses.replace(inst, max_lots=0.05)
    assert sizing.cap_binds_at_typical_size(cfg, tiny, equity=10000, stop_distance=3.7)
