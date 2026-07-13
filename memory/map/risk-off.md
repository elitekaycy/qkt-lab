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
    strength: moderate
    lag: same-day
    channel: safe-haven bid — capital rotates into gold when equity risk is repriced
    dominates_when: vix spike WITHOUT dollar-funding stress
    inverts_when: dollar-funding stress (Mar 2020, Sep 2008) — gold is what you SELL when you need dollars
    evidence: n=47 risk-off episodes since 2006, gold +0.8% median; BUT -4.2% median in the 5 funding-stress episodes
---
Risk-off is NOT automatically bullish gold. Two legs fire at once — the USD bid
(bearish gold) and the safe-haven bid (bullish gold) — and which dominates
depends on whether this is a growth scare or a funding event. Check SOFR-OIS and
cross-currency basis: if dollar funding is stressed, everything sells including
gold.
