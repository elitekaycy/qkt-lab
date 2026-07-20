# Phase 3 — First-party journal UI

Status: implemented
Depends on: Phase 2 chart evidence

## Why

The journal must represent the complete decision process, not only closed
trades. That includes TRADE, NO_TRADE, GATED, model failures, safety refusals,
broker outcomes, and the precise evidence available at decision time.

Keeping the read surface on the lab database removes an export job, a second
Postgres, a cache boundary, and a separate authentication model.

## Data contract

Postgres remains the only source of truth:

- `decision` stores proposal, rationale, thesis, invalidation, setup, factors,
  regime, knowledge provenance, gate rejections, execution response, and chart
  paths;
- `decision.context_snapshot` stores a versioned account/quote snapshot,
  complete broker bars, indicators, calendar, exact model packet, and
  TradingView-ready EMA/RSI/ATR series;
- `outcome` stores the broker-joined close, all raw deals, costs, net P&L, and R.

The immutable PNG remains the visual artifact shown to the model. The database
snapshot is sufficient to reconstruct the interactive chart if a sidecar file
is later unavailable.

## Read surface

The React/Tailwind app at port 8421 provides:

1. authenticated current-account truth;
2. realized net, win rate, profit factor, expectancy, average R, and drawdown;
3. cumulative realized net-P&L curve with an explicit zero basis;
4. UTC P&L and decision-activity calendar with day drilldown;
5. setup and UTC-hour analysis with sample sizes;
6. searchable/filterable complete decision journal;
7. deep decision detail for reasoning, gates, context, provenance, execution,
   archived PNG, and an official TradingView Lightweight Charts reconstruction;
8. operational status and explicit management boundaries.

Missing outcomes render as intentional empty states, never invented zero
performance.

## Acceptance

1. `docker compose up -d` uses one Postgres and starts the journal.
2. All decision types are visible and searchable.
3. A close joined by ticket immediately contributes to the calendar and widgets.
4. Detail shows the complete reason, exact UTC timestamps, chart PNG, and
   interactive DB-backed TradingView evidence.
5. Desktop collapse and the mobile drawer work without horizontal overflow.
6. The journal is read-only; disabling it does not change trading behavior.
