"""The calendar cache — the one place an LLM's reading of the web feeds a gate.

The gate NEVER calls a model. RESEARCH writes a cache file with provenance; this
module reads it, validates it, and hands the gate a plain list of events.

Three rules make an LLM-populated safety gate acceptable:

  1. Two independent sources, or the event is not `confirmed`.
     One source agreeing with itself is not corroboration.
  2. Fail-closed. Stale, missing, or uncertain => refuse to trade.
  3. The gate is arithmetic on the file. No judgment, no model.

The asymmetry is the whole point. A false positive costs one missed trade. A
false negative means being long gold into a CPI print we didn't know about. Those
costs are not comparable, so this is deliberately trigger-happy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import yaml

from .config import Config


@dataclass(frozen=True)
class CalendarRead:
    ok: bool
    reason: str
    events: list[dict[str, Any]]


def load(cfg: Config, now: datetime | None = None) -> CalendarRead:
    now = now or datetime.now(UTC)
    path = cfg.calendar.cache

    if not path.exists():
        return CalendarRead(False, f"calendar cache missing at {path}", [])

    try:
        doc = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as e:
        return CalendarRead(False, f"calendar cache unparseable: {e}", [])

    fetched = doc.get("fetched_at")
    if not fetched:
        return CalendarRead(False, "calendar cache has no fetched_at", [])
    if isinstance(fetched, str):
        fetched = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)

    age = now - fetched
    if age > timedelta(hours=cfg.calendar.max_age_hours):
        return CalendarRead(
            False,
            f"calendar cache is {age.total_seconds()/3600:.1f}h old "
            f"(max {cfg.calendar.max_age_hours}h) — refusing to trade blind",
            [],
        )

    events: list[dict[str, Any]] = []
    for ev in doc.get("events", []) or []:
        sources = ev.get("sources") or []
        confidence = str(ev.get("confidence", "uncertain")).lower()

        # An uncorroborated high-impact event is treated as REAL for gating
        # purposes — we would rather block on a rumour than trade through a print
        # we half-heard about. Under-corroboration makes us MORE cautious, never
        # less. Downgrading it to "ignore" is the failure mode that hurts.
        if str(ev.get("impact", "")).lower() == "high":
            if len(sources) < cfg.calendar.min_sources or confidence == "uncertain":
                ev = {**ev, "impact": "high", "under_corroborated": True}
        events.append(ev)

    return CalendarRead(True, "", events)


def upcoming(
    events: list[dict[str, Any]], symbol: str, bare: str, within: timedelta,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """High-impact events for this instrument inside the window."""
    now = now or datetime.now(UTC)
    out = []
    for ev in events:
        if str(ev.get("impact", "")).lower() != "high":
            continue
        affects = ev.get("affects") or []
        if symbol not in affects and bare not in affects:
            continue
        at = ev.get("at")
        if isinstance(at, str):
            at = datetime.fromisoformat(at.replace("Z", "+00:00"))
        if at is None:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        if abs(at - now) <= within:
            out.append(ev)
    return out
