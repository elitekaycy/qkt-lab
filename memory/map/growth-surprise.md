---
id: growth-surprise
kind: event
instruments: [XAUUSD]
retrieve_on: [retail_sales, jobless_claims, claims, philly_fed, empire, pmi, ism, nfp, payrolls]
edges:
  - to: XAUUSD
    sign: "-"
    strength: moderate
    lag: same-day
    channel: strong print -> rate-relief fades -> yields up -> gold down (the growth-side twin of [[inflation-surprise]], transmitted through [[real-yields]])
    dominates_when: the market is deciding between hold and hike into a live meeting and the print lands near/inside the FOMC blackout with no speaker to reframe it; survey beats count as much as hard data in this regime
    inverts_when: the print is weak enough to read as a [[growth-scare]] — then cut-repricing bids gold instead
evidence: >
  2026-07-16 12:30Z triple print — retail sales +0.2% m/m (in line; control
  +0.5%), initial claims 208k (10-week low, ~9k below consensus), Philly Fed
  41.4 vs ~10 expected (~4x consensus): GC=F 15m bars (yahoo-chart, hand-read
  2026-07-17): 12:30Z bar 4030.3 -> 4007.1 (-23.2, vol 5075), cumulative 12:00Z
  high 4048.7 -> 13:00Z low 3977.1 (-71.6), volumes 5075-8269 vs ~2000-2500
  adjacent (~3x). Retrace to ~4009 by 14:30Z (~60% of the flush), then NEW
  session lows into the close (spot range low 3969, settle -2.1% ~3975 per
  Kitco 2026-07-16). Same-day cross-checks: 10y ~4.57%, hold odds ~90% for
  Jul 29, DXY only ~100.5-100.7 — a yields move, not a dollar move.
---
Strong US growth data is currently gold-negative with roughly the same violence
as an inflation surprise, and the surprise can hide in the second-tier lines:
on 2026-07-16 the headline event (retail sales) printed in line while claims
and the Philly Fed survey carried the entire hawkish shock. Score the day's
prints by SURPRISE, not by billing — a 4x consensus beat on a "second-tier"
survey outranks an in-line "high-impact" headline.

Two reaction-shape lessons from the same episode, for the desk:
- The initial flush retraced ~60% within 90 minutes — an anomaly ticket read
  this as a "full reversal", but it was a dip-buy bounce that failed; price
  made new lows into the close. Fading the first hour's move against a
  genuine hawkish surprise was the losing side.
- Selling volume picked up on the 12:15Z bar, before the 12:30Z release
  (vol 6720, low 4017.4). One observation only — label: hypothesis
  (pre-positioning vs. leak vs. coincidence). Worth re-checking on the next
  12:30Z print.
