---
id: inflation-surprise
kind: event
instruments: [XAUUSD]
retrieve_on: [cpi, pce, inflation]
edges:
  - to: XAUUSD
    sign: "-"
    strength: moderate
    lag: same-day
    channel: hot print -> rate-hike repricing -> real yields up -> gold down (the textbook leg)
    inverts_when: the market reads the print as growth-negative and prices CUTS despite it, or the inflation-hedge bid dominates
---
The textbook reaction (hot CPI = gold down) fails often enough to matter. Watch
the FIRST 15m bar after the print rather than assuming: if gold rallies on a hot
print, the inflation-hedge bid or a cuts-despite-it repricing is dominating.
