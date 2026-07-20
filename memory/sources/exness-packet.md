---
source: EXNESS decision packet
updated_at: 2026-07-20
score_managed_by: runner
---

# EXNESS decision packet

Good for instrument-local observations when quote fields and every timeframe carry explicit timestamps, session state, and provenance. Potentially useful for reconstructing short-horizon price episodes when raw bars are complete.

Bad at causal attribution without synchronized DXY, real-yield, news, and flow data. Zero-filled quote fields are ambiguous without null/error/session semantics. Mixed quote, 15m, and 1h cutoffs can make indicator state irreproducible.

## Track record

- 2026-07-20: Failed verification for the 2026-07-19T19:00Z packet. Bid, ask, spread, and quote timestamp were zero; visible/latest series disagreed between July 17 and July 19; missing 1h bars prevented reproduction of the stated EMA. The packet did preserve enough clues to flag the integrity failure, but not to identify its cause.

