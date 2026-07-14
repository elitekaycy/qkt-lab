"""Join realized broker outcomes back onto the decisions that caused them.

This is the load-bearing piece of the whole project. If it is wrong, every
r_multiple is wrong, every belief is scored against corrupt data, and the agent
learns confidently false things.

The join key is the MT5 ticket:

    qkt bot buy   --json  ->  {"ticket": 88412, ...}
    qkt bot history --json ->  [{"positionTicket": 88412, "entry": "IN"|"OUT", ...}]

Do NOT join via the order comment. It is `bot-<as>-<epochms>`, the wire caps it at
31 chars, and MT5 persists only ~16 — it comes back truncated. It is not a key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .config import Config
from .qkt import Qkt
from .store import Store


@dataclass(frozen=True)
class Joined:
    ticket: int
    closed_at: datetime
    close_price: float | None
    gross_pnl: float
    commission: float
    swap: float
    net_pnl: float
    lots_closed: float
    duration_s: int
    deals: list[dict[str, Any]]


def aggregate(ticket: int, deals: list[dict[str, Any]]) -> Joined | None:
    """Fold every deal for one position into a single realized outcome.

    Correctness notes that are easy to get wrong and expensive to get wrong:

    - Sum commission across ALL deals, IN and OUT. MT5 books commission on the IN
      deal, so summing only the OUT rows silently under-counts cost. The trade
      looks more profitable than it was, forever.
    - A partial close produces SEVERAL OUT deals sharing one positionTicket.
      Aggregate; do not take-first.
    - qkt collapses MT5's INOUT and OUT_BY into "OUT", so any non-IN row is an exit.
    - Returns None if the position has no OUT deal yet (still open).
    """
    mine = [d for d in deals if int(d.get("positionTicket", 0)) == ticket]
    if not mine:
        return None

    ins = [d for d in mine if d.get("entry") == "IN"]
    outs = [d for d in mine if d.get("entry") != "IN"]
    if not ins or not outs:
        return None  # still open, or the IN deal is outside our --since window

    gross = sum(float(d.get("profit", 0)) for d in mine)
    commission = sum(float(d.get("commission", 0)) for d in mine)
    swap = sum(float(d.get("swap", 0)) for d in mine)
    net = gross + commission + swap

    lots_closed = sum(float(d.get("lots", 0)) for d in outs)

    open_ms = min(int(d["timeMs"]) for d in ins)
    close_ms = max(int(d["timeMs"]) for d in outs)

    # Volume-weighted close price across partial exits — a simple mean would be
    # wrong when the partials are different sizes.
    total_lots = sum(float(d.get("lots", 0)) for d in outs)
    close_price = (
        sum(float(d.get("price", 0)) * float(d.get("lots", 0)) for d in outs) / total_lots
        if total_lots > 0
        else None
    )

    return Joined(
        ticket=ticket,
        closed_at=datetime.fromtimestamp(close_ms / 1000, tz=UTC),
        close_price=close_price,
        gross_pnl=gross,
        commission=commission,
        swap=swap,
        net_pnl=net,
        lots_closed=lots_closed,
        duration_s=int((close_ms - open_ms) / 1000),
        deals=mine,
    )


def r_multiple(net_pnl: float, risk_at_entry: float | None) -> float | None:
    """Net PnL expressed in units of the risk taken.

    e.g. risked $48.62, made $147.85 -> +3.04R. This is the currency of everything
    downstream: beliefs are scored on it, and conviction is calibrated against it.
    """
    if not risk_at_entry or risk_at_entry <= 0:
        return None
    # risk_at_entry arrives as Decimal from postgres NUMERIC; float/Decimal raises.
    return net_pnl / float(risk_at_entry)


def run(cfg: Config, qkt: Qkt, store: Store) -> dict[str, Any]:
    """One joiner pass. Idempotent — running it twice must be a no-op."""
    open_ = store.open_tickets()
    if not open_:
        return {"checked": 0, "joined": 0, "still_open": 0, "alarms": []}

    live = {int(p["ticket"]) for p in qkt.positions()}

    joined = 0
    still_open = 0
    for row in open_:
        ticket = int(row["ticket"])
        if ticket in live:
            still_open += 1
            continue

        # Gone from positions => closed (by us, by TP, or by SL). Sweep history
        # with a window that actually covers the open date: `history` defaults to
        # 7d and has no --ticket filter, so a stale default would silently miss
        # an older trade and leave it unjoined forever.
        opened: datetime = row["ts"]
        days = max(2, (datetime.now(UTC) - opened).days + 2)
        deals = qkt.history(since=f"{days}d")

        agg = aggregate(ticket, deals)
        if agg is None:
            still_open += 1
            continue

        store.record_outcome(
            ticket=agg.ticket,
            closed_at=agg.closed_at,
            close_price=agg.close_price,
            gross_pnl=agg.gross_pnl,
            commission=agg.commission,
            swap=agg.swap,
            net_pnl=agg.net_pnl,
            r_multiple=r_multiple(agg.net_pnl, row.get("risk_at_entry")),
            lots_closed=agg.lots_closed,
            duration_s=agg.duration_s,
            deals=agg.deals,
        )
        joined += 1

    # A ticket open for days with no OUT deal is a bug, not a trade. Alarm rather
    # than let it sit unjoined and quietly absent from every study.
    alarms = [
        f"ticket {r['ticket']} ({r['symbol']}) open since {r['ts']} with no outcome"
        for r in store.unjoined_older_than(cfg.unjoined_alarm_days)
    ]

    return {
        "checked": len(open_),
        "joined": joined,
        "still_open": still_open,
        "alarms": alarms,
    }
