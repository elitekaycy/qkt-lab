# Phase 6 — Proof

Status: not started
Blocked by: Phase 5, and enough trades to power the test

## Why

Everything before this builds a self-improving trading agent. This phase asks
whether the self-improving part does anything at all.

That question is not rhetorical, and the honest prior is **no**.

## What the evidence actually says

Every published claim of a memory-augmented LLM trading agent that has been
independently replicated has collapsed:

- **FINSABER** re-ran FinMem and FinAgent over 2004-2024 across 63-91 symbols:
  alpha negative or insignificant. Buy-and-hold wins.
- **"Alpha Illusion"**: FinMem returns −72% once the evaluation window crosses the
  model's training cutoff. TradingAgents' Sharpe falls 0.43 → 0.22 with realistic
  costs.
- **Anonymized-ticker benchmark**: 9 of 10 frontier models show negative selection
  alpha once the ticker is masked. The "memory" wins were memorization of
  pretraining data.
- **Alpha Arena S1** (real money, 2025): 4 of 6 frontier models lost 30-63% in two
  weeks.

**No paper anywhere shows a leakage-controlled ablation where the reflection or
memory module adds out-of-sample alpha.** That is the exact claim this project
rests on, and it is currently unsupported by anyone.

So we build the test that could tell us we're wrong. If we won't run it, we
shouldn't have built the loop.

## The experiment

**Two arms, identical everything except memory.**

- `beliefs` arm: playbook + causal map + ACTIVE beliefs
- `control` arm: playbook + causal map, **no beliefs**

Same model, same prompt scaffold, same gates, same sizing, same instrument, same
bars. Arm assignment is **deterministic** on `hash(ts, symbol)` — not random per
run, so it's reproducible and cannot be silently re-rolled.

Note what this isolates: the *tactical belief* layer specifically. The causal map
is in both arms, because the map is validated against market data and its value
doesn't rest on this experiment. What's on trial is the claim that *learning
tactical edges from our own trade outcomes* adds anything.

**Metric**: mean R per trade, with a proper test on the difference. Not win rate,
not equity curve eyeballing, not "it feels smarter".

**Pre-register the threshold before seeing data.** `experiment.min_trades_per_arm`
goes in `lab.yaml` and is set *now*. Changing it after looking at results is
p-hacking, and if we do that we've built an elaborate machine for lying to
ourselves.

## The live gate

`lab.mode: live` **refuses to start** unless:

1. the A/B has run to the pre-registered sample, and
2. it passed, and
3. a human explicitly records `experiment.ab_passed: true` and flips the mode.

The executable recomputes the A/B from the current broker-joined `episode`
rows at every live process start. The config acknowledgement is not accepted as
proof by itself.

Not a warning. A refusal, in code.

## The honest outcome

If the A/B says beliefs add nothing:

- We say so. Publicly, in this repo.
- We keep the journal, the causal map, the procedures, and the sources — all of
  which are independently valuable and none of which depend on the belief loop
  working.
- We drop the belief layer, or we go back and work out *why* it didn't help.

That is a real possible ending and the project is not a failure if it lands there.
It would be the first leakage-controlled result on this question that anyone has
published, and a negative result honestly reported is worth more than a positive
one obtained by moving the threshold.

## Also in this phase

- Pending orders and partial closes (deferred from Phase 1 pending a spike on the
  pending→position ticket identity).
- Multi-instrument (EURUSD), once the loop is proven on one.

## Acceptance

1. Both arms run to the pre-registered sample size.
2. The comparison is computed with a stated test and reported with its confidence
   interval — including if the answer is "no effect".
3. `lab.mode: live` provably refuses to start when the gate is unmet.
4. The result is written up in the repo, whichever way it goes.

## Refs

Spec: this file
Depends on: `docs/specs/phase-5-learning.md`
Research verdict: `docs/RESEARCH-VERDICT.md`
