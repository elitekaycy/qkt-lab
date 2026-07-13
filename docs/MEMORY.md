# Memory and research

Companion to PLAN.md / LOOP.md. Supersedes the single-belief-store sketch.

The agent we're building is a commodities analyst and portfolio manager: it is
expected to *know* what moves the instrument, map it, keep the map current,
research anomalies it can't explain, remember which sources and methods paid off,
and get better at all of it over time.

That requires four distinct kinds of memory. They accumulate differently and are
validated differently. Applying one validation rule to all four is what made the
first draft feel like a cage.

---

## The four memory kinds

| kind | what it holds | how it's validated | how freely it grows |
|---|---|---|---|
| **Procedural** | how to get things done: commands, API recipes, query patterns, `qkt` invocations, scrapers that work | did it run and return usable data? | freely — write it down the moment it works |
| **Source** | which sites, feeds, reports, accounts proved useful for this instrument | was the information it gave later borne out? was it timely? | freely, with a decaying usefulness score |
| **Causal map** | what actually drives the commodity, the transmission channels, second-order effects, counter-reactions | tested against **market data**, not against our trades | richly — this is the analyst's worldview |
| **Tactical belief** | "this setup, in this regime, pays R" | tested against **our realized trades**, with a hard statistical gate | slowly and grudgingly — this is the only one that claims edge |

The strict gate (n≥30, family-wide multiple-testing correction) applies **only to
tactical beliefs**, because that is the only class that asserts a tradeable edge
from a small sample. Everything else should grow as fast as the agent can learn.

---

## 1. Procedural memory — `memory/procedures/`

Every time the agent works out how to get something, it writes the recipe down.
These are Claude skill files, structurally: a title, when to use it, the exact
commands, and the gotchas discovered the hard way.

```markdown
---
id: fetch-cot-positioning
what: CFTC Commitments of Traders — managed-money net positioning in gold
---
Released Fridays 15:30 ET, covering the prior Tuesday. Three-day lag matters —
do not treat it as current positioning.

    curl -s "https://.../dea/futures/deacmesf.htm" | ...
    # gold contract code 088691

Gotchas: the legacy report and the disaggregated report disagree; use
disaggregated. Holiday weeks shift the release to Monday.
```

Validation: it ran and returned usable data. That's it. No statistics. A recipe
that breaks gets fixed or marked dead.

This is the memory that makes the agent *faster and cheaper* over time — it stops
re-deriving how to reach data it already reached once. It is also the thing that
makes the whole lab reproducible by a human.

## 2. Source memory — `memory/sources/`

One card per source, with a track record.

```markdown
---
id: goldman-commodities-note
kind: research-note
instrument: XAUUSD
usefulness: 0.7        # decaying score, updated by the research loop
---
What it's good for: positioning and flow colour, central-bank demand estimates.
What it's bad at: short-term direction; its calls have been early by weeks.

Track record:
- 2026-05-14 called CB demand as the dominant 2026 bid → held up; gold rallied
  through the real-yield backup that would normally have capped it. (supported)
- 2026-06-02 called a Q3 pullback to 2450 → not borne out so far. (open)
```

Validation: was the information later borne out, and was it timely? Sources that
keep being right about *mechanism* score up; sources that keep being right about
*narrative but wrong on timing* get scored honestly as such — that's a different
kind of useful.

This is where "which websites proved useful for particular trades" lives, and it's
also where a source *loses* trust. The Reddit/X question from before answers
itself here: it becomes a source card with a track record, not a permanent fixture.

## 3. Causal graph — `memory/map/`

The analyst's worldview, and the thing we are really trying to model. **Full design
in [`CAUSAL-GRAPH.md`](CAUSAL-GRAPH.md)** — read that; this section is the summary.

Nodes are **entities** (assets, event classes, macro states, flows), not "drivers of
gold". Gold is just one node; it happens to be the one we trade. Edges are typed,
signed, lagged, and **conditional** — carrying `dominates_when` and `inverts_when`,
so the graph can represent the case where two paths from one event point in opposite
directions and the skill is knowing which dominates.

Traversal walks from an observed event to the instrument and returns *chains*, with
the mechanism named at each hop. That's what lets it answer "what does Apple falling
have to do with gold" — a question a per-driver lookup table cannot even parse.

The example below is a single node from that graph, to show the shape:

```markdown
---
id: real-yields
instrument: XAUUSD
channel: opportunity-cost
strength: strong        # strong | moderate | weak | contested
direction: inverse
---
Gold pays no yield, so the real (inflation-adjusted) yield on Treasuries is the
opportunity cost of holding it. Real yields up → gold down, historically the
single strongest macro relationship for gold.

Transmission: 10y TIPS yield → holding-cost of gold → ETF flows → spot.
Typical lag: same-day to 2 days on the ETF-flow leg.

Counter-reactions and where it BREAKS:
- Central-bank buying can fully offset it. 2022-2024 and again in 2026: gold rose
  through a real-yield backup because official-sector demand was price-insensitive.
  → when [[central-bank-demand]] is elevated, downgrade this driver's weight.
- In a risk-off spike, [[safe-haven-bid]] dominates for days and the sign flips.

Evidence: daily 10y TIPS vs XAUUSD, 2006-2026, rolling 60d correlation
mean −0.62, but the rolling correlation spent 2023-2026 near zero — see
`map/evidence/real-yields-corr.png`. The relationship is real and currently
suppressed. Do not trade it naked right now.

Related: [[dxy]] [[central-bank-demand]] [[etf-flows]] [[safe-haven-bid]]
[[positioning-cot]]
```

**This is the key unlock: the causal map is validated against market data, not
against our trades.** "Real yields up → gold down" can be tested on twenty years
of daily data — thousands of observations — without placing a single trade. So the
map can be rich, quantitative, and confidently held *immediately*, while tactical
beliefs are still starved for sample.

That also gives tactical beliefs a **prior**. A setup that has a mechanism in the
map ("this works because it's the ETF-flow leg of the real-yield channel") is a
different animal from a setup that's a bare pattern with no story. Both still need
their trades to activate — but the map tells the agent which patterns are worth
*hypothesising* in the first place, which is exactly how a good analyst prunes the
search space instead of data-mining it.

The map is where "counter-reactions and side effects" live, explicitly. Every
driver file has a **where it breaks** section, because knowing that real yields
stopped mattering in 2023 is worth more than knowing they usually matter.

## 4. Tactical beliefs — `memory/beliefs/`

As specified in LOOP.md §8: machine-evaluable predicate, scored by code over all
matching trades, n≥30 plus family-wide correction to activate, decrements not
deletes. This is the only memory with a hard statistical gate, and it keeps it,
because it's the only one that says "do this and you will make money."

New: each belief may cite `mechanism: [[real-yields]]` — a link into the causal
map. Beliefs with no mechanism are flagged. They're allowed, but they're the ones
most likely to be noise, and the distiller is told so.

---

## The research loop — a third clock

The trade loop runs hourly and must be fast. Deep research does not belong on that
hot path — an agent doing twenty web searches while a bar closes is an agent that
misses the bar. So research gets its own clock and its own budget.

**`bin/research` — scheduled (daily/weekly).** An open-ended Claude session with
web search, the full memory, and a standing brief: *keep the map current, keep the
sources scored, find what you don't understand yet.* Typical work: update the
central-bank-demand file after a WGC quarterly, add a driver node for a channel it
hadn't mapped, re-run the evidence chart for a relationship it suspects has
decayed, write a new procedure for a data source it just figured out how to reach.

**`bin/research --anomaly` — event-triggered.** This is the one that makes it feel
like an analyst. The trade loop and the joiner both emit anomaly triggers:

- price moved >3 ATR and **no factor in the current context explains it**
- a trade lost badly and its rationale still looks correct in hindsight
- a driver the map calls "strong" just failed to fire
- a scheduled release printed far off consensus

Each trigger spawns a research task: *find out what happened.* The output is a
durable artifact — a new or amended map node, a source card, a procedure — not a
paragraph of per-trade prose that gets read once and lost. Over time the map's
coverage of "things that moved gold that we didn't see coming" goes up, and that
is the actual measure of the analyst getting better.

**Budget and rabbit holes.** Research gets a token budget per run and a bounded
source list to start from (its own source memory, ranked). It's allowed to go
anywhere, but it has to come back with artifacts. An unbounded websearch agent
with no output contract will produce beautiful narratives and no durable knowledge
— and recency-biased narratives are exactly the failure mode that makes LLMs
confidently wrong about markets.

---

## What the trader sees at decision time

Not everything. The packet stays tight (~6-8k) because a bloated context makes
worse decisions, not better ones:

- the **playbook** for the instrument (the standing process)
- the **map nodes that are live right now** — if CPI is in 4 hours, the
  [[real-rates]] and [[inflation-surprise]] nodes come in; the
  [[mine-supply]] node does not
- **ACTIVE tactical beliefs** matching the current context
- the **procedures index** (so it knows what it can reach without re-deriving)
- current price/news/sentiment

The map is large; the *retrieved slice* is small and context-dependent. That's the
job of the retrieval step, and it's why the map can grow without the token bill
growing with it.

---

## Where the constraints stay

Open the input side all the way. Keep exactly three things closed:

1. **The model never places an order.** It proposes; deterministic code gates and
   executes. An agent with unbounded research reach and a live trigger is not an
   analyst, it's an incident.
2. **The model never sizes the position.** Lots come from risk-per-trade, equity,
   and stop distance. Arithmetic.
3. **A tactical edge claim needs trades to activate.** The map can say gold *should*
   fall; a belief that says *and therefore this setup pays 0.4R* needs the sample
   to prove it. Research generates hypotheses. It does not confer edge.

Everything else — what it reads, where it looks, what it maps, what it remembers,
how it learns — is wide open. That's the point.
