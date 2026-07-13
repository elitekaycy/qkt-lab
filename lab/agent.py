"""The bridge to `claude -p`.

The model is a proposal generator. It cannot place an order, it cannot size a
position, and it cannot write its own memory. Everything it returns is validated
against a schema before any other code touches it.

No API key: `claude -p` rides the subscription via CLAUDE_CODE_OAUTH_TOKEN.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SIDES = {"BUY", "SELL"}
ACTIONS = {"TRADE", "NO_TRADE"}


class AgentError(RuntimeError):
    pass


@dataclass(frozen=True)
class Proposal:
    action: str  # TRADE | NO_TRADE
    side: str | None
    sl: float | None
    tp: float | None
    conviction: float
    setup: str | None
    factors: list[str]
    regime: dict[str, Any]
    thesis: str | None
    rationale_md: str | None
    invalidation: str | None
    map_nodes_used: list[str]
    beliefs_used: list[str]
    unexplained: str | None
    raw: dict[str, Any]

    @property
    def wants_trade(self) -> bool:
        return self.action == "TRADE"


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of whatever the model wrapped it in.

    We ask for bare JSON, but a model that occasionally adds a sentence of
    preamble should not take the loop down.
    """
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise AgentError(f"no JSON object in model output: {text[:300]}")
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AgentError(f"model output is not valid JSON: {e}: {text[:300]}") from None


def validate(raw: dict[str, Any]) -> Proposal:
    """Reject anything malformed before it can reach the gates.

    A model that returns `action: "MAYBE"` or a conviction of 7 must fail loudly
    here, not be coerced into something plausible downstream.
    """
    action = str(raw.get("action", "")).upper()
    if action not in ACTIONS:
        raise AgentError(f"action must be one of {sorted(ACTIONS)}, got {action!r}")

    side = raw.get("side")
    side = str(side).upper() if side else None

    def num(k: str) -> float | None:
        v = raw.get(k)
        return None if v is None else float(v)

    conviction = float(raw.get("conviction", 0.0))
    if not 0.0 <= conviction <= 1.0:
        raise AgentError(f"conviction must be in [0,1], got {conviction}")

    if action == "TRADE":
        if side not in SIDES:
            raise AgentError(f"TRADE needs side BUY|SELL, got {side!r}")
        if num("sl") is None:
            raise AgentError("TRADE without a stop-loss — the gate would refuse it anyway")

    return Proposal(
        action=action,
        side=side,
        sl=num("sl"),
        tp=num("tp"),
        conviction=conviction,
        setup=raw.get("setup"),
        factors=[str(f) for f in raw.get("factors", [])],
        regime=dict(raw.get("regime", {})),
        thesis=raw.get("thesis"),
        rationale_md=raw.get("rationale_md"),
        invalidation=raw.get("invalidation"),
        map_nodes_used=[str(x) for x in raw.get("map_nodes_used", [])],
        beliefs_used=[str(x) for x in raw.get("beliefs_used", [])],
        unexplained=raw.get("unexplained") or None,
        raw=raw,
    )


def prompt_sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def run(
    system_prompt: Path,
    packet: dict[str, Any],
    *,
    model: str,
    images: list[Path] | None = None,
    allowed_tools: str = "",
    timeout_s: int = 300,
    cwd: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Invoke `claude -p` headlessly. Returns (parsed json, prompt sha).

    `allowed_tools` is empty by default: the trader gets NO tools. It reasons over
    the packet it was handed and returns JSON. The researcher is the only session
    that gets web access.
    """
    sys_text = system_prompt.read_text()
    body = json.dumps(packet, indent=2, default=str)

    user = f"{body}\n\nRespond with the JSON object only. No prose, no code fence."
    if images:
        # claude -p reads image paths referenced in the prompt when they're local.
        refs = "\n".join(f"Chart: {p}" for p in images)
        user = f"{refs}\n\n{user}"

    cmd = [
        "claude", "-p", user,
        "--append-system-prompt", sys_text,
        "--model", model,
        "--output-format", "text",
    ]
    if allowed_tools:
        cmd += ["--allowed-tools", allowed_tools]
    else:
        cmd += ["--allowed-tools", ""]

    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, cwd=cwd
        )
    except subprocess.TimeoutExpired:
        raise AgentError(f"claude -p timed out after {timeout_s}s") from None

    if p.returncode != 0:
        raise AgentError(f"claude -p exit {p.returncode}: {p.stderr.strip()[:400]}")

    return _extract_json(p.stdout), prompt_sha(sys_text + body)
