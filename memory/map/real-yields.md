---
id: real-yields
kind: state
instruments: [XAUUSD]
always: true
edges:
  - to: XAUUSD
    sign: "-"
    strength: contested
    lag: same-day
    channel: opportunity cost — gold pays no yield, so the real yield on Treasuries is the cost of holding it
    inverts_when: central-bank demand is elevated and price-insensitive (2022-2026)
    evidence: rolling 60d corr mean -0.62 over 2006-2026, but near zero 2023-2026 — relationship real, currently suppressed
---
Gold pays no yield, so the real (inflation-adjusted) Treasury yield is the
opportunity cost of holding it. Historically the single strongest macro channel
for gold — and currently SUPPRESSED: official-sector buying has been
price-insensitive since 2022, so do not trade this channel naked. Check
[[central-bank-demand]] before leaning on it.

Transmission: 10y TIPS yield -> holding cost -> ETF flows -> spot. Lag: same-day
to 2 days on the flow leg.
