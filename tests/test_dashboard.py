from __future__ import annotations

import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from lab.dashboard import Journal, _chart_relative, _enrich, _json_default, _status

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_navigation_and_responsive_sidebar_contract():
    app = (ROOT / "journal-ui" / "src" / "App.jsx").read_text()
    css = (ROOT / "journal-ui" / "src" / "index.css").read_text()
    built = (ROOT / "dashboard" / "dist" / "index.html").read_text()
    audit = (ROOT / "docs" / "UI-UX-AUDIT.md").read_text()

    for page in ("overview", "journal", "calendar", "analytics", "system"):
        assert f"{page}: <" in app
    assert "qkt-journal-sidebar" in app
    assert "setMobileOpen" in app
    assert "TradingViewEvidence" in app
    assert "chart.panes()" in app
    assert 'title: "RSI 14"' in app
    assert 'title: "ATR 14"' in app
    assert "md:hidden" in app
    assert "md:ml-[72px]" in app
    assert "Technical audit trail" in app
    assert "What the system observed" in app
    assert "Select a recorded day to review it" in app
    assert 'href="#main-content"' in app
    assert 'aria-current={page === id ? "page" : undefined}' in app
    assert "inert={!isDesktop && !mobileOpen}" in app
    assert 'aria-labelledby="decision-detail-title"' in app
    assert "returnFocusRef.current?.focus" in app
    assert 'scope="col"' in app
    assert "Save chart PNG" in app
    assert "cardView" in app
    assert "profitable close" not in app
    assert 'TRADE: "#5cb8ff"' in app
    assert 'return "bg-info/10 text-info"' in app
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "@media (forced-colors: active)" in css
    assert ":focus-visible" in css
    assert 'id="root"' in built
    assert '<html lang="en">' in built
    assert "## Component audit and resulting decisions" in audit
    assert "| Interactive chart |" in audit


def test_dashboard_text_and_control_tokens_meet_contrast_baseline():
    css = (ROOT / "journal-ui" / "src" / "index.css").read_text()

    def token(name):
        match = re.search(rf"--color-{name}: (#[0-9a-f]{{6}})", css)
        assert match is not None
        return match.group(1)

    def luminance(value):
        channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    def contrast(first, second):
        high, low = sorted((luminance(first), luminance(second)), reverse=True)
        return (high + 0.05) / (low + 0.05)

    raised = token("raised")
    assert contrast(token("faint"), raised) >= 4.5
    assert contrast(token("muted"), raised) >= 4.5
    assert contrast(token("line-strong"), raised) >= 3


def test_chart_relative_handles_container_and_relative_paths():
    assert _chart_relative("/lab/state/charts/2026-07-17T14/XAUUSD-1h.png") == (
        "2026-07-17T14/XAUUSD-1h.png"
    )
    assert _chart_relative("charts/2026-07-17T14/XAUUSD-15m.png") == (
        "2026-07-17T14/XAUUSD-15m.png"
    )


def test_enrich_adds_public_chart_views(monkeypatch):
    monkeypatch.setenv("LAB_CHARTS_PUBLIC_URL", "http://localhost:18080/charts")
    row = {
        "id": 7,
        "charts": ["/lab/state/charts/2026-07-17T14/XAUUSD-1h.png"],
    }
    enriched = _enrich(row)
    assert enriched["chartViews"][0]["image"] == (
        "http://localhost:18080/charts/2026-07-17T14/XAUUSD-1h.png"
    )
    assert enriched["chartViews"][0]["snapshot"] == "/api/decisions/7/snapshots/0"


def test_json_default_preserves_precision_and_utc_time():
    assert _json_default(Decimal("12.50")) == 12.5
    assert _json_default(datetime(2026, 7, 17, 14, 0, tzinfo=UTC)) == ("2026-07-17T14:00:00+00:00")
    assert _json_default(Path("state/charts/a.png")) == "state/charts/a.png"


def test_status_uses_authenticated_gateway_health_and_account(monkeypatch):
    calls = []

    def fake_probe(url, *, token=""):
        calls.append((url, token))
        return {"online": True, "http": 200}

    monkeypatch.setattr("lab.dashboard._probe", fake_probe)
    monkeypatch.setenv("MT5_GATEWAY_URL", "http://gateway:5001")
    monkeypatch.setenv("QKT_BROKER_EXNESS_API_KEY", "test-token")
    status = _status()

    assert status["gateway"]["online"] is True
    assert status["account"]["online"] is True
    assert status["database"] == {"online": True, "source": "lab Postgres"}
    assert calls == [
        ("http://gateway:5001/health/ready", "test-token"),
        ("http://gateway:5001/account", "test-token"),
    ]


class FakeStore:
    def __init__(self, responses):
        self.responses = iter(responses)

    def query(self, *_args, **_kwargs):
        return next(self.responses)


def journal_with(*responses):
    journal = Journal.__new__(Journal)
    journal.store = FakeStore(responses)
    return journal


def test_analytics_builds_curve_drawdown_and_widget_groups():
    closed = [
        {
            "id": 1,
            "symbol": "EXNESS:XAUUSD",
            "side": "BUY",
            "setup": "Breakout",
            "ts": datetime(2026, 7, 17, 9, tzinfo=UTC),
            "arm": "A",
            "closed_at": datetime(2026, 7, 17, 10, tzinfo=UTC),
            "net_pnl": Decimal("100"),
            "r_multiple": Decimal("2"),
            "duration_s": 3600,
            "commission": Decimal("-2"),
            "swap": Decimal("0"),
        },
        {
            "id": 2,
            "symbol": "EXNESS:XAUUSD",
            "side": "SELL",
            "setup": "Breakout",
            "ts": datetime(2026, 7, 18, 14, tzinfo=UTC),
            "arm": "B",
            "closed_at": datetime(2026, 7, 18, 15, tzinfo=UTC),
            "net_pnl": Decimal("-40"),
            "r_multiple": Decimal("-0.8"),
            "duration_s": 3600,
            "commission": Decimal("-2"),
            "swap": Decimal("0"),
        },
    ]
    journal = journal_with(
        closed,
        [{"action": "GATED", "count": 3}, {"action": "TRADE", "count": 2}],
    )

    result = journal.analytics()

    assert [point["cumulativePnl"] for point in result["curve"]] == [100.0, 60.0]
    assert result["maxDrawdown"] == 40.0
    assert result["setups"][0]["trades"] == 2
    assert result["setups"][0]["winRate"] == 50.0
    assert result["setups"][0]["averageR"] == 0.6
    assert result["hours"] == [
        {"hour": 9, "netPnl": 100.0, "trades": 1, "wins": 1, "winRate": 100.0},
        {"hour": 14, "netPnl": -40.0, "trades": 1, "wins": 0, "winRate": 0.0},
    ]


def test_calendar_combines_decision_and_close_dates_without_fake_zero_rows():
    journal = journal_with(
        [
            {
                "day": date(2026, 7, 17),
                "decisions": 4,
                "trade_decisions": 1,
                "no_trades": 2,
                "gated": 1,
            }
        ],
        [
            {
                "day": date(2026, 7, 18),
                "closed_trades": 1,
                "wins": 1,
                "net_pnl": Decimal("25.5"),
                "r_multiple": Decimal("1.2"),
            }
        ],
    )

    assert journal.calendar() == [
        {
            "date": "2026-07-17",
            "decisions": 4,
            "trade_decisions": 1,
            "no_trades": 2,
            "gated": 1,
        },
        {
            "date": "2026-07-18",
            "decisions": 0,
            "trade_decisions": 0,
            "no_trades": 0,
            "gated": 0,
            "closed_trades": 1,
            "wins": 1,
            "net_pnl": Decimal("25.5"),
            "r_multiple": Decimal("1.2"),
        },
    ]


def test_operations_reports_recorded_cycle_and_job_health(monkeypatch, cfg):
    now = datetime.now(UTC)
    journal = journal_with(
        [
            {
                "id": 9,
                "ts": now,
                "action": "GATED",
                "symbol": "EXNESS:XAUUSD",
                "setup": None,
                "gate_rejects": [{"gate": "quote_freshness", "detail": "stale"}],
            }
        ],
        [
            {
                "decisions_24h": 9,
                "trades_24h": 0,
                "no_trades_24h": 6,
                "gated_24h": 3,
            }
        ],
        [
            {
                "open_trades": 0,
                "closed_trades": 0,
                "venue_rejects": 0,
                "last_outcome_join_at": None,
            }
        ],
        [
            {
                "job": "join",
                "command": "python3 /lab/bin/join",
                "started_at": now,
                "finished_at": now,
                "ok": True,
                "detail": "exit 0",
            }
        ],
    )
    monkeypatch.setattr("lab.dashboard.cfgmod.load", lambda _path: cfg)

    result = journal.operations()

    assert result["cycleHealth"] == "healthy"
    assert result["cycleAgeSeconds"] < 5
    assert result["activity24h"]["no_trades_24h"] == 6
    assert result["jobRuns"][0]["ok"] is True
    assert {job["job"] for job in result["schedules"]} == {
        "trade",
        "join",
        "distill",
        "research",
    }


def test_snapshot_prefers_database_evidence_over_the_filesystem():
    stored = {
        "schemaVersion": 1,
        "title": "EXNESS:XAUUSD 1h",
        "bars": [{"time": 1, "open": 1, "high": 2, "low": 0.5, "close": 1.5}],
        "studies": {"ema50": [], "rsi14": [], "atr14": []},
    }
    journal = journal_with(
        [
            {
                "charts": ["/lab/state/charts/missing.png"],
                "context_snapshot": {"chartSnapshots": [stored]},
            }
        ]
    )

    assert journal.snapshot(42, 0) == stored
