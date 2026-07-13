"""Shape-checked wrapper around the `qkt bot` CLI.

Every quirk handled here is pinned from qkt's source, and each one is a bug
waiting to happen if you assume the obvious behaviour instead:

- The bot verbs return an OBJECT on error (`{"ok":false,"error":...}`) even for
  verbs whose success shape is an ARRAY. So a list-returning verb that comes back
  as a dict is an error, not an empty result. Treating it as "no positions" would
  be catastrophic.
- The arg parser is hand-rolled: there is NO `--flag=value` form, and an option's
  *value* is also counted as a positional. Positionals must come first.
- Bot verbs run with retryAttempts=0. The lab owns transient-failure retry.
- A venue reject exits non-zero.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any


class QktError(RuntimeError):
    """qkt refused, or the venue did."""


class QktUnavailable(QktError):
    """Transient: the gateway was unreachable. Retryable."""


class Qkt:
    def __init__(
        self,
        bin: str = "qkt",
        config: str | None = None,
        timeout_s: int = 30,
        retries: int = 2,
    ) -> None:
        self.bin = bin.split()  # allows `docker run ... qkt` as a "binary"
        # Never passed as --config: qkt's argv parser counts option VALUES as
        # positionals, so for verbs with no positional (`positions`, `history`)
        # the config path itself gets read as the symbol (qkt#804). Instead the
        # subprocess runs from the config's directory and qkt discovers
        # ./qkt.config.yaml on its default search path.
        self.cwd = str(Path(config).resolve().parent) if config else None
        self.timeout_s = timeout_s
        self.retries = retries

    def _run(self, verb: str, *args: str) -> Any:
        # Positionals first — the parser counts an option's value as a positional,
        # so `bot positions --broker icm` would read "icm" as the symbol.
        cmd = [*self.bin, "bot", verb, *args, "--json"]

        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                p = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=self.timeout_s, cwd=self.cwd
                )
            except subprocess.TimeoutExpired:
                last = QktUnavailable(f"{verb} timed out after {self.timeout_s}s")
                time.sleep(2**attempt)
                continue

            out = p.stdout.strip()
            if not out:
                last = QktUnavailable(
                    f"{verb} returned nothing (exit {p.returncode}): {p.stderr.strip()[:200]}"
                )
                time.sleep(2**attempt)
                continue

            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                # Not retryable — qkt said something we don't understand.
                raise QktError(f"{verb}: unparseable output: {out[:300]}") from None

            # An error is always an object with ok:false, whatever the success shape is.
            if isinstance(parsed, dict) and parsed.get("ok") is False:
                raise QktError(f"{verb}: {parsed.get('error') or parsed}")

            if p.returncode != 0:
                raise QktError(f"{verb}: exit {p.returncode}: {out[:300]}")

            return parsed

        raise last or QktUnavailable(f"{verb}: exhausted retries")

    def _list(self, verb: str, *args: str) -> list[dict[str, Any]]:
        """For verbs whose success shape is an array.

        A dict here means an error we somehow didn't catch — never an empty result.
        """
        got = self._run(verb, *args)
        if not isinstance(got, list):
            raise QktError(f"{verb}: expected an array, got {type(got).__name__}: {got}")
        return got

    def _obj(self, verb: str, *args: str) -> dict[str, Any]:
        got = self._run(verb, *args)
        if not isinstance(got, dict):
            raise QktError(f"{verb}: expected an object, got {type(got).__name__}")
        return got

    # --- reads: the only verbs the trader agent may reach ------------------

    def account(self, broker: str | None = None) -> dict[str, Any]:
        args = ["--broker", broker] if broker else []
        return self._obj("account", *args)

    def positions(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """WARNING: returns EVERY position on the account, including other
        strategies'. qkt applies no magic filter. Never count these for a gate —
        filter to lab-owned tickets from our own store.
        """
        return self._list("positions", *([symbol] if symbol else []))

    def quote(self, symbol: str) -> dict[str, Any]:
        return self._obj("quote", symbol)

    def bars(self, symbol: str, tf: str, count: int = 200) -> list[dict[str, Any]]:
        """Candles: [{t: epoch_ms, o, h, l, c, v}]. May return FEWER than `count`
        without erroring — the caller must assert a minimum."""
        return self._list("bars", symbol, "--tf", tf, "--count", str(count))

    def evaluate(self, expr: str, symbol: str, tf: str, count: int = 500) -> dict[str, Any]:
        return self._obj("eval", expr, symbol, "--tf", tf, "--count", str(count))

    def history(self, since: str = "7d", broker: str | None = None) -> list[dict[str, Any]]:
        """Realized deals. There is no --ticket filter — filter client-side on
        positionTicket. Default --since is 7d, so pass an explicit window that
        covers the open date or you will silently miss old trades.
        """
        args = ["--since", since]
        if broker:
            args += ["--broker", broker]
        return self._list("history", *args)

    # --- writes: ONLY the runner calls these, never the model --------------

    def buy(self, **kw: Any) -> dict[str, Any]:
        return self._order("buy", **kw)

    def sell(self, **kw: Any) -> dict[str, Any]:
        return self._order("sell", **kw)

    def _order(
        self,
        side: str,
        *,
        lots: float,
        symbol: str,
        sl: float | None = None,
        tp: float | None = None,
        as_name: str = "manual",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        # Positionals (lots, symbol) MUST come before options.
        args = [str(lots), symbol]
        if sl is not None:
            args += ["--sl", f"at:{sl}"]
        if tp is not None:
            args += ["--tp", f"at:{tp}"]
        args += ["--as", as_name]
        if dry_run:
            args += ["--dry-run"]
        return self._obj(side, *args)

    def close(self, symbol: str, ticket: int) -> list[dict[str, Any]]:
        """Close by ticket, always. Never --all: `positions` sees other strategies'
        positions too, and a blanket close would flatten them."""
        return self._list("close", symbol, "--ticket", str(ticket))
