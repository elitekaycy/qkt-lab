# Phase 5 — The learning loop

Status: not started
Blocked by: Phase 4, and a corpus of closed trades (≥50 to run the distiller
meaningfully; far more before anything activates)

## Why

This is the phase the whole project exists for: the agent gets better because of
what happened, not because it was told to reflect.

It is also the phase most likely to produce confident nonsense, so most of this
spec is about the machinery that stops it.

## The two learning channels

They run at different speeds, deliberately.

**RESEARCH learns fast.** An anomaly on Wednesday afternoon can update the causal
map by Thursday morning — because map claims are validated against decades of
market data, not against our handful of trades.

**DISTILL learns slowly.** A tactical belief is the only claim that says *do this
and you will make money*, and that claim needs a sample.

## RESEARCH — the analyst's own clock

Open-ended Claude session with web search, the full memory, and a **hard output
contract: come back with durable artifacts, not prose.** An unbounded websearch
agent with no output contract produces beautiful narratives and no knowledge — and
recency-biased narratives are exactly how LLMs get confidently wrong about markets.

**Scheduled (daily).** Keep the map current, keep the sources scored, find what you
don't understand yet. Re-run an evidence statistic it suspects has decayed. Write a
procedure for a source it just worked out how to reach.

**Anomaly-triggered.** The trigger set (all configured in `lab.yaml`):

- price moved >3 ATR and **nothing in the context explains it**
- a map node marked `strength: strong` failed to fire
- a trade lost badly and its rationale still looks correct in hindsight
- a trade won for a reason the thesis never named
- a release printed far off consensus
- the trader set `unexplained` on a decision

Each spawns *find out what happened*, and returns an artifact — a new map node, an
amended `where it breaks`, a source card, a procedure.

**The measure of the analyst improving is that the anomaly rate falls.** Fewer
things move gold that the map didn't see coming. That's a number we plot.

Budgeted per run (`agent.researcher.budget_tokens`). Open-ended, not unbounded.

## DISTILL — and the machinery that keeps it honest

**The LLM proposes. Code disposes.** This split is the single most load-bearing
decision in the project.

The distiller emits belief *drafts*:

```json
{"op": "ADD", "id": "gold-vwap-pullback-london",
 "statement": "XAUUSD pullbacks to VWAP in the first London hour resolve upward",
 "predicate": ["symbol = ICM:XAUUSD", "side = BUY",
               "regime.session = london", "factors contains level:vwap-touch"],
 "mechanism": "[[london-liquidity]]"}
```

**The LLM cannot write `status`, `n`, the stats, or the ticket lists.** It cannot
decide whether its own idea is true.

`lab/beliefs.py` compiles the `predicate` to SQL over `decision ⋈ outcome`, and:

**1. Scores it over every matching trade — not just the trades it caused.**
This is the difference between learning and self-confirmation. It is also why
CANDIDATE beliefs are withheld from the trader (`memory.beliefs.withhold_candidates`):
if the model could see them it would act on them, and they would confirm themselves.
They accrue evidence from incidental matches instead. Slower, and the only honest
way.

**2. Gates activation on sample size AND multiplicity.**
`CANDIDATE → ACTIVE` requires `n ≥ activate_min_trades` **and** survival of a
**family-wide** Benjamini-Hochberg correction applied across *all* candidate
beliefs that cycle.

This second clause is the one nobody in the published literature implements, and
it is why this loop might work where theirs didn't. A distiller proposing forty
lessons where one clears p<0.05 has discovered **nothing** — that's a max-of-N
statistic, and it is precisely the false-discovery machine that Harvey & Liu and
the Deflated Sharpe Ratio literature exist to warn about. qkt-forge already has the
DSR machinery; reuse it.

`n ≥ 30` is a floor for sanity, not a blessing. A true per-trade Sharpe of 0.2
needs **~96 trades** to reject zero edge. Narrow beliefs ("gold, NFP Fridays,
London only") will sit at CANDIDATE for months. **That is correct behaviour, not a
knob to tune away.** Anyone who lowers `activate_min_trades` to make beliefs
activate faster has broken the project and should be told so.

**3. Decrements, never deletes.** `ACTIVE → WEAKENING → INVALIDATED` as losses drag
the stats down. Contradicting outcomes decrement. Invalidated beliefs stay on disk
and in git with their full history — that's how you avoid re-learning the same
wrong thing next year.

**4. Scores on realized net PnL only.** Never on the model's own read of how well
it reasoned. LLM self-explanations are unfaithful and intrinsic self-correction
does not work; the journal's "why" labels are noisy and must never be the target.

**5. Embargo is automatic** by the cadence — beliefs are written at night from
trades that already closed, and read the next day. A trade can never contribute to
a belief that influenced it. **Do not break this by running the distiller
mid-session.**

**6. Beliefs with a `mechanism` link into the map are stronger hypotheses**, not
lower bars. Same activation gate. But a bare pattern with no story is flagged as
likelier noise, and the distiller is told so.

## Scoring the memory itself

Because decisions record `map_nodes_used` / `sources_read` / `beliefs_used`,
DISTILL can ask: which map nodes appear in profitable decisions? which sources were
being read before the losers? That feeds the source usefulness scores and tells
RESEARCH where the map is load-bearing versus decorative.

This is also how the sentiment question gets settled. If, after 60 trades,
`reddit-bullish-precedes-gold-up` has mean R of −0.02 and t=0.3, it lands
INVALIDATED, stops entering context, and we have an *evidence-based* answer to
"is that feed worth its API bill" instead of an opinion.

## Acceptance

1. The distiller runs on ≥50 closed trades and produces beliefs whose predicates
   compile and evaluate.
2. **Hand-check**: the supporting/refuting ticket lists are exactly what the SQL
   predicate selects. Not approximately. Exactly.
3. No belief reaches ACTIVE below `activate_min_trades`, and none reaches ACTIVE
   without surviving the family-wide correction. Prove it with a synthetic case:
   feed 40 pure-noise candidate beliefs and confirm **zero** activate.
4. A belief that goes cold demotes on its own within a week of losses.
5. An anomaly trigger fires and RESEARCH returns a durable artifact.
6. The anomaly rate is a plotted metric.

## Refs

Spec: this file
Design: `docs/MEMORY.md`, `docs/ARCHITECTURE.md`
Depends on: `docs/specs/phase-4-memory.md`
