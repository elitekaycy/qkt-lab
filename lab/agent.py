"""The bridge to a headless coding agent.

The model is a proposal generator. It cannot place an order, it cannot size a
position, and it cannot write its own memory. Everything it returns is validated
against a schema before any other code touches it.

Codex is the default provider and runs through `codex exec`. Claude remains
available as an explicit compatibility option for existing deployments.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
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


def _codex_command(
    *,
    agent_bin: str,
    system_text: str,
    model: str,
    images: list[Path] | None,
    research: bool,
    external_sandbox: bool,
) -> list[str]:
    """Build a non-interactive Codex command with a role-specific tool surface."""
    cmd = [
        *shlex.split(agent_bin),
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--disable",
        "apps",
        "--disable",
        "multi_agent",
        "-c",
        f"developer_instructions={json.dumps(system_text)}",
    ]
    if research and external_sandbox:
        # Docker is the sandbox: /lab is read-only and only memory/, state/, and
        # .git are over-mounted writable. Avoid adding SYS_ADMIN merely to make
        # nested bubblewrap user namespaces work.
        cmd.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        cmd += [
            "--sandbox",
            "workspace-write" if research else "read-only",
        ]
    if research:
        # The config form works in pinned Codex 0.144.5; newer releases also
        # expose this as `--search`, but pinning to the common form avoids drift.
        cmd += ["-c", 'web_search="live"']
        if external_sandbox:
            # With the shell removed, the research model has web search and file
            # editing but cannot inspect auth.json, call qkt, or reach the DB.
            cmd += ["--disable", "shell_tool"]
    else:
        # Trader and distiller only transform the packet into JSON. Removing the
        # shell makes the architecture's "cannot place an order" boundary real.
        cmd += [
            "--disable",
            "shell_tool",
            "-c",
            'web_search="disabled"',
        ]
    if model:
        cmd += ["--model", model]
    for image in images or []:
        cmd += ["--image", str(image.resolve())]
    # Read the prompt from stdin: packets can be large enough to exceed argv
    # limits, and stdin keeps their contents out of process listings.
    cmd.append("-")
    return cmd


def run_text(
    system_prompt: Path,
    user: str,
    *,
    provider: str,
    agent_bin: str,
    model: str,
    images: list[Path] | None = None,
    research: bool = False,
    external_sandbox: bool = False,
    allowed_tools: str = "",
    timeout_s: int = 300,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Run one headless model turn and return (final text, prompt sha)."""
    system_text = system_prompt.read_text()
    if provider == "codex":
        cmd = _codex_command(
            agent_bin=agent_bin,
            system_text=system_text,
            model=model,
            images=images,
            research=research,
            external_sandbox=external_sandbox,
        )
        stdin = user
        label = "codex exec"
    elif provider == "claude":
        cmd = [
            *shlex.split(agent_bin),
            "-p",
            user,
            "--append-system-prompt",
            system_text,
            "--model",
            model,
            "--output-format",
            "text",
            "--allowed-tools",
            allowed_tools,
        ]
        stdin = None
        label = "claude -p"
    else:
        raise AgentError(f"unsupported agent provider: {provider!r}")

    try:
        process = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=cwd,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise AgentError(f"{label} timed out after {timeout_s}s") from None

    if process.returncode != 0:
        detail = (process.stderr or process.stdout).strip()[:800]
        raise AgentError(f"{label} exit {process.returncode}: {detail}")

    return process.stdout.strip(), prompt_sha(system_text + user)


def run(
    system_prompt: Path,
    packet: dict[str, Any],
    *,
    provider: str,
    agent_bin: str,
    model: str,
    images: list[Path] | None = None,
    allowed_tools: str = "",
    timeout_s: int = 300,
    cwd: Path | None = None,
) -> tuple[dict[str, Any], str]:
    """Invoke the configured provider headlessly. Returns (parsed json, prompt sha).

    `allowed_tools` is empty by default: the trader gets NO tools. It reasons over
    the packet it was handed and returns JSON. The researcher is the only session
    that gets web access.
    """
    body = json.dumps(packet, indent=2, default=str)
    user = f"{body}\n\nRespond with the JSON object only. No prose, no code fence."
    if images and provider == "claude":
        # Claude reads image paths referenced in the prompt; Codex receives them
        # through its explicit --image flag.
        refs = "\n".join(f"Chart: {p}" for p in images)
        user = f"{refs}\n\n{user}"
    text, sha = run_text(
        system_prompt,
        user,
        provider=provider,
        agent_bin=agent_bin,
        model=model,
        images=images,
        allowed_tools=allowed_tools,
        timeout_s=timeout_s,
        cwd=cwd,
    )
    return _extract_json(text), sha
