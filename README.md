# qkt-lab

An autonomous commodities analyst: it researches what moves the instrument, keeps
a causal map of it, proposes trades, journals every decision with its reasoning,
joins the broker's realized outcomes back to that reasoning, and distills the
episodes into memory that makes the next decision better.

Everything is driven from one file: [`lab.yaml`](lab.yaml).

> **Status: running, in demo.** The scheduler is recording real decisions against
> an authenticated demo account, but there are no accepted or broker-joined
> trades yet, so the preregistered Phase 6 sample has not started. Nothing here
> has traded real money — `mode: live` refuses to start until that A/B has run
> and passed.

## Getting started

### What you need

- **Docker with Compose v2** on a linux/amd64 host (the MT5 gateway runs the
  Windows MT5 terminal under Wine). ~5 GB disk for images. Nothing installs on
  the host itself.
- **Codex access through ChatGPT** — run `codex login` once on the host. The
  scheduler runs `codex exec` headlessly and mounts only
  `~/.codex/auth.json`; no model API key is stored in `.env`.
- **An MT5 demo account** — free, takes two minutes at any MT5 broker (Exness
  demo used here). You need three strings: login, password, server name. The
  `EXNESS` broker label in the configs is just a name; `MT5_SERVER` decides the
  actual venue.

### First run

```bash
git clone https://github.com/elitekaycy/qkt-lab && cd qkt-lab
cp .env.example .env
```

Fill in `.env` (nothing else is edited on a first run):

| var | what to put there |
|---|---|
| `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` | your demo account — the gateway logs in headless on boot |
| `MT5_API_KEY` | any string you invent; it locks the gateway's REST port |

If port 8080 is already in use, set `LAB_CHARTS_PORT` in `.env`; the chart
server and journal URLs use it automatically.

Confirm `codex login status` says you are logged in before starting Compose.

```bash
docker compose up -d          # gateway, postgres, scheduler, charts, decision journal
touch KILL                    # emergency stop, any time; rm KILL to resume
```

That's the whole install. The scheduler generates its crontab from `lab.yaml`
(`bin/gen-crontab`) — trade hourly on the 1h close, join outcomes every 15 min,
distill nightly, research daily. Editing a schedule in `lab.yaml` and
`docker compose restart scheduler` is the whole deployment story.

### Confirm it works

| check | command | expect |
|---|---|---|
| services up | `docker compose ps` | `lab-mt5-gateway` and `lab-postgres` show `(healthy)` |
| Codex auth | `docker exec lab-scheduler codex login status` | logged in through the mounted host credential |
| broker login | `docker compose logs mt5-gateway \| tail` | a successful login line, no auth errors |
| a cycle, right now | `docker exec lab-scheduler python3 bin/trade EXNESS:XAUUSD` | ends in `TRADE`, `NO_TRADE`, or `GATED` — all three are success; the decision is the product |
| it was journaled | `docker exec lab-postgres psql -U lab -d lab -c "SELECT ts, action, arm, conviction, thesis FROM decision ORDER BY ts DESC LIMIT 5;"` | your cycle as a row, thesis included |
| kill switch | `touch KILL`, run a cycle | `GATED` with `kill_switch` in `gate_rejects` |

`NO_TRADE` on your first cycle is the common case and the honest one — most
hours have no edge, and the system journals that with the same rigor as a trade.

Open `http://localhost:8421` for the complete React journal. It includes an
authenticated account card, realized-performance widgets, equity curve,
calendar, setup/hour analytics, all TRADE/NO_TRADE/GATED cycles, exact UTC
timestamps, model reasoning, provenance, outcomes, and archived model-input
charts. A decision detail renders the stored broker bars and EMA/RSI/ATR with
TradingView Lightweight Charts and can save that complete view as PNG.

### Watching it think

Every decision is written down before anything else happens, so the audit trail
*is* the primary interface:

- **What it decided and why** — the `decision` table holds the thesis, the full
  `rationale_md`, conviction, which map nodes and beliefs it used, and what
  gates rejected. `docker exec -it lab-postgres psql -U lab -d lab` and look
  around.
- **What actually happened** — the `episode` view joins each trade to the
  broker's realized outcome: `SELECT ts, side, net_pnl, r_multiple, thesis FROM
  episode;`. Broker truth, not our optimism.
- **What it looked at** — the exact charts handed to the model are served at
  `http://localhost:8080/charts/`.
- **Every cycle's stdout** — `docker compose logs -f scheduler`.
- **What it learned** — `memory/` is git-tracked and bind-mounted; the agent's
  research lands as real commits. `git log --oneline -- memory/` is the history
  of it changing its mind.

### One journal, one database

The journal reads the same Postgres tables used by the gates, joiner, beliefs,
and outcome calculations. There is no export job, second database, cache, auth
bypass, or eventual-consistency boundary. Each decision stores a versioned
context snapshot in Postgres: account/quote truth, broker bars, indicators,
calendar, exact model packet, and TradingView-ready studies. Immutable PNGs
remain alongside it as the visual artifact shown to the model.

For frontend work:

```bash
make ui
docker compose restart journal-ui
```

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
For the exact running path, calculations, and management boundary, read
[`docs/DECISION-LIFECYCLE.md`](docs/DECISION-LIFECYCLE.md). The current
real-money verdict and required fixes are tracked in
[`docs/PRODUCTION-READINESS.md`](docs/PRODUCTION-READINESS.md).

### It writes its own tooling — carefully

The agent discovers how to reach data, records the working recipe, and never
re-derives it. Reach compounds; the trade loop gets *cheaper* as the agent learns.

The trap: **storing an LLM-written shell command and executing it later is remote
code execution.** This agent reads the open web for a living, and a web page can
carry text crafted to be read as an instruction. So procedures are **declarative
fetch specs** — url, params, parser, and a **mandatory validator** — run by an HTTP
client, never `bash -c` on a model-authored string.

Every procedure is validated on every fetch (shape, freshness, plausible range),
because a stored fetch that silently starts returning garbage is worse than one that
fails. When one dies, that fires an anomaly and RESEARCH goes and finds a new route
in. That's the system healing itself, and it only works because the failure is loud.

Details, including what could still go wrong: [`docs/SELF-ADVANCING.md`](docs/SELF-ADVANCING.md).

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

## No data or model API keys

The credentials are your **ChatGPT-managed Codex login** and the broker login
used by the MT5 gateway. No OpenAI API key, FRED key, Finnhub key, paid calendar,
or X plan is required for the default local deployment.

All market and macro data comes from keyless public endpoints, executed from
declarative fetch specs **the agent writes itself**:

```
FRED    fredgraph.csv?id=DFII10,DTWEXBGS     real yields, dollar, curve    keyless
Yahoo   /v8/finance/chart/AAPL               any ticker, cross-asset OHLC  keyless
```

If you find yourself adding a key, the loop has stopped being reproducible by
someone who just cloned the repo. That's the constraint, and it's deliberate.

See [`docs/RUNTIME.md`](docs/RUNTIME.md) for how that works — and §4 for the one
place it gets genuinely hard: **a safety gate whose data comes from an LLM reading
the web.** The resolution is that the gate never calls a model. It reads a cache file
with provenance, requires two independent sources, and **fails closed**. The model
may populate a gate; it may never *be* one.

## Dependencies

qkt-lab is MIT. Its two core dependencies:

- **[qkt](https://github.com/elitekaycy/qkt)** — the trading engine and the
  `qkt bot` CLI this drives. Apache-2.0.
- **[mt5-gateway](https://github.com/elitekaycy/mt5-gateway)** — the MT5 bridge. MIT.

The first-party journal is React, Tailwind CSS, Recharts, and the official
TradingView Lightweight Charts package; it ships under this repository's MIT
license.

---

## License

MIT. See [LICENSE](LICENSE).

## Contributing

Specs before plans, plans before issues, issues before code. See
[`.claude/skills/issue-flow`](.claude/skills/issue-flow/SKILL.md) and
[`.claude/skills/committing`](.claude/skills/committing/SKILL.md).
