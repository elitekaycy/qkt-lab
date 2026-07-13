"""Execute stored procedures: declarative fetch specs, never shell.

This module is the security boundary described in docs/SELF-ADVANCING.md §1.
The agent reads the open web for a living; a web page can carry text crafted to
be read as an instruction; if that text landed in a stored procedure and we
executed procedures as shell, any page the agent reads could run code here.

So a procedure is DATA — url, params, parser — run by an HTTP client, and:

  - a procedure with no validator is rejected at load (non-negotiable)
  - every fetch is validated (shape, freshness, plausible range) because a fetch
    that silently returns garbage is worse than one that fails
  - health is written by THIS runner, never by the model — the thing being
    measured does not get to write its own score
  - a failing source is reported as MISSING, never substituted with a stale value
"""

from __future__ import annotations

import csv
import io
import json as jsonlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml

ALLOWED_METHODS = {"GET"}
PARSERS = {"csv", "json"}


class ProcedureError(Exception):
    """The spec itself is unusable (missing validator, bad domain, shell-shaped)."""


@dataclass
class FetchResult:
    ok: bool
    procedure_id: str
    reason: str
    rows: list[dict[str, Any]]


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text()
    m = re.match(r"\A---\n(.*?)\n---", text, re.S)
    if m:
        return yaml.safe_load(m.group(1)) or {}
    # A pure-YAML procedure file is fine too.
    return yaml.safe_load(text) or {}


def load_spec(path: Path, allowed_domains: set[str]) -> dict[str, Any]:
    """Load and REJECT anything unsafe or unvalidated. Failing here is the point."""
    spec = _frontmatter(path)
    pid = spec.get("id", path.stem)
    fetch = spec.get("fetch")
    if not isinstance(fetch, dict):
        raise ProcedureError(f"{pid}: no fetch block — a procedure is data, not prose")

    if any(k in spec or k in fetch for k in ("command", "shell", "exec", "script")):
        raise ProcedureError(
            f"{pid}: contains a shell-shaped key. Model-authored shell is remote "
            f"code execution — a human writes and commits those, never this path."
        )

    method = str(fetch.get("method", "GET")).upper()
    if method not in ALLOWED_METHODS:
        raise ProcedureError(f"{pid}: method {method} not allowed")

    url = fetch.get("url", "")
    host = urlparse(url).hostname or ""
    if not host or (allowed_domains and host not in allowed_domains):
        raise ProcedureError(
            f"{pid}: domain {host!r} is not in the allowlist. New domains go "
            f"through the review queue first (docs/SELF-ADVANCING.md §1)."
        )

    if fetch.get("parser") not in PARSERS:
        raise ProcedureError(f"{pid}: parser must be one of {sorted(PARSERS)}")

    validate = spec.get("validate")
    if not isinstance(validate, dict) or not validate:
        raise ProcedureError(
            f"{pid}: no validator. A stored fetch that silently returns garbage is "
            f"worse than one that fails. Rejected at load, by design."
        )
    # A validator that checks nothing is a validator written to pass.
    meaningful = {"min_rows", "freshness_days", "value_range", "no_nulls_in", "columns"}
    if not meaningful & set(validate):
        raise ProcedureError(f"{pid}: validator is trivially permissive — add real checks")

    spec["id"] = pid
    return spec


def _parse(body: str, fetch: dict[str, Any]) -> list[dict[str, Any]]:
    if fetch["parser"] == "csv":
        reader = csv.DictReader(io.StringIO(body))
        return [dict(r) for r in reader]
    data = jsonlib.loads(body)
    path = fetch.get("json_path", "")
    for key in [p for p in path.split(".") if p]:
        data = data[int(key)] if isinstance(data, list) else data[key]
    if isinstance(data, dict):
        return [data]
    return list(data)


def _validate(rows: list[dict[str, Any]], v: dict[str, Any], now: datetime) -> str | None:
    """Returns a rejection reason, or None. Every check catches a real, observed
    failure mode — see the table in docs/SELF-ADVANCING.md §2."""
    if "min_rows" in v and len(rows) < int(v["min_rows"]):
        return f"{len(rows)} rows < min_rows {v['min_rows']} (anti-bot wall? rate limit?)"

    if cols := v.get("columns"):
        if rows and (missing := set(cols) - set(rows[0])):
            return f"columns missing: {sorted(missing)} (schema drift)"

    for col in v.get("no_nulls_in", []):
        if any(r.get(col) in (None, "", ".") for r in rows[-20:]):
            return f"nulls in {col} over the recent window"

    if rng := v.get("value_range"):
        lo, hi = float(rng[0]), float(rng[1])
        col = v.get("value_column") or (v.get("no_nulls_in") or [None])[0]
        if col:
            for r in rows[-20:]:
                raw = r.get(col)
                if raw in (None, "", "."):
                    continue
                try:
                    x = float(raw)
                except (TypeError, ValueError):
                    return f"{col}={raw!r} is not numeric (parse failure, not a market event)"
                if not lo <= x <= hi:
                    return (
                        f"{col}={x} outside [{lo}, {hi}] — a unit/decimal bug reads to "
                        f"an LLM as an extraordinary macro event"
                    )

    if days := v.get("freshness_days"):
        col = v.get("date_column", "observation_date")
        dates = [r.get(col) for r in rows if r.get(col)]
        if dates:
            try:
                latest = max(datetime.fromisoformat(str(d)).replace(tzinfo=UTC) for d in dates)
            except ValueError:
                return f"unparseable dates in {col}"
            if now - latest > timedelta(days=float(days)):
                return f"stale: latest {col} is {latest.date()} (max {days}d old)"

    return None


class Runner:
    def __init__(self, root: Path, allowed_domains: set[str], timeout_s: float = 20.0):
        self.root = root
        self.allowed_domains = allowed_domains
        self.timeout_s = timeout_s

    def run(self, procedure_id: str, now: datetime | None = None, **params: str) -> FetchResult:
        now = now or datetime.now(UTC)
        path = self.root / f"{procedure_id}.md"
        if not path.exists():
            path = self.root / f"{procedure_id}.yaml"
        if not path.exists():
            return FetchResult(False, procedure_id, "no such procedure", [])

        try:
            spec = load_spec(path, self.allowed_domains)
        except ProcedureError as e:
            return FetchResult(False, procedure_id, str(e), [])

        fetch = spec["fetch"]
        url = fetch["url"].format(**params) if params else fetch["url"]
        try:
            r = httpx.get(
                url,
                params={k: str(v).format(**params) if params else v
                        for k, v in (fetch.get("params") or {}).items()},
                headers=fetch.get("headers") or {},
                timeout=self.timeout_s,
                follow_redirects=True,
            )
            r.raise_for_status()
            rows = _parse(r.text, fetch)
        except Exception as e:
            self._health(path, ok=False)
            return FetchResult(False, procedure_id, f"fetch failed: {e}", [])

        if reason := _validate(rows, spec["validate"], now):
            # Degraded, and reported as MISSING upstream — never a stale substitute.
            self._health(path, ok=False)
            return FetchResult(False, procedure_id, f"validation: {reason}", [])

        self._health(path, ok=True)
        return FetchResult(True, procedure_id, "", rows)

    def _health(self, path: Path, *, ok: bool) -> None:
        """Health is written by the runner, in a sidecar — the model never touches it."""
        side = path.with_suffix(".health.yaml")
        h: dict[str, Any] = {}
        if side.exists():
            h = yaml.safe_load(side.read_text()) or {}
        if ok:
            h["last_ok"] = datetime.now(UTC).isoformat()
            h["consecutive_failures"] = 0
            h["used_count"] = int(h.get("used_count", 0)) + 1
        else:
            h["consecutive_failures"] = int(h.get("consecutive_failures", 0)) + 1
        h["status"] = "ok" if ok else ("dead" if h["consecutive_failures"] >= 5 else "degraded")
        side.write_text(yaml.safe_dump(h))
