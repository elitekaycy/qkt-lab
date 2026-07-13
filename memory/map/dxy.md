---
id: dxy
kind: asset
instruments: [XAUUSD]
always: true
edges:
  - to: XAUUSD
    sign: "-"
    strength: strong
    lag: same-day
    channel: denominator effect — gold is priced in dollars; a stronger dollar mechanically lowers the price, plus flows chase the move
    evidence: >
      Gold and DXY daily changes moved in opposite directions 42/62 sessions
      (68%) over 2026-04-13..2026-07-13 and 15/20 in the last month; DXY
      98.4->101.3 (+2.9%) while gold fell -15.5%. Sign-tally hand-computed
      2026-07-13 from daily closes (GC=F, DX-Y.NYB), tolerance ~±2 counts.
---
The broad dollar. Same-day inverse. A gold move AGAINST DXY is information: it
means a real (non-mechanical) bid or offer is in the market.
