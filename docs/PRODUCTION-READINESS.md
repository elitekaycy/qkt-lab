# Production-readiness audit

Audit date: 2026-07-19. Scope: the current Exness XAUUSD deployment.

## Verdict

**Not approved for real money.** It is suitable for continued throwaway-demo
observation with KILL engaged. The local services and read paths work, but the
system has no accepted or closed broker trade yet, the preregistered proof phase
has not started, and the execution recovery boundary is not strong enough for
unattended capital.

This verdict is enforced in code:

- `lab.mode` is `demo`;
- KILL exists;
- `lab.mode: live` needs explicit human acknowledgement;
- the executable also recomputes the beliefs-vs-control A/B from joined episodes
  and refuses live startup unless it currently passes.

## Verified now

| area | evidence | result |
|---|---|---|
| Broker | authenticated Exness-MT5Trial9 account, USD 10,000 balance/equity | pass, demo only |
| Gateway | authenticated `/health/ready` response | pass |
| Account exposure | qkt positions result is empty | pass |
| Safety state | repository `KILL` exists and UI reports it | pass |
| Decision journal | React UI reads real Postgres rows at port 8421 | pass |
| Responsive UI | desktop collapsible sidebar and 390 px mobile drawer | pass |
| Journal context | versioned account, quote, bars, studies, calendar, and model packet in Postgres | pass in tests |
| Chart evidence | immutable PNG plus DB-backed official TradingView renderer | pass |
| Closed-trade analytics | source database has zero closed trades | **not yet provable with real outcome** |
| A/B proof | zero trades; minimum is 100 closed trades per arm | **not started** |

Empty realized-performance widgets are currently correct. Inserting a synthetic
row and calling it real would make the audit worse, not better.

## Safety fixes completed in this audit

- require TP whenever minimum RR is enabled;
- validate TP and SL direction;
- reject NaN, infinity, and non-numeric trade values;
- reject stale, crossed, missing, future, or invalid quotes before Codex;
- journal stale-market refusals without spending a model call;
- use unique chart paths so repeated cycles cannot overwrite evidence;
- serialize same-symbol cycles with a Postgres advisory lock;
- recompute the live A/B from the database instead of trusting a boolean;
- replace the second journal database/export stack with the first-party journal;
- source current balance/equity from the authenticated gateway;
- store the complete versioned decision context in the lab database;
- render EMA, RSI, and ATR in the TradingView journal view.

## Blocking work before real money

### P0 — execution integrity

1. **Durable order intent before venue write.** The current order is sent before
   the final decision row is inserted. A crash or database failure in that gap
   can leave a broker position the lab does not own in its store.
2. **Idempotency per bar.** The advisory lock prevents overlap, not a sequential
   rerun in the same hour. Add a durable cycle/order key that the gateway also
   honors, or a reconciliation protocol that proves whether an ambiguous order
   executed before retrying.
3. **Startup reconciliation.** Compare broker positions carrying this magic/comment
   with stored accepted tickets; alarm and block on any orphan or mismatch.
4. **Post-order verification.** Re-read the accepted position and prove ticket,
   volume, side, SL, and TP match before considering execution healthy.

These are one failure domain and should be designed together. A local database
idempotency key alone cannot prevent a duplicate after an ambiguous network
response unless the venue/gateway recognizes the same key.

### P0 — empirical proof

1. Run the full demo path through actual accepted orders, broker closes, join,
   and first-party journal.
2. Reach the preregistered 100 joined trades in each A/B arm.
3. Publish the result and confidence interval. Do not set `ab_passed` by hand.
4. Keep sizing conviction-flat until its separate calibration passes.

### P1 — broker and risk metadata

1. Obtain contract size, volume min/max/step, digits, tick value, and stop/freeze
   levels from the broker at runtime. Today contract size `100` and lot step
   `0.01` are configuration constants.
2. Round SL/TP to broker digits and reject stop-level violations before submission.
3. Implement real correlation grouping or rename the current “correlation
   haircut”: today it is total portfolio-heat headroom and does not use the
   configured correlation threshold.
4. Decide whether daily loss is lab-only or entire-account. Current realized
   loss covers lab tickets; another strategy on a shared account is excluded.

### P1 — management policy

Broker-side SL/TP now bound every accepted trade, which is the minimum safe
baseline. If prose invalidations, trailing, time exits, break-even, or partial
closes are desired, implement and test a deterministic manager. Do not let the
AI's written invalidation imply automation that does not exist.

### P1 — operations and deployment

- authenticated TLS ingress for journal/chart surfaces;
- encrypted secret delivery instead of a production `.env` bind;
- Postgres backup, restore drill, retention, and volume monitoring;
- alerts for scheduler failures, stale calendar, stale quotes, execution
  ambiguity, rejected orders, unjoined tickets, and service health;
- pinned images by digest and a documented rollback;
- staging soak over market-open, weekend, restart, and broker-disconnect cases.

## Deployment sequence when blockers are closed

1. Build immutable images and run the complete test suite.
2. Restore a production-like database into staging and run reconciliation.
3. Soak in demo with KILL released only for the approved test window.
4. Verify one actual accepted/closed trade in MT5, Postgres, and port 8421 with
   identical ticket, UTC times, net P&L, stored context, and image.
5. Complete and publish the A/B proof.
6. Configure authenticated TLS, secrets, backups, alerts, and rollback.
7. Start real money at the broker's minimum lot with hard account-level limits
   and a human-supervised canary period.
