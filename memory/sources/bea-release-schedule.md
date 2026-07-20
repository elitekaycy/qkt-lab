---
id: bea-release-schedule
what: BEA's own release schedule — primary source for GDP, PCE (personal income/outlays), trade, and corporate profits dates/times
url_pattern: https://www.bea.gov/news/schedule
---
Good for: pinning US GDP and PCE release timestamps from the agency that
publishes them — the same role Census's calendar-listview plays for durable
goods and new home sales. All BEA releases are 8:30 ET on the listed date.
Notably, this fetch WORKS from the research session while the other stats
primaries (BLS, FRED, Treasury) are blocked — so BEA + Census together cover
most US hard-data primaries for calendar confirmation.

Bad at: everything non-BEA — no CPI/jobs (BLS), no Fed events, no surveys, no
auctions. HTML page, not a feed: fine for WebFetch-and-read during a calendar
refresh, but not runnable as a runner procedure (no json/csv endpoint found
without an API key).

Track record:
- 2026-07-20: first use. Confirmed Q2 2026 advance GDP and June personal
  income/outlays both Jul 30 8:30 ET, published simultaneously — upgraded the
  cache's FOMC-week Jul 30 entry to confirmed (second source: Scotiabank).
