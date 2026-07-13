---
id: fred-real-yield-10y
what: 10-year Treasury inflation-indexed (real) yield, daily, keyless
returns: timeseries[observation_date, DFII10]
fetch:
  method: GET
  url: https://fred.stlouisfed.org/graph/fredgraph.csv
  params:
    id: DFII10
  parser: csv
validate:
  min_rows: 1000
  columns: [observation_date, DFII10]
  freshness_days: 7
  value_range: [-3.0, 8.0]
  value_column: DFII10
  date_column: observation_date
---
The core opportunity-cost input for gold. Keyless: the graph CSV endpoint needs
no API key. Values are percent (2.31 = 2.31%); anything outside [-3, 8] is a
parse failure, not a market event. Weekends/holidays print "." — treated as null
by the validator's recent-window check only if persistent.
