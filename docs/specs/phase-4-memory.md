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

**Causal map (`memory/map/`).** One file per driver, cross-linked with `[[wikilinks]]`.
Each node carries:

- `channel` — the transmission mechanism, in plain language
- `strength` — `strong | moderate | weak | contested`
- `direction`, typical lag
- **`where it breaks`** — the counter-reactions. This section is the point. Knowing
  that real yields *stopped mattering* in 2023 because central-bank buying went
  price-insensitive is worth more than knowing they usually matter.
- `evidence` — a computed statistic over market data, with a chart, and a date

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

1. A map node exists for XAUUSD's principal drivers, each with a `where it breaks`
   section and an evidence statistic computed from real market data.
2. Retrieval is demonstrably context-conditioned: with CPI in the window, the
   packet contains `inflation-surprise` and does **not** contain `mine-supply`.
3. The packet stays under `context_budget_tokens` with 50+ map nodes on disk.
4. A decision row records which map nodes, sources, and procedures it used.
5. A procedure written by hand is picked up and used by the next cycle without a
   code change.

## Refs

Spec: this file
Design: `docs/MEMORY.md`
Depends on: `docs/specs/phase-2-context.md`
