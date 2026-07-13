"""The one code path that places an order.

Deterministic python. It receives a proposal that has already been validated and
gated, a size that was already computed, and it talks to the venue. No model is
reachable from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Config, Instrument
from .qkt import Qkt, QktError


@dataclass(frozen=True)
class Fill:
    accepted: bool
    ticket: int | None
    deal: int | None
    fill_price: float | None
    retcode: int | None
    error: str | None
    raw: dict[str, Any]


def place(
    cfg: Config,
    qkt: Qkt,
    inst: Instrument,
    *,
    side: str,
    lots: float,
    sl: float,
    tp: float | None,
) -> Fill:
    """Market order only (pendings wait for the ticket-identity spike, phase 6)."""
    if cfg.kill_switch_engaged:
        # Gates already check this, but the executor re-checks: the kill switch
        # must hold even if a caller wires around the gates by mistake.
        return Fill(False, None, None, None, None, "kill switch engaged", {})

    fn = qkt.buy if side == "BUY" else qkt.sell
    try:
        r = fn(lots=lots, symbol=inst.symbol, sl=sl, tp=tp, as_name=cfg.as_name(inst.symbol))
    except QktError as e:
        return Fill(False, None, None, None, None, str(e), {})

    return Fill(
        accepted=bool(r.get("ok")),
        ticket=int(r["ticket"]) if r.get("ticket") else None,
        deal=int(r["deal"]) if r.get("deal") else None,
        fill_price=float(r["fillPrice"]) if r.get("fillPrice") is not None else None,
        retcode=r.get("retcode"),
        error=r.get("error"),
        raw=r,
    )
