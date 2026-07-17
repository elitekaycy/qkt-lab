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
- 2026-07-17: ECB July decision listed at 8:15 ET (= 12:15Z), independently
  matching LiteFinance's 12:15 GMT — resolved the ECB time contest that
  financecalendar's 13:45 CET entry had forced to "uncertain". Also
  corroborated UMich Jul 17 10:00 ET (upgrading it to confirmed), housing
  starts Jul 17, new home sales Jul 24, durable goods Jul 27, and FOMC
  Jul 29 14:00 ET, all consistent with Census/Fed primaries.
