# The full pipeline

Companion to PLAN.md (build order) and MEMORY.md (the four memory kinds).
This is the whole system in motion: four clocks, who writes what, and a worked
week showing a decision become an outcome become knowledge become a better
decision.

---

## Four clocks

Nothing nests. Each is a separate process with its own prompt, its own token
budget, and — critically — its own **write permissions on memory**.

| clock | cadence | reads | writes |
|---|---|---|---|
| **RESEARCH** | daily + anomaly-triggered | web, all memory, market data | `map/`, `sources/`, `procedures/` |
| **TRADE** | per bar close (hourly) | retrieved memory slice, live venue | `decision` rows |
| **JOIN** | every 15 min | venue deal history | `outcome` rows, anomaly triggers |
| **DISTILL** | nightly | `decision ⋈ outcome`, map | `beliefs/` (proposals only — code sets status) |

The permissions column is the architecture. The trader cannot edit its own
memory. The distiller cannot see an open trade. The researcher cannot place an
order. Each is prevented from marking its own homework.

```
   RESEARCH ─────────────────► map/ sources/ procedures/ ──┐
      ▲                                                    │
      │ anomaly triggers                                   │ retrieved slice
      │                                                    ▼
   JOIN ◄──── venue ◄──── TRADE ◄─────────────── beliefs/ (ACTIVE only)
      │                     │                              ▲
      │                     ▼                              │
      └──► outcome ──► decision ──► DISTILL ───────────────┘
                                    (code scores, LLM proposes)
```

---

## RESEARCH — the analyst's own time

Two modes, same session type: open-ended Codex with web search, the full memory,
and a hard output contract — **come back with durable artifacts, not prose.**

**Scheduled (daily, ~30 min budget).** Standing brief: keep the map current, keep
the sources scored, find what you don't understand yet. Work it typically does:

- A WGC quarterly drops → update `map/central-bank-demand.md` with the new
  official-sector number, re-score the source card.
- It suspects the real-yield relationship has decayed further → pulls 20 years of
  10y TIPS vs XAUUSD from FRED, recomputes the rolling 60-day correlation, updates
  the evidence section and the `strength:` field on `map/real-yields.md`.
  **This is validated against market data, not our trades — so it's allowed to be
  confident immediately.**
- It works out how to pull CFTC positioning reliably → writes
  `procedures/fetch-cot-positioning.md` with the working curl and the gotchas
  (three-day lag, disaggregated not legacy report, holiday shifts).

**Anomaly-triggered.** This is the one that makes it an analyst rather than a
screen-watcher. Triggers are emitted by the other clocks:

- TRADE: price moved >3 ATR and **no factor in the current context explains it**
- TRADE: a driver the map calls `strength: strong` just failed to fire
- JOIN: a trade lost badly and its rationale still looks correct in hindsight
- JOIN: a trade won for a reason the rationale never mentioned
- any: a scheduled release printed far off consensus

Each spawns *find out what happened*, and must return an artifact — a new map
node, an amended "where it breaks" section, a source card, a procedure. Not a
paragraph that gets read once and lost.

**The measure of the analyst improving is that the anomaly rate falls** — fewer
things move gold that the map didn't see coming. That's a number you can plot.

---

## TRADE — the hourly cycle

### 1. Harvest

qkt is ground truth: `bot bars` (1h + 15m), `bot quote`, `bot account`,
`bot positions`, `bot eval "atr(14)"`. Then the external sources — calendar, FRED,
sentiment digest — **each fetched using a recipe from `procedures/`**, which is
why this step gets cheaper over time instead of being re-derived every hour.

A missing source is recorded as missing (`sources_missing: ["reddit"]`), never
silently treated as a neutral reading.

### 2. Retrieve the memory slice

Not all of memory — the slice that's live right now. This is where the map paying
for itself:

- **playbook** for the instrument (standing process)
- **map nodes currently in play.** CPI in four hours → pull `real-rates`,
  `inflation-surprise`, `dxy`. Don't pull `mine-supply`. Retrieval is
  context-conditioned, so the map can grow to hundreds of nodes without the token
  bill following it.
- **ACTIVE tactical beliefs** whose predicates match the context.
  CANDIDATE beliefs are deliberately withheld — if the model saw them it would act
  on them and they'd confirm themselves.
- **procedures index** — so the model knows what it can reach.
- **source cards** for anything it's reading right now, with their track records,
  so it knows how much to trust what it's looking at.

### 3. Propose

`codex exec` with the packet plus two chart PNGs. Strict JSON:

```json
{"action":"TRADE","side":"BUY","sl":2606.20,"tp":2621.40,"conviction":0.6,
 "setup":"london-open pullback to VWAP, 1h trend up",
 "factors":["trend:1h-up","level:vwap-touch","vol:atr-normal",
            "sentiment:reddit-mixed","calendar:cpi-4h-away"],
 "regime":{"session":"london","atr14":4.12,"trend_1h":"up","dxy_5d":-0.003},
 "map_nodes_used":["real-yields","central-bank-demand"],
 "beliefs_used":["gold-london-vwap-pullback"],
 "thesis":"CB demand is currently offsetting the real-yield channel, so I am not
           short into a firm DXY; the intraday structure is the trade, not macro.",
 "invalidation":"15m close below 2606, or DXY through 104.8",
 "unexplained":null}
```

Two new fields earn their place. `map_nodes_used` lets us later ask *which parts
of the worldview actually inform profitable decisions.* `unexplained` is the
model's own escape hatch — if it sees something the map doesn't cover, it says so
and that string becomes an anomaly trigger for RESEARCH.

The model cannot place an order and does not choose size. It proposes; code
disposes.

### 4. Gate — deterministic, no LLM

`require_sl`; `min_rr` recomputed from real prices; `news_blackout` from the
calendar; `max_daily_loss_pct` (realized-today + floating, vs equity);
`max_open_positions` / `max_exposure_lots` counted **from our own DB, never from
`qkt bot positions`** (that verb has no magic filter and sees the deployed
strategies too); per-instrument `max_lots`; kill-switch file.

Gated proposals are journaled as `action='GATED'` with reasons. They're the most
diagnostic rows in the table — what the model wanted, and what stopped it.

### 5. Size — arithmetic

```
risk_currency = equity × risk_per_trade_pct   → 10,142 × 0.5%   = 50.71
stop_distance = |entry − sl|                  → 2609.9 − 2606.2 = 3.70
lots = 50.71 / (3.70 × 100) = 0.137 → 0.13, capped by max_lots
```

### 6. Execute + journal

```
qkt bot buy 0.13 ICM:XAUUSD --sl at:2606.20 --tp at:2621.40 --as lab-xau --json
→ {"ok":true,"ticket":88412,"deal":51199,"fillPrice":2609.94,"retcode":10009}
```

One `decision` row — ticket, prices, setup, factors, regime, thesis, rationale,
chart paths, `map_nodes_used`, `beliefs_used`, `procedures_used`, `sources_read`,
arm, model, prompt_sha, and **`risk_at_entry`** (the denominator of R later; you
cannot reconstruct it after the fact).

Note what that row now captures: not just *what* it did, but *what knowledge it
used to do it*. That's what makes the memory itself scoreable.

---

## JOIN — every 15 minutes

Ticket 88412 gone from `bot positions` ⇒ closed. Sweep
`bot history --since <open day>` for every deal with `positionTicket == 88412`:

```
IN   lots 0.13  price 2609.94  profit 0       commission -0.91  swap  0
OUT  lots 0.13  price 2621.40  profit 148.98  commission  0     swap -0.22
```

Aggregate across **all** deals for the ticket — commission books on the IN deal,
so summing only OUT rows under-counts cost.

```
net_pnl    = 148.98 − 0.91 − 0.22 = 147.85
r_multiple = 147.85 / 48.62 = +3.04 R
duration   = 6h 10m
```

Then JOIN checks the episode for anomalies and fires triggers: did it lose while
its thesis stayed intact? did it win for a reason the thesis never named? Either
way, RESEARCH gets a task.

---

## DISTILL — nightly

Separate session, reads `decision ⋈ outcome` and the map, writes belief
*proposals*.

**LLM proposes:**
```json
{"op":"ADD","id":"gold-vwap-pullback-london",
 "statement":"XAUUSD pullbacks to VWAP in the first London hour resolve upward",
 "predicate":["symbol = ICM:XAUUSD","side = BUY",
              "regime.session = london","factors contains level:vwap-touch"],
 "mechanism":"[[london-liquidity]] — the first hour's flow reprices the Asian
              range; VWAP is where that flow clears."}
```

**Code disposes.** `beliefs.py` compiles the predicate to SQL, scores it over
**every matching trade — not just trades the belief caused** (the difference
between learning and self-confirmation), and sets the status arithmetically:

- **CANDIDATE → ACTIVE** needs `n ≥ 30` *and* survival of a family-wide
  multiple-testing correction across all candidates that night (Benjamini-Hochberg,
  or the DSR machinery qkt-forge already has). Forty proposed lessons where one
  clears p<0.05 is a max-of-N statistic, not a discovery.
- **ACTIVE → WEAKENING → INVALIDATED** as losses drag it down. Contradicting
  outcomes *decrement*; nothing is deleted. Invalidated beliefs stay in git with
  their history — that's how you avoid re-learning the same wrong thing next year.
- Scored on realized net PnL only. Never on the model's self-assessment.

A belief carrying a `mechanism` link into the map is treated as a stronger
hypothesis than a bare pattern — not a lower bar to activate, but a reason the
distiller was right to look there. Beliefs with no mechanism are flagged as
likelier noise.

**And the memory itself gets scored.** Because decisions record
`map_nodes_used` / `sources_read` / `beliefs_used`, DISTILL can answer: which map
nodes appear in profitable decisions? which sources were being read before the bad
ones? That feeds the source usefulness scores and tells RESEARCH where the map is
load-bearing versus decorative.

---

## A worked week

**Mon 06:00 — RESEARCH (scheduled).** Notes gold held firm through a 12bp real-yield
backup on Friday. That contradicts `map/real-yields.md` (`strength: strong`).
Pulls FRED, recomputes rolling correlation: −0.62 long-run, ~0.0 over the last
three years. Amends the node — relationship real but currently *suppressed*, with
a "where it breaks" pointer to `[[central-bank-demand]]`. Downgrades
`strength: strong → contested`. Writes an evidence chart.

**Mon 08:00 — TRADE.** Retrieval pulls the just-amended `real-yields` node. The
model reads that the macro short is not currently reliable and explicitly declines
to fade the rally on yields; takes the intraday VWAP pullback instead. Thesis
records exactly that. Gates pass. Sized at 0.13. Ticket 88412.

**Mon 14:10 — JOIN.** TP hit. +3.04R. Outcome row written. No anomaly.

**Wed 12:30 — TRADE.** CPI prints hot. Blackout gate blocks any new order ±30 min.
Proposal journaled as `GATED / news_blackout` — data, not a discarded event.

**Wed 13:15 — TRADE.** Gold *rallies* on the hot print. Nothing in the context
predicted that. Model sets `unexplained: "hot CPI, gold up 2 ATR — inflation-hedge
bid overwhelming the rate channel?"` → anomaly trigger fires.

**Wed 13:20 — RESEARCH (anomaly).** Web search + FRED. Finds the market is pricing
cuts *despite* the print, and ETF flows turned positive. Writes a **new map node**
`map/inflation-hedge-bid.md` with its transmission channel and the condition under
which it dominates the rate channel. Links it from `real-yields` "where it breaks."

**Thu 08:00 — TRADE.** Retrieval now pulls `inflation-hedge-bid` because there's an
inflation print in the window. **The agent knows something on Thursday it did not
know on Wednesday, and it learned it because it noticed it didn't understand
something.** That's the loop.

**Sun 22:00 — DISTILL (weekly cycle).** 34 closed trades match the
`gold-vwap-pullback-london` predicate. `n=34, mean_R=+0.31, t=2.4`. Passes the
n≥30 floor. Family-wide BH correction across the 11 candidates that night: it
survives. **CANDIDATE → ACTIVE.** From Monday it enters the trader's context.

Meanwhile `reddit-bullish-precedes-gold-up`: `n=61, mean_R=−0.02, t=0.3`.
**INVALIDATED.** It stops entering context, and you now have an evidence-based
answer to "is the sentiment feed worth its API bill" rather than an opinion.

---

## What stays closed

Everything above is wide open — what it reads, where it searches, what it maps,
what it remembers. Three constraints hold:

1. **The model never places an order.** It proposes; code gates and executes.
2. **The model never sizes the position.** Lots are arithmetic.
3. **Research generates hypotheses; it does not confer edge.** The map may say gold
   *should* fall. A belief that says *and therefore this setup pays 0.4R* still
   needs its 30 trades and its multiplicity correction.

Without those three, an agent with unbounded research reach and a live trigger is
not an analyst — it's a very well-read incident.
