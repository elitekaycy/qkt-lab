# The plan

Everything, in one place, in order. Design → architecture → runtime → phases.

**Nothing gets implemented until this plan is complete and agreed.** That is
deliberate: this is a system that will place real orders based on knowledge it wrote
itself, and the expensive mistakes here are design mistakes, not coding ones.

---

## Part 1 — The design (what we're building)

An autonomous commodities analyst. It researches what moves the instrument, keeps a
causal map of it, proposes trades with a stated conviction, journals every decision
with its reasoning, joins the broker's realized outcomes back to that reasoning, and
distills the episodes into memory that makes the next decision better.

**The honest prior is that this doesn't work.** Every replicated claim of a
memory-augmented LLM trading agent has collapsed under leakage or realistic costs.
No paper anywhere shows a leakage-controlled ablation where the memory module adds
out-of-sample alpha. So this is a hypothesis with a test attached (Phase 6), not a
product. → [`RESEARCH-VERDICT.md`](RESEARCH-VERDICT.md)

### The three ideas everything else follows from

**1. Nothing marks its own homework.**
The model writes hypotheses and prose. Code writes scores and health. The trader
can't edit its memory; the distiller can't see an open trade; the researcher can't
place an order; and the thing being measured never writes its own score.

**2. Two learning speeds.**
The **causal graph** is validated against *decades of market data* — so it can be
rich and confident immediately, and an anomaly on Wednesday can update the worldview
by Thursday. **Tactical beliefs** are validated against *our own handful of trades* —
so they must be slow, sample-gated, and multiplicity-corrected. Conflating the two
gives you an agent that is either credulous or paralysed.

**3. The model may populate a gate. It may never be one.**
Anything safety-critical is a file with provenance, validated on read, failing
closed.

### What the model owns, and what it doesn't

| the model decides | code decides |
|---|---|
| what to research, where to look | whether an order is placed |
| what the causal graph says | the risk officer's limits |
| whether to trade, direction, entry, stop, target | **position size** (from its conviction) |
| **how convinced it is** | whether conviction has earned the right to scale size |
| which beliefs to propose | whether a belief is true |

Open the input side all the way. Keep three things closed: it never places an order,
it never overrides the risk officer, and research generates hypotheses but doesn't
confer edge.

---

## Part 2 — The architecture (how the parts fit)

**Four clocks**, each a separate process with its own prompt and its own write
permissions. → [`ARCHITECTURE.md`](ARCHITECTURE.md)

```
   RESEARCH ─────────────────► map/ sources/ procedures/ calendar/ ──┐
      ▲                                                              │
      │ anomaly triggers                                             │ retrieved slice
      │                                                              ▼
   JOIN ◄──── venue ◄──── TRADE ◄──────────────────── beliefs/ (ACTIVE only)
      │                     │                                        ▲
      │                     ▼                                        │
      └──► outcome ──► decision ──► DISTILL ────────────────────────┘
                                    (LLM proposes, code scores)
```

**Four kinds of memory**, three validation regimes. → [`MEMORY.md`](MEMORY.md)

| kind | validated by | speed |
|---|---|---|
| procedures — recipes that work | did it run | instant |
| sources — what proved useful | was it borne out | fast |
| causal graph — what drives the market | **market data** | fast |
| beliefs — "this setup pays R" | **our trades**, hard gate | slow |

**The causal graph** is typed-edge, not a lookup table: nodes are entities, edges
carry `sign`/`strength`/`lag`/`dominates_when`/`inverts_when`. Traversal returns
*chains*, and surfaces conflicts rather than silently resolving them.
→ [`CAUSAL-GRAPH.md`](CAUSAL-GRAPH.md)

**Sizing** is composed, and the model owns the conviction term — but `f(conviction)`
is *fitted from realized outcomes*, never guessed. → [`SIZING.md`](SIZING.md)

**Self-advancement**: procedures are declarative fetch specs with mandatory
validators, never shell. → [`SELF-ADVANCING.md`](SELF-ADVANCING.md)

---

## Part 3 — The runtime (what runs on the box)

Cron, four thin python entrypoints, `claude -p` as the only LLM call. No server, no
daemon, no framework, **no API keys**. → [`RUNTIME.md`](RUNTIME.md)

```
0 6 * * *     bin/research     claude -p + web search
0 * * * *     bin/trade        claude -p + packet + chart images
*/15 * * * *  bin/join         pure python, ZERO LLM
0 22 * * *    bin/distill      claude -p + python stats
```

The only process that can place an order is deterministic python that never talks to
a model.

All data is keyless: FRED's graph CSV endpoint, Yahoo's chart endpoint, and whatever
else RESEARCH discovers and writes a spec for. Price is `qkt bot` — ground truth.

`memory/` is git-tracked, so `git log memory/map/real-yields.md` is the agent's
intellectual history. When a trade goes wrong, *"what did it believe, and when did it
start believing it"* is the first question, and it has an answer.

---

## Part 4 — The phases

Each phase ships a working system. No phase is a refactor of the last.

| # | phase | ships | issue |
|---|---|---|---|
| **0** | [Spikes](specs/phase-0-spikes.md) | the design survives contact, or it doesn't | [#1](../../issues/1) |
| **1** | [The loop](specs/phase-1-loop.md) | one honest trade, end to end | [#2](../../issues/2) |
| **2** | [Context](specs/phase-2-context.md) | charts, calendar, macro, sentiment | [#3](../../issues/3) |
| **3** | [Journal UI](specs/phase-3-journal.md) | Deltalytix — read, search, calendar, equity | [#4](../../issues/4) |
| **4** | [Memory](specs/phase-4-memory.md) | the causal graph + retrieval | [#5](../../issues/5) |
| **5** | [Learning](specs/phase-5-learning.md) | distiller, belief scoring, research clock | [#6](../../issues/6) |
| **6** | [Proof](specs/phase-6-proof.md) | the A/B that could sink it | [#7](../../issues/7) |

### Phase 0 gates everything

Six spikes. Each is an hour. Three can kill the design:

- **S0.1 / S0.2** — the outcome join. If a broker ticket doesn't join back to its
  realized deals, there is no journal, no R-multiple, no learning. Everything stops.
- **S0.4** — `claude -p` headless with images and strict JSON, **on the Max pool**.
  No agent runtime, no loop.
- **S0.6** — keyless cross-asset history. If the causal graph can't evidence its
  edges from market data, the two-speed design collapses and beliefs are all we have.

And one that's a money question rather than a design one:

- **S0.5** — the calendar. A safety gate fed by an LLM reading the web. If we can't
  corroborate event times to the minute, the honest options are buy a feed (breaking
  the no-keys constraint) or blanket-blackout the session (cruder, safer). We do not
  trade through CPI on an uncorroborated LLM reading of a webpage.

### The order is not arbitrary

**1 before 2** — build the spine with real money-shaped constraints before making the
inputs clever. A wrong skeleton can't be fixed by better eyes.

**2 before 3** — the journal UI is worth nothing until there are charts and reasoning
worth looking at.

**4 before 5** — the memory substrate and its retrieval must exist before anything
tries to learn into it.

**5 before 6** — obviously. But note that 6 is the only phase that can tell us 5 was
worth building, and we commit to publishing that answer either way.

### Where the trade corpus comes from

Phase 5 needs ≥50 closed trades to distill, and beliefs need `n ≥ 30` *each* to
activate. At ~8-12 decisions/day on one instrument with most returning `NO_TRADE`,
that is **months**, not weeks.

This is not a scheduling problem to optimize away. It is the honest cost of the
statistical gate, and anyone who "fixes" it by lowering `activate_min_trades` has
broken the project. Phases 0-4 are the buildable work; Phase 5 accumulates in the
background while it runs.

---

## Part 5 — What would tell us we're wrong

- **The join doesn't work** (S0.1/S0.2) → no learning loop is possible at all.
- **Tokens-per-cycle rises** as procedures and graph nodes accumulate → the retrieval
  discipline has failed and the "cheaper over time" claim inverts.
- **Conviction is uncorrelated with realized R** → the model doesn't know when it's
  right, and sizing stays flat forever. Valuable to know; changes the product.
- **The A/B says beliefs add nothing** (Phase 6) → we say so publicly, keep the
  journal and the causal graph (independently valuable), and drop the belief layer.
- **The anomaly rate doesn't fall** → the graph isn't learning, it's just accumulating.

Each of these is instrumented, not left to intuition. → the acceptance criteria in
each spec.

---

## Part 6 — Open questions

1. **Correlation estimate for the portfolio heat cap.** Rolling realized correlation
   is noisy short and stale long — and correlation regime-shifts exactly when it
   matters most (everything goes to 1.0 in a crisis). Not yet specced. Parkable until
   there's a multi-position book to protect.
2. **The new-domain review queue.** If it's never read, the security boundary in
   `SELF-ADVANCING.md` §1 is decorative. Who reads it, and how often?
3. **Licensing qkt and mt5-gateway** ([#8](../../issues/8)). Both public, both
   unlicensed — legally "all rights reserved". One file each.
