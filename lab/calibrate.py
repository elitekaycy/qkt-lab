"""Conviction calibration: does the model know when it's right?

Buckets closed trades by the conviction stated at decision time and computes mean
realized R per bucket. If — and only if — the relationship is monotone with
separating confidence intervals does `sizing.stage: fitted` become defensible.

If conviction is uncorrelated with outcome, sizing stays flat forever, and we have
learned something no prompt engineering would surface: the model thinks it knows
when it is right, and it doesn't.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .store import Store

BUCKETS = [(0.0, 0.3), (0.3, 0.6), (0.6, 0.8), (0.8, 1.01)]


@dataclass(frozen=True)
class Bucket:
    lo: float
    hi: float
    n: int
    mean_r: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class Calibration:
    buckets: list[Bucket]
    monotone: bool
    separated: bool
    fit: dict[str, float] | None  # slope/intercept for sizing, only if earned

    @property
    def supports_fitted(self) -> bool:
        return self.monotone and self.separated

    def render(self) -> str:
        lines = ["conviction   n      mean_R      95% CI"]
        for b in self.buckets:
            lines.append(
                f"{b.lo:.1f}-{b.hi:.1f}    {b.n:4d}   {b.mean_r:+8.3f}   "
                f"[{b.ci_low:+.3f}, {b.ci_high:+.3f}]"
            )
        verdict = (
            "SUPPORTS fitted sizing (monotone, intervals separate)"
            if self.supports_fitted
            else "does NOT support fitted sizing — stage stays flat"
        )
        return "\n".join(lines) + f"\n\n{verdict}"


def run(store: Store) -> Calibration:
    rows = store.query(
        "SELECT conviction, r_multiple FROM episode "
        "WHERE conviction IS NOT NULL AND r_multiple IS NOT NULL"
    )
    buckets: list[Bucket] = []
    for lo, hi in BUCKETS:
        rs = [float(r["r_multiple"]) for r in rows if lo <= float(r["conviction"]) < hi]
        n = len(rs)
        if n < 2:
            buckets.append(Bucket(lo, min(hi, 1.0), n, 0.0, 0.0, 0.0))
            continue
        mean = sum(rs) / n
        sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (n - 1))
        half = 1.96 * sd / math.sqrt(n)
        buckets.append(Bucket(lo, min(hi, 1.0), n, mean, mean - half, mean + half))

    populated = [b for b in buckets if b.n >= 20]
    monotone = len(populated) >= 3 and all(
        a.mean_r < b.mean_r for a, b in zip(populated, populated[1:], strict=False)
    )
    # "Separated" = the top populated bucket's CI floor clears the bottom's ceiling.
    separated = len(populated) >= 2 and populated[-1].ci_low > populated[0].ci_high

    fit = None
    if monotone and separated:
        # Least squares of mean_R on bucket midpoint -> a multiplier line centred
        # so f(overall mean conviction) ~ 1.0. Kelly damping happens in sizing.
        xs = [(b.lo + b.hi) / 2 for b in populated]
        ys = [b.mean_r for b in populated]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        denom = sum((x - mx) ** 2 for x in xs)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denom
        # Normalize into multiplier space: neutral at the mean bucket.
        fit = {
            "slope": round(slope / max(abs(my), 0.1), 3),
            "intercept": 1.0 - round(slope / max(abs(my), 0.1), 3) * mx,
        }

    return Calibration(buckets, monotone, separated, fit)
