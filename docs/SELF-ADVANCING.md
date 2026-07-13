# The self-advancing system

The agent discovers how to reach data, records what worked, and never re-derives
it. Reach compounds; token cost falls. That's the claim.

This document is the design **and its failure modes**, because a system that
writes its own tooling and then trusts it is one bad webpage away from being a
liability.

---

## The claim, stated precisely

Cycle 1: the agent works out how to get the 10-year real yield. It searches, it
tries three things, two fail, one returns clean CSV. That cost real tokens.

Cycle 400: it needs the same number. It reads one line from an index, executes a
stored spec, gets the number. That cost almost nothing.

**The token savings are real but they are not automatic.** They only materialize
if three things hold, and each is a design constraint:

1. The **index** stays small (retrieval, not a dump).
2. The stored spec is **still correct** (health, not hope).
3. The spec is **safe to execute** (declarative, not shell).

Get any of those wrong and the system is worse than having no memory at all —
because it will be confidently wrong, cheaply, at scale.

---

## 1. Procedures are declarative, never shell

**This is a security requirement, not a style preference.**

The obvious design — "the agent writes down the curl command that worked, and we
run it next time" — is a remote code execution vulnerability. The agent reads web
pages. A web page can contain text crafted to be read as an instruction. If that
text ends up in a stored procedure, and the runner executes stored procedures as
shell, then **any page the agent reads can run code on your machine.**

That is not a hypothetical risk in a system whose entire purpose is autonomously
reading the open web.

So a procedure is **data, not code**:

```yaml
id: fred-real-yield-10y
what: 10-year Treasury inflation-indexed (real) yield, daily
returns: timeseries[date, value]

fetch:
  method: GET
  url: https://fred.stlouisfed.org/graph/fredgraph.csv
  params:
    id: DFII10
  parser: csv
  columns: [observation_date, DFII10]

validate:                       # runs on EVERY fetch. See §2.
  min_rows: 100
  freshness_days: 5             # a stale series is a broken series
  value_range: [-3.0, 8.0]      # a real yield outside this is a parse failure,
                                # not a market event
  no_nulls_in: [DFII10]

health:                         # written by the runner, not the model
  last_ok: 2026-07-13T06:02Z
  consecutive_failures: 0
  used_count: 412
```

The runner executes this with an **HTTP client**, not a shell. There is no
interpolation of model-authored strings into a command line. The blast radius of a
poisoned procedure is "it fetches a URL we didn't want", which is bounded by:

- a **domain allowlist policy** — new domains require the domain to be recorded in
  a source card first, and the card is reviewed the same way any `risk:money`
  change is
- no credentials are ever attached to a fetch (we have none — see `RUNTIME.md`)
- responses are parsed into typed values, never `eval`'d

**If a procedure genuinely needs shell, it doesn't get written by the model.** A
human writes it, reviews it, and commits it. That path stays open and stays manual.

## 2. Every procedure carries a validator, and validators are the whole ballgame

A stored fetch that silently starts returning garbage is **worse than a fetch that
fails**, because the garbage flows into a decision and nobody notices.

The realistic failure modes, all of which return HTTP 200:

| failure | what you get | caught by |
|---|---|---|
| site adds an anti-bot wall | an HTML JS challenge instead of CSV | `parser` fails, `min_rows` |
| endpoint schema drifts | 200, valid CSV, different column names | `columns`, `no_nulls_in` |
| series discontinued | 200, valid shape, last row is 2024 | `freshness_days` |
| units change (% → bps) | 200, valid shape, values 100× off | `value_range` |
| rate limited | 200, empty body | `min_rows` |

Stooq is a live example of the first one. It looks like a working data source and
returns a JavaScript proof-of-work challenge instead of a price series. Without a
validator, that string would be "parsed" into nonsense and fed to the model.

**`value_range` is the one people skip and shouldn't.** A real yield of 230 instead
of 2.30 is a decimal-parse bug that will read to an LLM as an extraordinary macro
event. The model will write you a beautiful thesis about it.

**On failure**: mark the procedure `degraded`, record it, and — critically —
**record the source as MISSING for that cycle rather than substituting a stale
value.** A missing source must never be indistinguishable from a real reading. If
it is, every belief conditioned on that source is quietly poisoned and you will
never find out why.

After N consecutive failures a procedure is marked `dead` and an anomaly trigger
fires: RESEARCH goes and works out a new way in. **That is the system healing
itself, and it only works because the failure was loud.**

## 3. The index is what keeps the token bill down

The procedures directory can grow to hundreds of files. The trader must never see
them.

**Always loaded** — a one-line-per-procedure index, target ≤200 lines:

```
fred-real-yield-10y     10y real yield, daily          ok      412 uses
fred-dxy                broad dollar index, daily      ok      388 uses
yahoo-vix               VIX spot + history             ok      201 uses
yahoo-cross-asset       any ticker OHLC, keyless       ok      156 uses
cot-gold-positioning    CFTC managed-money net         ok       48 uses
stooq-gold              (dead: JS anti-bot wall)       dead      0 uses
```

**Loaded on demand** — the full spec, only when a procedure is actually invoked.

This is the same discipline as the causal graph: the store is large, the
*retrieved slice* is small and context-conditioned. Growth in knowledge must not
mean growth in context, or the "saves tokens" claim inverts and the system gets
more expensive the more it learns.

**Pruning.** A procedure that is `dead` and unused for 90 days is archived (moved,
not deleted — git keeps everything). The index is a working set, not a graveyard.

## 4. Source cards decay; procedures don't

A subtle distinction worth getting right.

**A procedure is right or wrong.** It fetches valid data or it doesn't. Binary,
mechanically checkable, no judgment. Health, not opinion.

**A source is useful or not, and that changes.** A research desk that called the
2026 central-bank bid correctly may be useless on timing. A subreddit that was a
decent contrarian signal in a retail-driven tape is noise in an institutional one.

So sources carry a **decaying usefulness score**, updated by whether their
information was borne out — and, once Phase 5 lands, by whether decisions that
*read* them made money (the decision row records `sources_read`, which is exactly
what makes this scoreable).

The two are stored separately because they answer different questions: *can I get
this?* versus *should I care?*

## 5. What the agent is allowed to write, and what it isn't

| artifact | written by | why |
|---|---|---|
| procedure `fetch` spec | model | it's data, executed by an HTTP client, validated |
| procedure `validate` block | model | but the runner **enforces** it, and a procedure with no validator is rejected at load |
| procedure `health` | **runner only** | the thing being measured does not get to write its own score |
| source card prose | model | it's an opinion, and it's labelled as one |
| source `usefulness` score | **runner only** | same reason |
| graph node / edge prose | model | |
| edge `evidence` statistic | **runner only** | computed from market data. The model proposes the hypothesis; code runs the episode study |
| belief `status`, `n`, ticket lists | **runner only** | see `docs/specs/phase-5-learning.md` |
| any shell command | **human only** | see §1 |

**The pattern**: the model writes *hypotheses and prose*; code writes *scores and
health*. Nothing marks its own homework. This is the same rule as the four clocks,
applied to the memory itself.

---

## What could still go wrong

Stated plainly, because a design doc that only lists strengths is marketing.

**Procedure sprawl.** The agent finds forty ways to get the dollar index. The index
bloats, and retrieval gets noisy. Mitigation: `max_new_sources_per_run`, and a
periodic consolidation pass where RESEARCH is explicitly asked to merge duplicates
and kill the redundant. Unmitigated risk: consolidation is itself an LLM judgment
call.

**Validators that are too loose.** A `value_range` of `[-100, 100]` catches nothing.
Validators written by the model may be written to pass. Mitigation: the runner
rejects a procedure whose validator is trivially permissive (no bounds, no freshness
check). This is a heuristic and it will miss cases.

**The allowlist becomes a rubber stamp.** If every new domain is auto-approved, §1's
security boundary is decorative. Mitigation: new domains land in a review queue. If
that queue is never read, the boundary is gone — and I'd rather say that now than
pretend the config solved it.

**The token-savings claim is unmeasured.** It is a claim, not a result. Instrument it:
log tokens-per-cycle over time. If it isn't falling as the procedure count rises, the
retrieval discipline has failed somewhere and we should find out from a graph, not a
feeling.

---

## Acceptance

1. A procedure written by RESEARCH is executed by the HTTP client on the next cycle
   with **no code change**.
2. A procedure with **no validator** is rejected at load. Non-negotiable.
3. Feeding a procedure a poisoned response (HTML anti-bot wall where CSV was
   expected) marks it `degraded` and records the source as **MISSING** — it does not
   substitute a stale value and does not pass garbage to the model.
4. A `dead` procedure fires an anomaly trigger, and RESEARCH finds a new route in.
5. **No code path exists that executes a model-authored string as shell.** Prove it
   by grep, and keep proving it in CI.
6. Tokens-per-cycle is a plotted metric, and it goes **down** as the procedure count
   goes up.

## Refs

Runtime: `docs/RUNTIME.md`
Memory design: `docs/MEMORY.md`
