"""The calendar is the one LLM-populated input that feeds a gate. Every test here
is about failing closed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lab import calendar as cal
from tests.conftest import cfg_with

NOW = datetime(2026, 7, 14, 8, 0, tzinfo=UTC)


def write_cache(path, fetched_at, events):
    import yaml

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"fetched_at": fetched_at, "events": events}))


def cache_cfg(cfg, tmp_path):
    from lab.config import Calendar

    return cfg_with(
        cfg,
        calendar=Calendar(
            cache=tmp_path / "upcoming.yaml",
            max_age_hours=cfg.calendar.max_age_hours,
            min_sources=cfg.calendar.min_sources,
            fail_closed=True,
        ),
    )


CPI = {
    "event": "US CPI",
    "at": "2026-07-14T12:30:00Z",
    "impact": "high",
    "affects": ["ICM:XAUUSD"],
    "confidence": "confirmed",
    "sources": ["https://bls.gov/...", "https://fred.stlouisfed.org/..."],
}


def test_missing_cache_fails_closed(cfg, tmp_path):
    c = cache_cfg(cfg, tmp_path)
    got = cal.load(c, NOW)
    assert not got.ok
    assert "missing" in got.reason


def test_stale_cache_fails_closed(cfg, tmp_path):
    c = cache_cfg(cfg, tmp_path)
    write_cache(c.calendar.cache, (NOW - timedelta(hours=40)).isoformat(), [CPI])
    got = cal.load(c, NOW)
    assert not got.ok
    assert "refusing to trade blind" in got.reason


def test_fresh_corroborated_cache_is_ok(cfg, tmp_path):
    c = cache_cfg(cfg, tmp_path)
    write_cache(c.calendar.cache, (NOW - timedelta(hours=2)).isoformat(), [CPI])
    got = cal.load(c, NOW)
    assert got.ok
    assert len(got.events) == 1


def test_under_corroboration_makes_us_MORE_cautious_never_less(cfg, tmp_path):
    """A single-source high-impact event is still treated as REAL for gating.
    We would rather block on a rumour than trade through a print we half-heard
    about. Downgrading it to 'ignore' is the failure mode that hurts."""
    c = cache_cfg(cfg, tmp_path)
    single = {**CPI, "sources": ["https://bls.gov/..."], "confidence": "single-source"}
    write_cache(c.calendar.cache, (NOW - timedelta(hours=1)).isoformat(), [single])
    got = cal.load(c, NOW)
    assert got.ok
    assert got.events[0]["impact"] == "high"  # still gates
    assert got.events[0].get("under_corroborated") is True


def test_corrupt_cache_fails_closed(cfg, tmp_path):
    c = cache_cfg(cfg, tmp_path)
    c.calendar.cache.parent.mkdir(parents=True, exist_ok=True)
    c.calendar.cache.write_text("{{{{ not yaml")
    got = cal.load(c, NOW)
    assert not got.ok


def test_upcoming_filters_by_symbol_impact_and_window(cfg, tmp_path):
    events = [
        CPI,  # 12:30Z — 4.5h away
        {**CPI, "event": "EU thing", "affects": ["EURUSD"]},
        {**CPI, "event": "minor", "impact": "low"},
    ]
    got = cal.upcoming(events, "ICM:XAUUSD", "XAUUSD", timedelta(hours=6), NOW)
    assert [e["event"] for e in got] == ["US CPI"]
    got = cal.upcoming(events, "ICM:XAUUSD", "XAUUSD", timedelta(hours=2), NOW)
    assert got == []
