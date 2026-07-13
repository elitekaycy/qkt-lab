# Phase 3 — The journal UI

Status: not started
Blocked by: Phase 2 (charts must exist before there's anything worth looking at)

## Why

You need to open the journal, read it, search it, and see the calendar and the
equity curve. Deltalytix (self-hosted) is that surface, and it's good at it.

## The division of labour, stated once

There are two stores and they do different jobs. This is not redundancy.

| | lab Postgres | Deltalytix |
|---|---|---|
| holds | `decision` + `outcome` — typed, structured | `Trade` + `Mood` — rich, browsable |
| read by | DISTILL, belief scoring, the A/B, research triggers | **you** |
| on the critical path | yes | **no** |

**Why Deltalytix cannot be the machine's store.** Two hard schema limits:

1. **`NO_TRADE` and `GATED` decisions cannot exist in it.** A `Trade` row requires
   `entryPrice`, `closePrice`, `pnl`, `quantity`. A decision not to trade has none
   of those. And those rows are among the most diagnostic data we have — a run of
   `GATED / min_rr` tells you the model keeps proposing bad risk-reward.
2. **Belief predicates need typed fields.** Scoring evaluates SQL like
   `(regime->>'atr14')::numeric between 3 and 5`. Deltalytix stores `tags` as
   `String[]` and even `entryPrice`/`entryDate` as `String`. You cannot range-query
   a string array. No typed fields → no predicate evaluation → no learning loop.

So: lab Postgres is the write-side truth; Deltalytix is the read surface. The
exporter is one-way and one-way only. Nothing ever reads back from Deltalytix.

## What we build

**Self-host (`docker-compose.yml`).** Deltalytix + its Postgres alongside the lab's.
Auth via `LOCAL_DASHBOARD_AUTH_BYPASS` — no Supabase needed.

**Exporter (`exporters/deltalytix.py`).** Closed trades only, one-way. Per S0.3:

- **`id` must be the app's deterministic UUIDv5** — namespace
  `6ba7b810-9dad-11d1-80b4-00c04fd430c8`, over the pipe-joined signature
  `userId|accountNumber|instrument|entryDate|closeDate|entryPrice|closePrice|quantity|entryId|closeId|timeInPosition|side|pnl|commission`.
  Then `ON CONFLICT (id) DO NOTHING`. `id` is the **only** unique key — random
  UUIDs duplicate every trade on every re-run.
- **A `Subscription` row** (`status='ACTIVE'`, email matching the user) or the UI
  silently hides everything older than **14 days**. Not documented anywhere. You
  would conclude your exporter was broken.
- `pnl` is **gross** and signed; `commission` is a **positive magnitude** (the app
  computes `pnl - commission` itself — do not pre-subtract).
- `timeInPosition` is **seconds**. Dates are **UTC ISO strings** (they're sorted
  lexically — a non-ISO date breaks ordering, silently).
- `side` is `"Long"` / `"Short"`.
- `comment` ← `thesis` + `rationale_md`. `tags[]` ← `factors[]` + `setup`.
  `images[]` ← chart **URLs** (serve `state/charts/` over HTTP; a bare filesystem
  path will not render).
- `Account` row with `startingBalance` — required for the equity curve.

**Daily narrative (`Mood` table).** One row per day: `journalContent` (the day's
thesis and what changed), `selectedNews[]`, and the free `conversation Json`
column for the structured record. This is where a day's story lives, as opposed to
a trade's.

## Out of scope

Reading anything back from Deltalytix. Exporting NO_TRADE/GATED (impossible).
Any code path where the loop breaks because the journal UI is down.

## Acceptance

1. Every closed lab trade appears in the Deltalytix UI with its rationale, its
   tags, and both chart images.
2. The PnL calendar and the equity curve render correctly.
3. Search/filter by tag (e.g. `level:vwap-touch`) returns the right trades.
4. Running the exporter twice inserts nothing the second time.
5. Trades older than 14 days are visible (i.e. the `Subscription` row is right).
6. **Stopping Deltalytix entirely does not stop the loop** — trades still execute,
   outcomes still join, beliefs still score.

## Known operational traps

- Reads go through a **1-hour cache**. A new trade may take up to an hour to
  appear. Restart the app container to force it.
- Run a **production** build. `bun run dev` has a browser IndexedDB trade cache
  with no TTL and no invalidation — new trades may never appear.
- `NEXT_PUBLIC_*` env vars are baked at **build** time; changing them needs a
  rebuild.

## License note

Deltalytix is **CC BY-NC 4.0** — not an OSI open-source license. Private personal
use is fine. If this ever instruments a commercial operation, whether that clears
the NonCommercial clause is genuinely ambiguous and worth one email to them. This
is why the exporter is a **plugin** behind `journal.deltalytix.enabled` and why
nothing in the loop depends on it: anyone can run qkt-lab without it.

## Refs

Spec: this file
Depends on: `docs/specs/phase-2-context.md`, S0.3
