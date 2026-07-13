---
id: fed-leadership
kind: state
instruments: [XAUUSD]
retrieve_on: [fed, fomc, warsh, testimony, powell, chair]
edges:
  - to: rate-cut-repricing
    sign: "-"
    strength: contested
    lag: same-day
    channel: a chair perceived as more hawkish raises the bar for cuts — communication events reprice the path even with no data
    evidence: hypothesis — no episode study yet; Warsh took office 2026-05-22 and the Jul 14-15 2026 testimonies are his first semiannual MPR, so there is no track record to score him against
---
Who chairs the Fed, and how the market reads them. Kevin Warsh became chair
2026-05-22 (17th chair), with a reputation as an inflation hawk; the first MPR
under him features money-supply analysis and five new working groups (framework,
balance sheet, data, productivity/employment, communications). Inflation ~3.3%
with rates on hold going into his debut testimony.

Why this node exists: chair-communication events (testimony, pressers) move
[[rate-cut-repricing]] directly, and with a NEW chair the market has no prior to
anchor on — every phrase gets traded. Hypothesis to test after Jul 14-15:
did gold's realized vol around the testimony exceed CPI-day norms? Timing note:
Q2 2026 gold drawdown (-15.5%) overlaps his arrival, but recency is a bias, not
a signal — do not credit the drawdown to him without an episode study.
