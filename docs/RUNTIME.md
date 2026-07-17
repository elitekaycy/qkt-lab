# Runtime

Design → architecture → what actually runs on the box. Plus the document map.

**Constraint that shapes everything here: no data or model API keys.** The
credentials are a ChatGPT-managed Codex login and the broker login used by the
MT5 gateway. No FRED key, no Finnhub key, no paid calendar, no X plan. Fully
autonomous, research-driven, and reproducible by anyone who clones the repo.

That is achievable. It also creates exactly one hard problem, and this document is
honest about it (§4).

---

## 1. What actually runs

Four processes. Cron drives them. Nothing is a daemon.

```
crontab
 │
 ├─ 0 6 * * *      bin/research            codex exec, web search, ~30min budget
 ├─ 0 * * * *      bin/trade ICM:XAUUSD    codex exec, ~1min
 ├─ */15 * * * *   bin/join                pure python, no LLM
 └─ 0 22 * * *     bin/distill             codex exec + python stats
                   bin/research --anomaly  event-triggered, spawned by the others
```

Each `bin/*` is a thin python entrypoint. The LLM work is a **subprocess call to
`codex exec`** with developer instructions, a context packet, and (for the
trader) chart images.
There is no server, no queue, no framework. If a process dies, the next cron tick
starts a fresh one and the state is on disk.

**Why no daemon.** State in a long-lived process is state you have to reason about
crashing. Everything here is a pure function of files + venue truth, so a crash is
a no-op and a restart is free. It also makes every step independently runnable by
hand, which is what you want at 3am.

## 2. The processes, and their permissions

The permission table *is* the architecture. Nothing marks its own homework.

| process | LLM? | reads | writes | may place orders |
|---|---|---|---|---|
| `bin/research` | yes, web search on | web, all memory, market data | graph nodes/edges, source cards, procedures | **no** |
| `bin/trade` | yes, no web | retrieved slice, venue (read-only verbs) | `decision` rows | **no — it proposes** |
| `bin/join` | **no** | venue deal history | `outcome` rows, anomaly triggers | no |
| `bin/distill` | yes, no web | `decision ⋈ outcome`, graph | belief *proposals* | no |
| the **runner** (`lab/execute.py`) | **no** | a gated proposal | places the order | **yes — only this** |

The only code that can place an order is deterministic python that never talks to a
model. The model's output reaches it as a validated dataclass, after gating.

In Docker, source and configuration are mounted read-only. The scheduler
over-mounts only `memory/`, `state/`, and `.git` as writable. Proposal roles have
no tools; research has live web and file editing but no shell, apps, subagents, or
broker credentials.

## 3. How data gets in — with no API keys

Two channels, and they do different jobs.

**Channel A — Codex live web search (RESEARCH only).**
Web search is built into the Codex runtime. This is how the agent *discovers* —
reads a WGC quarterly, finds a Fed speech transcript, works out what moved gold
yesterday.

Open-ended, and slow, and expensive. It runs on the research clock, not the trade
clock. An agent doing twenty web searches while a bar closes is an agent that
misses the bar.

**Channel B — stored procedures (everything else).**
Keyless public endpoints, executed by an HTTP client from a declarative spec. No
LLM in the loop at fetch time. Verified working today:

```
FRED, keyless:   https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10,DTWEXBGS
                 → real yields, dollar index, curve. Multi-series. No key.
Yahoo, keyless:  https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d
                 → any ticker: AAPL, ^VIX, DX-Y.NYB. Cross-asset OHLC.
                 This is what the causal graph's episode studies run on.
Dead:            Stooq — JS proof-of-work anti-bot wall. A live example of why
                 every procedure needs a validator (docs/SELF-ADVANCING.md §2).
```

RESEARCH discovers these and writes the procedure. The trade loop executes them.
**This is the split that makes the whole thing cheap**: expensive open-ended
discovery happens once, on its own clock; the hot path executes a spec.

Price data itself never comes from the web — it comes from `qkt bot`, which is
ground truth and already authenticated to your gateway.

## 4. The one hard problem: a gate that depends on the open web

The news blackout gate must be **deterministic at trade time**. But its data comes
from an LLM reading the internet. Those two facts are in tension, and pretending
otherwise would be how someone gets hurt.

**The resolution: the gate never calls an LLM. It reads a file.**

```
bin/research  ──(daily, codex exec, web)──►  memory/calendar/upcoming.yaml
                                                     │
                                                     ▼
bin/trade ──► gates.py ──► reads upcoming.yaml ──► blackout? ──► refuse
```

`upcoming.yaml` is a cache with provenance:

```yaml
fetched_at: 2026-07-13T06:04Z
events:
  - event: US CPI (YoY)
    at: 2026-07-14T12:30:00Z
    impact: high
    affects: [XAUUSD, DXY, US10Y-REAL]
    confidence: confirmed          # confirmed | single-source | uncertain
    sources:
      - https://www.bls.gov/schedule/news_release/cpi.htm
      - https://fred.stlouisfed.org/releases/...
```

Three rules make an LLM-populated safety gate acceptable:

**1. Two independent sources, or it's not `confirmed`.** One source agreeing with
itself is not corroboration.

**2. Fail-closed, always.** If the cache is stale (older than
`calendar.max_age_hours`), or the event is `uncertain`, or the file is missing —
**the loop refuses to trade.** It does not proceed on a guess.

The asymmetry is the whole point: the worst case of a false positive is *we miss a
trade*. The worst case of a false negative is *we're long gold into a CPI print we
didn't know about*. Those costs are not remotely comparable, so the gate is
deliberately trigger-happy.

**3. The gate is arithmetic on the file.** `now` within `±blackout_minutes` of an
`at` where `impact: high` and the symbol is in `affects`. No judgment, no model, no
"is this really high impact". Code.

This pattern generalizes: **any safety-critical input that comes from an LLM must
be cached to a file with provenance, validated on read, and fail-closed.** The
model can populate a gate. It can never *be* one.

## 5. The disk

```
qkt-lab/
  lab.yaml               ← the one file you edit
  .env                   ← DB DSNs only. No API keys. Ever.

  bin/                   trade  join  distill  research
  lab/                   config qkt context retrieve charts agent gates
                         sizing execute store join beliefs graph distill
  db/schema.sql          decision + outcome
  exporters/             deltalytix.py (optional; loop runs without it)

  prompts/               trader.md  distiller.md  researcher.md
  playbooks/             xauusd.md            ← human-authored standing process

  memory/                ← THE AGENT WRITES HERE. All of it is git-tracked.
    map/                 causal graph: nodes + typed edges + evidence
    beliefs/             tactical edges, code-scored, hard statistical gate
    sources/             the living registry, with decaying usefulness
    procedures/          declarative fetch specs + validators + health
    calendar/            upcoming.yaml — the gate's cache (§4)
    index.md             ← the ~200-line always-loaded table of contents

  state/                 charts/ run logs. Gitignored, reproducible.
  KILL                   ← touch this file and no order is ever placed.
```

**`memory/` is in git.** Every belief the agent forms, every edge it draws, every
source it trusts, and every time it changed its mind is a diff with a timestamp.
`git log memory/map/real-yields.md` is the agent's intellectual history, and you can
read it. That is not a nice-to-have — when a trade goes wrong, "what did it believe,
and when did it start believing it" is the first question.

## 6. One cycle, concretely

```
06:00  bin/research
       codex exec -c web_search="live"
       → notices gold held firm through a real-yield backup
       → executes procedure fred-real-yield-10y (no LLM, no key)
       → recomputes the rolling correlation over 20y
       → edits memory/map/real-yields.md: strength strong → contested
       → refreshes memory/calendar/upcoming.yaml (2 sources, confirmed)
       → git commit

08:00  bin/trade ICM:XAUUSD
       qkt bot bars/quote/account/positions/eval          (ground truth)
       execute procedures: fred, yahoo-vix                (keyless, validated)
       retrieve: playbook + LIVE graph nodes + ACTIVE beliefs + procedure index
       render charts → 1h.png, 15m.png
       codex exec (no tools/web) + packet + images → PROPOSAL json
       gates.py  → pass                                   (arithmetic, no LLM)
       sizing.py → 0.13 lots                              (arithmetic, no LLM)
       qkt bot buy ... --json → ticket 88412
       INSERT decision

14:10  bin/join
       ticket 88412 gone from `bot positions` → closed
       qkt bot history → aggregate ALL deals for positionTicket 88412
       net_pnl 147.85, r_multiple +3.04
       INSERT outcome
       no anomaly → no trigger

22:00  bin/distill
       codex exec (no tools/web) → belief proposals
       beliefs.py → compile predicate to SQL, score over ALL matching trades,
                    apply family-wide BH correction, set status
       git commit memory/beliefs/
```

## 7. Usage

Model usage is charged against the authenticated Codex plan. Everything else is
keyless public data and your existing broker.

| clock | calls/day | shape |
|---|---|---|
| research | 1 scheduled + anomalies | expensive: web search, long context |
| trade | ~8-12 (session hours) | ~8k packet + 2 images, small output |
| join | 96 | **zero LLM** |
| distill | 1 | medium context, small output |

The trade loop — the one that runs most — is the *cheapest*, because procedures and
retrieval do the work that research already paid for. **That inversion is the design
working.** If tokens-per-cycle isn't falling as the procedure and graph counts rise,
something in the retrieval discipline has broken, and we should learn that from a
plotted metric rather than a surprise bill.

Automated sessions disable subagents to keep usage and behavior predictable.

---

## 8. Document map

Read in this order.

| doc | answers |
|---|---|
| [`README.md`](../README.md) | what is this, and why should I doubt it |
| [`RESEARCH-VERDICT.md`](RESEARCH-VERDICT.md) | what the evidence says (mostly: this doesn't work) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | the four clocks, and a worked week |
| **`RUNTIME.md`** (this) | what runs on the box, with no API keys |
| [`MEMORY.md`](MEMORY.md) | four kinds of memory, three validation regimes |
| [`CAUSAL-GRAPH.md`](CAUSAL-GRAPH.md) | typed edges, conflicting paths, multi-hop |
| [`SELF-ADVANCING.md`](SELF-ADVANCING.md) | procedures, sources, and how they rot |
| [`SIZING.md`](SIZING.md) | conviction has to earn its book |
| [`specs/`](specs/) | phase 0-6, each with observable acceptance |

**The three ideas the whole thing rests on**, if you read nothing else:

1. **Nothing marks its own homework.** The model writes hypotheses and prose; code
   writes scores and health. Four clocks, four permission sets.
2. **Two learning speeds.** The causal graph is validated against *decades of market
   data* and can be confident immediately. Tactical beliefs are validated against
   *our own handful of trades* and must be slow, gated, and multiplicity-corrected.
   Conflating them gives you an agent that is either credulous or paralysed.
3. **The model may populate a gate. It may never be one.** Everything
   safety-critical is a file with provenance, validated on read, failing closed.
