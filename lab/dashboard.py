"""Read-only HTTP journal for every lab decision and broker-joined outcome.

The first-party journal is the complete audit surface: TRADE, NO_TRADE, GATED,
model failures, reasoning, broker outcomes, and the exact chart artifacts
handed to the model.
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import config as cfgmod
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "dashboard" / "dist"


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def _chart_relative(path: str) -> str:
    normalized = path.replace("\\", "/")
    marker = "/charts/"
    if marker in normalized:
        return normalized.split(marker, 1)[1]
    if normalized.startswith("charts/"):
        return normalized.removeprefix("charts/")
    return Path(normalized).name


def _chart_view(
    path: str,
    decision_id: int,
    index: int,
    *,
    stored_snapshots: int = 0,
) -> dict[str, Any]:
    public_base = os.environ.get("LAB_CHARTS_PUBLIC_URL", "http://localhost:8080/charts")
    relative = _chart_relative(path)
    snapshot = Path(path).with_suffix(".json")
    return {
        "image": f"{public_base.rstrip('/')}/{relative}",
        "label": Path(path).stem,
        "snapshotAvailable": index < stored_snapshots or snapshot.exists(),
        "snapshot": f"/api/decisions/{decision_id}/snapshots/{index}",
    }


def _enrich(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    decision_id = int(result["id"])
    stored_snapshots = int(result.pop("stored_snapshots", 0) or 0)
    result["chartViews"] = [
        _chart_view(
            str(path),
            decision_id,
            index,
            stored_snapshots=stored_snapshots,
        )
        for index, path in enumerate(result.get("charts") or [])
    ]
    return result


class Journal:
    def __init__(self, dsn: str) -> None:
        self.store = Store(dsn)

    def overview(self) -> dict[str, Any]:
        row = self.store.query(
            """
            SELECT
                COUNT(*)::int AS decisions,
                COUNT(*) FILTER (WHERE action = 'TRADE')::int AS trades,
                COUNT(*) FILTER (WHERE action = 'NO_TRADE')::int AS no_trades,
                COUNT(*) FILTER (WHERE action = 'GATED')::int AS gated,
                COUNT(*) FILTER (WHERE accepted)::int AS accepted,
                MAX(ts) AS latest_decision_at
            FROM decision
            """
        )[0]
        outcomes = self.store.query(
            """
            SELECT COUNT(*)::int AS closed_trades,
                   COALESCE(SUM(net_pnl), 0) AS realized_pnl,
                   AVG(r_multiple) AS average_r,
                   AVG(net_pnl) AS expectancy,
                   COUNT(*) FILTER (WHERE net_pnl > 0)::int AS wins,
                   COUNT(*) FILTER (WHERE net_pnl < 0)::int AS losses,
                   COALESCE(SUM(net_pnl) FILTER (WHERE net_pnl > 0), 0) AS gross_profit,
                   COALESCE(ABS(SUM(net_pnl) FILTER (WHERE net_pnl < 0)), 0) AS gross_loss,
                   COALESCE(SUM(commission), 0) AS commission,
                   COALESCE(SUM(swap), 0) AS swap,
                   MAX(net_pnl) AS best_trade,
                   MIN(net_pnl) AS worst_trade
            FROM outcome
            """
        )[0]
        closed = int(outcomes["closed_trades"])
        wins = int(outcomes["wins"])
        gross_loss = float(outcomes["gross_loss"])
        gross_profit = float(outcomes["gross_profit"])
        return {
            **row,
            **outcomes,
            "win_rate": wins / closed * 100 if closed else None,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else None,
            "timezone": "UTC",
        }

    def analytics(self) -> dict[str, Any]:
        """Widget-ready analytics derived only from broker-joined lab outcomes."""
        outcomes = self.store.query(
            """
            SELECT d.id, d.symbol, d.side, d.setup, d.ts, d.arm,
                   o.closed_at, o.net_pnl, o.r_multiple, o.duration_s,
                   o.commission, o.swap
            FROM decision d
            JOIN outcome o USING (ticket)
            WHERE d.action = 'TRADE' AND d.accepted
            ORDER BY o.closed_at, d.id
            """
        )

        cumulative = 0.0
        cumulative_r = 0.0
        peak = 0.0
        max_drawdown = 0.0
        curve: list[dict[str, Any]] = []
        by_day: dict[str, dict[str, Any]] = {}
        by_setup: dict[str, dict[str, Any]] = {}
        by_hour: dict[int, dict[str, Any]] = {}

        for row in outcomes:
            net = float(row["net_pnl"])
            r_value = float(row["r_multiple"]) if row.get("r_multiple") is not None else None
            cumulative += net
            if r_value is not None:
                cumulative_r += r_value
            peak = max(peak, cumulative)
            max_drawdown = max(max_drawdown, peak - cumulative)
            closed = row["closed_at"]
            curve.append(
                {
                    "decisionId": int(row["id"]),
                    "at": closed,
                    "netPnl": net,
                    "cumulativePnl": cumulative,
                    "cumulativeR": cumulative_r,
                    "drawdown": peak - cumulative,
                }
            )

            day = closed.date().isoformat()
            daily = by_day.setdefault(
                day, {"date": day, "netPnl": 0.0, "trades": 0, "wins": 0, "r": 0.0}
            )
            daily["netPnl"] += net
            daily["trades"] += 1
            daily["wins"] += int(net > 0)
            daily["r"] += r_value or 0.0

            setup = str(row.get("setup") or "Unclassified")
            setup_row = by_setup.setdefault(
                setup, {"setup": setup, "netPnl": 0.0, "trades": 0, "wins": 0, "r": 0.0}
            )
            setup_row["netPnl"] += net
            setup_row["trades"] += 1
            setup_row["wins"] += int(net > 0)
            setup_row["r"] += r_value or 0.0

            hour = int(row["ts"].hour)
            hour_row = by_hour.setdefault(
                hour, {"hour": hour, "netPnl": 0.0, "trades": 0, "wins": 0}
            )
            hour_row["netPnl"] += net
            hour_row["trades"] += 1
            hour_row["wins"] += int(net > 0)

        decisions = self.store.query(
            """
            SELECT action, COUNT(*)::int AS count
            FROM decision
            GROUP BY action
            ORDER BY action
            """
        )

        def finish(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            for row in rows:
                trades = int(row["trades"])
                row["winRate"] = row["wins"] / trades * 100 if trades else None
                if "r" in row:
                    row["averageR"] = row["r"] / trades if trades else None
            return rows

        return {
            "curve": curve,
            "daily": finish(list(by_day.values())),
            "setups": sorted(
                finish(list(by_setup.values())),
                key=lambda item: (item["trades"], abs(item["netPnl"])),
                reverse=True,
            ),
            "hours": sorted(finish(list(by_hour.values())), key=lambda item: item["hour"]),
            "decisionBreakdown": [
                {"action": row["action"], "count": int(row["count"])} for row in decisions
            ],
            "maxDrawdown": max_drawdown,
            "timezone": "UTC",
            "curveBasis": "Cumulative realized lab net P&L from zero",
        }

    def calendar(self) -> list[dict[str, Any]]:
        decisions = self.store.query(
            """
            SELECT (ts AT TIME ZONE 'UTC')::date AS day,
                   COUNT(*)::int AS decisions,
                   COUNT(*) FILTER (WHERE action = 'TRADE')::int AS trade_decisions,
                   COUNT(*) FILTER (WHERE action = 'NO_TRADE')::int AS no_trades,
                   COUNT(*) FILTER (WHERE action = 'GATED')::int AS gated
            FROM decision
            GROUP BY day
            ORDER BY day
            """
        )
        outcomes = self.store.query(
            """
            SELECT (closed_at AT TIME ZONE 'UTC')::date AS day,
                   COUNT(*)::int AS closed_trades,
                   COUNT(*) FILTER (WHERE net_pnl > 0)::int AS wins,
                   COALESCE(SUM(net_pnl), 0) AS net_pnl,
                   COALESCE(SUM(r_multiple), 0) AS r_multiple
            FROM outcome
            GROUP BY day
            ORDER BY day
            """
        )
        days: dict[str, dict[str, Any]] = {}
        for row in decisions:
            key = row["day"].isoformat()
            days[key] = {"date": key, **{k: v for k, v in row.items() if k != "day"}}
        for row in outcomes:
            key = row["day"].isoformat()
            target = days.setdefault(
                key,
                {
                    "date": key,
                    "decisions": 0,
                    "trade_decisions": 0,
                    "no_trades": 0,
                    "gated": 0,
                },
            )
            target.update({k: v for k, v in row.items() if k != "day"})
        return [days[key] for key in sorted(days)]

    def operations(self) -> dict[str, Any]:
        """Recorded scheduler activity and trade lifecycle, not inferred service decoration."""
        latest_rows = self.store.query(
            """
            SELECT id, ts, action, symbol, setup, gate_rejects
            FROM decision
            ORDER BY ts DESC
            LIMIT 1
            """
        )
        activity = self.store.query(
            """
            SELECT COUNT(*) FILTER (WHERE ts >= now() - interval '24 hours')::int
                       AS decisions_24h,
                   COUNT(*) FILTER (
                       WHERE ts >= now() - interval '24 hours' AND action = 'TRADE'
                   )::int AS trades_24h,
                   COUNT(*) FILTER (
                       WHERE ts >= now() - interval '24 hours' AND action = 'NO_TRADE'
                   )::int AS no_trades_24h,
                   COUNT(*) FILTER (
                       WHERE ts >= now() - interval '24 hours' AND action = 'GATED'
                   )::int AS gated_24h
            FROM decision
            """
        )[0]
        lifecycle = self.store.query(
            """
            SELECT COUNT(*) FILTER (WHERE d.accepted AND o.ticket IS NULL)::int
                       AS open_trades,
                   COUNT(*) FILTER (WHERE d.accepted AND o.ticket IS NOT NULL)::int
                       AS closed_trades,
                   COUNT(*) FILTER (WHERE d.action = 'TRADE' AND NOT d.accepted)::int
                       AS venue_rejects,
                   MAX(o.joined_at) AS last_outcome_join_at
            FROM decision d
            LEFT JOIN outcome o USING (ticket)
            """
        )[0]
        runs = self.store.query(
            """
            SELECT DISTINCT ON (job)
                   job, command, started_at, finished_at, ok, detail
            FROM job_run
            ORDER BY job, started_at DESC
            """
        )

        latest = latest_rows[0] if latest_rows else None
        cycle_age = None
        cycle_health = "waiting"
        if latest:
            cycle_age = max(0, int((datetime.now(UTC) - latest["ts"]).total_seconds()))
            cycle_health = (
                "healthy"
                if cycle_age <= 90 * 60
                else "delayed"
                if cycle_age <= 3 * 3600
                else "stale"
            )

        cfg = cfgmod.load(ROOT / "lab.yaml")
        schedules = [
            {
                "job": "trade",
                "label": f"Decision cycle · {instrument.symbol}",
                "schedule": instrument.schedule,
                "purpose": "Refresh venue context, ask Codex for a proposal, then apply deterministic gates.",
            }
            for instrument in cfg.instruments
        ]
        schedules.extend(
            [
                {
                    "job": "join",
                    "label": "Outcome join",
                    "schedule": cfg.raw["store"]["join_interval"],
                    "purpose": "Reconcile accepted tickets with broker closes and calculate net P&L and R.",
                },
                {
                    "job": "distill",
                    "label": "Nightly learning",
                    "schedule": cfg.raw["agent"]["distiller"]["schedule"],
                    "purpose": "Score completed episodes and propose evidence-backed belief updates.",
                },
                {
                    "job": "research",
                    "label": "Daily research",
                    "schedule": cfg.raw["agent"]["researcher"]["schedule"],
                    "purpose": "Refresh sources, procedures, causal evidence, and the event calendar.",
                },
            ]
        )
        return {
            "cycleHealth": cycle_health,
            "cycleAgeSeconds": cycle_age,
            "latestDecision": latest,
            "activity24h": activity,
            "lifecycle": lifecycle,
            "jobRuns": runs,
            "schedules": schedules,
            "timezone": "UTC",
            "healthBasis": "Latest recorded decision cycle; healthy within 90 minutes.",
        }

    def decisions(
        self, *, limit: int = 100, action: str | None = None, search: str = ""
    ) -> list[dict[str, Any]]:
        where: list[str] = []
        params: list[Any] = []
        if action in {"TRADE", "NO_TRADE", "GATED"}:
            where.append("d.action = %s")
            params.append(action)
        if search:
            where.append(
                """(
                    d.symbol ILIKE %s OR d.as_name ILIKE %s OR
                    COALESCE(d.setup, '') ILIKE %s OR COALESCE(d.thesis, '') ILIKE %s OR
                    COALESCE(d.rationale_md, '') ILIKE %s
                )"""
            )
            needle = f"%{search}%"
            params.extend([needle] * 5)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        params.append(max(1, min(limit, 500)))
        rows = self.store.query(
            f"""
            SELECT d.id, d.ts, d.arm, d.as_name, d.symbol, d.broker_symbol,
                   d.action, d.side, d.lots, d.sl, d.tp, d.expected_rr,
                   d.conviction, d.setup, d.factors, d.news, d.regime,
                   d.thesis, d.rationale_md, d.invalidation, d.charts,
                   d.map_nodes_used, d.beliefs_used, d.sources_read,
                   d.procedures_used, d.sources_missing, d.unexplained,
                   d.ticket, d.open_deal, d.fill_price, d.retcode, d.accepted,
                   d.gate_rejects, d.risk_at_entry, d.equity_at_entry,
                   d.conviction_mult, d.model, d.prompt_sha, d.canonical_dsl,
                   d.cmd_sha256, d.qkt_version,
                   jsonb_array_length(
                       COALESCE(d.context_snapshot->'chartSnapshots', '[]'::jsonb)
                   ) AS stored_snapshots,
                   o.closed_at, o.close_price, o.gross_pnl, o.commission,
                   o.swap, o.net_pnl, o.r_multiple, o.duration_s, o.lots_closed
            FROM decision d
            LEFT JOIN outcome o USING (ticket)
            {clause}
            ORDER BY d.ts DESC
            LIMIT %s
            """,
            tuple(params),
        )
        return [_enrich(row) for row in rows]

    def decision(self, decision_id: int) -> dict[str, Any] | None:
        rows = self.store.query(
            """
            SELECT d.*, o.closed_at, o.close_price, o.gross_pnl, o.commission,
                   o.swap, o.net_pnl, o.r_multiple, o.duration_s, o.lots_closed,
                   o.deals
            FROM decision d
            LEFT JOIN outcome o USING (ticket)
            WHERE d.id = %s
            """,
            (decision_id,),
        )
        return _enrich(rows[0]) if rows else None

    def snapshot(self, decision_id: int, index: int) -> dict[str, Any] | None:
        rows = self.store.query(
            "SELECT charts, context_snapshot FROM decision WHERE id = %s",
            (decision_id,),
        )
        if not rows:
            return None
        stored = (rows[0].get("context_snapshot") or {}).get("chartSnapshots") or []
        if 0 <= index < len(stored):
            return stored[index]
        charts = rows[0].get("charts") or []
        if index < 0 or index >= len(charts):
            return None
        path = Path(str(charts[index])).with_suffix(".json").resolve()
        state_root = (ROOT / "state" / "charts").resolve()
        if state_root not in path.parents or not path.is_file():
            return None
        return json.loads(path.read_text())


def _probe(url: str, *, token: str = "") -> dict[str, Any]:
    request = urllib.request.Request(url)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = response.read(4096).decode(errors="replace")
            try:
                body = json.loads(payload)
            except json.JSONDecodeError:
                body = None
            return {"online": True, "http": response.status, "body": body}
    except urllib.error.HTTPError as error:
        return {"online": True, "http": error.code, "body": None}
    except Exception as error:
        return {"online": False, "error": type(error).__name__}


def _status() -> dict[str, Any]:
    gateway = os.environ.get("MT5_GATEWAY_URL", "http://mt5-gateway:5001")
    token = os.environ.get("QKT_BROKER_EXNESS_API_KEY", "")
    gateway_health = _probe(f"{gateway.rstrip('/')}/health/ready", token=token)
    account = _probe(f"{gateway.rstrip('/')}/account", token=token)
    return {
        "gateway": gateway_health,
        "account": account,
        "database": {"online": True, "source": "lab Postgres"},
        "killSwitch": (ROOT / "KILL").exists(),
        "timezone": "UTC",
    }


class Handler(BaseHTTPRequestHandler):
    journal: Journal

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"journal-ui {self.address_string()} {fmt % args}")

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, default=_json_default, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        target = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in target.parents or not target.is_file():
            target = WEB_ROOT / "index.html"
        body = target.read_bytes()
        kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type", f"{kind}; charset=utf-8" if kind.startswith("text/") else kind
        )
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Cache-Control",
            "public, max-age=31536000, immutable" if target.parent.name == "assets" else "no-cache",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/healthz":
                self._send_json({"ok": True})
                return
            if path == "/api/overview":
                self._send_json(self.journal.overview())
                return
            if path == "/api/status":
                status = _status()
                status["operations"] = self.journal.operations()
                self._send_json(status)
                return
            if path == "/api/analytics":
                self._send_json(self.journal.analytics())
                return
            if path == "/api/calendar":
                self._send_json(self.journal.calendar())
                return
            if path == "/api/decisions":
                query = parse_qs(parsed.query)
                limit = int(query.get("limit", ["100"])[0])
                action = query.get("action", [None])[0]
                search = query.get("q", [""])[0].strip()
                self._send_json(self.journal.decisions(limit=limit, action=action, search=search))
                return
            parts = [part for part in path.split("/") if part]
            if len(parts) == 3 and parts[:2] == ["api", "decisions"]:
                decision = self.journal.decision(int(parts[2]))
                self._send_json(
                    decision if decision is not None else {"error": "not found"},
                    HTTPStatus.OK if decision is not None else HTTPStatus.NOT_FOUND,
                )
                return
            if len(parts) == 5 and parts[:2] == ["api", "decisions"] and parts[3] == "snapshots":
                snapshot = self.journal.snapshot(int(parts[2]), int(parts[4]))
                self._send_json(
                    snapshot if snapshot is not None else {"error": "not found"},
                    HTTPStatus.OK if snapshot is not None else HTTPStatus.NOT_FOUND,
                )
                return
            self._send_static(path)
        except (ValueError, TypeError):
            self._send_json({"error": "bad request"}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            print(f"journal-ui request failed: {type(error).__name__}: {error}")
            self._send_json({"error": "internal error"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    dsn = os.environ.get("LAB_DATABASE_URL", "postgresql://lab:lab@localhost:5432/lab")
    Handler.journal = Journal(dsn)
    port = int(os.environ.get("LAB_JOURNAL_INTERNAL_PORT", "8421"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"journal-ui listening on 0.0.0.0:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
