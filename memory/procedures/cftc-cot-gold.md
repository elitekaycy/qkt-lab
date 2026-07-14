---
id: cftc-cot-gold
what: CFTC Commitments of Traders, COMEX gold futures, weekly, keyless
returns: rows[report_date_as_yyyy_mm_dd, noncomm_positions_long_all, noncomm_positions_short_all]
fetch:
  method: GET
  url: https://publicreporting.cftc.gov/resource/6dca-aqww.json
  params:
    $limit: "104"
    $where: market_and_exchange_names like 'GOLD%'
    $order: report_date_as_yyyy_mm_dd DESC
  parser: json
validate:
  min_rows: 50
  columns: [report_date_as_yyyy_mm_dd, noncomm_positions_long_all, noncomm_positions_short_all]
  freshness_days: 14
---
Speculative positioning in COMEX gold: net non-commercial = long - short (e.g.
2026-07-07 printed 194,246 net long). Weekly, published Friday for the prior
Tuesday, so freshness allows 14 days. Keyless Socrata endpoint — the $-prefixed
params are Socrata query syntax, not shell. Crowded-long extremes are a
squeeze-risk input, not a direction signal on their own.
