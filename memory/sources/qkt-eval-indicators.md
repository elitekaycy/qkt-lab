---
id: qkt-eval-indicators
what: indicator values (atr/ema/rsi) in the decision packet, via `qkt bot eval` against the mt5-gateway
---
Good for: venue-truth indicators computed on the same bars the charts render —
no third-party feed drift. The `bars` verb and `eval` verb share the gateway
data path, so if charts render, bar data is present.

Bad at: failing loudly. Two separate null paths in lab/context.py (~line 101),
and only ONE of them is recorded in sources_missing:
- QktError (gateway reject, timeout) -> null + `indicator:<expr>` in
  sources_missing. Visible.
- `isReady: false` in a successful eval response -> null with NO
  sources_missing entry. Invisible — the packet shows null indicators and
  nothing explains why. This violates context.py's own "MISSING is recorded,
  never silent" rule. Flagged to elitekaycy 2026-07-14; code fix is out of
  scope for a research run.

Failure mode to remember: `eval` fetches by TIME RANGE (count x tf, widened
~3x for gaps) and the gateway rejects ranges over 31 days. `bars` with
count=200 stays under the cap while `eval` with its old default count=500
(~62 widened days) got rejected — so bars present + all indicators null is
the signature of an eval-window reject, not a data outage.

Track record:
- 2026-07-14: anomaly ticket "atr(14)/ema(50)/rsi(14) null in packet despite
  bar data present" — root-caused to the eval-window reject above. Cycles
  before 01:15 UTC ran eval with default count=500; commit debf0db (01:15
  UTC) pins count=200 (~25 widened days, under the 31-day cap; ~3 warmups
  past the ema(50) lookback). Scheduler bind-mounts the repo so the fix was
  live from the next cycle. OPEN QUESTION: post-fix cycles not yet verified
  non-null — this research session cannot run qkt or query the decisions
  table (sandbox); check `select decided_at, sources_missing from decisions
  where decided_at > '2026-07-14T01:15Z'` next run with db access, and
  whether the packet's indicators are populated.
