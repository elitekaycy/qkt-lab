"""Render candle charts from `qkt bot bars --json`.

Charts are produced BEFORE the proposal — they are model input, and they are
archived with the decision so we can later look at exactly what the model saw.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import matplotlib

matplotlib.use("Agg")  # headless — no display in a container

import mplfinance as mpf
import pandas as pd

ACCENT = "#c8f74a"
UP = "#3fe08c"
DOWN = "#ff6b6b"
MUTED = "#79828c"
PANEL = "#121518"
INK = "#0a0c0e"
LINE = "#22272d"


def to_frame(bars: list[dict[str, Any]]) -> pd.DataFrame:
    """qkt bar fields: t (epoch ms), o, h, l, c, v."""
    if not bars:
        raise ValueError("no bars to render")
    df = pd.DataFrame(bars)
    df.index = pd.to_datetime(df.pop("t"), unit="ms", utc=True)
    df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    return df[["Open", "High", "Low", "Close", "Volume"]]


def studies(df: pd.DataFrame) -> pd.DataFrame:
    """The exact overlays archived with the chart.

    EMA is the standard recursive EMA. RSI and ATR use Wilder smoothing
    (alpha=1/n), matching the definitions named in the model context.
    """
    out = pd.DataFrame(index=df.index)
    out["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

    delta = df["Close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = gain / loss.replace(0, float("nan"))
    out["RSI14"] = 100 - (100 / (1 + rs))
    out.loc[(loss == 0) & (gain > 0), "RSI14"] = 100.0
    out.loc[(loss == 0) & (gain == 0), "RSI14"] = 50.0

    previous = df["Close"].shift(1)
    true_range = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - previous).abs(),
            (df["Low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["ATR14"] = true_range.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    return out


def _point_series(values: pd.Series) -> list[dict[str, Any]]:
    return [
        {"time": int(at.timestamp()), "value": float(value)}
        for at, value in values.dropna().items()
    ]


def write_snapshot(
    bars: list[dict[str, Any]],
    out: Path,
    *,
    title: str,
    derived: pd.DataFrame,
) -> Path:
    """Archive broker bars and studies for the interactive TradingView renderer."""
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "Exness MT5 via qkt",
        "timezone": "UTC",
        "title": title,
        "barCount": len(bars),
        "bars": [
            {
                "time": int(int(bar["t"]) / 1000),
                "open": float(bar["o"]),
                "high": float(bar["h"]),
                "low": float(bar["l"]),
                "close": float(bar["c"]),
                "value": float(bar.get("v", 0)),
            }
            for bar in bars
        ],
        "studies": {
            "ema50": _point_series(derived["EMA50"]),
            "rsi14": _point_series(derived["RSI14"]),
            "atr14": _point_series(derived["ATR14"]),
        },
    }
    target = out.with_suffix(".json")
    target.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return target


def render(
    bars: list[dict[str, Any]],
    out: Path,
    *,
    title: str,
    sl: float | None = None,
    tp: float | None = None,
) -> Path:
    df = to_frame(bars)
    derived = studies(df)
    out.parent.mkdir(parents=True, exist_ok=True)

    hlines: dict[str, Any] = {}
    levels = [x for x in (sl, tp) if x is not None]
    if levels:
        hlines = {"hlines": levels, "colors": [DOWN, UP][: len(levels)], "linestyle": "--"}

    market = mpf.make_marketcolors(
        up=UP,
        down=DOWN,
        edge={"up": UP, "down": DOWN},
        wick={"up": UP, "down": DOWN},
        volume={"up": UP, "down": DOWN},
    )
    style = mpf.make_mpf_style(
        base_mpf_style="nightclouds",
        marketcolors=market,
        facecolor=PANEL,
        figcolor=INK,
        gridcolor=LINE,
        gridstyle="-",
        rc={
            "axes.labelcolor": MUTED,
            "axes.titlecolor": "#f2f4f6",
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "font.family": "sans-serif",
        },
    )
    rsi_30 = pd.Series(30.0, index=df.index)
    rsi_70 = pd.Series(70.0, index=df.index)
    overlays = [
        mpf.make_addplot(derived["EMA50"], panel=0, color=ACCENT, width=1.1),
        mpf.make_addplot(derived["RSI14"], panel=2, color="#a78bfa", width=1.0, ylabel="RSI 14"),
        mpf.make_addplot(rsi_30, panel=2, color=LINE, width=0.7),
        mpf.make_addplot(rsi_70, panel=2, color=LINE, width=0.7),
    ]
    latest = derived.iloc[-1]
    metrics = (
        f"EMA50 {latest['EMA50']:.2f} · RSI14 {latest['RSI14']:.1f} · ATR14 {latest['ATR14']:.2f}"
    )

    mpf.plot(
        df,
        type="candle",
        volume=True,
        style=style,
        title=f"{title}\n{metrics}",
        addplot=overlays,
        panel_ratios=(6, 2, 2),
        tight_layout=True,
        savefig={"fname": str(out), "dpi": 110, "bbox_inches": "tight"},
        **({"hlines": hlines} if hlines else {}),
    )
    write_snapshot(bars, out, title=title, derived=derived)
    return out


def chart_paths(
    state_dir: Path,
    symbol: str,
    timeframes: list[str],
    *,
    now: datetime | None = None,
    run_id: str | None = None,
) -> list[Path]:
    """Unique immutable locations for the exact evidence from one cycle.

    Multiple/manual runs inside an hour must not overwrite an earlier
    decision's PNG or broker-data JSON sidecar.
    """
    at = now or datetime.now(UTC)
    stamp = at.strftime("%Y-%m-%dT%H-%M-%S")
    identity = run_id or uuid4().hex[:12]
    bare = symbol.split(":")[-1]
    base = state_dir / "charts" / f"{stamp}Z-{identity}"
    return [base / f"{bare}-{tf}.png" for tf in timeframes]
