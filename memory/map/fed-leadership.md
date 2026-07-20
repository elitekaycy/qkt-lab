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
    evidence: >
      First episode, 2026-07-14/15 debut MPR testimony (GC=F 15m bars,
      hand-read 2026-07-16). House day, 14:00-16:00Z: two-way chop 4071.3-4108.7
      ($37 total range) with volume 2-5.5k/bar vs ~1-2k baseline — a pop to
      4108.7 at 15:00Z fully retraced to 4071 by 15:45Z, no persistent
      direction. Senate day, same window: drift 4070.8 -> 4053.2 (-$18), peak
      bar range $20 at 15:00Z. Comparable realized vol to a second-tier data
      print, but round-trip rather than repricing — and both windows are
      confounded by same-morning CPI/PPI digestion, so n=2 confounded episodes.
      Strength stays contested.
---
Who chairs the Fed, and how the market reads them. Kevin Warsh became chair
2026-05-22 (17th chair), with a reputation as an inflation hawk; the first MPR
under him features money-supply analysis and five new working groups (framework,
balance sheet, data, productivity/employment, communications). Inflation ~3.3%
with rates on hold going into his debut testimony.

Why this node exists: chair-communication events (testimony, pressers) move
[[rate-cut-repricing]] directly, and with a NEW chair the market has no prior to
anchor on — every phrase gets traded. The Jul 14-15 hypothesis (does testimony
vol exceed CPI-day norms?) is now answered: NO — the CPI print bar alone did
$76.5 of range in 15 minutes vs $37 across two hours of House Q&A. Data
dominates the new chair's words, at least while prints are surprising. Timing:
Q2 2026 gold drawdown (-15.5%) overlaps his arrival, but recency is a bias, not
a signal — do not credit the drawdown to him without an episode study.
