"""The A/B that could sink the project: beliefs arm vs control arm, identical
gates and sizing, compared on mean R with a real test.

Nobody has published a leakage-controlled ablation showing a memory module adds
out-of-sample alpha. This module is the honest attempt. If it says the beliefs
add nothing, we say so and keep the journal and the map — both independently
valuable — and drop the belief layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import Config
from .store import Store


class LiveReadinessError(RuntimeError):
    """The configured experiment has not earned permission to trade live."""


@dataclass(frozen=True)
class ArmStats:
    arm: str
    n: int
    mean_r: float
    sd: float


@dataclass(frozen=True)
class ABResult:
    beliefs: ArmStats
    control: ArmStats
    diff: float  # beliefs mean_R - control mean_R
    t_stat: float
    p_value: float  # two-sided, Welch
    reached_sample: bool
    passed: bool

    def render(self) -> str:
        lines = [
            f"{'arm':10} {'n':>5} {'mean_R':>9} {'sd':>7}",
            f"{self.beliefs.arm:10} {self.beliefs.n:>5} {self.beliefs.mean_r:>+9.3f} {self.beliefs.sd:>7.2f}",
            f"{self.control.arm:10} {self.control.n:>5} {self.control.mean_r:>+9.3f} {self.control.sd:>7.2f}",
            "",
            f"diff (beliefs - control): {self.diff:+.3f} R   Welch t={self.t_stat:.2f}   p={self.p_value:.3f}",
        ]
        if not self.reached_sample:
            lines.append("PRE-REGISTERED SAMPLE NOT REACHED — no conclusion may be drawn yet.")
        elif self.passed:
            lines.append("PASSED: beliefs arm outperforms at the pre-registered threshold.")
        else:
            lines.append(
                "NOT PASSED: no evidence the belief layer adds anything. The honest "
                "outcome is to publish this, keep the journal and the map, and drop "
                "or rethink the belief layer."
            )
        return "\n".join(lines)


def _arm(store: Store, arm: str) -> ArmStats:
    rows = store.query(
        "SELECT r_multiple FROM episode WHERE arm = %s AND r_multiple IS NOT NULL",
        (arm,),
    )
    rs = [float(r["r_multiple"]) for r in rows]
    n = len(rs)
    if n < 2:
        return ArmStats(arm, n, sum(rs) / n if n else 0.0, 0.0)
    mean = sum(rs) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in rs) / (n - 1))
    return ArmStats(arm, n, mean, sd)


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def run(cfg: Config, store: Store) -> ABResult:
    exp = cfg.raw.get("experiment", {})
    min_n = int(exp.get("min_trades_per_arm", 100))  # pre-registered. Never edit after data.

    b = _arm(store, "beliefs")
    c = _arm(store, "control")

    if b.n < 2 or c.n < 2 or b.sd == 0 or c.sd == 0:
        return ABResult(b, c, b.mean_r - c.mean_r, 0.0, 1.0, False, False)

    se = math.sqrt(b.sd**2 / b.n + c.sd**2 / c.n)
    t = (b.mean_r - c.mean_r) / se
    p = 2.0 * (1.0 - _phi(abs(t)))  # normal approx; fine at the pre-registered n

    reached = b.n >= min_n and c.n >= min_n
    passed = reached and t > 0 and p < 0.05
    return ABResult(b, c, b.mean_r - c.mean_r, t, p, reached, passed)


def assert_live_ready(cfg: Config, store: Store) -> None:
    """Recompute the proof from broker-joined episodes at process start.

    ``experiment.ab_passed`` is only the human acknowledgement required by
    config loading. It is not evidence and cannot substitute for the database.
    """
    if cfg.mode != "live":
        return
    result = run(cfg, store)
    if not result.passed:
        raise LiveReadinessError(
            "LIVE REFUSED: the current episode database does not pass the "
            "pre-registered beliefs-vs-control A/B.\n" + result.render()
        )
