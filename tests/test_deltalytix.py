"""The exporter's two landmines, under test: the UUIDv5 recipe (the only unique
key — get it wrong and every re-run duplicates every trade) and the field-shape
conventions the app silently depends on."""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from exporters.deltalytix import NAMESPACE, Target, to_trade_row, trade_uuid

T = Target(
    dsn="postgresql://ignored",
    user_id="local-dashboard-user",
    user_email="local-dashboard@deltalytix.local",
    account_number="LAB-XAU",
    starting_balance=10000,
    charts_base_url="http://localhost:8080/charts",
)


def episode(**kw):
    base = dict(
        symbol="ICM:XAUUSD", side="BUY", lots=0.13,
        ts=datetime(2026, 7, 14, 8, 0, 4, tzinfo=UTC),
        closed_at=datetime(2026, 7, 14, 14, 10, 33, tzinfo=UTC),
        fill_price=2609.94, close_price=2621.40,
        gross_pnl=148.98, commission=-0.91, swap=-0.22, net_pnl=147.85,
        duration_s=22229, ticket=88412,
        thesis="structure is the trade", rationale_md="fuller reasoning",
        setup="vwap pullback", factors=["trend:1h-up", "level:vwap-touch"],
        charts=["/lab/state/charts/2026-07-14T08/XAUUSD-1h.png"],
    )
    base.update(kw)
    return base


def test_uuid_recipe_matches_the_apps_signature():
    """Replicate the app's exact pipe-join by hand for one known trade."""
    row = to_trade_row(episode(), T)
    sig = "|".join([
        "local-dashboard-user", "LAB-XAU", "XAUUSD",
        "2026-07-14T08:00:04+00:00", "2026-07-14T14:10:33+00:00",
        "2609.94", "2621.4", "13", "88412", "88412",
        "22229.0", "Long", "148.98", "0.91",
    ])
    assert row["id"] == str(uuid.uuid5(NAMESPACE, sig))


def test_same_episode_same_uuid_every_time():
    """Idempotency lives or dies here."""
    assert to_trade_row(episode(), T)["id"] == to_trade_row(episode(), T)["id"]


def test_different_trades_get_different_uuids():
    a = to_trade_row(episode(), T)
    b = to_trade_row(episode(ticket=99999), T)
    assert a["id"] != b["id"]


def test_pnl_is_gross_and_commission_positive():
    """The app computes pnl - commission itself. Pre-subtracting double-counts;
    a negative commission would ADD to displayed pnl."""
    row = to_trade_row(episode(), T)
    assert row["pnl"] == 148.98          # gross, not 147.85
    assert row["commission"] == 0.91     # positive magnitude, not -0.91


def test_side_is_long_short_and_time_in_seconds():
    row = to_trade_row(episode(), T)
    assert row["side"] == "Long"
    assert row["timeInPosition"] == 22229.0
    assert to_trade_row(episode(side="SELL"), T)["side"] == "Short"


def test_dates_are_utc_iso_strings():
    """The app sorts and range-filters dates LEXICALLY. Non-ISO breaks ordering
    silently."""
    row = to_trade_row(episode(), T)
    assert row["entryDate"] == "2026-07-14T08:00:04+00:00"
    assert isinstance(row["entryDate"], str) and isinstance(row["entryPrice"], str)


def test_images_are_urls_not_paths():
    row = to_trade_row(episode(), T)
    assert row["images"] == ["http://localhost:8080/charts/2026-07-14T08/XAUUSD-1h.png"]


def test_rationale_and_factors_survive_the_lossy_mapping():
    row = to_trade_row(episode(), T)
    assert "structure is the trade" in row["comment"]
    assert "fuller reasoning" in row["comment"]
    assert row["tags"][0] == "vwap-pullback"
    assert "trend:1h-up" in row["tags"]


def test_trade_uuid_handles_nullish_as_empty_string():
    a = trade_uuid({"userId": "u", "entryId": None})
    b = trade_uuid({"userId": "u", "entryId": ""})
    assert a == b
