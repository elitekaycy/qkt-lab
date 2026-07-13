---
id: fred-dxy
what: Broad dollar index (DTWEXBGS), daily, keyless
returns: timeseries[observation_date, DTWEXBGS]
fetch:
  method: GET
  url: https://fred.stlouisfed.org/graph/fredgraph.csv
  params:
    id: DTWEXBGS
  parser: csv
validate:
  min_rows: 1000
  columns: [observation_date, DTWEXBGS]
  freshness_days: 10
  value_range: [80, 150]
  value_column: DTWEXBGS
  date_column: observation_date
---
Same-day inverse channel for gold. Keyless via the graph CSV endpoint.
