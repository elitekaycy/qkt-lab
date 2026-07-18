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
