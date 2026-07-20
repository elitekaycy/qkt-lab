"""The live gate and the A/B: `mode: live` must be a refusal in code, and the
A/B must be honest about not-enough-data."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from lab import config as cfgmod
from lab.experiment import LiveReadinessError, assert_live_ready
from lab.experiment import run as ab_run
from tests.conftest import cfg_with

ROOT = Path(__file__).resolve().parents[1]


def test_live_mode_refuses_without_ab_pass(tmp_path, monkeypatch):
    """Not a warning. A refusal, in code, at config load."""
    monkeypatch.setenv("LAB_DATABASE_URL", "postgresql://x")
    raw = yaml.safe_load((ROOT / "lab.yaml").read_text())
    raw["lab"]["mode"] = "live"
    p = tmp_path / "lab.yaml"
    # keep relative paths resolvable
    raw["instruments"][0]["playbook"] = str(ROOT / "playbooks" / "xauusd.md")
    p.write_text(yaml.safe_dump(raw))
    with pytest.raises(cfgmod.ConfigError, match="ab_passed"):
        cfgmod.load(p)


def test_live_mode_with_ab_passed_loads(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_DATABASE_URL", "postgresql://x")
    raw = yaml.safe_load((ROOT / "lab.yaml").read_text())
    raw["lab"]["mode"] = "live"
    raw.setdefault("experiment", {})["ab_passed"] = True
    raw["instruments"][0]["playbook"] = str(ROOT / "playbooks" / "xauusd.md")
    p = tmp_path / "lab.yaml"
    p.write_text(yaml.safe_dump(raw))
    assert cfgmod.load(p).mode == "live"


class FakeStore:
    def __init__(self, beliefs_rs, control_rs):
        self.data = {"beliefs": beliefs_rs, "control": control_rs}

    def query(self, sql, params=()):
        return [{"r_multiple": r} for r in self.data[params[0]]]


def _cfg_with_min(cfg, n):
    import dataclasses

    raw = copy.deepcopy(cfg.raw)
    raw.setdefault("experiment", {})["min_trades_per_arm"] = n
    return dataclasses.replace(cfg, raw=raw)


def test_ab_below_sample_draws_no_conclusion(cfg):
    """Peeking early and concluding is p-hacking with extra steps."""
    store = FakeStore([1.0, 2.0, 1.5] * 10, [0.1, -0.2, 0.0] * 10)
    r = ab_run(_cfg_with_min(cfg, 100), store)
    assert not r.reached_sample and not r.passed
    assert "SAMPLE NOT REACHED" in r.render()


def test_ab_beliefs_outperform_passes(cfg):
    import random

    rng = random.Random(3)
    beliefs = [rng.gauss(0.5, 1.0) for _ in range(150)]
    control = [rng.gauss(0.0, 1.0) for _ in range(150)]
    r = ab_run(_cfg_with_min(cfg, 100), FakeStore(beliefs, control))
    assert r.reached_sample and r.passed


def test_ab_no_difference_reports_not_passed_honestly(cfg):
    import random

    rng = random.Random(9)
    beliefs = [rng.gauss(0.1, 1.0) for _ in range(150)]
    control = [rng.gauss(0.1, 1.0) for _ in range(150)]
    r = ab_run(_cfg_with_min(cfg, 100), FakeStore(beliefs, control))
    assert r.reached_sample and not r.passed
    assert "NOT PASSED" in r.render()


def test_demo_runtime_does_not_require_ab_proof(cfg):
    assert_live_ready(cfg, FakeStore([], []))


def test_live_runtime_recomputes_ab_instead_of_trusting_flag(cfg):
    live = cfg_with(cfg, mode="live")
    with pytest.raises(LiveReadinessError, match="LIVE REFUSED"):
        assert_live_ready(live, FakeStore([], []))


def test_live_runtime_allows_a_database_result_that_really_passes(cfg):
    import random

    rng = random.Random(3)
    beliefs = [rng.gauss(0.5, 1.0) for _ in range(150)]
    control = [rng.gauss(0.0, 1.0) for _ in range(150)]
    assert_live_ready(cfg_with(cfg, mode="live"), FakeStore(beliefs, control))
