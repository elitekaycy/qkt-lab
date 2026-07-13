"""Retrieve the memory slice for a trade cycle.

Context-conditioned, not load-everything: the store can grow to hundreds of files
while the packet stays inside its token budget. Growth in knowledge must not mean
growth in context, or the "cheaper over time" claim inverts.

The control arm of the A/B gets the playbook and the map but NO beliefs — the
tactical-belief layer is what is on trial, and the causal map's value does not
rest on that experiment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import Config, Instrument

# A rough char budget per section. ~4 chars/token; keep each slice small.
BELIEFS_BUDGET = 4000
MAP_BUDGET = 8000


@dataclass
class Slice:
    beliefs_text: str = ""
    map_text: str = ""
    belief_ids: list[str] = field(default_factory=list)
    map_ids: list[str] = field(default_factory=list)


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text()
    m = re.match(r"\A---\n(.*?)\n---\n?(.*)\Z", text, re.S)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, m.group(2)


def active_beliefs(cfg: Config, inst: Instrument) -> list[tuple[str, str]]:
    """(id, rendered text) for ACTIVE beliefs matching this instrument.

    CANDIDATE beliefs are deliberately withheld: if the model could see them it
    would act on them, and they would confirm themselves. They accrue evidence
    from incidental matches instead.
    """
    out: list[tuple[str, str]] = []
    root = cfg.beliefs.path
    if not root.exists():
        return out
    for f in sorted(root.glob("*.md")):
        meta, body = _frontmatter(f)
        if str(meta.get("status", "")).upper() != "ACTIVE":
            continue
        symbols = meta.get("symbols") or [meta.get("symbol")] or []
        if symbols and inst.symbol not in symbols and inst.bare not in symbols:
            continue
        bid = str(meta.get("id", f.stem))
        out.append((bid, f"[{bid}] {meta.get('statement', '')}\n{body.strip()}"))
    return out


def live_map_nodes(
    cfg: Config, inst: Instrument, events: list[dict[str, Any]]
) -> list[tuple[str, str]]:
    """Map nodes whose triggers match the current context.

    A node declares `retrieve_on` tags (event classes, always). CPI in the window
    pulls `inflation-surprise`; nothing pulls `mine-supply` on an ordinary hour.
    Nodes tagged `always: true` are pinned (the instrument's core drivers).
    """
    out: list[tuple[str, str]] = []
    root = cfg.memory_root / "map"
    if not root.exists():
        return out

    event_words = " ".join(str(e.get("event", "")).lower() for e in events)

    for f in sorted(root.glob("*.md")):
        meta, body = _frontmatter(f)
        nid = str(meta.get("id", f.stem))
        instruments = meta.get("instruments") or []
        if instruments and inst.symbol not in instruments and inst.bare not in instruments:
            continue
        if meta.get("always"):
            out.append((nid, body.strip()))
            continue
        triggers = [str(t).lower() for t in (meta.get("retrieve_on") or [])]
        if any(t in event_words for t in triggers):
            out.append((nid, body.strip()))
    return out


def _pack(items: list[tuple[str, str]], budget: int) -> tuple[str, list[str]]:
    used: list[str] = []
    parts: list[str] = []
    total = 0
    for nid, text in items:
        if total + len(text) > budget:
            break
        parts.append(text)
        used.append(nid)
        total += len(text)
    return "\n\n---\n\n".join(parts), used


def retrieve(
    cfg: Config, inst: Instrument, *, events: list[dict[str, Any]], arm: str = "beliefs"
) -> Slice:
    s = Slice()
    s.map_text, s.map_ids = _pack(live_map_nodes(cfg, inst, events), MAP_BUDGET)
    if arm != "control":
        s.beliefs_text, s.belief_ids = _pack(active_beliefs(cfg, inst), BELIEFS_BUDGET)
    return s
