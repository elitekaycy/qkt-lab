"""One-way export of closed lab trades into a self-hosted Deltalytix.

Deltalytix is the journal YOU read — calendar, equity curve, search. It is not
the machine's store and nothing ever reads back from it: if it is down, trades
still execute and beliefs still score.

Everything here is pinned from the Deltalytix repo (commit 3a8223a):

- Table names are quoted PascalCase ("Trade") — no @@map in its Prisma schema.
- `id` is the ONLY unique key. The app derives it as a deterministic UUIDv5 over
  a pipe-joined 14-field signature. Replicate that exactly and re-runs become
  `ON CONFLICT DO NOTHING`; use random UUIDs and every re-run duplicates every
  trade.
- A `Subscription` row (status ACTIVE, email matching the user) is REQUIRED or
  the UI silently hides everything older than 14 days.
- `pnl` is GROSS and signed; `commission` is a POSITIVE magnitude (the app
  computes pnl - commission itself — do not pre-subtract).
- `timeInPosition` is SECONDS. Dates are UTC ISO STRINGS (sorted lexically).
- `side` is "Long"/"Short". `images` holds URLs, not filesystem paths.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import psycopg

# The app uses the standard DNS namespace for its UUIDv5.
NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

SIGNATURE_FIELDS = [
    "userId",
    "accountNumber",
    "instrument",
    "entryDate",
    "closeDate",
    "entryPrice",
    "closePrice",
    "quantity",
    "entryId",
    "closeId",
    "timeInPosition",
    "side",
    "pnl",
    "commission",
]


def trade_uuid(trade: dict[str, Any]) -> str:
    """The app's exact recipe: pipe-join the 14 fields (empty string for nullish,
    numbers stringified), UUIDv5 under the DNS namespace."""
    parts = []
    for f in SIGNATURE_FIELDS:
        v = trade.get(f)
        parts.append("" if v is None else str(v))
    return str(uuid.uuid5(NAMESPACE, "|".join(parts)))


@dataclass(frozen=True)
class Target:
    dsn: str
    user_id: str
    user_email: str
    account_number: str
    starting_balance: float
    charts_base_url: str


def to_trade_row(episode: dict[str, Any], t: Target) -> dict[str, Any]:
    """Map one lab episode (decision ⋈ outcome) onto Deltalytix's Trade shape.

    Deliberately lossy: factors+setup -> tags, thesis+rationale -> comment,
    chart paths -> URLs. NO_TRADE/GATED rows cannot exist in its schema and are
    not exported — they stay in the lab store where the machine learns from them.
    """
    side = "Long" if episode.get("side") == "BUY" else "Short"
    gross = float(episode["gross_pnl"])
    commission = abs(float(episode["commission"]))  # positive magnitude, per the app

    comment_parts = [episode.get("thesis") or "", episode.get("rationale_md") or ""]
    comment = "\n\n".join(p for p in comment_parts if p).strip() or None

    tags = list(episode.get("factors") or [])
    if episode.get("setup"):
        tags.insert(0, str(episode["setup"]).replace(" ", "-"))

    images = [
        f"{t.charts_base_url.rstrip('/')}/{str(p).split('charts/', 1)[-1]}"
        for p in (episode.get("charts") or [])
    ]

    opened = episode["ts"]
    closed = episode["closed_at"]

    trade = {
        "userId": t.user_id,
        "accountNumber": t.account_number,
        "instrument": str(episode["symbol"]).split(":")[-1],
        # Lot quantity doesn't fit an Int cleanly; Deltalytix's importers use
        # contract counts. 0.13 lots -> 13 micro-contracts keeps it integral.
        "quantity": int(round(float(episode["lots"]) * 100)),
        "entryId": str(episode.get("ticket") or ""),
        "closeId": str(episode.get("ticket") or ""),
        "entryPrice": str(episode["fill_price"]),
        "closePrice": str(episode["close_price"]),
        "entryDate": opened.isoformat(),
        "closeDate": closed.isoformat(),
        "pnl": gross,
        "timeInPosition": float(episode["duration_s"]),
        "side": side,
        "commission": commission,
        "comment": comment,
        "tags": tags,
        "images": images,
        "videoUrl": None,
        "imageBase64": None,
        "imageBase64Second": None,
        "groupId": "",
    }
    trade["id"] = trade_uuid(trade)
    return trade


def ensure_scaffolding(conn: psycopg.Connection, t: Target) -> None:
    """User, Account, and the load-bearing Subscription row."""
    conn.execute(
        """
        INSERT INTO "User" (id, auth_user_id, email, language)
        VALUES (%s, %s, %s, 'en')
        ON CONFLICT (id) DO NOTHING
        """,
        (t.user_id, t.user_id, t.user_email),
    )
    conn.execute(
        """
        INSERT INTO "Account" (id, number, "userId", "startingBalance")
        VALUES (gen_random_uuid()::text, %s, %s, %s)
        ON CONFLICT (number, "userId") DO NOTHING
        """,
        (t.account_number, t.user_id, t.starting_balance),
    )
    # Without this row the UI hides everything older than 14 days — silently.
    conn.execute(
        """
        INSERT INTO "Subscription" (id, email, plan, "userId", status)
        VALUES (gen_random_uuid()::text, %s, 'Plus', %s, 'ACTIVE')
        ON CONFLICT (email) DO NOTHING
        """,
        (t.user_email, t.user_id),
    )


def export(episodes: list[dict[str, Any]], t: Target) -> dict[str, int]:
    """Idempotent by construction: same episode -> same UUIDv5 -> DO NOTHING."""
    rows = [to_trade_row(e, t) for e in episodes]
    inserted = 0
    with psycopg.connect(t.dsn) as conn:
        ensure_scaffolding(conn, t)
        for r in rows:
            cur = conn.execute(
                """
                INSERT INTO "Trade" (id, "userId", "accountNumber", instrument,
                    quantity, "entryId", "closeId", "entryPrice", "closePrice",
                    "entryDate", "closeDate", pnl, "timeInPosition", side,
                    commission, comment, tags, images, "groupId")
                VALUES (%(id)s, %(userId)s, %(accountNumber)s, %(instrument)s,
                    %(quantity)s, %(entryId)s, %(closeId)s, %(entryPrice)s,
                    %(closePrice)s, %(entryDate)s, %(closeDate)s, %(pnl)s,
                    %(timeInPosition)s, %(side)s, %(commission)s, %(comment)s,
                    %(tags)s, %(images)s, %(groupId)s)
                ON CONFLICT (id) DO NOTHING
                """,
                r,
            )
            inserted += cur.rowcount
        conn.commit()
    return {"exported": len(rows), "inserted": inserted}
