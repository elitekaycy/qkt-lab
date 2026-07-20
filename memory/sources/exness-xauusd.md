---
id: exness-xauusd
what: The desk's execution venue feed for XAUUSD (EXNESS) — session hours and quote-staleness behavior
url_pattern: https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours
---
Good for: the only feed whose prices the desk actually transacts at, so its
session boundaries — not CME's — define when a packet quote can be live.
Multiple independent third-party docs (goldsniper.io, tradingbeasts.com, and
Exness marketing pages surfaced via WebSearch 2026-07-18) agree XAUUSD on
Exness is 24/5: open Monday ~01:00 GMT, CLOSED Saturday and Sunday.

Bad at: primary verification — the Exness help-center page itself returns 403
to the research session's fetcher, so the exact weekly close is contested
across secondary sources (Friday 21:45 GMT vs 23:59 GMT variants). OPEN
QUESTION: pin the Friday close minute from inside the platform or via the
runner. Until then treat 21:45Z Friday as the conservative last-live moment.

Track record:
- 2026-07-20: 17 more tickets, Sat Jul 18 09:00Z through Sun Jul 19 ~20:00Z —
  the anomaly ran the ENTIRE weekend, same alternation as diagnosed Jul 19:
  some packets carry stale Friday quotes (~24-40h old, correctly stamped),
  others carry cached data RE-STAMPED live (quote timeMs matching packet
  'now', in-progress bars opening on the current weekend hour). New datum: a
  Sun ~19:00-20:00Z 1h bar with v=5300 and a live-looking quote — 2h+ before
  even the earliest contested reopen (~22:00Z Sun per one secondary source;
  ~01:00 GMT Mon per others). Volume on a re-stamped bar means the packet
  builder synthesizes/copies volume too, so nonzero v is NOT evidence of a
  live session. Web re-check 2026-07-20 (help-center still 403; secondary
  pages incl. exness.com/blog, scribehow SEO pages): unanimous that Exness
  gold is closed Sat/Sun — no weekend session launched. Alternative
  explanation (venue reopened early Sunday) stays unfalsified only for the
  19:00-20:00Z tickets; next weekend's first genuinely-live bar will pin the
  reopen minute — OPEN QUESTION, worth one targeted check next Sunday.
  Chart-pack lag also persisted: charts still ended Fri Jul 17 ~15:00Z in
  Sat-afternoon packets. Standing flag to runner unchanged: session table
  decides liveness, packet timestamps do not; nothing trades off Sat/Sun
  packets. If weekend cycles are not going to be skipped by the scheduler,
  they should at least be tagged market_closed so the distiller stops
  raising one ticket per hour.
- 2026-07-19: ~15 tickets spanning Sat Jul 18 01:00Z through Sun Jul 19 05:00Z
  show the packets ALTERNATING hour to hour between (a) stale reads — quote
  timeMs decoding to Friday ~20:00-21:00Z, price pinned at the ~4023 close —
  and (b) live-looking reads — quote timeMs matching packet 'now' (e.g. 13:58Z
  Saturday), in-progress 1h/15m bars stamped same-hour Saturday, and one Sunday
  05:00Z 15m bar with nonzero volume (v=1752). Web re-verification (WebSearch
  2026-07-19, exness.com and get.exness.help both 403) is unanimous that Exness
  gold remains 24/5, closed Sat/Sun — so the live-looking reads cannot be a
  real weekend session. A consistent stale re-emit is also ruled out: half the
  packets carry fresh weekend timestamps. Best explanation: some component
  (packet builder or quote cache) intermittently RE-STAMPS cached Friday data
  with fetch-time timestamps — and appears to synthesize bar boundaries too,
  since "fresh" weekend bars open on the current hour. Confusion risk to note:
  Vantage (a different broker) launched "XAUUSD247" 24/7 weekend gold CFDs in
  Jul 2026; headlines about it must not be mistaken for an Exness session
  change. FLAG TO RUNNER (upgraded): timestamps in weekend packets are not
  trustworthy even for staleness detection — the session table, not the packet
  clock, must decide liveness; nothing trades off Sat/Sun packets. Related: the
  chart pack lags separately (Jul 18 tickets: both chart images ended Jul 17
  ~15:00Z, ~6h before the Friday close, ~21h behind 'now').
- 2026-07-18: two anomaly tickets reported "live quote and fresh bars" at
  01:00Z and 04:00Z on SATURDAY Jul 18. Every documented schedule has the
  venue closed then; no evidence found of an Exness weekend gold session
  (weekend trading there is crypto-only per its own marketing). Conclusion:
  the pipeline re-emitted Friday's last ticks without a staleness stamp —
  a venue-clock/packet-scheduler issue, not a market session. Flagged to the
  runner: packets should carry bar age vs. a venue session table, and the
  playbook's session table needs an explicit weekend row saying "nothing
  trades off Sat/Sun packets". Cross-check that supports the stale-tick read:
  the Jul 18 packet quote sat at Friday's ~4023 close level (GC=F last close
  4023.0, yahoo-chart 2026-07-18).
