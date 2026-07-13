"""Retrieval: context-conditioned, candidate-withholding, arm-aware."""

from __future__ import annotations

import dataclasses

from lab.retrieve import retrieve
from tests.conftest import cfg_with


def write(path, meta_lines, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + "\n".join(meta_lines) + "\n---\n" + body)


def mem_cfg(cfg, tmp_path):
    beliefs = dataclasses.replace(cfg.beliefs, path=tmp_path / "beliefs")
    return cfg_with(cfg, memory_root=tmp_path, beliefs=beliefs)


CPI_EVENT = [
    {"event": "US CPI", "at": "2026-07-14T12:30:00Z", "impact": "high", "affects": ["ICM:XAUUSD"]}
]


def test_candidate_beliefs_are_withheld(cfg, tmp_path):
    """If the model could see CANDIDATE beliefs it would act on them and they
    would confirm themselves. Only ACTIVE enters the packet."""
    c = mem_cfg(cfg, tmp_path)
    write(
        c.beliefs.path / "active-one.md",
        [
            "id: active-one",
            "status: ACTIVE",
            "statement: vwap pullbacks resolve up",
            "symbols: [ICM:XAUUSD]",
        ],
        "n: 34 mean_R: +0.31",
    )
    write(
        c.beliefs.path / "cand-one.md",
        [
            "id: cand-one",
            "status: CANDIDATE",
            "statement: fridays are bearish",
            "symbols: [ICM:XAUUSD]",
        ],
        "n: 12",
    )
    s = retrieve(c, c.instruments[0], events=[], arm="beliefs")
    assert "active-one" in s.belief_ids
    assert "cand-one" not in s.belief_ids
    assert "fridays" not in s.beliefs_text


def test_control_arm_gets_no_beliefs(cfg, tmp_path):
    """The A/B isolates the tactical-belief layer. Control keeps playbook + map."""
    c = mem_cfg(cfg, tmp_path)
    write(
        c.beliefs.path / "active-one.md",
        ["id: active-one", "status: ACTIVE", "statement: s", "symbols: [XAUUSD]"],
        "",
    )
    s = retrieve(c, c.instruments[0], events=[], arm="control")
    assert s.belief_ids == [] and s.beliefs_text == ""


def test_map_retrieval_is_event_conditioned(cfg, tmp_path):
    """CPI in the window pulls inflation nodes; mine-supply stays on disk."""
    c = mem_cfg(cfg, tmp_path)
    write(
        tmp_path / "map" / "inflation-surprise.md",
        ["id: inflation-surprise", "instruments: [XAUUSD]", "retrieve_on: [cpi]"],
        "hot CPI -> rate repricing -> gold",
    )
    write(
        tmp_path / "map" / "mine-supply.md",
        ["id: mine-supply", "instruments: [XAUUSD]", "retrieve_on: [supply report]"],
        "mine output moves slowly",
    )
    s = retrieve(c, c.instruments[0], events=CPI_EVENT)
    assert "inflation-surprise" in s.map_ids
    assert "mine-supply" not in s.map_ids

    s2 = retrieve(c, c.instruments[0], events=[])
    assert "inflation-surprise" not in s2.map_ids


def test_always_nodes_are_pinned(cfg, tmp_path):
    c = mem_cfg(cfg, tmp_path)
    write(
        tmp_path / "map" / "real-yields.md",
        ["id: real-yields", "instruments: [XAUUSD]", "always: true"],
        "the core driver",
    )
    s = retrieve(c, c.instruments[0], events=[])
    assert "real-yields" in s.map_ids


def test_budget_bounds_the_slice(cfg, tmp_path):
    """Growth in knowledge must not mean growth in context."""
    c = mem_cfg(cfg, tmp_path)
    for i in range(50):
        write(
            tmp_path / "map" / f"node-{i:02}.md",
            [f"id: node-{i:02}", "instruments: [XAUUSD]", "always: true"],
            "x" * 1000,
        )
    s = retrieve(c, c.instruments[0], events=[])
    assert len(s.map_text) <= 8000 + 200
    assert len(s.map_ids) < 50
