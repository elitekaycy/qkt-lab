# The causal graph

The thing we are actually trying to model.

A top commodities PM does not look up facts. Given "AAPL down 6% pre-market" they
*traverse* — through sector concentration, through risk appetite, through the
dollar, through rate expectations — and arrive at a view on gold, along with an
honest sense of which leg of the argument is load-bearing and what would flip it.

That traversal is the skill. This document specifies it as a data structure.

---

## Why isolated nodes aren't enough

The first draft of the map had one file per driver of gold: real yields, DXY,
central-bank demand. Each with its own evidence and its own "where it breaks".

That is a lookup table, not a mind. It cannot answer "what does Apple have to do
with gold", because Apple is not a driver of gold — it is four hops away, and the
path runs through things that are.

Worse: it cannot represent **disagreement**. And disagreement is where the money is.

---

## The structure

### Nodes are entities, not "drivers of gold"

An asset (`AAPL`, `XAUUSD`, `DXY`, `US10Y-REAL`), an event class (`fomc-speech`,
`cpi-print`, `equity-drawdown`), a macro state (`risk-off`, `dollar-funding-stress`,
`growth-scare`), or a flow (`etf-flows`, `cb-demand`, `cot-positioning`).

Gold is just one node in the graph. It happens to be the one we trade.

### Edges are typed, signed, lagged, and conditional

```yaml
edge: risk-off -> XAUUSD
  sign: +
  strength: moderate
  lag: same-day
  channel: safe-haven bid — capital rotates into gold when equity risk is repriced

  dominates_when: vix_spike AND NOT dollar_funding_stress
  inverts_when:   dollar_funding_stress

  evidence:
    n: 47 risk-off episodes since 2006
    median gold response: +0.8%
    BUT in the 5 dollar-funding-stress episodes: -4.2%
    computed: 2026-07-13   chart: map/evidence/riskoff-gold.png
```

`inverts_when` is the field that makes this worth building. In March 2020 and
September 2008, gold *sold off* with everything else — because gold is what you
sell when you need dollars. A map that only knows "risk-off → gold up" would have
had you long into the worst two days of the decade.

---

## The traversal

Given an observed event, walk the graph to the traded instrument and return
**ranked chains**, not facts:

```
AAPL -6% pre-market
│
└─► equity-drawdown              [sector concentration; same-day; strong]
      │
      ├─► risk-off               [same-day; strong]
      │     │
      │     ├─► USD bid ──────────────► XAUUSD  (−)  opportunity cost
      │     └─► safe-haven bid ───────► XAUUSD  (+)  rotation into gold
      │
      │     ⚠  CONFLICT: two paths, opposite signs.
      │        Resolver: is this a growth scare or a funding event?
      │        Current state: VIX +18%, no funding stress (SOFR-OIS normal,
      │        cross-currency basis normal) → safe-haven leg dominates.
      │        Net: mildly bullish gold.
      │
      └─► growth-scare           [same-day]
            │
            └─► rate-cut repricing        [1-3 day lag]
                  │
                  └─► real-yields DOWN ──► XAUUSD  (+)  strong
                        Note: this leg is SLOWER than the risk-off leg.
                        It shows up over days, not in the first hour.
```

Three properties fall out that the lookup table couldn't give us:

**1. Multi-hop.** The model sees the chain, with the mechanism named at each hop.
It can reason about *which hop is weak*, which is what an analyst actually argues
about.

**2. Conflict is first-class.** When two paths from one event disagree, the graph
**surfaces the conflict and names the resolving condition.** It does not silently
pick a side. That ambiguity is the edge — it's precisely where everyone else is
confidently wrong, and where a PM earns their seat.

**3. Lags are explicit.** The risk-off leg fires today; the rate-repricing leg
takes days. An event can be bearish gold at 09:30 and bullish gold by Thursday,
and the graph says so. Most systems collapse this into one signal and get chopped
up.

---

## Validated against market data, not against our trades

This is the unlock, and it's worth being explicit about why it matters so much.

"Risk-off → gold up, except under funding stress" is an **episode study**. Find
every risk-off episode since 2006, measure gold's response, split by funding
stress. n=47. That is a real statistic, computed from decades of data, and it
requires **zero trades**.

So the graph gets deep, quantitative, and confidently held *immediately* — while
tactical beliefs are still starved for sample and will be for months.

Two learning channels, two speeds, on purpose:

| | validated against | speed | can be wrong by |
|---|---|---|---|
| **causal graph** | decades of market data | fast | being a stale relationship |
| **tactical beliefs** | our own realized trades | slow | being a false discovery |

The graph tells the agent *which hypotheses are worth having*. The beliefs tell it
*which ones actually pay*. Neither substitutes for the other, and conflating them
is how you get an agent that is either credulous or paralysed.

---

## How the graph grows

RESEARCH owns it. Nobody hand-authors the whole thing.

- **Scheduled**: re-run the evidence statistic on edges it suspects have decayed.
  Add nodes for channels it hadn't mapped. Score sources.
- **Anomaly-triggered**: gold moved 2 ATR on a hot CPI print and *rallied*. Nothing
  in the graph explains it. → research task → discovers the market is pricing cuts
  despite the print and ETF flows turned positive → writes a **new node**
  (`inflation-hedge-bid`), a **new edge** into gold, and links it from the
  `real-yields` node's `inverts_when`.

**The measure of the analyst improving is that the anomaly rate falls.** Fewer
things move gold that the graph didn't see coming. That is a number, and we plot it.

Sources and procedures grow the same way: the agent discovers a feed, records what
it was good for and whether its information was borne out, and writes down the
recipe that reached it so it never re-derives it. Reach compounds.

---

## Storage

Markdown files with `[[wikilinks]]` and YAML edge blocks. **This is a graph** — it
traverses fine at hundreds of nodes, it's inspectable, it's diffable, and its whole
history lives in git.

Not reaching for Neo4j or Graphiti until file traversal is a *measured* bottleneck.
But `lab/graph.py` keeps traversal behind an interface, so swapping the backend
later is a storage change, not a rewrite of the reasoning.

When would we switch? When node count makes in-memory traversal slow (thousands,
not hundreds), or when we need queries the file layout genuinely can't express. Not
before. A graph database is not a substitute for having thought about the edges.

---

## Acceptance

1. Given "AAPL -6%", traversal returns the chains above — including the ambiguity
   and the funding-stress inversion.
2. Every edge carries an evidence statistic computed from market data, with a date.
3. Conflicting paths are surfaced to the model **as a conflict**, with the resolving
   condition. Never silently resolved.
4. Retrieval returns chains within `context_budget_tokens` with 200+ nodes on disk.
5. RESEARCH adds a node and an edge from an anomaly, with no code change.
6. Swapping the storage backend would not require rewriting traversal.

## Refs

Issue: #16
Spec: `docs/specs/phase-4-memory.md`
Design: `docs/MEMORY.md`
