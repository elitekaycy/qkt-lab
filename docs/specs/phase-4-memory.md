# Phase 4 — The memory substrate

Status: not started
Blocked by: Phase 2

## Why

An analyst who forgets everything overnight is a chartist. This phase gives the
agent knowledge that persists, and — critically — a *retrieval* step, so that
knowledge can grow without the token bill growing with it.

Nothing here learns from trades yet. That's Phase 5. This phase builds the
substrate and the retrieval, and lets RESEARCH start filling it.

## The four kinds, and why they aren't one thing

The mistake to avoid is applying one validation rule to all knowledge. Different
kinds of knowledge earn trust differently, and forcing a t-statistic onto "here is
the curl that fetches COT data" is how you end up with an agent that can't learn
anything cheaply.

| kind | holds | validated by | grows |
|---|---|---|---|
| **procedures** | commands, API recipes, query patterns that work | did it run and return usable data | freely |
| **sources** | which sites/feeds/reports proved useful, with track records | was its information borne out, and was it timely | freely, with a decaying score |
| **causal map** | what actually drives the commodity, transmission channels, second-order effects, counter-reactions | **market data** — not our trades | richly |
| **beliefs** | "this setup, in this regime, pays R" | **our realized trades**, hard statistical gate | slowly, grudgingly |

**The unlock is the third row.** "Real yields up → gold down" can be tested on
twenty years of daily data — thousands of observations — without placing a single
trade. So the map can be rich, quantitative, and confidently held *immediately*,
while beliefs are still starved for sample. The two learning channels run at
completely different speeds, on purpose.

## What we build

**Procedures (`memory/procedures/`).** One file per recipe. Title, when to use,
the exact command, and the gotchas found the hard way (COT: released Friday
15:30 ET covering the prior Tuesday — a three-day lag; use the disaggregated
report, not the legacy one; holiday weeks shift the release). Validated by
"it ran". No statistics.

This is the memory that makes the agent *cheaper* over time — it stops
re-deriving how to reach data it already reached once.

**Sources (`memory/sources/`).** One card per source with a track record. What
it's good for, what it's bad at, a decaying `usefulness` score, and a dated log of
calls that were or weren't borne out. A desk that is right about *mechanism* and
early by weeks scores differently from one that is right about *timing* — both are
useful, differently, and the card says which.

**Causal graph (`memory/map/`).** Full design in `docs/CAUSAL-GRAPH.md`. This is not
a lookup table of "drivers of gold" — that cannot answer *what does Apple have to do
with gold*, because Apple is not a driver of gold. It is four hops away, and the path
runs through things that are.

**Nodes are entities**, not drivers: an asset (`AAPL`, `DXY`, `US10Y-REAL`), an event
class (`fomc-speech`, `cpi-print`), a macro state (`risk-off`,
`dollar-funding-stress`), a flow (`etf-flows`, `cb-demand`). Gold is just one node.
It happens to be the one we trade.

**Edges are typed, signed, lagged, and conditional:**

```yaml
edge: risk-off -> XAUUSD
  sign: +      strength: moderate      lag: same-day
  channel: safe-haven bid — capital rotates into gold when equity risk reprices
  dominates_when: vix_spike AND NOT dollar_funding_stress
  inverts_when:   dollar_funding_stress
  evidence: n=47 risk-off episodes since 2006; gold +0.8% median,
            BUT -4.2% in the 5 funding-stress episodes.  computed 2026-07-13
```

`inverts_when` is the field that makes this worth building. In March 2020 and
September 2008 gold *sold off* with everything — gold is what you sell when you need
dollars. A map that only knew "risk-off → gold up" would have had you long into the
worst two days of the decade.

**Traversal (`lab/graph.py`)** walks from an observed event to the instrument and
returns ranked *chains*, with the mechanism named at each hop — and when two paths
from one event disagree, it **surfaces the conflict and names the resolving
condition** rather than silently picking a side. That ambiguity is the edge; it is
exactly where everyone else is confidently wrong.

Lags are explicit: the risk-off leg fires today, the rate-repricing leg takes days.
An event can be bearish gold at 09:30 and bullish gold by Thursday, and the graph
says so. Most systems collapse that into one signal and get chopped up.

**Storage:** markdown with `[[wikilinks]]` and YAML edge blocks. That *is* a graph —
it traverses fine at hundreds of nodes, it's diffable, and its history is in git.
Traversal sits behind an interface so swapping to Neo4j/Graphiti later is a storage
change, not a rewrite of the reasoning. We switch when file traversal is a *measured*
bottleneck — thousands of nodes, not hundreds. A graph database is not a substitute
for having thought about the edges.

**Retrieval (`lab/retrieve.py`).** Context-conditioned, not "load everything".
CPI in four hours ⇒ pull `real-rates`, `inflation-surprise`, `dxy`. Don't pull
`mine-supply`. This is what lets the map grow to hundreds of nodes while the packet
stays at ~8k tokens.

The trader's packet gets: playbook, live map nodes, ACTIVE beliefs matching
context, the procedures index, and the source cards for whatever it's reading
right now (so it knows how much to trust it).

**Decision provenance.** The `decision` row gains `map_nodes_used[]`,
`sources_read[]`, `procedures_used[]`, and `unexplained`. This is what makes the
*memory itself* scoreable in Phase 5 — we can ask which map nodes appear in
profitable decisions and which sources were being read before the bad ones.

`unexplained` is the model's own escape hatch: if it sees something the map doesn't
cover, it says so, and that string becomes an anomaly trigger.

## Out of scope

Belief scoring, the distiller, the research loop. Phase 5.

## Acceptance

1. Given "AAPL -6% pre-market", traversal returns the multi-hop chains to XAUUSD —
   including the risk-off/safe-haven **conflict** and the dollar-funding-stress
   **inversion**. Not a list of facts. A chain, with the mechanism named at each hop.
2. Every edge carries an evidence statistic computed from **market data** (an episode
   study), with a date. No trades required to earn it.
3. Conflicting paths are surfaced to the model *as a conflict*, with the resolving
   condition — never silently resolved.
4. Retrieval is demonstrably context-conditioned: with CPI in the window, the packet
   contains `inflation-surprise` and does **not** contain `mine-supply`.
5. The packet stays under `context_budget_tokens` with 200+ nodes on disk.
6. A decision row records which map nodes, sources, and procedures it used.
7. A source card or procedure written by hand is picked up by the next cycle **with
   no code change**.
8. Swapping the storage backend would not require rewriting traversal.

## Refs

Spec: this file
Design: `docs/MEMORY.md`
Depends on: `docs/specs/phase-2-context.md`
