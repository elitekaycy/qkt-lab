# qkt-lab — implementation plan

> Historical design record. The July 2026 implementation replaced the evaluated
> Deltalytix export plugin with the first-party React journal and one Postgres.

Status: plan, not started. Date: 2026-07-13.
Builds on the RFC verdict (own the store; markdown beliefs; gate the loop hard).
Two verification sweeps behind it: `qkt bot` source read (file:line pinned) and
the Deltalytix repo read (commit 3a8223a).

---

## What the sweeps changed

**1. The outcome join needs zero qkt changes.** `qkt bot buy --json` returns
`ticket` (the MT5 order ticket; for a market fill the position ticket equals it).
`qkt bot history --json` returns deal rows carrying `positionTicket`, `entry`
("IN"/"OUT"), `profit`, `commission`, `swap`, `timeMs`. So the lab keys its
decision record on `ticket` and joins on `positionTicket`. No `--note` flag, no
`bot journal add`, no qkt PR. qkt stays a pure execution surface; the lab owns
every byte of rationale. This kills the "greenfield piece (a)" from the RFC.

Do **not** join via the MT5 order comment. The comment is `bot-<as>-<epochms>`,
the wire caps it at 31 chars, and MT5 persists only ~16 — it comes back
truncated (`bot-manual-17523`). It is not a key.

**2. The LLM must not hold the trigger.** Gates are only real if they run outside
the model. The agent proposes a trade as structured JSON; a deterministic runner
validates it against `lab.yaml` and *then* shells out to `qkt bot buy`. The agent
gets read-only qkt verbs (`quote`, `bars`, `positions`, `account`, `eval`,
`history`) and no ability to send an order. This is the Project Vend lesson —
scaffolding and constraints, not self-restraint — and it is the difference
between a lab and a liability.

**3. Belief conditions must be machine-evaluable, or the loop is a fiction.**
A belief like "gold mean-reverts after the NFP spike" can only be scored
honestly if code — not an LLM — can decide which past trades match it. So each
belief carries a restricted predicate over the decision/outcome tables (a list of
`field op value` clauses, AND-ed). The distiller LLM *writes* the predicate and
the prose; deterministic code *evaluates* it, counts supporting/refuting tickets,
computes the stats, and decides the status transition. The LLM never sets a
belief's status. This is the single most load-bearing design call in the plan.

---

## Blocking decisions (need elitekaycy before Phase 1)

**D1 — separate MT5 account for the lab.** `qkt bot positions` has no magic
filter (BotGateway.kt:105) and returns *every* position on the account, including
deployed strategies'. qkt-prod currently runs hedge_straddle and latch-stack.
If the lab shares that account: exposure gates, daily-loss gates, and equity
readings all get polluted by strategy PnL, and any `--all` close is a live
incident. Recommendation: a second demo MT5 account + gateway instance, and the
lab's close path is *only* ever `--ticket <known lab ticket>`. Never `--all`.

**D2 — licensing of the two private deps.** qkt-lab can be MIT day one, but it
depends on `qkt` (private) and `mt5-gateway` (no LICENSE file at all — issue #45
in that repo). "Usable by anyone" is false until both get a license decision.
Not a blocker for building; is a blocker for the README's claims.

**D3 — Deltalytix stays an optional plugin.** CC BY-NC is not open source, and
whether instrumenting a money-making operation counts as "commercial advantage"
is genuinely ambiguous. `journal.deltalytix.enabled: false` default; the loop
must run fully without it.

---

## Architecture

```
                    ┌──────────── cron ────────────┐
                    │                              │
              trade.sh (per instrument)      join.sh (15m)      distill.sh (nightly)
                    │                              │                    │
        ┌───────────┴──────────┐                   │                    │
        │ 1 gather context     │                   │                    │
        │   qkt bot quote/bars/positions/account   │                    │
        │   news (FRED/calendar)                   │                    │
        │   playbooks/<sym>.md                     │                    │
        │   memory/beliefs/*  (ACTIVE only)        │                    │
        │ 2 render charts (mplfinance) → PNG       │                    │
        │ 3 claude -p → PROPOSAL json  ◄── model never touches an order │
        │ 4 gates.py (deterministic) ── reject ──► decision row (no_trade)
        │ 5 qkt bot buy/sell --json → ticket       │                    │
        │ 6 decision row (ticket, rationale, …)    │                    │
        └──────────────────────────────────────────┘                    │
                    │                              │                    │
                    ▼                              ▼                    ▼
             ┌──────────────────────── Postgres (lab) ──────────────────────┐
             │  decision (ticket PK-ish)   outcome (ticket)                 │
             └──────────────────────────────────────────────────────────────┘
                    │                                                   │
                    ▼ (optional plugin)                                 ▼
             Deltalytix Postgres                              memory/beliefs/*.md
             (UUIDv5 idempotent insert)                       (git-tracked, code-scored)
```

The trader session and the distiller session are separate processes with
separate prompts and separate DB grants (trader: insert decision, read beliefs.
distiller: read decision+outcome, write beliefs). Letta's sleep-time pattern —
the agent that trades cannot edit its own memory.

---

## The join, precisely

Given a decision with `ticket = T`:

1. **Open detection** — `qkt bot positions --json | .[] | select(.ticket == T)`.
   Present ⇒ still open.
2. **Close detection** — absent from positions ⇒ closed (by TP, SL, or us).
3. **Outcome** — `qkt bot history --since <open_day> --json`, filter client-side
   to rows with `positionTicket == T` (there is no `--ticket` flag; default
   `--since` is 7d, so the joiner must pass an explicit `--since` covering the
   open date).
   - `net_pnl   = Σ profit + Σ commission + Σ swap` over **all** deals with that
     `positionTicket` — IN and OUT. MT5 books commission on the IN deal; summing
     only OUT rows silently under-counts cost.
   - `gross_pnl = Σ profit` (this is what Deltalytix wants; it subtracts
     commission itself).
   - `duration_s = (max OUT timeMs − IN timeMs) / 1000`.
   - Partial closes produce several OUT deals sharing one `positionTicket` —
     aggregate, don't take-first.
4. Write the `outcome` row.

Caveats pinned from source: `entry` collapses MT5's `INOUT`/`OUT_BY` into
`"OUT"`; a pending order's `deal` comes back `0` (so Phase 1 restricts to market
orders — pendings land in Phase 5 after a spike confirms the pending→position
ticket identity); `symbol` in history is the **broker-side** symbol (`XAUUSDm`),
not the qkt form (`ICM:XAUUSD`) — store both.

---

## Phase 0 — spikes (kill the plan cheaply if any fail)

Each spike is an hour or less. Do them before writing the runner.

| # | Spike | Passes if |
|---|---|---|
| S1 | On the lab demo account: `qkt bot buy 0.01 ICM:XAUUSD --sl … --tp … --json`, note `ticket`; close it; `qkt bot history --since 1d --json` | a row exists with `positionTicket == ticket`; commission appears on the IN deal; the IN/OUT pair reconciles to the terminal's reported PnL |
| S2 | Let a position close by **SL hit** (server-side, not our close call) | the OUT deal still shows up in `bot history` with the same `positionTicket` — i.e. the joiner works when we aren't the one closing |
| S3 | Deltalytix: `docker compose up` + seed + raw insert of one trade (UUIDv5 id) + a `Subscription` row | the trade renders in the UI, and re-running the insert is a no-op |
| S4 | `claude -p` with a chart PNG attached, forced to emit strict JSON | valid JSON on 10/10 runs; images actually influence the text. **Also confirms the Max pool still serves `claude -p`** (the subagent spend cap was hit 2026-06-15) |
| S5 | News: FRED release-dates API + a high-impact calendar source | we can answer "is there a red-folder event on XAUUSD in the next 60m" reproducibly. ForexFactory has no official API — if scraping is the only path, say so and pick a licensed free alternative |

S3 failing ⇒ drop Deltalytix (it is optional anyway). S1/S2 failing ⇒ the whole
join model is wrong and we stop and rethink. S4 failing ⇒ no loop at all.

---

## Phase 1 — one honest trade, end to end

Deliverable: a single cron-able command that gathers context, asks Claude for a
proposal, gates it, executes it on demo, and records the decision — plus a joiner
that fills in the outcome when the position closes. No memory, no charts, no
Deltalytix yet.

### Repo skeleton

```
qkt-lab/
  LICENSE (MIT)  README.md  PLAN.md
  lab.yaml
  docker-compose.yml            # postgres only, for now
  db/schema.sql
  lab/
    config.py     # lab.yaml → typed
    qkt.py        # subprocess wrapper: run(verb, *args) -> parsed json
    context.py    # gather quote/bars/positions/account + playbook + news
    agent.py      # claude -p invocation, strict-JSON proposal
    gates.py      # deterministic pre-order validation
    execute.py    # gate-passed proposal -> qkt bot buy/sell -> ticket
    store.py      # postgres: decision/outcome
    join.py       # outcome joiner
  prompts/trader.md
  playbooks/xauusd.md
  bin/trade  bin/join
```

### Schema (`db/schema.sql`)

```sql
create table decision (
  id             bigserial primary key,
  ts             timestamptz not null default now(),
  arm            text not null default 'beliefs',   -- beliefs | control (Phase 5 A/B)
  as_name        text not null,                     -- qkt --as
  symbol         text not null,                     -- ICM:XAUUSD
  broker_symbol  text,                              -- XAUUSDm (from history)
  action         text not null,                     -- TRADE | NO_TRADE | GATED
  side           text,                              -- BUY | SELL
  lots           numeric,
  sl             numeric,
  tp             numeric,
  expected_rr    numeric,
  -- the journal proper
  setup          text,
  factors        jsonb not null default '[]',
  news           jsonb not null default '[]',
  regime         jsonb not null default '{}',
  rationale_md   text,
  charts         text[] not null default '{}',
  beliefs_used   text[] not null default '{}',
  -- execution truth
  ticket         bigint unique,                     -- MT5 order/position ticket == join key
  open_deal      bigint,
  fill_price     numeric,
  retcode        int,
  accepted       boolean not null default false,
  gate_rejects   jsonb not null default '[]',
  -- provenance
  model          text,
  prompt_sha     text,
  canonical_dsl  text,
  cmd_sha256     text,
  qkt_version    text
);

create table outcome (
  ticket       bigint primary key references decision(ticket),
  closed_at    timestamptz not null,
  close_price  numeric,
  gross_pnl    numeric not null,      -- Σ profit
  commission   numeric not null,      -- Σ commission (signed as MT5 reports: negative)
  swap         numeric not null,
  net_pnl      numeric not null,      -- gross + commission + swap
  r_multiple   numeric,               -- net_pnl / risk_at_entry
  lots_closed  numeric not null,
  duration_s   bigint not null,
  deals        jsonb not null,        -- raw history rows, for audit
  joined_at    timestamptz not null default now()
);
```

`r_multiple` is the currency of everything downstream — beliefs are scored on it,
not on win rate alone. `risk_at_entry = |fill_price − sl| × lots × contract_value`;
compute it at join time from the decision row.

### Tasks

**T1.1 — `lab.yaml` + config loader.** The file from the RFC, plus:
`qkt.bin` (path to the qkt CLI), `qkt.config` (qkt.config.yaml path),
`lab.kill_switch` (path to a file whose existence blocks all orders).

**T1.2 — `lab/qkt.py`.** Thin subprocess wrapper. Every call appends `--json`,
parses stdout, and **checks the shape**: bot verbs return an object on error
(`{"ok":false,"error":…}`) even when success is an array — so a list-returning
verb that comes back as a dict is an error, not an empty result. Non-zero exit
on a venue reject (exit 1) must raise. `retryAttempts` is 0 inside the bot CLI,
so the lab owns retry/backoff for transient gateway failures.

**T1.3 — `lab/context.py`.** Gathers, per instrument:
`bot account`, `bot positions <sym>`, `bot quote <sym>`, `bot bars <sym> --tf 1h
--count 200`, `bot bars --tf 15m --count 200`, plus the playbook markdown and
(Phase 2) news. Emits one context dict. Note `bars` can return *fewer* than
`--count` bars without erroring — assert a minimum and abort the cycle if thin.

**T1.4 — `prompts/trader.md`.** Extends `examples/bot/SYSTEM_PROMPT.md`'s
ANALYZE → ACT with PLAN. The output contract is strict JSON, no prose:

```json
{
  "action": "TRADE" | "NO_TRADE",
  "side": "BUY" | "SELL",
  "lots": 0.02,
  "sl": 2608.4, "tp": 2621.0,
  "expected_rr": 2.1,
  "setup": "london-open pullback to VWAP",
  "factors": ["trend:1h-up", "level:prior-day-high", "vol:atr14-normal"],
  "news": [{"event": "US CPI", "at": "2026-07-14T12:30:00Z", "impact": "high"}],
  "regime": {"session": "london", "atr14_pct": 0.42, "trend_1h": "up"},
  "rationale_md": "...",
  "beliefs_used": []
}
```

The prompt states plainly that the model cannot place orders, that the proposal
will be mechanically gated, and that `NO_TRADE` is a first-class, unpenalized
answer. (Half of the published agent-trading failures are agents that felt
obliged to act.)

**T1.5 — `lab/gates.py`.** Pure function, `(proposal, context, config) → [reject…]`.
Order refused unless the list is empty. Gates:
`require_sl`; `min_rr` (recomputed from prices, never trusting `expected_rr`);
`max_open_positions` counted over **lab-owned tickets only** (from our DB —
never from `bot positions`, which sees other strategies); `max_exposure_lots`
same; `max_daily_loss_pct` from realized net PnL of lab tickets closed today +
floating PnL on lab tickets, against `bot account` equity; `max_lots` per
instrument; symbol whitelist; kill-switch file; and a news blackout window
(Phase 2). Every rejection is persisted on the decision row (`action='GATED'`,
`gate_rejects`) — a gated proposal is *data*, not a discarded event.

**T1.6 — `lab/execute.py`.** Market order only in Phase 1:
`qkt bot buy <lots> <sym> --sl at:<x> --tp at:<y> --as <as_prefix>-<sym> --json`.
Note the CLI's hand-rolled arg parser has no `--flag=value` form and treats an
option's *value* as a positional — put positionals first. `--as` must be ≤ 13
chars or the MT5 comment blows the 31-char wire cap and the order is rejected
outright (not truncated — rejected). Assert this at config load, not at trade time.

**T1.7 — `lab/store.py`.** Insert decision (always, including NO_TRADE and GATED).
Insert outcome. Idempotent on ticket.

**T1.8 — `lab/join.py`.** As specified in "The join, precisely" above. Runs every
15m from cron. For each decision with `ticket` and no `outcome`: still in
`bot positions`? leave. Else sweep history with `--since` = open date and
aggregate. Guard: if a ticket has an IN deal but no OUT after N days, alarm —
don't silently leave it unjoined.

**Phase 1 acceptance:** one demo trade proposed, gated, executed, recorded; it
closes; `join` fills `outcome` with a `net_pnl` that matches the MT5 terminal to
the cent; a second `join` run is a no-op; a proposal with no SL is rejected and
lands as a `GATED` row with the reason.

---

## Phase 2 — charts, news, playbooks

**T2.1 — `lab/charts.py`.** `bot bars --json` → mplfinance PNG (fields are
`t` epoch-ms, `o/h/l/c/v`). Two panes (1h context, 15m entry), SL/TP levels drawn
if the proposal exists. Charts are produced *before* the proposal (as model
input) and archived with the decision (`charts` column holds paths).

**T2.2 — `lab/news.py`.** Per S5's outcome. Interface:
`events(symbol, window) → [{event, at, impact, source}]`. Feeds both the model
context and the blackout gate. Per-instrument source lists live in the playbook
files, not in code.

**T2.3 — `playbooks/xauusd.md`.** The human-authored, slowly-refined "stored
process": which sessions to trade, what data to pull, what invalidates a setup,
which news matters. This is the file that makes future prompts *shorter*, not
longer — it replaces re-deriving context every cycle.

**Acceptance:** the model receives two chart images and a news block; a proposal
inside a high-impact blackout window is gated with reason `news_blackout`.

---

## Phase 3 — Deltalytix export (optional plugin, `enabled: false` default)

One-way, closed-trades-only, direct Postgres insert. Facts pinned from the repo:

- Table names are quoted PascalCase (`"Trade"`) — no `@@map`.
- **`id` must be the app's UUIDv5**, namespace `6ba7b810-9dad-11d1-80b4-00c04fd430c8`,
  over the pipe-joined string
  `userId|accountNumber|instrument|entryDate|closeDate|entryPrice|closePrice|quantity|entryId|closeId|timeInPosition|side|pnl|commission`.
  Then `ON CONFLICT (id) DO NOTHING`. `id` is the only unique key — random UUIDs
  duplicate every trade on every re-run.
- **Insert a `Subscription` row** (`status='ACTIVE'`, email matching the user's)
  or the UI silently hides everything older than 14 days.
- `pnl` is **gross** and signed; `commission` is a **positive magnitude** (the app
  computes `pnl - commission`). `timeInPosition` is **seconds**. `entryPrice`/
  `closePrice`/`entryDate`/`closeDate` are **strings** (dates must be UTC ISO or
  lexical ordering breaks). `side` is `"Long"`/`"Short"`.
- `comment` (String) takes our `rationale_md`; `tags` (String[]) takes our
  `factors`; `images` (String[]) takes chart **URLs** — serve `charts/` over HTTP
  and store `/img/...`, or the images won't render.
- Reads go through a 1h `unstable_cache`; after a raw insert the UI may lag up to
  an hour. Restart the app container to force it. Run a **production** build —
  the dev build has a TTL-less IndexedDB trade cache that will never show new rows.
- Auth: `LOCAL_DASHBOARD_AUTH_BYPASS=true` + `LOCAL_DASHBOARD_USER_ID`. No Supabase
  needed. `NEXT_PUBLIC_*` vars are baked at build time.

**Acceptance:** every closed lab trade appears in the Deltalytix UI with its
rationale and chart; running the exporter twice inserts nothing the second time;
`enabled: false` and the whole loop still runs.

---

## Phase 4 — beliefs + distiller

### Belief file

`memory/beliefs/<id>.md`, git-tracked, one belief per file:

```markdown
---
id: gold-london-vwap-pullback
status: CANDIDATE            # CANDIDATE | ACTIVE | WEAKENING | INVALIDATED
statement: "XAUUSD long pullbacks to VWAP in the first London hour resolve up"
predicate:                   # machine-evaluable; code scores, LLM only proposes
  - symbol = ICM:XAUUSD
  - side = BUY
  - regime.session = london
  - factors contains level:vwap
created: 2026-07-20
updated: 2026-08-14
---
n: 21   wins: 12   losses: 9
mean_R: +0.08   t: 0.91   p: 0.37
supporting: [88412, 88530, ...]
refuting:   [88477, 88611, ...]

CANDIDATE: n=21 < activate_min_trades=30. Not injected into trader context.
```

`memory/index.md` is a ~200-line always-loaded table of contents: id, status,
one-line statement, n. Only the index plus **ACTIVE** beliefs enter the trader's
context. Token cost falls as beliefs consolidate — the stated goal.

### The honest-scoring rules (these are the point)

1. **Code scores, the LLM only proposes.** The distiller emits belief *drafts*
   (statement, predicate, prose). `lab/beliefs.py` evaluates the predicate as SQL
   over `decision ⋈ outcome`, counts supporting/refuting tickets, computes mean R
   and a t-stat, and sets the status. The LLM never writes `status`, `n`, or a
   ticket list.
2. **A belief is scored over every matching trade, not just trades it caused.**
   Otherwise it is self-fulfilling. This is why CANDIDATE beliefs stay out of the
   trader's context and still accrue evidence — from incidental matches.
3. **Activation gate.** `CANDIDATE → ACTIVE` requires `n ≥ activate_min_trades`
   (30 default; a per-trade SR of 0.2 needs ~96 trades to reject zero edge, so 30
   is a floor, not a blessing) **and** family-level significance: at each nightly
   cycle, apply Benjamini-Hochberg (or the DSR machinery qkt-forge already has)
   across *all* candidate beliefs, not per-belief. The distiller proposing 40
   lessons and one clearing p<0.05 is a max-of-N statistic, not an edge.
4. **Contradiction decrements, never deletes.** A losing match moves a ticket to
   `refuting`; status recomputes. `ACTIVE → WEAKENING → INVALIDATED` as the stats
   decay. Invalidated beliefs stay on disk, in git, with their history.
5. **Scored on realized net PnL only.** Never on the model's self-assessment —
   LLM self-explanations are unfaithful and intrinsic self-correction doesn't work.
6. **Embargo is automatic** by the nightly cadence: a belief's stats only ever
   include trades closed before that belief version was written, and the trader
   only loads yesterday's beliefs. Don't break this by running the distiller
   mid-session.

**Acceptance:** distiller runs on a corpus of ≥50 closed demo trades; produces
beliefs with predicates that evaluate; hand-check that the supporting/refuting
ticket lists are exactly what the SQL predicate selects; no belief reaches ACTIVE
on n<30; a belief that goes cold demotes on its own within a week of losses.

---

## Phase 5 — prove it, or don't ship it

**T5.1 — A/B harness.** Deterministic arm assignment per cycle (hash of ts+symbol):
`beliefs` arm gets index+ACTIVE beliefs, `control` arm gets playbook only. Same
model, same gates, same sizing. Compare mean R with a proper test. This is the
experiment nobody in the literature has published — FINSABER, the Alpha Illusion
paper, and the anonymized-ticker benchmark all show the published wins were
leakage or memorization, and *no* paper shows a leakage-controlled ablation where
the memory module adds out-of-sample alpha. If our A/B says beliefs add nothing,
the honest outcome is to say so and keep the journal (which is valuable on its
own) without the loop.

**T5.2 — pendings + partial closes**, once S1/S2's ticket identity is confirmed
for pending fills.

**T5.3 — live gate.** `lab.mode: live` refuses to start unless the A/B has run to
a pre-registered minimum sample and passed. Pre-register the threshold *now*,
before seeing data.

---

## Explicit non-goals

- No knowledge graph (Graphiti/Neo4j) until multi-hop retrieval is a *measured*
  bottleneck. Trades have hard fields; "does factor X work in regime Y" is a SQL
  aggregate.
- No LangChain, no mem0, no Notion.
- No qkt changes. If the lab ever needs one, that's a signal the boundary is wrong.
- No claim that the loop works. It is a hypothesis with a test attached.

---

## Open questions for elitekaycy

1. Separate MT5 demo account for the lab? (D1 — I think this is required, not optional.)
2. Which instrument first — XAUUSD only, or XAUUSD + EURUSD from day one?
3. Pre-register the A/B success threshold now, or after Phase 1 gives us a
   trade-rate estimate?
