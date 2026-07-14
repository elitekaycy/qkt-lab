"""Episode study: does risk-off move gold, and when does the sign flip?

The claim under test is the map's most load-bearing edge pair:
    equity-drawdown -> risk-off -> gold UP (safe-haven bid)
    ...EXCEPT under dollar-funding stress, where gold sells off WITH equities
    (gold is what you sell when you need dollars).

Method: 25 years of keyless daily data (Yahoo v8 chart, GC=F and ^GSPC).
An episode is a day where SPX falls at least 2%. We measure gold's same-day
and next-day return across all episodes, then inside known funding-stress
windows (Lehman Sep-Dec 2008, COVID dash-for-cash Mar 2020), then outside them.

Run:  python3 studies/risk_off_gold.py
Output is the evidence block pasted into memory/map/risk-off.md, with n's.
"""

from __future__ import annotations

import datetime as dt
import statistics

import httpx

UA = {"User-Agent": "Mozilla/5.0 (qkt-lab episode study)"}
STRESS_WINDOWS = [
    (dt.date(2008, 9, 1), dt.date(2008, 12, 31)),
    (dt.date(2020, 3, 1), dt.date(2020, 3, 31)),
]


def daily_closes(ticker: str) -> dict[dt.date, float]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
    r = httpx.get(url, params={"range": "25y", "interval": "1d"}, headers=UA, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    out = {}
    for t, c in zip(ts, closes, strict=True):
        if c is not None:
            out[dt.datetime.fromtimestamp(t, dt.UTC).date()] = float(c)
    if len(out) < 5000:
        raise SystemExit(f"{ticker}: only {len(out)} closes — data quality gate failed")
    return out


def returns(closes: dict[dt.date, float]) -> dict[dt.date, float]:
    days = sorted(closes)
    return {d2: closes[d2] / closes[d1] - 1.0 for d1, d2 in zip(days, days[1:], strict=False)}


def in_stress(d: dt.date) -> bool:
    return any(a <= d <= b for a, b in STRESS_WINDOWS)


def describe(label: str, rows: list[tuple[float, float]]) -> None:
    if not rows:
        print(f"{label:34} n=0")
        return
    same = [r[0] for r in rows]
    nxt = [r[1] for r in rows if r[1] is not None]
    pos = sum(1 for r in same if r > 0)
    print(
        f"{label:34} n={len(rows):3}  same-day mean {statistics.mean(same) * 100:+.2f}% "
        f"(gold up {pos}/{len(same)})  next-day mean {statistics.mean(nxt) * 100:+.2f}%"
    )


def main() -> None:
    spx = returns(daily_closes("%5EGSPC"))
    gold = returns(daily_closes("GC=F"))
    gold_days = sorted(gold)

    episodes: list[tuple[dt.date, float, float | None]] = []
    for d, r in sorted(spx.items()):
        if r > -0.02 or d not in gold:
            continue
        later = [g for g in gold_days if g > d]
        episodes.append((d, gold[d], gold[later[0]] if later else None))

    print(f"episodes (SPX <= -2%): {len(episodes)} over {gold_days[0]} .. {gold_days[-1]}\n")
    describe("ALL episodes", [(s, n) for _, s, n in episodes])
    describe("funding stress (2008-Q4, 2020-03)", [(s, n) for d, s, n in episodes if in_stress(d)])
    describe("outside stress windows", [(s, n) for d, s, n in episodes if not in_stress(d)])

    # Daily means hide the funding-stress inversion: it plays out over weeks of
    # forced liquidation, not on the crash day itself. Cumulative window view:
    spx_px = daily_closes("%5EGSPC")
    gold_px = daily_closes("GC=F")
    print()

    def window(px: dict[dt.date, float], a: dt.date, b: dt.date) -> tuple[float, float, float]:
        vals = [px[d] for d in sorted(px) if a <= d <= b]
        return vals[0], min(vals), vals[-1]

    for a, b in STRESS_WINDOWS:
        s0, smin, s1 = window(spx_px, a, b)
        g0, gmin, g1 = window(gold_px, a, b)
        print(
            f"stress {a}..{b}:  SPX {(s1 / s0 - 1) * 100:+.1f}% (trough {(smin / s0 - 1) * 100:+.1f}%)   "
            f"GOLD {(g1 / g0 - 1) * 100:+.1f}% (trough {(gmin / g0 - 1) * 100:+.1f}%)"
        )


if __name__ == "__main__":
    main()
