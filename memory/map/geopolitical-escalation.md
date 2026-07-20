---
id: geopolitical-escalation
kind: event
instruments: [XAUUSD]
retrieve_on: [geopolitics, iran, hormuz, airstrike, war, escalation, oil, middle_east]
edges:
  - to: XAUUSD
    sign: "+"
    strength: weak
    lag: same-day
    channel: safe-haven bid — the textbook reaction (see [[risk-off]] for why even this leg is weaker than folklore says)
    dominates_when: the escalation threatens growth/markets but NOT energy supply, or the market is already pricing cuts
  - to: XAUUSD
    sign: "-"
    strength: moderate
    lag: same-day to 2 days
    channel: escalation -> oil supply risk (Hormuz) -> energy-driven inflation expectations -> hike repricing -> [[real-yields]] up -> gold down
    dominates_when: the escalation runs through OIL (supply routes, producer strikes) while the central bank is hike-sensitive (2026 Warsh Fed regime)
    inverts_when: the Fed is in easing mode and looks through energy prices, or the event escalates to broad risk-off with equity liquidation
evidence: >
  2026-07-13: US-Iran airstrike exchanges over the weekend + Strait of Hormuz
  closure fears -> oil sharply higher -> gold DOWN, not up: GC=F daily close
  4104.1 (Jul 10) -> 3997.0 (Jul 13), -2.6%, the single biggest down day of
  the week (spot -1.52% to ~4057 per same-day coverage). Same-day press
  (Yahoo Finance, Voice of Emirates 2026-07-13) attributes the fall to
  hike-repricing on energy-inflation fears outweighing the safe-haven bid.
  Confirmed again 2026-07-15: FXStreet, "Gold price slips as Iran escalation
  overshadows soft US PPI" — the oil->rates leg beat BOTH the haven bid and
  a soft inflation print on the same day. Two same-week episodes, one sign;
  daily bars hand-read from yahoo-chart GC=F 1d, 2026-07-17.
---
"Geopolitical escalation is bullish gold" is folklore, not a channel. In a
hike-sensitive regime an escalation that threatens OIL SUPPLY is a rates event
wearing a war costume: oil up -> inflation-expectations up -> hike odds up ->
real yields up -> gold down. That leg out-muscled the safe-haven bid twice in
the week of Jul 13, and it is the missing driver behind "gold trended down all
week despite soft CPI and PPI" — the trend was set Monday by Hormuz-driven
hike repricing, and the soft prints only produced intraday pops against it.

Routing rule for the desk: when the headline is geopolitical, first ask what
it does to OIL, then what oil does to the hike odds. Only if the answer is
"nothing" does the safe-haven edge get the wheel.

Open question (hypothesis): where is the flip point at which escalation stops
being a rates story and becomes forced-liquidation risk-off (the [[risk-off]]
funding case)? No episode this week reached it — equity indices did not enter
drawdown. Unresolved until we see one.
