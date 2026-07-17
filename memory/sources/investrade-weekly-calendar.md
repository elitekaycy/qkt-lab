---
id: investrade-weekly-calendar
what: US weekly economic-event calendar with exact ET times, one page per week
url_pattern: https://investrade.com/weekly-event-calendar-MM-DD-YYYY-MM-DD-YYYY/
---
Good for: a full trading week of US releases in one fetch, with times to the
minute in ET — CPI/PPI/retail sales/claims plus the second-tier prints
(Empire, Philly, NAHB, TIC, UMich) that aggregator summaries drop. Fetchable
by plain HTTP where the primary sources are not (bls.gov and
fred.stlouisfed.org return 403 to the research session's fetcher;
home.treasury.gov CSV times out).

Bad at: Fed events — it listed no Beige Book and no Fed speakers for a week
that had the chair's debut semiannual testimony on BOTH days of CPI/PPI. Never
use it as the only source for anything Fed-related, and it is US-only (no
China data, no ECB). URL must be constructed per-week, so misses moved/added
events between fetches.

Track record:
- 2026-07-13: times for CPI (Jul 14 8:30 ET), PPI (Jul 15 8:30 ET), retail
  sales (Jul 16 8:30 ET) all matched the BLS schedule and Census release
  schedule independently. Missed both Warsh testimonies and the Beige Book.
- 2026-07-16: next week's page (weekly-event-calendar-07-20-2026-07-24-2026)
  returned 404 on Thursday morning — pages appear to publish late in the prior
  week. Cannot be the corroborating source for a refresh that runs mid-week
  and reaches into the following week; Census list-view calendar filled the
  gap this run.
- 2026-07-17: its UMich Jul 17 10:00 ET time was corroborated by Scotiabank's
  monthly calendar (upgraded that event to confirmed), and its Jul 13-17 week
  of times held throughout — including retail sales/claims/Philly Fed at
  8:30 ET Jul 16, verified against the actual print reaction. For weeks it
  covers, its ET times remain the best available; the 404-until-late-week
  limitation stands (scotiabank-econ-calendar now covers that gap).
