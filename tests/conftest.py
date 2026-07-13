from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from lab import config as cfgmod

ROOT = Path(__file__).resolve().parents[1]


def cfg_with(cfg: cfgmod.Config, **kw):
    return dataclasses.replace(cfg, **kw)


@pytest.fixture
def cfg(monkeypatch, tmp_path) -> cfgmod.Config:
    """The real lab.yaml, so the tests exercise the config we actually ship."""
    monkeypatch.setenv("LAB_DATABASE_URL", "postgresql://lab:lab@localhost:5432/lab")
    monkeypatch.setenv("DELTALYTIX_DATABASE_URL", "postgresql://x:x@localhost:5433/x")
    c = cfgmod.load(ROOT / "lab.yaml")
    # Point the kill switch somewhere that definitely does not exist, so a stray
    # KILL file in the working tree cannot make the suite pass for the wrong reason.
    return dataclasses.replace(c, kill_switch=tmp_path / "no-kill")
