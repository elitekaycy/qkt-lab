"""Belief scoring: the LLM proposes, this module disposes.

A belief is the only memory that claims a tradeable edge, so it is the only one
with a hard statistical gate. The distiller LLM writes the statement and the
predicate; THIS code compiles the predicate to SQL, scores it over every matching
trade, applies the family-wide multiple-testing correction, and sets the status.
The model can never write `status`, `n`, the stats, or the ticket lists.

The rules that keep it honest (docs/specs/phase-5-learning.md):

1. Scored over EVERY matching trade, not just trades the belief caused — the
   difference between learning and self-confirmation.
2. CANDIDATE -> ACTIVE needs n >= activate_min_trades AND survival of a
   family-wide Benjamini-Hochberg correction across all candidates that cycle.
   Forty proposed lessons where one clears p<0.05 is a max-of-N statistic.
3. Decrement, never delete: ACTIVE -> WEAKENING -> INVALIDATED, history in git.
4. Scored on realized net PnL (as R) only. Never on the model's self-assessment.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .config import Config
from .store import Store

# Predicate grammar — deliberately small. Each clause compiles to one SQL
# condition; clauses are AND-ed. Anything outside the grammar is rejected: a
# predicate that cannot be evaluated mechanically is prose, not a hypothesis.
#
#   symbol = ICM:XAUUSD
#   side = BUY
#   regime.session = london
#   regime.atr14 between 3 and 5
#   factors contains level:vwap-touch
_CLAUSE = re.compile(
    r"^\s*(?:"
    r"(?P<field>symbol|side|setup)\s*=\s*(?P<val>\S+)"
    r"|regime\.(?P<rkey>[\w-]+)\s*=\s*(?P<rval>\S+)"
    r"|regime\.(?P<nkey>[\w-]+)\s+between\s+(?P<lo>-?[\d.]+)\s+and\s+(?P<hi>-?[\d.]+)"
    r"|factors\s+contains\s+(?P<factor>\S+)"
    r")\s*$",
    re.I,
)


class PredicateError(ValueError):
    """The predicate is outside the grammar — unevaluable, therefore not a belief."""


def compile_predicate(clauses: list[str]) -> tuple[str, list[Any]]:
    if not clauses:
        raise PredicateError("empty predicate — a belief must be checkable")
    where, params = [], []
    for c in clauses:
        m = _CLAUSE.match(c)
        if not m:
            raise PredicateError(f"unparseable clause: {c!r}")
        if m["field"]:
            where.append(f"{m['field'].lower()} = %s")
            params.append(m["val"])
        elif m["rkey"]:
            where.append("regime->>%s = %s")
            params += [m["rkey"], m["rval"]]
        elif m["nkey"]:
            where.append("(regime->>%s)::numeric BETWEEN %s AND %s")
            params += [m["nkey"], float(m["lo"]), float(m["hi"])]
        else:
            where.append("factors @> %s::jsonb")
            params.append(f'["{m["factor"]}"]')
    return " AND ".join(where), params


@dataclass
class Scored:
    belief_id: str
    n: int
    wins: int
    losses: int
    mean_r: float
    t_stat: float
    p_value: float
    supporting: list[int]
    refuting: list[int]


def score(store: Store, belief_id: str, clauses: list[str]) -> Scored:
    """Evaluate the predicate over decision ⋈ outcome. Every matching closed
    trade counts — including ones this belief never influenced."""
    where, params = compile_predicate(clauses)
    rows = store.query(
        f"SELECT ticket, r_multiple FROM episode WHERE r_multiple IS NOT NULL AND {where}",
        tuple(params),
    )
    rs = [float(r["r_multiple"]) for r in rows]
    n = len(rs)
    supporting = [int(r["ticket"]) for r in rows if float(r["r_multiple"]) > 0]
    refuting = [int(r["ticket"]) for r in rows if float(r["r_multiple"]) <= 0]

    if n < 2:
        return Scored(
            belief_id,
            n,
            len(supporting),
            len(refuting),
            sum(rs) / n if n else 0.0,
            0.0,
            1.0,
            supporting,
            refuting,
        )

    mean = sum(rs) / n
    var = sum((x - mean) ** 2 for x in rs) / (n - 1)
    sd = math.sqrt(var)
    t = mean / (sd / math.sqrt(n)) if sd > 0 else 0.0
    # One-sided p against mean_R <= 0, normal approximation. With the BH pass on
    # top and n>=30 to activate, the approximation error is not the binding risk.
    p = 1.0 - _phi(t)
    return Scored(belief_id, n, len(supporting), len(refuting), mean, t, p, supporting, refuting)


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def benjamini_hochberg(p_values: dict[str, float], alpha: float) -> set[str]:
    """Which hypotheses survive the family-wide FDR correction.

    Applied across ALL candidates in the cycle — the distiller proposing forty
    lessons and one clearing raw p<0.05 discovers nothing.
    """
    items = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(items)
    survivors: set[str] = set()
    max_k = 0
    for k, (_, p) in enumerate(items, start=1):
        if p <= alpha * k / m:
            max_k = k
    for k, (bid, _) in enumerate(items, start=1):
        if k <= max_k:
            survivors.add(bid)
    return survivors


# --- status transitions: arithmetic, never judgment -----------------------------


def next_status(current: str, s: Scored, cfg: Config, survives_family: bool) -> str:
    """CANDIDATE -> ACTIVE -> WEAKENING -> INVALIDATED. Decrement, never delete."""
    cur = current.upper()

    if cur == "CANDIDATE":
        if s.n >= cfg.beliefs.activate_min_trades and survives_family and s.mean_r > 0:
            return "ACTIVE"
        return "CANDIDATE"

    if cur == "ACTIVE":
        # Demote when the evidence no longer supports it — not on one bad trade.
        if s.mean_r <= 0 or s.t_stat < 1.0:
            return "WEAKENING"
        return "ACTIVE"

    if cur == "WEAKENING":
        if s.mean_r > 0 and s.t_stat >= 1.5:
            return "ACTIVE"  # recovered
        if s.mean_r <= 0:
            return "INVALIDATED"
        return "WEAKENING"

    return "INVALIDATED"  # terminal: stays on disk, in git, with its history


# --- the belief file on disk ----------------------------------------------------


def _frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text()
    m = re.match(r"\A---\n(.*?)\n---\n?(.*)\Z", text, re.S)
    if not m:
        return {}, text
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def rescore_all(cfg: Config, store: Store, now: datetime | None = None) -> dict[str, str]:
    """The nightly pass: score every belief file, apply BH across the candidates,
    write updated stats + status back. Returns {belief_id: new_status}."""
    now = now or datetime.now(UTC)
    root = cfg.beliefs.path
    root.mkdir(parents=True, exist_ok=True)

    loaded: dict[str, tuple[Path, dict[str, Any], list[str]]] = {}
    scores: dict[str, Scored] = {}
    for f in sorted(root.glob("*.md")):
        meta, _ = _frontmatter(f)
        bid = str(meta.get("id", f.stem))
        clauses = [str(c) for c in (meta.get("predicate") or [])]
        try:
            scores[bid] = score(store, bid, clauses)
        except PredicateError as e:
            # Unevaluable = not a belief. Mark it so the distiller sees the reject.
            meta["status"] = "REJECTED"
            meta["reject_reason"] = str(e)
            _write(f, meta, f"REJECTED: {e}")
            continue
        loaded[bid] = (f, meta, clauses)

    # Family-wide correction across THIS cycle's candidates only — ACTIVE beliefs
    # already passed their gate; re-testing them nightly would be its own
    # multiplicity problem in the other direction.
    candidate_ps = {
        bid: scores[bid].p_value
        for bid, (f, meta, _) in loaded.items()
        if str(meta.get("status", "CANDIDATE")).upper() == "CANDIDATE"
    }
    survivors = benjamini_hochberg(candidate_ps, cfg.beliefs.alpha) if candidate_ps else set()

    out: dict[str, str] = {}
    for bid, (f, meta, _) in loaded.items():
        s = scores[bid]
        status = next_status(str(meta.get("status", "CANDIDATE")), s, cfg, bid in survivors)
        meta["status"] = status
        meta["updated"] = now.date().isoformat()
        body = (
            f"n: {s.n}   wins: {s.wins}   losses: {s.losses}\n"
            f"mean_R: {s.mean_r:+.3f}   t: {s.t_stat:.2f}   p: {s.p_value:.3f}\n"
            f"supporting: {s.supporting}\n"
            f"refuting: {s.refuting}\n"
        )
        if status == "CANDIDATE" and s.n < cfg.beliefs.activate_min_trades:
            body += (
                f"\nCANDIDATE: n={s.n} < activate_min_trades="
                f"{cfg.beliefs.activate_min_trades}. Not injected into trader context.\n"
            )
        _write(f, meta, body)
        out[bid] = status
    return out


def _write(path: Path, meta: dict[str, Any], body: str) -> None:
    path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body)
