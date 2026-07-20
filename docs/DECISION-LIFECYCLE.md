# Decision lifecycle: scheduler to journal

This describes the code that is running, not a future architecture. All internal
times are UTC.

## 1. Scheduler

`bin/gen-crontab` generates the scheduler from `lab.yaml`:

| cadence | command | purpose |
|---|---|---|
| `0 * * * *` | `bin/trade EXNESS:XAUUSD` | one hourly decision cycle |
| `*/15 * * * *` | `bin/join` | join broker closes into the journal database |
| `0 22 * * *` | `bin/distill` | score outcomes and propose beliefs |
| `0 6 * * *` | `bin/research` | refresh research artifacts and calendar |

Supercronic runs the generated file and sends output to the scheduler container
log. `bin/trade` holds a Postgres advisory lock for the symbol, so cron, a manual
invocation, and another scheduler replica cannot overlap the same cycle.

## 2. Deterministic preflight

`lab.context.gather` asks qkt for:

- the authenticated Exness account and current equity;
- bid, ask, spread, and the broker quote timestamp;
- 200 broker candles for 1h and 15m (at least 50 are required);
- ATR(14), EMA(50), and RSI(14);
- the XAUUSD playbook.

The quote then passes a code-only integrity/freshness gate. Missing, crossed,
non-finite, future, or older-than-120-second prices produce a journaled `GATED`
decision before Codex runs. This is important when MT5 retains Friday's last
tick through the weekend.

## 3. Context and evidence

The calendar cache is read from `memory/calendar/upcoming.yaml`. It is populated
by the separate research clock, requires corroboration, and fails closed when
missing or older than 30 hours.

Retrieval supplies:

- the instrument playbook;
- relevant causal-map nodes;
- `ACTIVE` beliefs for the beliefs A/B arm;
- no tactical beliefs for the control arm;
- upcoming relevant events and explicit missing-source labels.

The exact broker candles and derived EMA/RSI/ATR series are archived before the
proposal. Each cycle gets immutable unique PNG and JSON sidecar paths. The PNG is
the static model input. The JSON sidecar drives the official TradingView
Lightweight Charts renderer in the journal, including candle, EMA, RSI, and ATR
panes; its screenshot button saves that complete TradingView view.

## 4. Codex headless proposal

The trader runs through ephemeral `codex exec`:

- read-only sandbox;
- shell, apps, subagents, and web search disabled;
- the bounded JSON packet plus chart images are its only decision inputs;
- it can return only a proposal; it cannot invoke qkt or choose a lot number.

The requested fields include action, side, SL, TP, conviction, setup, factors,
regime, thesis, rationale, invalidation, map nodes, beliefs, and unexplained
observations. Code rejects malformed actions, sides, convictions, and all
non-numeric or non-finite trade numbers. Agent failure is stored as
`NO_TRADE / agent_error`.

`NO_TRADE` is a complete decision: it is timestamped and stored with the model's
reasoning and evidence.

## 5. Size and gates

For a proposed market trade, entry is the current ask for BUY and bid for SELL.
Sizing is deterministic:

```text
base risk       = equity × 0.5%
stop distance   = |entry − SL|
raw lots        = base risk / (stop distance × 100 oz per XAUUSD lot)
                 × conviction multiplier × heat haircut
final lots      = floor to 0.01, capped at 0.30 lots
```

Conviction is recorded but its multiplier is exactly `1.0` while
`sizing.stage: flat`. It may affect money only after a reviewed calibration
supports the fitted stage.

The heat haircut shrinks the next trade as stored open risk approaches 2% of
equity. The following code-only gates all run after sizing:

- KILL file;
- SL present and on the loss side;
- TP present and on the profit side;
- actual RR from entry/SL/TP is at least 1.5;
- finite prices and positive size;
- per-instrument, open-position, and total-lot caps;
- realized plus floating daily loss below 2%;
- fresh/corroborated calendar and no high-impact event inside ±30 minutes.

Any rejection becomes `GATED` with every rejecting gate stored. The model's own
RR claim is never trusted.

## 6. Execution and management

`lab.execute.place` rechecks KILL and sends one qkt market order with broker-side
SL and TP attached. If accepted, the decision stores the MT5 position ticket,
deal, actual fill, retcode, broker symbol, qkt version, and:

```text
risk_at_entry = |actual fill − SL| × lots × 100
```

Today, management means broker-held SL and TP only. The prose `invalidation`
field is journal evidence; it is **not** an automatically monitored exit rule.
There is no trailing stop, break-even move, time stop, partial-close manager, or
LLM management loop. Those features must not be inferred from the rationale.

## 7. Close, calculations, and journals

Every 15 minutes the joiner compares lab-owned open tickets with MT5 and reads
all IN and OUT deals for a closed position. It supports partial close aggregation:

```text
gross P&L = sum(deal profit)
commission = sum(all IN and OUT commission)
swap = sum(all deal swap)
net P&L = gross P&L + commission + swap
R = net P&L / risk_at_entry
```

The Postgres `decision` and `outcome` rows are the only journal source of truth.
Each decision also carries a versioned `context_snapshot` JSONB document with
the account, quote, complete broker-bar sets, indicators, calendar, exact model
packet, and TradingView-ready chart series. Port 8421 shows all `TRADE`,
`NO_TRADE`, and `GATED` decisions, exact UTC times, reasoning, broker result,
analytics, calendar, and chart evidence without an export database.

The “Equity” widget is explicitly a cumulative realized lab net-P&L curve from
zero; it is not presented as the broker account-balance history. The account
widget separately reads current authenticated broker balance and equity.
