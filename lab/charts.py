"""Render candle charts from `qkt bot bars --json`.

Charts are produced BEFORE the proposal — they are model input, and they are
archived with the decision so we can later look at exactly what the model saw.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless — no display in a container

import mplfinance as mpf
import pandas as pd


def to_frame(bars: list[dict[str, Any]]) -> pd.DataFrame:
    """qkt bar fields: t (epoch ms), o, h, l, c, v."""
    if not bars:
        raise ValueError("no bars to render")
    df = pd.DataFrame(bars)
    df.index = pd.to_datetime(df.pop("t"), unit="ms", utc=True)
    df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    return df[["Open", "High", "Low", "Close", "Volume"]]


def render(
    bars: list[dict[str, Any]],
    out: Path,
    *,
    title: str,
    sl: float | None = None,
    tp: float | None = None,
) -> Path:
    df = to_frame(bars)
    out.parent.mkdir(parents=True, exist_ok=True)

    hlines: dict[str, Any] = {}
    levels = [x for x in (sl, tp) if x is not None]
    if levels:
        hlines = {"hlines": levels, "colors": ["r", "g"][: len(levels)], "linestyle": "--"}

    mpf.plot(
        df,
        type="candle",
        volume=True,
        style="yahoo",
        title=title,
        savefig={"fname": str(out), "dpi": 110, "bbox_inches": "tight"},
        **({"hlines": hlines} if hlines else {}),
    )
    return out


def chart_paths(state_dir: Path, symbol: str, timeframes: list[str]) -> list[Path]:
    """Deterministic per-cycle chart locations, e.g. state/charts/2026-07-14T08/XAUUSD-1h.png"""
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H")
    bare = symbol.split(":")[-1]
    base = state_dir / "charts" / stamp
    return [base / f"{bare}-{tf}.png" for tf in timeframes]
