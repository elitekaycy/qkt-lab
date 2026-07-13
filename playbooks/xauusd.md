# XAUUSD playbook

The standing process for trading gold. This file holds what does not change hour
to hour, so the model stops re-deriving it every cycle. Human-edited; refined
slowly as the journal teaches us things.

## The instrument

- Spot gold vs USD. 1 lot = 100 oz, so a $1 move = $100/lot.
- Prefixed symbol `ICM:XAUUSD`; the venue-side symbol may carry a broker suffix.
- Spread is tightest during London and New York; Asian-session spreads and thin
  books make most setups untradeable — the bar for an Asia trade is much higher.

## Sessions (UTC)

| session | hours | character |
|---|---|---|
| Asia | 00-07 | range-building, thin. Usually NO_TRADE. |
| London open | 07-09 | the day's first real flow; Asian range often breaks or fails here |
| NY overlap | 12-16 | highest volume; macro prints land here (12:30/14:00 favourites) |
| Late NY | 19-21 | positioning unwinds, moves fade |

## What moves gold (short form — the map nodes carry the full causal detail)

- **Real yields** (10y TIPS): the core opportunity-cost channel, inverse. Currently
  check the map node for whether the relationship is live or suppressed.
- **DXY**: inverse, same-day. A gold move *against* DXY is information.
- **Risk-off**: usually a bid — EXCEPT under dollar-funding stress, when gold sells
  off with everything (Mar 2020, Sep 2008). Check the map node's inversion clause.
- **Central-bank demand**: price-insensitive structural bid; dampens macro shorts.
- **Prints that matter**: CPI, NFP, FOMC. Do not carry a fresh position into any of
  them — the blackout gate will refuse anyway, but do not propose it.

## Setups I take

1. **London-open pullback**: 1h trend intact, 15m pullback to VWAP/EMA cluster,
   stop under the pullback low, target the session extension. Best odds of the day.
2. **Post-print continuation**: after a print resolves and the first 15m bar
   closes directional, join with a stop beyond the print bar. Never fade a print.
3. **Range fade at Asia extremes** only when the 1h is flat AND spread is normal.
   Half conviction by default.

## What invalidates a setup

- 15m close through the level the idea is built on — out, no averaging.
- DXY breaking its own session structure against the trade.
- Anything on the calendar within the blackout window.

## Discipline reminders

- Stops go where the idea is wrong, not at round dollar amounts.
- One position per direction; adding to winners only after a fresh setup.
- A missed trade costs nothing. NO_TRADE is the default state, not a failure.
