"""Deterministic pre-order gates.

The model never sees these and cannot argue with them. It emits a proposal; this
runs afterwards, in code, and refuses.

Every gate is arithmetic. There is no judgment here, and there is no LLM in this
path. That is the entire point: gates are only real if they run outside the model.

A rejected proposal is still written to the journal (action='GATED') with its
reasons. Those rows are the most diagnostic data we have — they say what the model
wanted to do and what stopped it. Throwing them away would be the mistake.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import Config, Instrument


@dataclass(frozen=True)
class Reject:
    gate: str
    detail: str

    def __str__(self) -> str:
        return f"{self.gate}: {self.detail}"


@dataclass(frozen=True)
class Book:
    """The lab's own open exposure.

    Built from OUR store, never from `qkt bot positions` — that verb applies no
    magic filter and returns every position on the account, including the deployed
    strategies'. Counting those would let another strategy's book silently consume
    our risk budget.
    """

    open_positions: int
    open_lots: float
    open_risk_currency: float
    realized_today: float  # net PnL of lab tickets closed today (negative = loss)
    floating: float  # floating PnL on open lab tickets


def check(
    cfg: Config,
    inst: Instrument,
    proposal: dict[str, Any],
    *,
    equity: float,
    book: Book,
    lots: float,
    events: list[dict[str, Any]],
    now: datetime | None = None,
    calendar_ok: bool = True,
    calendar_reason: str = "",
) -> list[Reject]:
    """Returns every reason to refuse. Empty list means the order may be placed."""
    now = now or datetime.now(timezone.utc)
    out: list[Reject] = []

    # 1. Kill switch. `touch KILL` must stop the next cycle, full stop.
    if cfg.kill_switch_engaged:
        out.append(Reject("kill_switch", f"{cfg.kill_switch} exists — refusing all orders"))

    # 2. Stop-loss. No stop, no trade. Never negotiable.
    sl = proposal.get("sl")
    entry = proposal.get("entry_price")
    tp = proposal.get("tp")
    if cfg.gates.require_sl and sl is None:
        out.append(Reject("require_sl", "proposal has no stop-loss"))

    # 3. Risk-reward, RECOMPUTED from real prices. The model's own expected_rr is
    #    never trusted — it is a claim, not a measurement.
    if sl is not None and tp is not None and entry is not None:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk <= 0:
            out.append(Reject("min_rr", "stop distance is zero"))
        else:
            rr = reward / risk
            if rr < cfg.gates.min_rr:
                claimed = proposal.get("expected_rr")
                detail = f"actual rr {rr:.2f} < {cfg.gates.min_rr}"
                if claimed is not None and float(claimed) >= cfg.gates.min_rr:
                    detail += f" (model claimed {float(claimed):.2f})"
                out.append(Reject("min_rr", detail))

        # Direction sanity: a BUY whose stop is above entry is a mis-specified order,
        # not a strategy. The venue might even accept it.
        side = proposal.get("side")
        if side == "BUY" and sl >= entry:
            out.append(Reject("sl_direction", f"BUY with sl {sl} at/above entry {entry}"))
        if side == "SELL" and sl <= entry:
            out.append(Reject("sl_direction", f"SELL with sl {sl} at/below entry {entry}"))

    # 4. Sizing produced nothing tradeable.
    if lots <= 0:
        out.append(Reject("size", "computed size is zero (heat cap, or below min lot)"))
    if lots > inst.max_lots:
        out.append(Reject("max_lots", f"{lots} > {inst.max_lots} for {inst.symbol}"))

    # 5. Book limits — counted over LAB-OWNED tickets only.
    if book.open_positions >= cfg.gates.max_open_positions:
        out.append(
            Reject(
                "max_open_positions",
                f"{book.open_positions} lab positions already open "
                f"(max {cfg.gates.max_open_positions})",
            )
        )
    if book.open_lots + lots > cfg.gates.max_exposure_lots:
        out.append(
            Reject(
                "max_exposure_lots",
                f"{book.open_lots} + {lots} > {cfg.gates.max_exposure_lots}",
            )
        )

    # 6. Daily loss limit. Realized + floating, against equity. A breach halts new
    #    orders for the rest of the day — it does not close what is open.
    if equity > 0:
        day_pnl = book.realized_today + book.floating
        loss_pct = -day_pnl / equity * 100.0
        if loss_pct >= cfg.gates.max_daily_loss_pct:
            out.append(
                Reject(
                    "max_daily_loss_pct",
                    f"down {loss_pct:.2f}% today (limit {cfg.gates.max_daily_loss_pct}%) "
                    f"— no new orders until tomorrow",
                )
            )

    # 7. News blackout. FAIL-CLOSED: if the calendar could not be read or is stale,
    #    we refuse rather than trade blind through a print.
    #
    #    The asymmetry is the whole point. A false positive costs one missed trade.
    #    A false negative means being long gold into a CPI we didn't know about.
    #    Those are not comparable, so this gate is deliberately trigger-happy.
    if not calendar_ok:
        if cfg.calendar.fail_closed:
            out.append(Reject("calendar_unavailable", calendar_reason or "calendar unreadable"))
    else:
        window = timedelta(minutes=cfg.gates.news_blackout_minutes)
        for ev in events:
            if str(ev.get("impact", "")).lower() != "high":
                continue
            affects = ev.get("affects") or []
            if inst.symbol not in affects and inst.bare not in affects:
                continue
            at = ev.get("at")
            if isinstance(at, str):
                at = datetime.fromisoformat(at.replace("Z", "+00:00"))
            if at is None:
                continue
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            if abs(at - now) <= window:
                out.append(
                    Reject(
                        "news_blackout",
                        f"{ev.get('event')} at {at.isoformat()} is within "
                        f"{cfg.gates.news_blackout_minutes}min",
                    )
                )

    return out
