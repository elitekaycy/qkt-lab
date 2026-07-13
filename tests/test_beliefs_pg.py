"""The end-to-end noise test against a real Postgres: 200 random-walk trades,
40 pure-noise candidate beliefs, one full rescore cycle -> ZERO activations.

This is the acceptance criterion that separates this loop from every published
memory-trading agent: the distiller can propose whatever it likes; the scorer
must not let noise through.
"""

from __future__ import annotations

import dataclasses
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lab.beliefs import rescore_all, score
from lab.store import Decision, Store
from tests.conftest import cfg_with

DSN = os.environ.get("LAB_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="LAB_TEST_DSN not set")

ROOT = Path(__file__).resolve().parents[1]

SESSIONS = ["asia", "london", "ny"]
FACTORS = ["level:vwap-touch", "level:pdh", "trend:1h-up", "trend:1h-down",
           "vol:atr-high", "vol:atr-normal"]


@pytest.fixture
def store():
    s = Store(DSN)
    s.migrate(ROOT / "db" / "schema.sql")
    with s._conn() as c:
        c.execute("TRUNCATE outcome, decision RESTART IDENTITY CASCADE")
        c.commit()
    return s


def seed_random_trades(store: Store, n: int, rng: random.Random) -> None:
    """Trades whose outcomes are pure noise: mean-zero R, no structure at all."""
    t0 = datetime(2026, 5, 1, tzinfo=UTC)
    for i in range(n):
        ticket = 10_000 + i
        store.record(Decision(
            as_name="lab-xau", symbol="ICM:XAUUSD", action="TRADE",
            side=rng.choice(["BUY", "SELL"]),
            lots=0.13, sl=2600.0, tp=2620.0, conviction=rng.random(),
            setup=rng.choice(["vwap-pullback", "range-fade", "print-follow"]),
            factors=rng.sample(FACTORS, k=2),
            regime={"session": rng.choice(SESSIONS),
                    "atr14": round(rng.uniform(2.0, 6.0), 2)},
            ticket=ticket, fill_price=2610.0, accepted=True,
            risk_at_entry=50.0, equity_at_entry=10000.0,
        ))
        r = rng.gauss(0.0, 1.0)  # NO edge, by construction
        store.record_outcome(
            ticket=ticket, closed_at=t0 + timedelta(hours=i * 6),
            close_price=2610.0 + r, gross_pnl=r * 50.0, commission=-0.9, swap=0.0,
            net_pnl=r * 50.0, r_multiple=r, lots_closed=0.13,
            duration_s=3600, deals=[],
        )


def noise_belief(i: int, rng: random.Random) -> str:
    session = rng.choice(SESSIONS)
    factor = rng.choice(FACTORS)
    return f"""---
id: noise-{i:02}
status: CANDIDATE
statement: "made-up lesson {i}"
symbols: [ICM:XAUUSD]
predicate:
  - symbol = ICM:XAUUSD
  - regime.session = {session}
  - factors contains {factor}
---
"""


def test_forty_noise_beliefs_zero_activations(store, cfg, tmp_path):
    rng = random.Random(1729)
    seed_random_trades(store, 200, rng)

    beliefs_dir = tmp_path / "beliefs"
    beliefs_dir.mkdir()
    for i in range(40):
        (beliefs_dir / f"noise-{i:02}.md").write_text(noise_belief(i, rng))

    c = cfg_with(cfg, beliefs=dataclasses.replace(cfg.beliefs, path=beliefs_dir))
    statuses = rescore_all(c, store)

    assert len(statuses) == 40
    activated = [b for b, s in statuses.items() if s == "ACTIVE"]
    assert activated == [], (
        f"noise activated: {activated} — the false-discovery gate has failed"
    )
    # And the files carry code-written evidence the model never touches.
    sample = (beliefs_dir / "noise-00.md").read_text()
    assert "supporting:" in sample and "refuting:" in sample


def test_a_real_edge_planted_in_the_noise_is_found(store, cfg, tmp_path):
    """The gate must not be so tight that nothing true can ever pass: plant a
    genuine +0.8R edge on london+vwap trades and it should activate."""
    rng = random.Random(42)
    seed_random_trades(store, 150, rng)

    # 45 additional trades with a REAL edge under a specific condition.
    t0 = datetime(2026, 6, 20, tzinfo=UTC)
    for i in range(45):
        ticket = 90_000 + i
        store.record(Decision(
            as_name="lab-xau", symbol="ICM:XAUUSD", action="TRADE", side="BUY",
            lots=0.13, sl=2600.0, conviction=0.6, setup="vwap-pullback",
            factors=["level:vwap-touch", "trend:1h-up"],
            regime={"session": "london", "atr14": 4.0},
            ticket=ticket, fill_price=2610.0, accepted=True,
            risk_at_entry=50.0, equity_at_entry=10000.0,
        ))
        r = rng.gauss(0.8, 1.0)  # real positive edge
        store.record_outcome(
            ticket=ticket, closed_at=t0 + timedelta(hours=i * 3),
            close_price=2612.0, gross_pnl=r * 50, commission=-0.9, swap=0.0,
            net_pnl=r * 50, r_multiple=r, lots_closed=0.13, duration_s=3600,
            deals=[],
        )

    beliefs_dir = tmp_path / "beliefs"
    beliefs_dir.mkdir()
    (beliefs_dir / "real-edge.md").write_text("""---
id: real-edge
status: CANDIDATE
statement: "london vwap pullbacks resolve up"
symbols: [ICM:XAUUSD]
predicate:
  - symbol = ICM:XAUUSD
  - side = BUY
  - regime.session = london
  - factors contains level:vwap-touch
---
""")
    for i in range(10):
        (beliefs_dir / f"noise-{i:02}.md").write_text(noise_belief(i, rng))

    c = cfg_with(cfg, beliefs=dataclasses.replace(cfg.beliefs, path=beliefs_dir))
    statuses = rescore_all(c, store)
    assert statuses["real-edge"] == "ACTIVE"


def test_scoring_counts_incidental_matches_too(store, cfg):
    """A belief is scored over every matching trade — including trades it never
    influenced. Self-confirmation dies here."""
    rng = random.Random(7)
    seed_random_trades(store, 60, rng)
    s = score(store, "any", ["symbol = ICM:XAUUSD", "regime.session = london"])
    # None of these trades cited any belief, yet they all count.
    assert s.n > 0
    assert s.n == len(s.supporting) + len(s.refuting)


def test_unevaluable_belief_is_rejected_on_disk(store, cfg, tmp_path):
    beliefs_dir = tmp_path / "beliefs"
    beliefs_dir.mkdir()
    (beliefs_dir / "prose.md").write_text("""---
id: prose
status: CANDIDATE
statement: "gold rises when people are scared"
predicate:
  - people are scared
---
""")
    c = cfg_with(cfg, beliefs=dataclasses.replace(cfg.beliefs, path=beliefs_dir))
    statuses = rescore_all(c, store)
    assert "prose" not in statuses  # not scored
    assert "REJECTED" in (beliefs_dir / "prose.md").read_text()
