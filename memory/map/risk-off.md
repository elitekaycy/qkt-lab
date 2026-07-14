---
id: risk-off
kind: state
instruments: [XAUUSD]
retrieve_on: [equity, drawdown, vix, selloff, crash]
edges:
  - to: usd-bid
    sign: "+"
    strength: moderate
    lag: same-day
    channel: flight to the reserve currency
  - to: XAUUSD
    sign: "+"
    strength: weak
    lag: 1-3 days
    channel: safe-haven bid — capital rotates into gold when equity risk is repriced
    dominates_when: vix spike WITHOUT dollar-funding stress
    inverts_when: dollar-funding stress (Mar 2020, Sep 2008) — gold is what you SELL when you need dollars
    evidence: >
      studies/risk_off_gold.py, 2026-07-14, 25y Yahoo daily (GC=F, ^GSPC),
      n=256 SPX<=-2% days: same-day gold +0.09% mean, up only 131/256 — the
      SAME-DAY safe-haven bid is NOT evidenced; it is a coin flip. The signal
      is cumulative and conditional: Sep-Dec 2008 gold trough -12.4% before
      finishing +9.8% (SPX -29.3%); Mar 2020 trough -7.2%, flat by month end
      (SPX -16.4%). Gold sells off DURING forced liquidation and outperforms
      on the recovery leg.
---
Risk-off is NOT automatically bullish gold. Two legs fire at once — the USD bid
(bearish gold) and the safe-haven bid (bullish gold) — and which dominates
depends on whether this is a growth scare or a funding event. Check SOFR-OIS and
cross-currency basis: if dollar funding is stressed, everything sells including
gold.

The 25-year episode study demoted this edge from moderate to weak on the day
scale: do NOT buy gold into an equity crash expecting a same-day hedge. The
tradeable version is the sequence — funding-stress drawdown first, safe-haven
outperformance on the weeks after — which is a swing thesis, not a day trade.
