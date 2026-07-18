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
  2026-07-17 12:30Z housing starts 1427k vs ~1310k exp (+19% m/m) BUT permits
  1367k vs ~1403k exp (10-month low) and single-family starts down a 3rd
  month: GC=F 15m (yahoo-chart period1/period2 slice, hand-read 2026-07-18,
  close->open continuity verified across all 32 bars): 12:30Z bar 3991.0 ->
  3973.3 (vol 3597 vs ~600-900 adjacent, ~4-5x), session low 3963.0 on the
  13:00Z bar (-$36 from the 12:00Z level), reversal ignited on the 13:30Z
  bar (= NYSE open) 3971.9 -> 3988.5 high 4007.9 on vol 6794 (day's
  largest), fully round-tripped above 4001 by 13:45Z — ~75 min, BEFORE the
  14:00Z UMich beat. Day closed UP ~+0.9% (~4023 vs 3985.6 Jul 16) despite
  the beat. Outcomes per Census/TradingEconomics/SeekingAlpha 2026-07-17.
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
  (pre-positioning vs. leak vs. coincidence). RE-CHECKED 2026-07-17: did NOT
  repeat — 12:15Z bar vol 1571 vs 1643 on the 12:00Z bar, no bulge, no
  directional lean before the housing-starts flush. Score 1 of 2; keep the
  label hypothesis and keep checking, but do not trade it.

The 2026-07-17 episode adds a third lesson: surprise QUALITY gates whether the
flush sticks. Housing starts beat consensus by ~9% and gold flushed $36 in 45
minutes exactly as this edge predicts — but the beat was multifamily-driven
while permits (the forward-looking line) missed at a 10-month low and
single-family starts fell a third straight month. The market sold the headline,
then fully reversed at the 13:30Z equity open, before UMich, and the day closed
UP ~1%. Contrast Jul 16: a clean multi-line beat made new lows into the close.
Read the composition, not just the headline-vs-consensus gap: a dirty beat on a
Friday before a blackout weekend (short-covering flow after the largest weekly
decline in ~6 weeks, per same-day coverage) is a fade candidate, not a trend
signal. The reversal needed no dovish catalyst — position flow alone carried it.
