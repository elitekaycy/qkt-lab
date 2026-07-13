"""Position sizing.

The model DOES determine size — it states a conviction, and that is a real input.
What it does not do is pick a lot number freely, because a model that picks lots
is a model that sizes up after losses.

    lots = (equity x risk_pct) / (stop_distance x contract_value)   <- vol-targeted
           x f(conviction)                                          <- the model's call
           x correlation_haircut(open book)
           capped by max_lots and portfolio_heat_pct

f() is FITTED from realized outcomes, never guessed. Until a calibration report
shows that high-conviction trades actually outperform, f() returns 1.0 and
conviction is merely recorded. See docs/SIZING.md.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import Config, Instrument

# Venue lot granularity. Smaller than this cannot be traded.
LOT_STEP = 0.01


@dataclass(frozen=True)
class Sized:
    lots: float
    risk_currency: float  # what we lose if the stop is hit — the denominator of R
    conviction_mult: float
    correlation_haircut: float
    capped_by: str | None  # which cap bound, if any


def risk_currency(entry: float, sl: float, lots: float, contract_value: float) -> float:
    """Money at risk if the stop is hit.

    e.g. gold, entry 2609.9, sl 2606.2, 0.13 lots, 100 oz/lot
         -> |2609.9 - 2606.2| x 0.13 x 100 = $48.10
    """
    return abs(entry - sl) * lots * contract_value


def conviction_multiplier(cfg: Config, conviction: float) -> float:
    """Map the model's stated conviction to a size multiplier.

    Stage `flat`: always 1.0. Conviction is recorded but does not move size — we
    are collecting the data that will tell us whether it means anything.

    Stage `fitted`: a curve fitted to realized R per conviction bucket, damped by
    kelly_fraction. Never full Kelly: full Kelly is growth-optimal only if the edge
    estimate is exactly right, and catastrophically over-levered when it isn't.
    """
    if cfg.sizing.stage == "flat":
        return 1.0

    fit = cfg.sizing.fit or {}
    slope = float(fit.get("slope", 0.0))
    intercept = float(fit.get("intercept", 1.0))
    raw = intercept + slope * conviction

    # Fractional Kelly: damp the fitted signal toward neutral.
    damped = 1.0 + (raw - 1.0) * cfg.sizing.kelly_fraction
    return max(0.0, min(damped, cfg.sizing.conviction_max_mult))


def correlation_haircut(cfg: Config, open_risk_currency: float, equity: float) -> float:
    """Shrink size as the book's total open risk approaches the heat cap.

    Long gold + short DXY + long silver is one trade wearing three hats. Sizing
    each in isolation is how a book that looks diversified turns out not to be.

    Returns a multiplier in [0, 1]. Zero means the heat cap is already consumed
    and no further risk may be added.
    """
    heat_budget = equity * cfg.risk.portfolio_heat_pct / 100.0
    if heat_budget <= 0:
        return 0.0
    headroom = heat_budget - open_risk_currency
    if headroom <= 0:
        return 0.0
    # Full size while there is a full trade's worth of headroom; shrink linearly
    # as we approach the cap.
    trade_budget = equity * cfg.risk.risk_per_trade_pct / 100.0
    if trade_budget <= 0:
        return 0.0
    return min(1.0, headroom / trade_budget)


def cap_binds_at_typical_size(
    cfg: Config, inst: Instrument, *, equity: float, stop_distance: float
) -> bool:
    """Would max_lots bind on an ordinary trade?

    If it would, the risk model is inert: max_lots has quietly become the only
    sizing rule, every trade is the same size regardless of stop distance, and the
    vol-targeting property is gone. That is a config bug that produces no error and
    no symptom you would notice — the account just stops respecting your risk
    budget. Worth surfacing loudly.
    """
    if stop_distance <= 0:
        return False
    base = equity * cfg.risk.risk_per_trade_pct / 100.0
    typical = base / (stop_distance * inst.contract_value)
    return typical > inst.max_lots


def size(
    cfg: Config,
    inst: Instrument,
    *,
    equity: float,
    entry: float,
    sl: float,
    conviction: float,
    open_risk_currency: float = 0.0,
) -> Sized:
    """Compose the stack. Pure arithmetic — no model in this path."""
    stop_distance = abs(entry - sl)
    if stop_distance <= 0:
        raise ValueError("stop distance is zero — entry and sl are the same price")

    base = equity * cfg.risk.risk_per_trade_pct / 100.0

    # Dividing by the stop distance IS volatility targeting when the stop is
    # ATR-derived: a wide stop in a volatile tape gets a smaller position, so the
    # money at risk stays constant in R terms across regimes.
    vol_adjusted = base / (stop_distance * inst.contract_value)

    cmult = conviction_multiplier(cfg, conviction)
    haircut = correlation_haircut(cfg, open_risk_currency, equity)

    raw = vol_adjusted * cmult * haircut

    capped_by: str | None = None
    lots = raw
    if lots > inst.max_lots:
        lots, capped_by = inst.max_lots, "max_lots"

    # Floor to the venue lot step. Floor, never round — rounding up would breach
    # the very cap we just applied.
    lots = math.floor(lots / LOT_STEP) * LOT_STEP
    lots = round(lots, 2)

    if lots < LOT_STEP:
        lots, capped_by = 0.0, capped_by or "below_min_lot"

    return Sized(
        lots=lots,
        risk_currency=risk_currency(entry, sl, lots, inst.contract_value),
        conviction_mult=cmult,
        correlation_haircut=haircut,
        capped_by=capped_by,
    )
