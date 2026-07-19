"""One trade cycle: gather -> retrieve -> propose -> gate -> size -> execute -> record.

This is the orchestrator. Every decision — TRADE, NO_TRADE, GATED, even an agent
failure — lands as a decision row. The rows most systems throw away are the most
diagnostic ones we have.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from . import agent as agent_mod
from . import calendar as calendar_mod
from . import charts as charts_mod
from .config import Config, Instrument
from .context import Context, gather, gather_venue
from .execute import place
from .gates import Book, check, check_quote
from .qkt import Qkt
from .retrieve import retrieve
from .sizing import risk_currency, size
from .store import Decision, Store


def assign_arm(cfg: Config, symbol: str, now: datetime) -> str:
    """Deterministic A/B arm: hash of (hour, symbol). Reproducible — the arm for a
    given cycle can be recomputed later, and cannot be silently re-rolled."""
    if not cfg.raw.get("experiment", {}).get("ab_enabled"):
        return "beliefs"
    key = f"{now.strftime('%Y-%m-%dT%H')}|{symbol}"
    arms = cfg.raw["experiment"].get("arms", ["beliefs", "control"])
    idx = int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(arms)
    return arms[idx]


@dataclass
class CycleResult:
    decision_id: int
    action: str
    detail: str


def _book(cfg: Config, store: Store, qkt: Qkt) -> Book:
    """The lab's own exposure — from OUR store, never from `bot positions`."""
    open_rows = store.open_tickets()
    live = {int(p["ticket"]): p for p in qkt.positions()}
    floating = sum(
        float(live[int(r["ticket"])].get("profit", 0))
        for r in open_rows
        if int(r["ticket"]) in live
    )
    return Book(
        open_positions=len(open_rows),
        open_lots=sum(float(r["lots"] or 0) for r in open_rows),
        open_risk_currency=sum(float(r["risk_at_entry"] or 0) for r in open_rows),
        realized_today=store.realized_today(),
        floating=floating,
    )


def run(cfg: Config, qkt: Qkt, store: Store, inst: Instrument) -> CycleResult:
    now = datetime.now(UTC)
    arm = assign_arm(cfg, inst.symbol, now)

    # 1. Venue truth + external context. If this fails there is no cycle at all —
    #    nothing to journal because nothing was decided.
    account, quote = gather_venue(qkt, inst)

    # Market freshness is deterministic and precedes the expensive/model path.
    # Closed markets retain the last tick, so a numerically plausible quote can
    # be days old. Journal the refusal explicitly instead of asking the model to
    # notice it.
    quote_rejects = check_quote(
        quote,
        max_age_seconds=cfg.gates.max_quote_age_seconds,
        now=now,
    )
    if quote_rejects:
        stale = Decision(
            as_name=cfg.as_name(inst.symbol),
            symbol=inst.symbol,
            action="GATED",
            arm=arm,
            model=cfg.model,
            equity_at_entry=float(account.get("equity", 0)),
            gate_rejects=[{"gate": r.gate, "detail": r.detail} for r in quote_rejects],
            context_snapshot={
                "schemaVersion": 1,
                "capturedAt": now.isoformat(),
                "stage": "venue_preflight",
                "account": account,
                "quote": quote,
            },
        )
        did = store.record(stale)
        return CycleResult(did, "GATED", "; ".join(str(r) for r in quote_rejects))

    ctx: Context = gather(cfg, qkt, inst, account=account, quote=quote)

    # 2. Calendar — the only LLM-populated input that feeds a gate. Fail-closed.
    cal = calendar_mod.load(cfg, now)
    horizon = timedelta(hours=12)
    events = (
        calendar_mod.upcoming(cal.events, inst.symbol, inst.bare, horizon, now) if cal.ok else []
    )

    # 3. Memory slice — ACTIVE beliefs and live map nodes, context-conditioned.
    #    The control arm gets the playbook but no beliefs: that is the experiment.
    slice_ = retrieve(cfg, inst, events=events, arm=arm)

    # 4. Charts, rendered BEFORE the proposal — they are model input.
    chart_paths: list[str] = []
    images = []
    for tf, out in zip(
        inst.timeframes,
        charts_mod.chart_paths(cfg.state_dir, inst.symbol, inst.timeframes),
        strict=True,
    ):
        charts_mod.render(ctx.bars[tf], out, title=f"{inst.symbol} {tf}")
        chart_paths.append(str(out))
        images.append(out)

    book = _book(cfg, store, qkt)
    packet = ctx.packet(
        events=events,
        beliefs=slice_.beliefs_text,
        map_nodes=slice_.map_text,
        open_positions=book.open_positions,
        realized_today=book.realized_today,
    )
    chart_snapshots = [json.loads(path.with_suffix(".json").read_text()) for path in images]

    base = Decision(
        as_name=cfg.as_name(inst.symbol),
        symbol=inst.symbol,
        action="NO_TRADE",
        arm=arm,
        news=events,
        charts=chart_paths,
        sources_missing=ctx.sources_missing,
        map_nodes_used=slice_.map_ids,
        model=cfg.model,
        equity_at_entry=ctx.equity,
        context_snapshot={
            "schemaVersion": 1,
            "capturedAt": ctx.now.isoformat(),
            "stage": "proposal",
            "account": ctx.account,
            "quote": ctx.quote,
            "bars": ctx.bars,
            "indicators": ctx.indicators,
            "calendar": events,
            "openPositions": book.open_positions,
            "realizedToday": book.realized_today,
            "modelPacket": packet,
            "chartSnapshots": chart_snapshots,
        },
    )

    # 5. The model proposes. A malformed response is itself a journaled decision —
    #    an agent that returns garbage is data, not an exception to swallow.
    try:
        raw, psha = agent_mod.run(
            cfg.root / "prompts" / "trader.md",
            packet,
            provider=cfg.agent_provider,
            agent_bin=cfg.agent_bin,
            model=cfg.model,
            images=images,
            cwd=cfg.root,
        )
        prop = agent_mod.validate(raw)
    except agent_mod.AgentError as e:
        base.action = "NO_TRADE"
        base.rationale_md = f"agent failure: {e}"
        base.unexplained = "agent_error"
        did = store.record(base)
        return CycleResult(did, "NO_TRADE", f"agent error: {e}")

    base.prompt_sha = psha
    base.side = prop.side
    base.sl = prop.sl
    base.tp = prop.tp
    base.expected_rr = (
        float(prop.raw["expected_rr"]) if prop.raw.get("expected_rr") is not None else None
    )
    base.conviction = prop.conviction
    base.setup = prop.setup
    base.factors = prop.factors
    base.regime = prop.regime
    base.thesis = prop.thesis
    base.rationale_md = prop.rationale_md
    base.invalidation = prop.invalidation
    base.beliefs_used = prop.beliefs_used
    base.map_nodes_used = sorted(set(slice_.map_ids) | set(prop.map_nodes_used))
    base.unexplained = prop.unexplained

    if not prop.wants_trade:
        did = store.record(base)
        return CycleResult(did, "NO_TRADE", prop.thesis or "model declined")

    # 6. Size — arithmetic. Entry estimated from the quote (market order).
    entry = float(ctx.quote["ask" if prop.side == "BUY" else "bid"])
    sized = size(
        cfg,
        inst,
        equity=ctx.equity,
        entry=entry,
        sl=float(prop.sl),  # validate() guarantees sl on TRADE
        conviction=prop.conviction,
        open_risk_currency=book.open_risk_currency,
    )
    base.lots = sized.lots
    base.conviction_mult = sized.conviction_mult

    # 7. Gates — deterministic, after the proposal, before the venue.
    proposal_for_gates = {
        **prop.raw,
        "entry_price": entry,
        "side": prop.side,
        "sl": prop.sl,
        "tp": prop.tp,
    }
    rejects = check(
        cfg,
        inst,
        proposal_for_gates,
        equity=ctx.equity,
        book=book,
        lots=sized.lots,
        events=cal.events if cal.ok else [],
        now=now,
        calendar_ok=cal.ok,
        calendar_reason=cal.reason,
    )
    if rejects:
        base.action = "GATED"
        base.gate_rejects = [{"gate": r.gate, "detail": r.detail} for r in rejects]
        did = store.record(base)
        return CycleResult(did, "GATED", "; ".join(str(r) for r in rejects))

    # 8. Execute — the only path to the venue.
    fill = place(cfg, qkt, inst, side=prop.side, lots=sized.lots, sl=float(prop.sl), tp=prop.tp)

    base.action = "TRADE"
    base.accepted = fill.accepted
    base.ticket = fill.ticket
    base.open_deal = fill.deal
    base.fill_price = fill.fill_price
    base.retcode = fill.retcode
    base.qkt_version = fill.raw.get("qktVersion")
    base.broker_symbol = fill.raw.get("symbol")
    if fill.accepted and fill.fill_price is not None:
        # risk_at_entry from the ACTUAL fill, not the quote — this is the
        # denominator of R and it cannot be reconstructed later.
        base.risk_at_entry = risk_currency(
            fill.fill_price, float(prop.sl), sized.lots, inst.contract_value
        )
    if not fill.accepted:
        base.rationale_md = (base.rationale_md or "") + f"\n\nVENUE REJECT: {fill.error}"

    did = store.record(base)
    detail = f"ticket {fill.ticket}" if fill.accepted else f"venue reject: {fill.error}"
    return CycleResult(did, "TRADE" if fill.accepted else "TRADE_REJECTED", detail)
