"""The causal graph: typed edges, multi-hop traversal, conflicts surfaced.

A lookup table of "drivers of gold" cannot answer what Apple falling has to do
with gold — Apple is hops away, and the path runs through things that are.
This module walks those paths and, critically, REFUSES to silently resolve a
conflict: when two chains from one event point in opposite directions, both are
returned with the condition that decides between them. That ambiguity is the
edge — it is where everyone else is confidently wrong.

Storage is markdown + YAML frontmatter behind this interface, so swapping the
backend later (if traversal ever becomes a measured bottleneck) is a storage
change, not a rewrite of the reasoning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    sign: int  # +1 | -1
    strength: str  # strong | moderate | weak | contested
    lag: str
    channel: str
    dominates_when: str | None
    inverts_when: str | None
    evidence: str | None


@dataclass(frozen=True)
class Node:
    id: str
    kind: str  # asset | event | state | flow
    body: str
    edges: tuple[Edge, ...]


@dataclass(frozen=True)
class Chain:
    """One causal path from an observed event to the instrument."""

    hops: tuple[Edge, ...]

    @property
    def net_sign(self) -> int:
        s = 1
        for e in self.hops:
            s *= e.sign
        return s

    @property
    def slowest_lag(self) -> str:
        # The chain is only as fast as its slowest hop.
        order = {"same-day": 0, "1-3 days": 1, "days": 1, "weeks": 2, "months": 3}
        return max((e.lag for e in self.hops), key=lambda lag: order.get(lag, 1))

    @property
    def conditions(self) -> list[str]:
        out = []
        for e in self.hops:
            if e.inverts_when:
                out.append(f"{e.src}->{e.dst} INVERTS when {e.inverts_when}")
            if e.dominates_when:
                out.append(f"{e.src}->{e.dst} dominates when {e.dominates_when}")
        return out

    def render(self) -> str:
        path = " -> ".join([self.hops[0].src] + [e.dst for e in self.hops])
        sign = "+" if self.net_sign > 0 else "-"
        lines = [f"({sign}) {path}  [lag: {self.slowest_lag}]"]
        for e in self.hops:
            lines.append(f"    {e.src} -> {e.dst} ({'+' if e.sign > 0 else '-'}, "
                         f"{e.strength}, {e.lag}): {e.channel}")
        for c in self.conditions:
            lines.append(f"    ⚠ {c}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Traversal:
    chains: tuple[Chain, ...]
    conflict: bool
    resolver: str

    def render(self) -> str:
        if not self.chains:
            return "(no causal path known — candidate for research)"
        parts = [c.render() for c in self.chains]
        if self.conflict:
            parts.append(
                "⚠ CONFLICT: paths disagree on direction. Resolving conditions:\n  "
                + (self.resolver or "none recorded — treat direction as UNKNOWN")
            )
        return "\n\n".join(parts)


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text()
    m = re.match(r"\A---\n(.*?)\n---\n?(.*)\Z", text, re.S)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


class Graph:
    def __init__(self, nodes: dict[str, Node]):
        self.nodes = nodes

    @classmethod
    def load(cls, root: Path) -> Graph:
        nodes: dict[str, Node] = {}
        if not root.exists():
            return cls(nodes)
        for f in sorted(root.glob("*.md")):
            meta, body = _frontmatter(f)
            nid = str(meta.get("id", f.stem))
            edges = tuple(
                Edge(
                    src=nid,
                    dst=str(e["to"]),
                    sign=1 if str(e.get("sign", "+")).strip() in ("+", "1", "+1") else -1,
                    strength=str(e.get("strength", "moderate")),
                    lag=str(e.get("lag", "same-day")),
                    channel=str(e.get("channel", "")),
                    dominates_when=e.get("dominates_when"),
                    inverts_when=e.get("inverts_when"),
                    evidence=e.get("evidence"),
                )
                for e in (meta.get("edges") or [])
            )
            nodes[nid] = Node(id=nid, kind=str(meta.get("kind", "state")),
                              body=body.strip(), edges=edges)
        return cls(nodes)

    def traverse(self, source: str, target: str, max_hops: int = 4) -> Traversal:
        """Every acyclic path from source to target, up to max_hops.

        Conflict detection is the point: if the chains disagree on net sign, say
        so and surface every recorded condition that could decide it.
        """
        chains: list[Chain] = []

        def walk(node: str, path: tuple[Edge, ...], seen: frozenset[str]) -> None:
            if len(path) >= max_hops:
                return
            for e in self.nodes.get(node, Node(node, "state", "", ())).edges:
                if e.dst in seen:
                    continue
                new_path = (*path, e)
                if e.dst == target:
                    chains.append(Chain(new_path))
                else:
                    walk(e.dst, new_path, seen | {e.dst})

        walk(source, (), frozenset({source}))

        signs = {c.net_sign for c in chains}
        conflict = len(signs) > 1
        resolver = "\n  ".join(
            sorted({cond for c in chains for cond in c.conditions})
        )
        # Stronger/faster chains first: fewer hops is a rough proxy for confidence.
        chains.sort(key=lambda c: (len(c.hops), c.slowest_lag))
        return Traversal(tuple(chains), conflict, resolver)
