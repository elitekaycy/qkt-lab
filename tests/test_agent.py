"""Proposal validation: garbage from the model must fail loudly here, never be
coerced into something plausible downstream."""

from __future__ import annotations

import subprocess

import pytest

from lab.agent import AgentError, _extract_json, run, run_text, validate


def ok_trade(**kw):
    base = {
        "action": "TRADE",
        "side": "BUY",
        "sl": 2606.2,
        "tp": 2621.4,
        "conviction": 0.6,
        "setup": "x",
        "factors": ["a:b"],
        "regime": {},
        "thesis": "t",
        "invalidation": "i",
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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sl", float("nan")),
        ("tp", float("inf")),
        ("conviction", float("-inf")),
        ("expected_rr", "NaN"),
    ],
)
def test_non_finite_trade_numbers_are_rejected(field, value):
    with pytest.raises(AgentError, match="finite"):
        validate(ok_trade(**{field: value}))


def test_non_numeric_trade_number_is_rejected_cleanly():
    with pytest.raises(AgentError, match="sl must be a number"):
        validate(ok_trade(sl="below support"))


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


def test_codex_proposal_is_headless_ephemeral_and_has_no_tools(monkeypatch, tmp_path):
    prompt = tmp_path / "trader.md"
    prompt.write_text("You only propose.")
    image = tmp_path / "chart.png"
    image.touch()
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout='{"action":"NO_TRADE","conviction":0.1}',
            stderr="progress stays off stdout",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    raw, sha = run(
        prompt,
        {"quote": {"bid": 1}},
        provider="codex",
        agent_bin="codex",
        model="gpt-test",
        images=[image],
        cwd=tmp_path,
    )

    cmd = captured["cmd"]
    assert cmd[:2] == ["codex", "exec"]
    assert "--ephemeral" in cmd
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert "shell_tool" in cmd and "apps" in cmd and "multi_agent" in cmd
    assert "--search" not in cmd
    assert cmd[-1] == "-"
    assert str(image.resolve()) in cmd
    assert captured["kwargs"]["input"].startswith('{\n  "quote"')
    assert raw["action"] == "NO_TRADE"
    assert len(sha) == 16


def test_codex_research_gets_web_and_memory_workspace(monkeypatch, tmp_path):
    prompt = tmp_path / "researcher.md"
    prompt.write_text("Write durable research.")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(cmd, 0, stdout="done", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    text, _ = run_text(
        prompt,
        "refresh the calendar",
        provider="codex",
        agent_bin="codex",
        model="gpt-test",
        research=True,
        cwd=tmp_path,
        env={"PATH": "/bin"},
    )

    cmd = captured["cmd"]
    assert cmd[cmd.index("--sandbox") + 1] == "workspace-write"
    assert 'web_search="live"' in cmd
    assert "shell_tool" not in cmd
    assert captured["kwargs"]["cwd"] == tmp_path
    assert captured["kwargs"]["env"] == {"PATH": "/bin"}
    assert text == "done"


def test_codex_research_uses_outer_container_sandbox_without_shell(monkeypatch, tmp_path):
    prompt = tmp_path / "researcher.md"
    prompt.write_text("Write only memory artifacts.")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="done", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_text(
        prompt,
        "refresh",
        provider="codex",
        agent_bin="codex",
        model="gpt-test",
        research=True,
        external_sandbox=True,
        cwd=tmp_path,
    )

    cmd = captured["cmd"]
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "--sandbox" not in cmd
    assert "shell_tool" in cmd
    assert 'web_search="live"' in cmd
