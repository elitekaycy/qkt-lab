"""Proposal validation: garbage from the model must fail loudly here, never be
coerced into something plausible downstream."""

from __future__ import annotations

import pytest

from lab.agent import AgentError, _extract_json, validate


def ok_trade(**kw):
    base = {
        "action": "TRADE", "side": "BUY", "sl": 2606.2, "tp": 2621.4,
        "conviction": 0.6, "setup": "x", "factors": ["a:b"], "regime": {},
        "thesis": "t", "invalidation": "i",
    }
    base.update(kw)
    return base


def test_valid_trade_passes():
    p = validate(ok_trade())
    assert p.wants_trade and p.side == "BUY" and p.sl == 2606.2


def test_no_trade_needs_no_side_or_stop():
    p = validate({"action": "NO_TRADE", "conviction": 0.2, "thesis": "nothing on"})
    assert not p.wants_trade


def test_unknown_action_rejected():
    with pytest.raises(AgentError):
        validate(ok_trade(action="MAYBE"))


def test_trade_without_stop_rejected():
    with pytest.raises(AgentError):
        validate(ok_trade(sl=None))


def test_trade_without_side_rejected():
    with pytest.raises(AgentError):
        validate(ok_trade(side=None))


def test_conviction_out_of_range_rejected():
    """A conviction of 7 must not be clamped into looking calibrated."""
    with pytest.raises(AgentError):
        validate(ok_trade(conviction=7))
    with pytest.raises(AgentError):
        validate(ok_trade(conviction=-0.1))


def test_extract_bare_json():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    got = _extract_json('Here you go:\n```json\n{"a": 1}\n```\nthanks')
    assert got == {"a": 1}


def test_extract_json_with_preamble():
    got = _extract_json('Sure! {"action": "NO_TRADE", "conviction": 0.1}')
    assert got["action"] == "NO_TRADE"


def test_no_json_at_all_raises():
    with pytest.raises(AgentError):
        _extract_json("I think we should buy gold.")
