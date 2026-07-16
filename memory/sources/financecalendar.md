---
id: financecalendar
what: Per-event pages for major macro releases (US and ECB), fetchable by plain HTTP
url_pattern: https://www.financecalendar.com/event/<event-slug>-<month>-<year>/
---
Good for: corroborating the DATE of a headline event (US CPI, ECB decisions)
when the primary source is unfetchable or vague. One page per event with date,
time, and a preview paragraph; plain HTTP, no login.

Bad at: ECB decision TIMES — its July 2026 ECB page states 13:45 CET decision /
14:30 presser, which is the pre-2022 ECB convention; the ECB moved to 14:15 /
14:45 in July 2022. Treat any off-convention time it gives as suspect until a
primary source confirms. Preview prose is generic filler ("hawks could push for
another move") — never evidence, never a channel.

Track record:
- 2026-07-14: US CPI date/time (Jul 14 8:30 ET) matched BLS schedule. Used as
  second source, held up.
- 2026-07-16: ECB July date (Jul 23) matched the ECB's own Governing Council
  calendar; its TIME conflicts with the post-2022 convention, so the calendar
  entry was marked uncertain rather than trusting it.
