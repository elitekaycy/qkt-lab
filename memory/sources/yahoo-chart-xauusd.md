---
id: yahoo-chart-xauusd
kind: http_json
url: https://query1.finance.yahoo.com/v8/finance/chart/GC=F
method: GET
params:
  interval: 1h
  range: 1mo
parser:
  rows_path: chart.result[0]
  timestamp_path: timestamp
  value_paths:
    open: indicators.quote[0].open
    high: indicators.quote[0].high
    low: indicators.quote[0].low
    close: indicators.quote[0].close
validators:
  min_rows: 100
  freshness_days: 3
  value_range:
    close:
      min: 500
      max: 10000
notes: COMEX front-month gold is a cross-check, not a substitute for EXNESS:XAUUSD. Preserve exchange timezone and null bars; do not silently forward-fill. Respect HTTP cache headers and rate limits.
---

# Yahoo chart cross-check for gold

Declarative hourly gold-futures fetch for testing whether a purported XAUUSD move is broadly present in an independent market series. Contract rolls and basis mean price levels must not be treated as identical to spot.
