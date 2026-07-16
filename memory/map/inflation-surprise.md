---
id: inflation-surprise
kind: event
instruments: [XAUUSD]
retrieve_on: [cpi, ppi, pce, inflation]
edges:
  - to: XAUUSD
    sign: "-"
    strength: moderate
    lag: same-day
    channel: hot print -> rate-hike repricing -> real yields up -> gold down (the textbook leg)
    dominates_when: the market is pricing HIKES into a live meeting (2026 regime — Warsh Fed, ECB hiking) and the print lands inside/near the FOMC blackout, leaving no speaker to reframe it
    inverts_when: the market reads the print as growth-negative and prices CUTS despite it, or the inflation-hedge bid dominates
evidence: >
  2026-07-14 CPI (soft) 12:30Z: GC=F 15m bar 4036.1 -> 4101.1 close, high
  4112.5 (+65 close-open, 76.5 range), volume 21802 vs ~1600 on adjacent bars
  (~13x). 2026-07-15 PPI (-0.3% m/m vs 0.0% exp) 12:30Z: 15m bar 4045.1 ->
  4069.8 close (+24.7), 12:00->13:00 swing 4044.9 -> 4080.7 high (+35.8),
  volume 7384 vs ~1100 adjacent (~6.7x). Two consecutive soft prints, both
  gold UP within one bar — sign "-" held both times (soft = rally). Bars
  hand-read from yahoo-chart GC=F 15m slices, 2026-07-16; narrative
  corroborated by Kitco/CNBC/Invezz same-day coverage.
---
The textbook reaction (hot CPI = gold down, soft = gold up) is currently firing
cleanly and violently: in a hike-repricing regime the print IS the rate path, so
the first 15m bar after 12:30Z carries 6-15x normal volume and $25-75 of range.
Watch the FIRST 15m bar after the print rather than assuming: if gold ever
rallies on a HOT print, the inflation-hedge bid or a cuts-despite-it repricing
has taken over — that would flip the regime and this edge's strength.

Retrieve PPI alongside CPI: the 2026-07-15 episode shows PPI alone moves gold
~half a CPI when it surprises, which is far from ignorable. (Prior version of
this node did not list ppi in retrieve_on — that gap is why the Jul 15 rally
arrived with no map node retrieved.)
