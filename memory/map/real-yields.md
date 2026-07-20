---
id: real-yields
kind: state
instruments: [XAUUSD]
always: true
edges:
  - to: XAUUSD
    sign: "-"
    strength: moderate
    lag: same-day
    channel: opportunity cost — gold pays no yield, so the real yield on Treasuries is the cost of holding it
    inverts_when: central-bank demand is elevated and price-insensitive (2022-2026)
    evidence: >
      RE-ENGAGED in Q2 2026: gold and 10y yield daily changes moved in opposite
      directions 44/62 sessions (71%) over 2026-04-13..2026-07-13, 12/20 in the
      last month, while gold fell -15.5% (4742->4009) as 10y rose 4.30->4.61.
      Caveat: 10y NOMINAL used as proxy (DFII10 unreachable from the research
      session this run; runner fetches it fine — re-run with the real series).
      Sign-tally hand-computed 2026-07-13, tolerance ~±2 counts. Prior: rolling
      60d corr mean -0.62 over 2006-2026, near zero 2023-2026. Week of
      2026-07-13..16 re-confirms and rules out the dollar as confounder: gold
      -2.9% (GC=F daily closes 4104.1 Jul 10 -> 3985.6 Jul 16) while 10y rose
      to ~4.57% AND DXY fell 100.97 -> 100.74 — the down-move happened against
      a falling dollar, so the yields leg, not [[usd-bid]] / [[dxy]], carried
      it. Drivers: Hormuz oil shock hike-repricing ([[geopolitical-escalation]])
      + strong claims/Philly Fed ([[growth-surprise]]); hold odds ~90% for the
      Jul 29 FOMC (Kitco 2026-07-16). Nominal-proxy caveat still open.
---
Gold pays no yield, so the real (inflation-adjusted) Treasury yield is the
opportunity cost of holding it. Historically the single strongest macro channel
for gold. It was SUPPRESSED 2023-2026 by price-insensitive official-sector
buying, but the Q2 2026 drawdown traded WITH the channel again (see evidence) —
treat it as live but not yet fully trusted, and check [[central-bank-demand]]
before leaning on it hard. Open question: is the re-engagement because official
buying decelerated, or just because the yield move was large enough to dominate?

Transmission: 10y TIPS yield -> holding cost -> ETF flows -> spot. Lag: same-day
to 2 days on the flow leg.
