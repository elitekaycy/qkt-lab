# Phase 0 — Spikes

Status: not started
Kind: time-boxed investigation. Output is a decision, not code.

## Why

Four assumptions hold up the entire design. Each is cheap to test and expensive
to be wrong about. If any fails we would rather find out in an hour than in
Phase 4.

Nothing else starts until these land.

## S0.1 — The outcome join (`risk:invalidates-design`)

**Assumption.** `qkt bot buy --json` returns `ticket`; the realized deals for
that position come back from `qkt bot history --json` with
`positionTicket == ticket`. This is the join that makes the whole journal
possible, and it means we need zero changes to qkt.

**Test.** On the lab demo account: place a 0.01 XAUUSD market buy with an SL and
TP. Record `ticket`. Close it. Run `qkt bot history --since 1d --json`.

**Passes if:**
- rows exist with `positionTicket == ticket`
- there is exactly one `entry:"IN"` row and at least one `entry:"OUT"` row
- `Σ profit + Σ commission + Σ swap` across **all** rows for that ticket
  reconciles to the MT5 terminal's reported net PnL, to the cent
- commission's location is pinned (we expect it on the IN deal — confirm)

**Kill condition.** If the ticket does not join, the decision-record design is
wrong and we stop and rethink the whole store before writing any of it.

## S0.2 — Server-side closes (`risk:invalidates-design`)

**Assumption.** The joiner works when *we* are not the one closing — i.e. when
the broker closes the position on an SL or TP hit.

**Test.** Open a position with a tight SL. Let the server hit it. Do not call
`qkt bot close`.

**Passes if** the OUT deal appears in `bot history` with the same
`positionTicket`, and the joiner produces the same reconciliation as S0.1.

**Kill condition.** If server-side closes don't surface, the loop can only learn
from trades it closes itself — which is most of them, but it would mean the
`r_multiple` for every stopped-out trade is unrecoverable. That is fatal to the
learning loop and we would need a different outcome source.

## S0.3 — Deltalytix as the journal UI (historical, superseded)

**Assumption.** We can self-host Deltalytix and write trades into its Postgres
directly, and they render — with rationale, tags, charts, calendar, and an
equity curve.

**Test.** `docker compose up`. Create the `User`, `Account`, and — critically —
the **`Subscription`** row (`status='ACTIVE'`, email matching the user), without
which the UI silently hides every trade older than 14 days. Insert one trade with
a deterministic **UUIDv5** id (namespace `6ba7b810-9dad-11d1-80b4-00c04fd430c8`,
over the pipe-joined 14-field signature the app uses) plus a `comment`, `tags[]`,
and an `images[]` URL. Run the insert twice.

**Passes if:**
- the trade renders in the UI with its rationale, tags, and chart image
- it appears on the PnL calendar and in the equity curve
- the second insert is a no-op (`ON CONFLICT (id) DO NOTHING`)
- search/filter by tag works

**Notes that will bite:** reads go through a 1-hour cache — restart the app to
force it. Run a **production** build; the dev build has a TTL-less IndexedDB trade
cache that may never show new rows.

**Kill condition.** If the UUIDv5 recipe can't be replicated, every export re-run
duplicates every trade (`id` is the only unique key). If that can't be solved,
Deltalytix is export-once-only and we reconsider the UI.

## S0.4 — The agent runtime

**Assumption.** `claude -p` can be driven headlessly, accepts chart images, and
reliably emits strict JSON.

**Test.** Feed it a rendered 1h chart PNG plus a context packet. Force the
proposal schema. Run it 10 times.

**Passes if:**
- 10/10 runs return schema-valid JSON
- the images demonstrably influence the output (swap the chart for an inverted
  one; the proposal should change)
- **it still runs on the Max subscription pool.** The subagent spend cap was hit
  on 2026-06-15; confirm `claude -p` is unaffected, or price the API path.

**Kill condition.** No headless agent, no loop. If the Max pool won't serve it,
this becomes a cost decision before anything else is built.

## S0.5 — The calendar cache, and a safety gate fed by an LLM (`risk:money`)

**Constraint.** No API keys. The only credential in the system is the Claude
subscription. So the economic calendar comes from RESEARCH reading the open web —
and the news blackout gate depends on it.

**The tension.** A gate must be deterministic at trade time. Its data comes from an
LLM reading web pages. Those two facts are in conflict, and hand-waving it is how
someone gets hurt.

**The design under test** (`docs/RUNTIME.md` §4): the gate **never calls an LLM**.
RESEARCH writes `memory/calendar/upcoming.yaml` with provenance; `gates.py` reads
the file and does arithmetic on it.

**Test.**
- Have `claude -p` (web search on) produce `upcoming.yaml` for the next 7 days:
  event, UTC time, impact, affects[], confidence, and **≥2 independent source URLs**.
- Verify every event and time against the primary issuer (BLS, BEA, the Fed).
- Verify the gate refuses when the cache is stale, missing, or `uncertain`.

**Passes if:**
- ≥2 independent keyless sources can corroborate each high-impact event's **time**
- times are correct against the primary issuer, **to the minute** — a CPI print at
  12:30Z that we recorded as 13:30Z is worse than having no calendar at all
- the gate **fail-closes** on a stale/missing/uncertain cache, verifiably
- the whole thing works with no API key

**Kill condition.** If we cannot get corroborated event times reliably enough to
trust a gate, then the honest options are: (a) buy a calendar feed and break the
no-keys constraint, or (b) do not trade around high-impact events *at all* — a
blanket time-of-day blackout, which is cruder and safer. **What we do not do is
trade through CPI on an uncorroborated LLM reading of a webpage.**

The asymmetry that decides this: a false positive costs us one missed trade. A
false negative means being long gold into a print we didn't know about. Those costs
are not comparable.

## S0.6 — Keyless data reach (`risk:invalidates-design`)

**Assumption.** Everything the loop needs — macro, cross-asset, positioning — is
reachable with **no API key**, from declarative fetch specs.

**Already verified** (2026-07-13, by direct curl):

```
FRED    https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFII10,DTWEXBGS
        → real yields, broad dollar, curve. Multi-series. Keyless. WORKS.
Yahoo   https://query1.finance.yahoo.com/v8/finance/chart/AAPL?range=5d&interval=1d
        → any ticker: AAPL, ^VIX, DX-Y.NYB. Cross-asset OHLC. Keyless. WORKS.
Stooq   → DEAD. Returns a JavaScript proof-of-work anti-bot challenge, with a
          200 status. A live demonstration of why every procedure needs a
          validator: without one, that JS blob gets "parsed" into nonsense and
          fed to the model.
```

**Still to test.**
- CFTC COT positioning, keyless
- whether the causal graph's episode studies can actually run on Yahoo history
  (enough years, adequate quality) — this is what lets an edge earn its evidence
  **without any trades**, so it matters
- rate limits under a realistic daily research load

**Passes if** an edge like *"risk-off → gold, inverts under dollar-funding stress"*
can be evidenced from keyless data alone, across 20 years.

**Kill condition.** If cross-asset history isn't reachable keyless, the causal graph
cannot validate its edges against market data — and that is the property that lets it
learn fast while beliefs learn slowly. Losing it collapses the two-speed design.

## Acceptance for the phase

Every spike closed with **evidence in the closing comment** — the command and its
output, or the row that appeared. Each of S0.1–S0.6 has either passed, or failed
with a written decision about what changes as a result.

## Refs

- Architecture: `docs/ARCHITECTURE.md`
- The join, in detail: `docs/ARCHITECTURE.md` § JOIN
