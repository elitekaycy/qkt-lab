"""The nightly distillation pass.

Order matters and is load-bearing:

1. The LLM reads recent closed episodes and proposes belief operations.
2. Code validates each proposal (predicate must compile) and writes CANDIDATE
   files. The model's `status`/stats, if it sent any, are discarded.
3. `beliefs.rescore_all` scores everything and sets statuses — including the
   family-wide BH correction across this cycle's candidates.
4. The conviction calibration report is recomputed.

Run at night, after the session. A trade can never contribute to a belief that
influenced it, because beliefs written tonight are read tomorrow.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from . import agent as agent_mod
from . import calibrate
from .beliefs import PredicateError, compile_predicate, rescore_all
from .config import Config
from .store import Store


def recent_episodes(store: Store, limit: int = 200) -> list[dict[str, Any]]:
    return store.query(
        """
        SELECT ticket, ts, symbol, side, setup, factors, regime, conviction,
               thesis, invalidation, r_multiple, net_pnl, duration_s
        FROM episode ORDER BY closed_at DESC LIMIT %s
        """,
        (limit,),
    )


def existing_beliefs(cfg: Config) -> str:
    parts = []
    for f in sorted(cfg.beliefs.path.glob("*.md")):
        parts.append(f.read_text())
    return "\n\n".join(parts) or "(none yet)"


def apply_ops(cfg: Config, ops: list[dict[str, Any]]) -> dict[str, str]:
    """Write/edit CANDIDATE files from validated proposals. Code owns status."""
    results: dict[str, str] = {}
    cfg.beliefs.path.mkdir(parents=True, exist_ok=True)
    for op in ops:
        bid = str(op.get("id", "")).strip()
        kind = str(op.get("op", "")).upper()
        if not bid or kind not in ("ADD", "EDIT", "NOTE"):
            results[bid or "?"] = "skipped: malformed op"
            continue
        path = cfg.beliefs.path / f"{bid}.md"

        if kind == "NOTE":
            if path.exists():
                path.write_text(path.read_text() + f"\nnote ({datetime.now(UTC).date()}): {op.get('note', '')}\n")
                results[bid] = "noted"
            else:
                results[bid] = "skipped: NOTE on unknown belief"
            continue

        predicate = [str(c) for c in (op.get("predicate") or [])]
        try:
            compile_predicate(predicate)
        except PredicateError as e:
            results[bid] = f"rejected: {e}"
            continue

        if kind == "ADD" and path.exists():
            results[bid] = "skipped: exists (use EDIT)"
            continue

        current_status = "CANDIDATE"
        if kind == "EDIT" and path.exists():
            # An edited predicate is a NEW hypothesis: back to CANDIDATE it goes.
            current_status = "CANDIDATE"

        meta = {
            "id": bid,
            "status": current_status,  # code-owned; whatever the model sent is gone
            "statement": str(op.get("statement", "")),
            "symbols": op.get("symbols") or ["ICM:XAUUSD"],
            "predicate": predicate,
            "mechanism": op.get("mechanism"),
            "created": str(op.get("created") or datetime.now(UTC).date()),
        }
        path.write_text("---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n")
        results[bid] = "written"
    return results


def run(cfg: Config, store: Store) -> dict[str, Any]:
    episodes = recent_episodes(store)
    report: dict[str, Any] = {"episodes": len(episodes)}

    if len(episodes) >= 10:
        packet = {
            "closed_episodes": episodes,
            "existing_beliefs": existing_beliefs(cfg),
        }
        try:
            raw, _ = agent_mod.run(
                cfg.root / "prompts" / "distiller.md", packet, model=cfg.model,
                timeout_s=600,
            )
            ops = raw if isinstance(raw, list) else raw.get("ops", [])
            report["proposals"] = apply_ops(cfg, ops)
        except agent_mod.AgentError as e:
            report["proposals"] = {"error": str(e)}
    else:
        report["proposals"] = "skipped: corpus too small (<10 episodes)"

    # Scoring runs regardless — existing beliefs decay on their own schedule
    # whether or not the model had anything new to say.
    report["statuses"] = rescore_all(cfg, store)

    cal = calibrate.run(store)
    report["calibration"] = cal.render()
    (cfg.state_dir / "calibration.txt").parent.mkdir(parents=True, exist_ok=True)
    (cfg.state_dir / "calibration.txt").write_text(cal.render() + "\n")
    if cal.supports_fitted and cal.fit:
        # Never auto-promote: write the evidence where a human (and the config
        # validator) can see it. Flipping sizing.stage is a reviewed change.
        (cfg.state_dir / "calibration-fit.json").write_text(json.dumps(cal.fit))
        report["calibration_fit"] = cal.fit

    return report


def anomaly_tickets(store: Store, cfg: Config) -> list[str]:
    """Episodes that should trigger research: big losses with intact theses is
    approximated here by |R| outliers; `unexplained` flags pass through as-is."""
    out = []
    for r in store.query(
        "SELECT ticket, unexplained FROM decision "
        "WHERE unexplained IS NOT NULL AND ts > now() - interval '2 days'"
    ):
        out.append(f"decision {r['ticket'] or '(no ticket)'}: {r['unexplained']}")
    for r in store.query(
        "SELECT ticket, r_multiple FROM episode "
        "WHERE closed_at > now() - interval '2 days' AND abs(r_multiple) > 2.5"
    ):
        out.append(f"ticket {r['ticket']}: |R|={float(r['r_multiple']):+.2f} outlier — verify the thesis held")
    return out


def _unused(_: Path) -> None:  # placate linters for Path import in type context
    pass
