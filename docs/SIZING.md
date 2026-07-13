# Sizing

How much to put on is the portfolio manager's decision. This document says how
the agent makes it, and what it has to prove before it's allowed to make it
freely.

## The wrong two extremes

**"The model picks the lot size."** A model that picks a number is a model that
sizes up after losses, and that is the single most reliable way to blow an
account. It is also unfalsifiable — you cannot tell a good sizing decision from a
lucky one without a framework.

**"Sizing is a fixed constant."** This is what a risk system does when it doesn't
trust its PM. It throws away the most valuable thing an analyst produces —
*differentiated conviction* — and turns a hedge fund into an index. If every trade
is the same size, being right more often on the trades you're sure about buys you
nothing.

A real fund does neither. It gives the PM a **risk budget**, lets them allocate
within it, measures whether their conviction was any good, and adjusts the budget
accordingly. Small book, prove yourself, book grows.

## The stack

Sizing is composed, not chosen. Each term is separately inspectable, and the model
owns exactly one of them.

```
base_risk           = equity × risk_per_trade_pct
vol_adjusted        = base_risk / (stop_distance × contract_value)
conviction_mult     = f(conviction)                  ← THE MODEL'S CALL
correlation_haircut = g(open book)
──────────────────────────────────────────────────────────────────
lots = vol_adjusted × conviction_mult × correlation_haircut
       floored to lot step, capped by max_lots and portfolio heat
```

### `vol_adjusted` — volatility targeting, for free

Dividing the risk budget by the stop distance means that when the stop is
ATR-derived, **risk stays constant in R terms across volatility regimes**. A wide
stop in a volatile market gets a smaller position; a tight stop in a quiet market
gets a bigger one. Same money at risk either way.

This is real vol-targeting and it comes out of the arithmetic without anyone
having to reason about it. It is why the formula is
`risk / stop_distance` and not `equity × some_percent`.

### `conviction_mult` — the model's call, and the only one

The model states a `conviction` in `[0, 1]` on every proposal. `f()` maps it to a
multiplier.

**`f()` is fitted from realized outcomes. It is never guessed, and it is never set
by hand because someone wanted bigger size.**

Three stages:

**Stage A — `flat` (the default, and where we start).**
`f(conviction) = 1.0` for all conviction. The number is *recorded on every decision*
but does not affect size. We are collecting the data that will tell us whether
conviction means anything.

**Stage B — `fitted`.**
Once there is a corpus, bucket the closed trades by stated conviction and compute
mean realized R per bucket, with confidence intervals:

```
conviction 0.0-0.3   n=41   mean R  −0.06   [−0.31, +0.19]
conviction 0.3-0.6   n=88   mean R  +0.11   [−0.04, +0.26]
conviction 0.6-0.8   n=52   mean R  +0.38   [+0.12, +0.64]
conviction 0.8-1.0   n=19   mean R  +0.71   [+0.22, +1.20]
```

If conviction genuinely predicts realized R — a monotone relationship with the
confidence intervals actually separating — then `f()` is fitted to that
relationship and conviction starts driving real size, bounded by
`conviction_max_mult`.

The fit is deliberately conservative: **fractional-Kelly, not full Kelly.** Full
Kelly is the growth-optimal bet *if your edge estimate is exactly right*, and it is
catastrophically over-levered if it's even slightly wrong — which, with n=19 in the
top bucket, it will be. Half-Kelly or less, and the cap binds before the fit does.

**Stage C — flat forever.**
If conviction turns out to be uncorrelated with outcome, `f()` stays flat, and we
have learned something genuinely important: **the model thinks it knows when it is
right, and it doesn't.** That's not a failure of the project; that's the project
working. It's a fact about the model that no amount of prompt engineering would
have surfaced.

The transition A→B is not a config edit someone makes on a hunch. It requires the
calibration report, and it is reviewed like any other `risk:money` change.

### `correlation_haircut` — the portfolio, not the trade

Sizing a trade in isolation is how a book that looks diversified turns out to be
one position wearing four hats. Long gold, short DXY, long silver, and long miners
is *one* trade.

Total open risk across the book is capped (`portfolio_heat_pct`). Correlated
positions share that budget: if two open positions have historical correlation
above a threshold, their risk contributions are added, not counted separately.

The practical effect: the third correlated position gets a smaller size, or gets
refused. That's correct. It's also the thing most retail systems never do and most
funds consider table stakes.

## What is never the model's call

The risk officer is not the PM. Regardless of conviction:

- `max_daily_loss_pct` — breach halts new orders for the day
- `portfolio_heat_pct` — total open risk across the book
- `max_lots` per instrument
- `min_rr`, `require_sl`
- the kill switch

These are not suggestions the model weighs. It never sees them. They are evaluated
in code after the proposal exists, and they refuse.

High risk, high reward — but the tail is bounded by something the model cannot
argue with.

## Config

```yaml
risk:
  risk_per_trade_pct: 0.5
  portfolio_heat_pct: 2.0
  correlation_threshold: 0.6

sizing:
  stage: flat                # flat | fitted
  conviction_max_mult: 2.0   # the ceiling on f(), whatever the fit says
  kelly_fraction: 0.5        # fractional Kelly. Never 1.0.
  fit: null                  # written by the calibration report, not by hand
```

## Acceptance

1. In stage `flat`, `lots` equals the hand-computed formula with multiplier 1.0.
2. The calibration report can be produced from the journal at any time: mean
   realized R per conviction bucket, with confidence intervals and sample sizes.
3. `stage: fitted` is only reachable with a calibration report that supports it.
   The code refuses otherwise.
4. The portfolio heat cap provably blocks a third correlated position when the
   first two already consume the budget.
5. No sizing path exists that can exceed `max_lots` or `portfolio_heat_pct`,
   whatever the model says.

## Refs

Issue: #14
Calibration lives with the distiller: `docs/specs/phase-5-learning.md`
