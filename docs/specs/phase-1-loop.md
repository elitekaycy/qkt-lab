# Phase 1 — One honest trade, end to end

Status: not started
Blocked by: Phase 0 (S0.1, S0.2, S0.4)

## Why

Everything else in this project is an elaboration on a single spine: gather →
propose → gate → size → execute → record → join. Build that spine, with real
money-shaped constraints, before building anything clever on top of it.

No memory, no charts, no research, no journal UI in this phase. Those are
elaborations. This is the skeleton, and if the skeleton is wrong nothing built on
it can be right.

## What we build

**Config (`lab/config.py`).** `lab.yaml` → typed objects. Secrets via `${VAR}`
from `.env`, never in the YAML. Validated at load: fail loudly on a missing
instrument, an unreachable `qkt` binary, or an `as_prefix` long enough to blow the
MT5 comment limit (see below).

**qkt wrapper (`lab/qkt.py`).** One shape-checked subprocess wrapper around the
CLI. Non-negotiable details, all pinned from qkt's source:

- Every call appends `--json`.
- The bot verbs return `{"ok":false,"error":...}` on failure **even for verbs
  whose success shape is an array** — so a list-returning verb that comes back as
  a dict is an error, not an empty result. Check the shape.
- The arg parser has **no `--flag=value` form**, and treats an option's *value* as
  a positional. Positionals go first.
- Bot verbs run with `retryAttempts=0`. The lab owns transient-failure retry.
- A venue reject exits non-zero. Raise, don't swallow.

**Context (`lab/context.py`).** Per instrument: `bot account`, `bot positions`,
`bot quote`, `bot bars` at each configured timeframe, `bot eval "atr(14)"`.
`bot bars` can return **fewer** bars than `--count` without erroring — assert a
minimum and abort the cycle if the history is thin.

**Trader prompt (`prompts/trader.md`).** Emits strict JSON. States plainly that
the model cannot place an order, does not choose size, and that `NO_TRADE` is a
first-class, unpenalized answer.

**Gates (`lab/gates.py`).** Pure function: `(proposal, context, config) → [reject]`.
Non-empty ⇒ no order. `require_sl`; `min_rr` **recomputed from real prices**, never
trusting the model's `expected_rr`; `max_open_positions` and `max_exposure_lots`
counted over **lab-owned tickets from our own DB** — never from `qkt bot positions`,
which has no magic filter and would also count other strategies' positions;
`max_daily_loss_pct`; per-instrument `max_lots`; symbol whitelist; kill-switch file.

**Sizing (`lab/sizing.py`).** Arithmetic. The model never chooses lots.

```
risk_currency = equity × risk_per_trade_pct
stop_distance = |entry − sl|
lots          = risk_currency / (stop_distance × contract_value)
```
Floored to the venue's lot step, capped by `max_lots`.

**Execute (`lab/execute.py`).** Market orders only this phase (pending orders wait
for a spike confirming the pending→position ticket identity). `--as` must keep the
resulting order comment `bot-<as>-<13-digit-ms>` **under 31 characters** — MT5
*rejects* longer comments outright rather than truncating. Assert this at config
load, not at trade time.

**Store (`lab/store.py`, `db/schema.sql`).** `decision` and `outcome`. Every
decision is written — `TRADE`, `NO_TRADE`, and `GATED` alike. `risk_at_entry` is
stored at decision time because it is the denominator of R later and cannot be
reconstructed after the fact.

**Joiner (`lab/join.py`).** Every 15 min. A ticket absent from `bot positions` has
closed; sweep `bot history --since <open day>` (the default `--since` is 7d and
there is no `--ticket` filter — pass an explicit window and filter client-side)
and aggregate **all** deals for that `positionTicket`. Commission books on the IN
deal; summing only OUT rows under-counts cost. A ticket open past
`unjoined_alarm_days` with no OUT deal is a bug — alarm, don't ignore.

## Out of scope

Charts, news, sentiment, memory, beliefs, research, Deltalytix, pending orders,
partial closes, multi-instrument.

## Acceptance

Observable, not asserted:

1. `bin/trade` runs a full cycle on the lab demo account and writes a `decision`
   row.
2. A proposal with no stop-loss is **rejected**, and lands as a `GATED` row whose
   `gate_rejects` names `require_sl`.
3. A proposal whose real risk-reward is below `min_rr` is rejected even when the
   model claimed a higher `expected_rr`.
4. An executed trade's `lots` equals the sizing formula computed by hand from the
   equity and stop distance in that decision row.
5. The position closes; `bin/join` writes an `outcome` row whose `net_pnl`
   **matches the MT5 terminal to the cent**.
6. Running `bin/join` a second time is a no-op.
7. `touch KILL` ⇒ the next cycle places no order and says why.

## Refs

Spec: this file
Architecture: `docs/ARCHITECTURE.md`
Depends on: `docs/specs/phase-0-spikes.md` (S0.1, S0.2, S0.4)
