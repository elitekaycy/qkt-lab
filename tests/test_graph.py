"""The causal graph: the AAPL scenario from the spec, executable.

Acceptance (docs/specs/phase-4-memory.md): given an equity drawdown, traversal
returns the multi-hop chains to XAUUSD including the risk-off/safe-haven
CONFLICT and the funding-stress INVERSION — never a silently resolved direction.
"""

from __future__ import annotations

from pathlib import Path

from lab.graph import Graph

ROOT = Path(__file__).resolve().parents[1]


def graph():
    return Graph.load(ROOT / "memory" / "map")


def test_shipped_map_loads():
    g = graph()
    assert {"real-yields", "dxy", "risk-off", "equity-drawdown",
            "central-bank-demand"} <= set(g.nodes)


def test_aapl_scenario_multi_hop():
    """equity-drawdown reaches gold through BOTH the fast risk-off legs and the
    slow growth-scare -> rate-cut leg."""
    t = graph().traverse("equity-drawdown", "XAUUSD")
    paths = {" -> ".join([c.hops[0].src] + [e.dst for e in c.hops]) for c in t.chains}
    assert "equity-drawdown -> risk-off -> XAUUSD" in paths
    assert "equity-drawdown -> risk-off -> usd-bid -> XAUUSD" in paths
    assert "equity-drawdown -> growth-scare -> rate-cut-repricing -> XAUUSD" in paths


def test_conflict_is_surfaced_not_resolved():
    """Two legs of the same event point in opposite directions. The graph must say
    CONFLICT and name the resolving condition — never pick a side silently."""
    t = graph().traverse("equity-drawdown", "XAUUSD")
    assert t.conflict
    assert "dollar-funding stress" in t.resolver
    rendered = t.render()
    assert "CONFLICT" in rendered


def test_net_sign_composes_along_the_chain():
    t = graph().traverse("equity-drawdown", "XAUUSD")
    by_path = {
        " -> ".join([c.hops[0].src] + [e.dst for e in c.hops]): c.net_sign
        for c in t.chains
    }
    # risk-off -> safe-haven bid: (+)(+) = +
    assert by_path["equity-drawdown -> risk-off -> XAUUSD"] == 1
    # risk-off -> usd-bid -> gold: (+)(+)(-) = -
    assert by_path["equity-drawdown -> risk-off -> usd-bid -> XAUUSD"] == -1


def test_lag_is_the_slowest_hop():
    t = graph().traverse("equity-drawdown", "XAUUSD")
    slow = next(c for c in t.chains
                if any(e.dst == "rate-cut-repricing" for e in c.hops))
    assert slow.slowest_lag == "1-3 days"


def test_inversion_conditions_ride_along():
    t = graph().traverse("equity-drawdown", "XAUUSD")
    fast = next(c for c in t.chains if len(c.hops) == 2 and c.hops[1].dst == "XAUUSD")
    assert any("INVERTS" in c for c in fast.conditions)


def test_unknown_path_is_a_research_candidate_not_an_error():
    t = graph().traverse("mine-supply-shock", "XAUUSD")
    assert t.chains == ()
    assert "research" in t.render()


def test_cycles_do_not_hang(tmp_path):
    (tmp_path / "a.md").write_text("---\nid: a\nedges: [{to: b, sign: '+'}]\n---\n")
    (tmp_path / "b.md").write_text("---\nid: b\nedges: [{to: a, sign: '+'}, {to: X, sign: '+'}]\n---\n")
    t = Graph.load(tmp_path).traverse("a", "X")
    assert len(t.chains) == 1
