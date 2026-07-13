"""The decision log. Postgres, typed, queryable.

Every decision is written — TRADE, NO_TRADE, and GATED alike. The rows most
systems throw away (a proposal that was refused) are the most diagnostic ones we
have.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


@dataclass
class Decision:
    as_name: str
    symbol: str
    action: str  # TRADE | NO_TRADE | GATED

    side: str | None = None
    lots: float | None = None
    sl: float | None = None
    tp: float | None = None
    expected_rr: float | None = None
    conviction: float | None = None

    setup: str | None = None
    factors: list[str] = field(default_factory=list)
    news: list[dict[str, Any]] = field(default_factory=list)
    regime: dict[str, Any] = field(default_factory=dict)
    thesis: str | None = None
    rationale_md: str | None = None
    invalidation: str | None = None
    charts: list[str] = field(default_factory=list)

    map_nodes_used: list[str] = field(default_factory=list)
    beliefs_used: list[str] = field(default_factory=list)
    sources_read: list[str] = field(default_factory=list)
    procedures_used: list[str] = field(default_factory=list)
    sources_missing: list[str] = field(default_factory=list)
    unexplained: str | None = None

    ticket: int | None = None
    open_deal: int | None = None
    fill_price: float | None = None
    retcode: int | None = None
    accepted: bool = False
    gate_rejects: list[dict[str, str]] = field(default_factory=list)

    risk_at_entry: float | None = None
    equity_at_entry: float | None = None
    conviction_mult: float | None = None
    broker_symbol: str | None = None

    arm: str = "beliefs"
    model: str | None = None
    prompt_sha: str | None = None
    qkt_version: str | None = None


_JSON_COLS = {"factors", "news", "regime", "gate_rejects"}
_ARRAY_COLS = {
    "charts",
    "map_nodes_used",
    "beliefs_used",
    "sources_read",
    "procedures_used",
    "sources_missing",
}


class Store:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _conn(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def migrate(self, schema: Path) -> None:
        with self._conn() as c:
            c.execute(schema.read_text())
            c.commit()

    def record(self, d: Decision) -> int:
        data = asdict(d)
        cols = list(data)
        vals = [Jsonb(data[k]) if k in _JSON_COLS else data[k] for k in cols]
        sql = (
            f"INSERT INTO decision ({', '.join(cols)}) "
            f"VALUES ({', '.join(['%s'] * len(cols))}) RETURNING id"
        )
        with self._conn() as c:
            row = c.execute(sql, vals).fetchone()
            c.commit()
        assert row is not None
        return int(row["id"])

    def record_outcome(
        self,
        *,
        ticket: int,
        closed_at: datetime,
        close_price: float | None,
        gross_pnl: float,
        commission: float,
        swap: float,
        net_pnl: float,
        r_multiple: float | None,
        lots_closed: float,
        duration_s: int,
        deals: list[dict[str, Any]],
    ) -> None:
        """Idempotent: re-running the joiner must be a no-op."""
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO outcome (ticket, closed_at, close_price, gross_pnl,
                                     commission, swap, net_pnl, r_multiple,
                                     lots_closed, duration_s, deals)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ticket) DO NOTHING
                """,
                (
                    ticket,
                    closed_at,
                    close_price,
                    gross_pnl,
                    commission,
                    swap,
                    net_pnl,
                    r_multiple,
                    lots_closed,
                    duration_s,
                    Jsonb(deals),
                ),
            )
            c.commit()

    # --- reads the gates and joiner depend on ------------------------------

    def open_tickets(self) -> list[dict[str, Any]]:
        """Lab-owned tickets with no outcome yet.

        This — not `qkt bot positions` — is what the gates count. qkt applies no
        magic filter and would hand us the deployed strategies' positions too.
        """
        with self._conn() as c:
            return c.execute(
                """
                SELECT d.ticket, d.symbol, d.side, d.lots, d.sl, d.fill_price,
                       d.risk_at_entry, d.ts
                FROM decision d
                LEFT JOIN outcome o USING (ticket)
                WHERE d.ticket IS NOT NULL
                  AND d.accepted
                  AND o.ticket IS NULL
                """
            ).fetchall()

    def realized_today(self) -> float:
        with self._conn() as c:
            row = c.execute(
                """
                SELECT COALESCE(SUM(o.net_pnl), 0) AS pnl
                FROM outcome o
                WHERE o.closed_at >= date_trunc('day', now() AT TIME ZONE 'utc')
                """
            ).fetchone()
        return float(row["pnl"]) if row else 0.0

    def unjoined_older_than(self, days: int) -> list[dict[str, Any]]:
        """A ticket open this long with no OUT deal is a bug, not a trade."""
        with self._conn() as c:
            return c.execute(
                """
                SELECT d.ticket, d.symbol, d.ts
                FROM decision d
                LEFT JOIN outcome o USING (ticket)
                WHERE d.ticket IS NOT NULL AND d.accepted AND o.ticket IS NULL
                  AND d.ts < now() - (%s || ' days')::interval
                """,
                (days,),
            ).fetchall()

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._conn() as c:
            return c.execute(sql, params).fetchall()
