"""Distillation: proposals validated, model-sent statuses discarded, calibration
honest about small samples."""

from __future__ import annotations

import dataclasses

from lab.calibrate import Calibration
from lab.calibrate import run as calibrate_run
from lab.distill import apply_ops
from tests.conftest import cfg_with


def beliefs_cfg(cfg, tmp_path):
    return cfg_with(cfg, beliefs=dataclasses.replace(cfg.beliefs, path=tmp_path / "beliefs"))


def test_add_writes_a_candidate_and_discards_model_status(cfg, tmp_path):
    c = beliefs_cfg(cfg, tmp_path)
    got = apply_ops(c, [{
        "op": "ADD", "id": "gold-vwap-london",
        "status": "ACTIVE",  # the model trying to bless itself
        "statement": "vwap pullbacks resolve up",
        "predicate": ["symbol = ICM:XAUUSD", "regime.session = london"],
        "mechanism": "[[london-liquidity]]",
    }])
    assert got["gold-vwap-london"] == "written"
    text = (c.beliefs.path / "gold-vwap-london.md").read_text()
    assert "status: CANDIDATE" in text
    assert "ACTIVE" not in text  # the self-blessing did not survive


def test_prose_predicate_is_rejected(cfg, tmp_path):
    c = beliefs_cfg(cfg, tmp_path)
    got = apply_ops(c, [{
        "op": "ADD", "id": "vibes",
        "predicate": ["gold rises when people are scared"],
    }])
    assert got["vibes"].startswith("rejected")
    assert not (c.beliefs.path / "vibes.md").exists()


def test_edit_resets_to_candidate(cfg, tmp_path):
    """An edited predicate is a NEW hypothesis — its old evidence doesn't carry."""
    c = beliefs_cfg(cfg, tmp_path)
    apply_ops(c, [{"op": "ADD", "id": "b1", "predicate": ["side = BUY"]}])
    p = c.beliefs.path / "b1.md"
    p.write_text(p.read_text().replace("status: CANDIDATE", "status: ACTIVE"))
    apply_ops(c, [{"op": "EDIT", "id": "b1", "predicate": ["side = SELL"]}])
    assert "status: CANDIDATE" in p.read_text()


def test_add_on_existing_is_skipped_not_overwritten(cfg, tmp_path):
    c = beliefs_cfg(cfg, tmp_path)
    apply_ops(c, [{"op": "ADD", "id": "b1", "predicate": ["side = BUY"]}])
    got = apply_ops(c, [{"op": "ADD", "id": "b1", "predicate": ["side = SELL"]}])
    assert got["b1"].startswith("skipped")


class FakeStore:
    def __init__(self, rows):
        self.rows = rows

    def query(self, sql, params=()):
        return self.rows


def test_calibration_small_sample_does_not_support_fitted():
    rows = [{"conviction": 0.9, "r_multiple": 2.0}] * 5 + [
        {"conviction": 0.1, "r_multiple": -1.0}] * 5
    cal = calibrate_run(FakeStore(rows))
    assert not cal.supports_fitted  # n<20 per bucket: no promotion on 10 trades


def test_calibration_monotone_separated_supports_fitted():
    rows = (
        [{"conviction": 0.15, "r_multiple": -0.1 + 0.02 * i} for i in range(40)]
        + [{"conviction": 0.45, "r_multiple": 0.15 + 0.02 * i} for i in range(40)]
        + [{"conviction": 0.7, "r_multiple": 0.5 + 0.02 * i} for i in range(40)]
        + [{"conviction": 0.9, "r_multiple": 0.9 + 0.02 * i} for i in range(40)]
    )
    cal = calibrate_run(FakeStore(rows))
    assert cal.monotone and cal.separated and cal.supports_fitted
    assert cal.fit and cal.fit["slope"] > 0


def test_calibration_flat_conviction_yields_no_fit():
    """The model thinks it knows when it's right, and it doesn't: same R
    distribution in every bucket."""
    rows = [
        {"conviction": c, "r_multiple": 0.1 + 0.01 * (i % 7)}
        for i, c in enumerate([0.1, 0.4, 0.7, 0.9] * 60)
    ]
    cal = calibrate_run(FakeStore(rows))
    assert not cal.supports_fitted
    assert cal.fit is None
    assert isinstance(cal, Calibration)
