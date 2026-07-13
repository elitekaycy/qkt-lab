---
id: yahoo-chart
what: Cross-asset OHLC for any ticker (AAPL, ^VIX, DX-Y.NYB), keyless
returns: yahoo chart json (meta + quotes)
fetch:
  method: GET
  url: https://query1.finance.yahoo.com/v8/finance/chart/{ticker}
  params:
    range: "{range}"
    interval: "{interval}"
  headers:
    User-Agent: Mozilla/5.0
  parser: json
  json_path: chart.result
validate:
  min_rows: 1
---
The episode-study workhorse: cross-asset history with no key. This is what lets a
causal-graph edge earn its evidence from market data with zero trades.
Parameterized: run("yahoo-chart", ticker="^VIX", range="5d", interval="1d").
