"""Assemble the decision packet.

The model does not get the firehose. It gets a bounded packet: venue truth,
charts, calendar, the playbook, and the retrieved memory slice. Anything that
doesn't fit gets summarized, not truncated.

A missing source is recorded as MISSING — never silently treated as a neutral
reading, or every belief conditioned on it is quietly poisoned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .config import Config, Instrument
from .qkt import Qkt, QktError

MIN_BARS = 50  # fewer than this and the charts/indicators are junk — abort the cycle


class ContextError(RuntimeError):
    """The cycle cannot proceed — venue truth is unavailable or too thin."""


@dataclass
class Context:
    instrument: Instrument
    now: datetime
    account: dict[str, Any]
    quote: dict[str, Any]
    bars: dict[str, list[dict[str, Any]]]  # tf -> bars
    indicators: dict[str, Any]
    playbook: str
    sources_missing: list[str] = field(default_factory=list)

    @property
    def equity(self) -> float:
        return float(self.account.get("equity", 0))

    def packet(
        self,
        *,
        events: list[dict[str, Any]],
        beliefs: str = "",
        map_nodes: str = "",
        open_positions: int = 0,
        realized_today: float = 0.0,
    ) -> dict[str, Any]:
        """The dict handed to the model. Bars are summarized — the charts carry
        the detail; the packet carries the numbers."""
        last = {tf: bars[-1] for tf, bars in self.bars.items() if bars}
        return {
            "instrument": self.instrument.symbol,
            "now": self.now.isoformat(),
            "account": {
                "equity": self.account.get("equity"),
                "currency": self.account.get("currency"),
                "open_lab_positions": open_positions,
                "realized_today": realized_today,
            },
            "quote": self.quote,
            "last_bars": last,
            "indicators": self.indicators,
            "calendar": events,
            "playbook": self.playbook,
            "beliefs": beliefs or "(none active)",
            "map_nodes": map_nodes or "(none retrieved)",
            "sources_missing": self.sources_missing,
        }


def gather(cfg: Config, qkt: Qkt, inst: Instrument) -> Context:
    now = datetime.now(UTC)
    missing: list[str] = []

    # Venue truth is the one non-optional source. If it's down, there is no cycle.
    try:
        account = qkt.account(broker=inst.symbol.split(":")[0])
        quote = qkt.quote(inst.symbol)
    except QktError as e:
        raise ContextError(f"venue unavailable: {e}") from e

    bars: dict[str, list[dict[str, Any]]] = {}
    for tf in inst.timeframes:
        got = qkt.bars(inst.symbol, tf, inst.bars)
        # qkt over-fetches and takeLast()s — it can return FEWER than asked with
        # no error. Thin history means junk indicators; abort rather than guess.
        if len(got) < MIN_BARS:
            raise ContextError(f"only {len(got)} {tf} bars for {inst.symbol} (need {MIN_BARS})")
        bars[tf] = got

    indicators: dict[str, Any] = {}
    for expr in ("atr(14)", "ema(50)", "rsi(14)"):
        try:
            r = qkt.evaluate(expr, inst.symbol, inst.timeframes[0])
            indicators[expr] = r.get("value") if r.get("isReady") else None
        except QktError:
            indicators[expr] = None
            missing.append(f"indicator:{expr}")

    playbook = ""
    if inst.playbook.exists():
        playbook = inst.playbook.read_text()
    else:
        missing.append(f"playbook:{inst.playbook.name}")

    return Context(
        instrument=inst,
        now=now,
        account=account,
        quote=quote,
        bars=bars,
        indicators=indicators,
        playbook=playbook,
        sources_missing=missing,
    )
