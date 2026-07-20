from __future__ import annotations

import json
from datetime import UTC, datetime

from lab.charts import chart_paths, render, studies, to_frame


def bars(count: int = 80):
    return [
        {
            "t": 1_700_000_000_000 + index * 3_600_000,
            "o": 2000 + index,
            "h": 2002 + index,
            "l": 1998 + index,
            "c": 2001 + index,
            "v": 100 + index,
        }
        for index in range(count)
    ]


def test_studies_preserve_unknown_warmup_and_produce_latest_values():
    derived = studies(to_frame(bars()))
    assert derived["RSI14"].iloc[:13].isna().all()
    assert derived["ATR14"].iloc[:13].isna().all()
    assert derived["EMA50"].iloc[-1] > 0
    assert derived["ATR14"].iloc[-1] > 0


def test_render_writes_png_and_broker_snapshot(tmp_path):
    target = tmp_path / "XAUUSD-1h.png"
    render(bars(), target, title="EXNESS:XAUUSD 1h")
    snapshot = json.loads(target.with_suffix(".json").read_text())
    assert target.stat().st_size > 0
    assert snapshot["source"] == "Exness MT5 via qkt"
    assert snapshot["timezone"] == "UTC"
    assert snapshot["barCount"] == 80
    assert len(snapshot["studies"]["ema50"]) == 80


def test_chart_paths_are_immutable_per_cycle(tmp_path):
    now = datetime(2026, 7, 19, 20, 0, tzinfo=UTC)
    first = chart_paths(tmp_path, "EXNESS:XAUUSD", ["1h", "15m"], now=now, run_id="run-a")
    second = chart_paths(tmp_path, "EXNESS:XAUUSD", ["1h", "15m"], now=now, run_id="run-b")
    assert first != second
    assert first[0].parent == first[1].parent
    assert "2026-07-19T20-00-00Z-run-a" in str(first[0])
