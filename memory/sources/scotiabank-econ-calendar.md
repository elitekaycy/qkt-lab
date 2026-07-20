---
id: scotiabank-econ-calendar
what: Full-month economic release calendar (US, Canada, Eurozone, some Asia) with ET times, one page per month
url_pattern: https://www.scotiabank.com/ca/en/about/economics/economics-publications/post.other-publications.calendar-of-economic-release-dates.calendar-of-economic-release-dates--<month>-<year>-.html
---
Good for: a whole month of US + Eurozone + Canada releases in one plain-HTTP
fetch, with ET times — covers the gap that killed investrade last refresh
(its next-week page 404s until late in the prior week, while this page exists
for the entire current month). Includes central-bank meetings (ECB, FOMC) with
times, which the Census/BLS primaries obviously lack. Useful as the
cross-region second source that lets a refresh mark events confirmed.

Bad at: granularity and completeness — it is a bank summary, not a feed. No
Fed speakers, no auctions, no revisions of moved dates between monthly
publications, and Asia coverage is spotty (Japan CPI listed, PBoC not). The
month page must exist for the month you need; untested whether next-month
pages publish early.

Track record:
- 2026-07-20: fetched for FOMC-week (Jul 27-31) detail while investrade's
  27-31 page still 404s — delivered the whole week: consumer confidence +
  Richmond Fed + Case-Shiller Jul 28, FOMC Jul 29, Q2 advance GDP + personal
  income/outlays Jul 30 (matches BEA primary), ECI + Chicago PMI + UMich
  final Jul 31, plus eurozone Q2 GDP Jul 30 and flash CPI Jul 31. One MISS to
  weigh against it: today's read put durable goods on Jul 28, contradicting
  Census's primary (Jul 27) AND this page's own Jul 17 reading — likely
  conflated with Census's Jul 28 "Advance Economic Indicators" release. First
  recorded date error for this source; forced the cache's durables entry down
  to uncertain.
- 2026-07-17: ECB July decision listed at 8:15 ET (= 12:15Z), independently
  matching LiteFinance's 12:15 GMT — resolved the ECB time contest that
  financecalendar's 13:45 CET entry had forced to "uncertain". Also
  corroborated UMich Jul 17 10:00 ET (upgrading it to confirmed), housing
  starts Jul 17, new home sales Jul 24, durable goods Jul 27, and FOMC
  Jul 29 14:00 ET, all consistent with Census/Fed primaries.
- 2026-07-18: re-fetched for the Jul 20-27 window. Corroborated US leading
  indicators Jul 20 10:00 ET (promoted to confirmed) and Japan CPI Jul 23
  19:30 ET; ECB/new-home-sales/durables entries unchanged. Puts UK CPI on
  Jul 21 (2:00 ET = 06:00Z) against LiteFinance's Jul 22 — the date contest
  is now 2-vs-1 for Jul 21, so the cache entry moved to Jul 21 but stays
  uncertain. Completeness limits confirmed again: no jobless claims, no
  S&P flash PMIs, no Treasury auctions, no regional Fed surveys (KC Fed,
  Chicago Fed NAI all absent).
