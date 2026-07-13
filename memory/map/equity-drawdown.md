---
id: equity-drawdown
kind: event
instruments: [XAUUSD]
retrieve_on: [equity, aapl, nasdaq, spx, tech]
edges:
  - to: risk-off
    sign: "+"
    strength: strong
    lag: same-day
    channel: a large-cap selloff reprices equity risk broadly (index concentration)
  - to: growth-scare
    sign: "+"
    strength: moderate
    lag: same-day
    channel: mega-cap earnings/health read as a growth signal
---
A sharp drawdown in a mega-cap or an index. Two onward channels with DIFFERENT
speeds: the risk-off leg fires today, the growth-scare -> rates leg takes days.
An event can be bearish gold at 09:30 and bullish gold by Thursday.
