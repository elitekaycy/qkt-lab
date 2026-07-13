# qkt-lab

An autonomous commodities analyst: it researches what moves the instrument, keeps
a causal map of it, proposes trades, journals every decision with its reasoning,
joins the broker's realized outcomes back to that reasoning, and distills the
episodes into memory that makes the next decision better.

Everything is driven from one file: [`lab.yaml`](lab.yaml).

> **Status: design complete, implementation not started.** The specs are written,
> the phases are planned, and the assumptions that hold it up are about to be
> tested in Phase 0. Nothing here has traded yet.

---

## The honest framing, up front

**There is no published evidence that a self-improving LLM trading agent works.**
Every replicated claim has collapsed under data leakage or realistic costs —
FINSABER, the "Alpha Illusion" paper, and the anonymized-ticker benchmark all
found that the wins were memorization, not alpha. In real money, Alpha Arena S1
saw four of six frontier models lose 30-63% in two weeks.

So this repo is a **hypothesis with a test attached**, not a product. Phase 6 is an
A/B — memory versus no memory, identical gates and sizing — designed to tell us the
loop is worthless if it is. If it says that, we'll say so here.

Read [`docs/RESEARCH-VERDICT.md`](docs/RESEARCH-VERDICT.md) before you get excited.

---

## How it works

Four clocks. None nests, and none marks its own homework.

| clock | cadence | reads | writes |
|---|---|---|---|
| **RESEARCH** | daily + anomaly-triggered | web, all memory, market data | the causal map, sources, procedures |
| **TRADE** | per bar close | a retrieved memory slice, the live venue | decision records |
| **JOIN** | every 15 min | broker deal history | outcomes, anomaly triggers |
| **DISTILL** | nightly | decisions ⋈ outcomes | belief *proposals* — code sets status |

The trader cannot edit its own memory. The distiller cannot see an open trade. The
researcher cannot place an order.

Full walkthrough with a worked week: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### Memory is four kinds, not one

Different knowledge earns trust differently. Forcing a t-statistic onto "here is
the curl that fetches COT data" is how you get an agent that can't learn anything
cheaply.

| kind | validated by | grows |
|---|---|---|
| **procedures** — commands and recipes that work | did it run | freely |
| **sources** — which feeds proved useful | was it borne out | freely |
| **causal map** — what drives the commodity, and *where it breaks* | **market data** | richly |
| **beliefs** — "this setup pays R" | **our realized trades**, hard statistical gate | grudgingly |

The unlock is the third row: *"real yields up → gold down"* can be tested on twenty
years of daily data without placing a single trade. So the worldview can be rich and
confident immediately, while tactical beliefs are still starved for sample. The two
channels learn at very different speeds, on purpose.

Details: [`docs/MEMORY.md`](docs/MEMORY.md).

### Deductive chains, not a lookup table

"What does Apple falling have to do with gold?" is not a fact to look up — Apple is
four hops away, and the path runs through things that aren't.

```
AAPL -6% → equity drawdown → risk-off ─┬─► USD bid        → gold DOWN
                                       └─► safe-haven bid → gold UP
                                       ⚠ CONFLICT. Resolver: growth scare or
                                         funding event? VIX +18%, no funding
                                         stress → safe-haven leg dominates.
                    └─► growth scare → rate-cut repricing → real yields DOWN
                                        → gold UP  [1-3 day lag, slower leg]

  ⚠ INVERTS under dollar-liquidity stress (Mar 2020, Sep 2008): gold sells off
    with everything, because gold is what you sell when you need dollars.
```

Edges are typed, signed, lagged, and conditional — with `dominates_when` and
`inverts_when`. When two paths from one event disagree, the graph **surfaces the
conflict and names the resolving condition** rather than silently picking a side.
That ambiguity is the edge; it's where everyone else is confidently wrong.

Details: [`docs/CAUSAL-GRAPH.md`](docs/CAUSAL-GRAPH.md).

### Sizing: the model decides, but conviction has to earn it

A fund doesn't take size out of the PM's hands — it gives them a risk budget, lets
them allocate within it, then measures whether their conviction was any good. Small
book, prove yourself, book grows.

```
lots = (equity × risk%) / (stop × contract_value)   ← vol-targeted, for free
       × f(conviction)                              ← THE MODEL'S CALL
       × correlation_haircut(open book)             ← long gold + short DXY +
                                                      long silver is ONE trade
```

**`f()` is fitted from realized outcomes, never guessed.** We start flat — conviction
recorded, multiplier 1.0 — and promote to `fitted` only when the journal shows
high-conviction trades genuinely outperform (monotone mean-R across buckets,
intervals that separate). Fractional Kelly, never full.

If conviction turns out uncorrelated with outcome, sizing stays flat forever, and
we've learned something no prompt engineering would have surfaced: the model thinks
it knows when it's right, and doesn't.

Details: [`docs/SIZING.md`](docs/SIZING.md).

### Three things the model is never allowed to do

Open the input side all the way — what it reads, where it searches, what it maps,
how much conviction it expresses. Keep exactly three things closed:

1. **It never places an order.** It emits a proposal; deterministic code gates it
   and executes. An agent with unbounded research reach and a live trigger is not
   an analyst, it's an incident.
2. **It never overrides the risk officer.** Daily loss limit, portfolio heat cap,
   `max_lots`, `min_rr`, `require_sl`, kill switch. It never sees them and cannot
   argue with them. Every fund has a risk officer, and the risk officer is not the PM.
3. **Research generates hypotheses; it does not confer edge.** The graph may say gold
   *should* fall. A belief saying *and therefore this setup pays 0.4R* still needs
   its trades and its multiple-testing correction.

### The part nobody else does

Belief activation requires a minimum sample **and** a family-wide Benjamini-Hochberg
correction across every candidate that cycle. A distiller proposing forty lessons
where one clears p<0.05 has discovered nothing — that's a max-of-N statistic, and
it's the false-discovery machine the Deflated Sharpe Ratio literature exists to warn
about.

`n ≥ 30` is a floor for sanity, not a blessing: a true per-trade Sharpe of 0.2 needs
~96 trades to reject zero edge. Narrow beliefs will sit unactivated for months.
**That is correct behaviour, not a knob to tune away.**

---

## Phases

| phase | what | spec |
|---|---|---|
| 0 | Spikes — kill the design cheaply if it's wrong | [spec](docs/specs/phase-0-spikes.md) |
| 1 | One honest trade, end to end | [spec](docs/specs/phase-1-loop.md) |
| 2 | Context — charts, calendar, macro, sentiment | [spec](docs/specs/phase-2-context.md) |
| 3 | The journal UI | [spec](docs/specs/phase-3-journal.md) |
| 4 | The memory substrate | [spec](docs/specs/phase-4-memory.md) |
| 5 | The learning loop | [spec](docs/specs/phase-5-learning.md) |
| 6 | Proof — the A/B that could sink it | [spec](docs/specs/phase-6-proof.md) |

---

## Dependencies, honestly

qkt-lab is MIT and the orchestration is reusable. But two of its dependencies are
not public today:

- **[qkt](https://github.com/elitekaycy/qkt)** — the trading engine and the
  `qkt bot` CLI this drives. Private.
- **mt5-gateway** — the MT5 bridge. Has no LICENSE file at all.

So you can read the design and lift the patterns, but you cannot yet run the loop
without those. Resolving that is tracked as an issue. I'd rather say this plainly
than let the MIT badge imply something untrue.

**Deltalytix** (the journal UI) is **CC BY-NC 4.0** — not an OSI license. It's a
plugin behind `journal.deltalytix.enabled`, and the loop runs fully without it.

---

## License

MIT. See [LICENSE](LICENSE).

## Contributing

Specs before plans, plans before issues, issues before code. See
[`.claude/skills/issue-flow`](.claude/skills/issue-flow/SKILL.md) and
[`.claude/skills/committing`](.claude/skills/committing/SKILL.md).
