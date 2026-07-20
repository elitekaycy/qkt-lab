---
entity: EXNESS:XAUUSD packet integrity
type: market_data_quality
updated_at: 2026-07-20T00:00:00Z
---

# EXNESS:XAUUSD packet integrity

The 2026-07-19T19:00Z decision packet is not sufficient to establish a live, synchronized market state. This is a data-quality node, not a directional gold thesis.

## Typed edges

- from: weekend_or_inactive_session
  to: zero_bid_ask_spread_and_timestamp
  sign: positive
  strength: hypothesis
  lag: immediate
  dominates_when: the venue is closed or its quote stream is inactive
  inverts_when: a valid contemporaneous tradeable quote is present
  claim: A closed weekend market or inactive feed can produce an empty/zero quote payload; the packet does not expose an explicit session-status field, so these cases cannot be distinguished.

- from: independently_cached_timeframes
  to: packet_timeframe_desynchronization
  sign: positive
  strength: hypothesis
  lag: immediate_to_one_refresh_cycle
  dominates_when: 15m/current-quote data advance while the 1h series remains cached at 2026-07-17
  inverts_when: all series share a documented common cutoff and complete bar sequence
  claim: The July 19 current/15m timestamp combined with a 1h chart ending near July 17 is consistent with independently refreshed caches or a failed 1h backfill, but the packet contains no provenance fields that prove this mechanism.

- from: missing_weekend_reopen_1h_bars
  to: unverifiable_higher_timeframe_state
  sign: positive
  strength: hypothesis
  lag: until_backfill
  dominates_when: an indicated 1h EMA near 4009 is supplied without the bars needed to reproduce it
  inverts_when: a complete timestamped 1h series reproduces the indicator within declared rounding tolerance
  claim: The higher-timeframe state and EMA cannot be independently verified from the packet.

- from: late_asia_rally_4005_to_4028
  to: causal_driver
  sign: unknown
  strength: contested
  lag: unknown
  dominates_when: unknown
  inverts_when: unknown
  claim: No DXY, real-yield, flow, or timestamped news series was supplied, so attributing the rally to any macro channel would be narrative fitting.

evidence: unavailable as of 2026-07-20; no runnable stored market-data procedure or raw packet series was available in this cycle, so no episode statistic was fabricated. All causal claims above remain hypotheses or contested.

## Open questions

- Does the quote adapter expose venue session status and last-successful-update separately from quote time?
- Are zero values serialization defaults, or actual upstream fields?
- What are the cache keys, cutoffs, and refresh results for quote, 15m, and 1h payloads?
- Can the complete July 17-20 1h bar sequence reproduce the stated EMA near 4009?
- Did the 4005-to-4028 move coincide with DXY, US real-yield, geopolitical-news, or identifiable flow impulses? A synchronized episode study is required.

