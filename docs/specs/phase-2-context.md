# Phase 2 — Context: charts, calendar, macro, sentiment, playbooks

Status: not started
Blocked by: Phase 1, and S0.5 (calendar source)

## Why

Phase 1 gives the model price and nothing else. That is not an analyst, it is a
chartist with amnesia. This phase gives it eyes and a world.

It also introduces the first gate that depends on an external source — the news
blackout — which is the point at which "the source was down" stops being a
curiosity and starts being a safety question.

## What we build

**Charts (`lab/charts.py`).** `qkt bot bars --json` (fields are `t` epoch-ms,
`o/h/l/c/v`) → mplfinance PNGs, one per configured timeframe. Rendered **before**
the proposal so they are model input, and archived with the decision so we can
later look at exactly what it saw. The `charts[]` column holds the paths.

**Calendar (`lab/sources/calendar.py`).** Whatever S0.5 pinned. Normalized to
`{event, at_utc, impact, actual, forecast, previous, affects:[symbols]}`. Feeds two
consumers: the model's context, and the `news_blackout` gate.

**Macro (`lab/sources/fred.py`).** Slow-moving regime context — 10y real yield,
dollar index, curve. Fetched daily, not per cycle. Feeds the `regime` block.

**Sentiment (`lab/sources/reddit.py`).** A bounded, pre-summarized digest —
never a raw dump. At most ~200 tokens of
`{bias, intensity, themes[], sample_n}`.

It enters the model's context and is logged as a **factor**. It gates nothing and
gets no privileged treatment. Whether `sentiment:reddit-bullish` has any
relationship to realized R is a question Phase 5's belief loop *answers*, not one
we assume. If it doesn't, it earns an INVALIDATED belief and we stop paying for
it. That is the entire reason to build the loop rather than argue about the feed.

(X stays off. Its free tier is write-only; reading requires the paid plan. Not a
technical blocker, a cost decision — deferred, not forgotten.)

**The missing-source rule.** A source that fails is recorded as
`sources_missing: ["reddit"]`. **A missing source must never be indistinguishable
from a neutral reading.** Otherwise the distiller cannot tell "we had no sentiment"
apart from "sentiment was flat", and every belief conditioned on sentiment is
quietly poisoned.

**Blackout gate.** No new order within `news_blackout_minutes` of a high-impact
event affecting the instrument. Arithmetic, not judgment.

**Fail-closed on the calendar.** If the calendar source is unavailable, the
blackout gate **cannot** be evaluated, and the loop must refuse to trade rather
than trade blind through CPI. Fail-closed, and say so loudly.

**Playbook (`playbooks/xauusd.md`).** Human-authored, slowly refined: which
sessions to trade, what invalidates a setup, which levels matter, which sources
matter for gold. This is the file that makes future prompts *shorter* — it holds
the standing process so the model stops re-deriving it every hour.

## Out of scope

Memory, beliefs, research, the causal map, Deltalytix.

## Acceptance

1. The model receives two chart images and a news block; the decision row records
   the chart paths and the events.
2. A proposal inside a high-impact blackout window is gated with reason
   `news_blackout`, and the row is in the store.
3. Killing the calendar source causes the cycle to **refuse to trade**, with a
   clear reason — not to trade blind.
4. Killing the Reddit source lets the cycle proceed, with `sources_missing`
   recording it.
5. Swapping in an inverted chart demonstrably changes the proposal (the images are
   actually being read, not decoratively attached).

## Refs

Spec: this file
Depends on: `docs/specs/phase-1-loop.md`, S0.5
