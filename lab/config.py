"""Load and validate lab.yaml.

Everything the lab does is reachable from that one file. If a behaviour is not
expressible there, that is a bug in the design, not a reason to hardcode it.

Validation happens at load, loudly. A config that would blow the MT5 comment
limit, or a gate that has been quietly disabled, should fail on startup rather
than at the moment an order is placed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# MT5 rejects an order whose comment exceeds 31 characters. It does not truncate
# — it rejects. qkt builds the comment as "bot-<as>-<13-digit-epoch-ms>", so the
# --as name has a hard budget. Blowing it means every order fails at the venue.
MT5_COMMENT_MAX = 31
_COMMENT_OVERHEAD = len("bot-") + len("-") + 13


class ConfigError(Exception):
    """lab.yaml is wrong in a way that would break at trade time."""


def _expand(value: Any) -> Any:
    """Expand ${VAR} and ${VAR:-default} from the environment, recursively."""
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if not isinstance(value, str):
        return value

    def sub(m: re.Match[str]) -> str:
        name, default = m.group(1), m.group(2)
        got = os.environ.get(name)
        if got is None:
            if default is None:
                raise ConfigError(f"${{{name}}} is referenced in lab.yaml but not set")
            return default
        return got

    return re.sub(r"\$\{(\w+)(?::-([^}]*))?\}", sub, value)


@dataclass(frozen=True)
class Instrument:
    symbol: str  # ICM:XAUUSD — broker prefix selects the gateway
    contract_value: float  # 1 lot = this many units. Gold: 100 oz.
    playbook: Path
    schedule: str
    timeframes: list[str]
    bars: int
    max_lots: float

    @property
    def bare(self) -> str:
        """XAUUSD — the symbol without the broker prefix."""
        return self.symbol.split(":", 1)[-1]


@dataclass(frozen=True)
class Gates:
    require_sl: bool
    min_rr: float
    max_open_positions: int
    max_exposure_lots: float
    max_daily_loss_pct: float
    news_blackout_minutes: int


@dataclass(frozen=True)
class Risk:
    risk_per_trade_pct: float
    portfolio_heat_pct: float
    correlation_threshold: float


@dataclass(frozen=True)
class Sizing:
    stage: str  # flat | fitted
    conviction_max_mult: float
    kelly_fraction: float
    fit: dict[str, Any] | None


@dataclass(frozen=True)
class Beliefs:
    path: Path
    activate_min_trades: int
    multiple_testing: str
    alpha: float
    score_on: str
    withhold_candidates: bool


@dataclass(frozen=True)
class Calendar:
    cache: Path
    max_age_hours: int
    min_sources: int
    fail_closed: bool


@dataclass(frozen=True)
class Config:
    root: Path
    mode: str  # demo | live
    state_dir: Path
    kill_switch: Path

    qkt_bin: str
    qkt_config: str
    qkt_timeout_s: int
    qkt_retries: int

    instruments: list[Instrument]
    as_prefix: str
    agent_provider: str
    agent_bin: str
    model: str

    risk: Risk
    sizing: Sizing
    gates: Gates
    beliefs: Beliefs
    calendar: Calendar

    memory_root: Path
    store_dsn: str
    unjoined_alarm_days: int

    raw: dict[str, Any] = field(repr=False, default_factory=dict)

    def instrument(self, symbol: str) -> Instrument:
        for i in self.instruments:
            if i.symbol == symbol:
                return i
        known = ", ".join(i.symbol for i in self.instruments)
        raise ConfigError(f"{symbol} is not in lab.yaml (have: {known})")

    def as_name(self, symbol: str) -> str:
        """The --as name qkt tags the order with, e.g. lab-xau.

        Kept short on purpose: it lands in the MT5 order comment, which has a
        hard 31-char cap that rejects rather than truncates.
        """
        return f"{self.as_prefix}-{symbol.split(':')[-1][:3].lower()}"

    @property
    def kill_switch_engaged(self) -> bool:
        return self.kill_switch.exists()


def load(path: str | Path = "lab.yaml") -> Config:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"no config at {path}")

    raw = _expand(yaml.safe_load(path.read_text()) or {})
    root = path.parent.resolve()

    def rel(p: str) -> Path:
        return (root / p).resolve()

    lab = raw.get("lab", {})
    q = raw.get("qkt", {})
    agent = raw.get("agent", {})
    risk = raw.get("risk", {})
    sizing = raw.get("sizing", {})
    gates = raw.get("gates", {})
    mem = raw.get("memory", {})
    bel = mem.get("beliefs", {})
    cal = raw.get("calendar", {})
    store = raw.get("store", {})

    instruments = [
        Instrument(
            symbol=i["symbol"],
            contract_value=float(i["contract_value"]),
            playbook=rel(i["playbook"]),
            schedule=i["schedule"],
            timeframes=list(i.get("timeframes", ["1h"])),
            bars=int(i.get("bars", 200)),
            max_lots=float(i["max_lots"]),
        )
        for i in raw.get("instruments", [])
    ]
    if not instruments:
        raise ConfigError("lab.yaml declares no instruments")

    cfg = Config(
        root=root,
        mode=lab.get("mode", "demo"),
        state_dir=rel(lab.get("state_dir", "./state")),
        kill_switch=rel(lab.get("kill_switch", "./KILL")),
        qkt_bin=q.get("bin", "qkt"),
        qkt_config=q.get("config", "./qkt.config.yaml"),
        qkt_timeout_s=int(q.get("timeout_s", 30)),
        qkt_retries=int(q.get("retries", 2)),
        instruments=instruments,
        as_prefix=agent.get("as_prefix", "lab"),
        agent_provider=agent.get("provider", "codex"),
        agent_bin=agent.get("bin", "codex"),
        model=agent.get("model", "gpt-5.6-sol"),
        risk=Risk(
            risk_per_trade_pct=float(risk["risk_per_trade_pct"]),
            portfolio_heat_pct=float(risk.get("portfolio_heat_pct", 2.0)),
            correlation_threshold=float(risk.get("correlation_threshold", 0.6)),
        ),
        sizing=Sizing(
            stage=sizing.get("stage", "flat"),
            conviction_max_mult=float(sizing.get("conviction_max_mult", 2.0)),
            kelly_fraction=float(sizing.get("kelly_fraction", 0.5)),
            fit=sizing.get("fit"),
        ),
        gates=Gates(
            require_sl=bool(gates.get("require_sl", True)),
            min_rr=float(gates.get("min_rr", 1.5)),
            max_open_positions=int(gates.get("max_open_positions", 3)),
            max_exposure_lots=float(gates.get("max_exposure_lots", 0.5)),
            max_daily_loss_pct=float(gates.get("max_daily_loss_pct", 2.0)),
            news_blackout_minutes=int(gates.get("news_blackout_minutes", 30)),
        ),
        beliefs=Beliefs(
            path=rel(bel.get("path", "memory/beliefs/")),
            activate_min_trades=int(bel.get("activate_min_trades", 30)),
            multiple_testing=bel.get("multiple_testing", "benjamini-hochberg"),
            alpha=float(bel.get("alpha", 0.05)),
            score_on=bel.get("score_on", "realized_net_pnl"),
            withhold_candidates=bool(bel.get("withhold_candidates", True)),
        ),
        calendar=Calendar(
            cache=rel(cal.get("cache", "memory/calendar/upcoming.yaml")),
            max_age_hours=int(cal.get("max_age_hours", 30)),
            min_sources=int(cal.get("min_sources", 2)),
            fail_closed=bool(cal.get("fail_closed", True)),
        ),
        memory_root=rel(mem.get("root", "memory/")),
        store_dsn=store.get("dsn", ""),
        unjoined_alarm_days=int(store.get("unjoined_alarm_days", 3)),
        raw=raw,
    )
    _validate(cfg)
    return cfg


def _validate(cfg: Config) -> None:
    """Fail at startup, not at the moment an order is placed."""
    if cfg.mode not in ("demo", "live"):
        raise ConfigError(f"lab.mode must be demo|live, got {cfg.mode!r}")
    if cfg.agent_provider not in ("codex", "claude"):
        raise ConfigError(f"agent.provider must be codex|claude, got {cfg.agent_provider!r}")
    if not cfg.agent_bin.strip():
        raise ConfigError("agent.bin must not be empty")
    if not cfg.model.strip():
        raise ConfigError("agent.model must not be empty")

    # `live` is gated on the phase-6 A/B. Refusing here is the gate.
    if cfg.mode == "live" and not cfg.raw.get("experiment", {}).get("ab_passed"):
        raise ConfigError(
            "lab.mode=live requires experiment.ab_passed — the A/B has not run and "
            "passed. See docs/specs/phase-6-proof.md. This is a refusal, not a warning."
        )

    for inst in cfg.instruments:
        as_name = cfg.as_name(inst.symbol)
        budget = _COMMENT_OVERHEAD + len(as_name)
        if budget > MT5_COMMENT_MAX:
            raise ConfigError(
                f"--as {as_name!r} makes a {budget}-char MT5 order comment, over the "
                f"{MT5_COMMENT_MAX} limit. MT5 REJECTS long comments (it does not "
                f"truncate), so every order would fail. Shorten agent.as_prefix."
            )
        if ":" not in inst.symbol:
            raise ConfigError(
                f"{inst.symbol!r} needs a broker prefix (e.g. ICM:XAUUSD) — qkt routes "
                "to a gateway by that prefix"
            )
        if inst.contract_value <= 0:
            raise ConfigError(f"{inst.symbol}: contract_value must be > 0")
        if inst.max_lots <= 0:
            raise ConfigError(f"{inst.symbol}: max_lots must be > 0")

    if not cfg.gates.require_sl:
        raise ConfigError("gates.require_sl=false. Every trade must carry a stop. Not negotiable.")
    if not cfg.calendar.fail_closed:
        raise ConfigError(
            "calendar.fail_closed=false. A stale calendar would let the loop trade "
            "blind through CPI. The asymmetry (missed trade vs unhedged print) makes "
            "this indefensible."
        )
    if cfg.sizing.stage not in ("flat", "fitted"):
        raise ConfigError(f"sizing.stage must be flat|fitted, got {cfg.sizing.stage!r}")
    if cfg.sizing.stage == "fitted" and not cfg.sizing.fit:
        raise ConfigError(
            "sizing.stage=fitted but sizing.fit is empty. Conviction may only scale "
            "size once a calibration report shows it predicts realized R. Run the "
            "calibration (bin/distill --calibrate) first."
        )
    if cfg.sizing.kelly_fraction > 1.0:
        raise ConfigError("sizing.kelly_fraction > 1.0 is over-betting by construction")
