"""Belief scoring: the machinery that stops the loop being a false-discovery
machine. The load-bearing test is the last one — 40 pure-noise beliefs, zero
activations."""

from __future__ import annotations

import pytest

from lab.beliefs import PredicateError, Scored, benjamini_hochberg, compile_predicate, next_status

# --- predicate grammar ----------------------------------------------------------


def test_predicate_compiles_to_parameterized_sql():
    where, params = compile_predicate(
        [
            "symbol = ICM:XAUUSD",
            "side = BUY",
            "regime.session = london",
            "regime.atr14 between 3 and 5",
            "factors contains level:vwap-touch",
        ]
    )
    assert "symbol = %s" in where
    assert "regime->>%s = %s" in where
    assert "(regime->>%s)::numeric BETWEEN %s AND %s" in where
    assert "factors @> %s::jsonb" in where
    assert "ICM:XAUUSD" in params and "london" in params
    # No user text ever lands in the SQL string itself — injection-shaped clauses
    # must either parse as harmless parameters or fail.
    assert "';DROP" not in where


def test_prose_is_rejected_not_guessed_at():
    """A predicate that cannot be evaluated mechanically is prose, not a belief."""
    with pytest.raises(PredicateError):
        compile_predicate(["gold goes up when people are scared"])
    with pytest.raises(PredicateError):
        compile_predicate([])


def test_injection_shaped_clause_is_rejected():
    with pytest.raises(PredicateError):
        compile_predicate(["side = BUY; DROP TABLE decision"])


# --- benjamini-hochberg -----------------------------------------------------------


def test_bh_one_lucky_p_out_of_forty_does_not_survive():
    """The max-of-N statistic, dead: 39 noise p-values and one at 0.04. Raw
    p<0.05 would call it a discovery; the family-wide correction does not."""
    ps = {f"noise-{i}": 0.3 + i * 0.015 for i in range(39)}
    ps["lucky"] = 0.04
    assert benjamini_hochberg(ps, alpha=0.05) == set()


def test_bh_a_genuinely_strong_signal_survives_among_noise():
    ps = {f"noise-{i}": 0.4 + i * 0.01 for i in range(39)}
    ps["real"] = 0.0005
    assert "real" in benjamini_hochberg(ps, alpha=0.05)


def test_bh_step_up_includes_everything_below_the_threshold_rank():
    ps = {"a": 0.001, "b": 0.002, "c": 0.9}
    got = benjamini_hochberg(ps, alpha=0.05)
    assert got == {"a", "b"}


# --- status transitions -----------------------------------------------------------


def scored(n=40, mean_r=0.3, t=2.5, p=0.01):
    return Scored(
        "x",
        n,
        wins=n // 2,
        losses=n - n // 2,
        mean_r=mean_r,
        t_stat=t,
        p_value=p,
        supporting=[],
        refuting=[],
    )


def test_candidate_below_min_n_stays_candidate_whatever_the_stats(cfg):
    """n >= 30 is a floor for sanity, not a knob. A p of 0.001 on 12 trades is
    still 12 trades."""
    s = scored(n=12, mean_r=1.5, t=4.0, p=0.001)
    assert next_status("CANDIDATE", s, cfg, survives_family=True) == "CANDIDATE"


def test_candidate_without_family_survival_stays_candidate(cfg):
    s = scored(n=45, mean_r=0.4, t=2.2, p=0.02)
    assert next_status("CANDIDATE", s, cfg, survives_family=False) == "CANDIDATE"


def test_candidate_with_n_and_family_survival_activates(cfg):
    s = scored(n=34, mean_r=0.31, t=2.4, p=0.008)
    assert next_status("CANDIDATE", s, cfg, survives_family=True) == "ACTIVE"


def test_active_decays_to_weakening_then_invalidated_never_deleted(cfg):
    cold = scored(n=61, mean_r=-0.02, t=0.3, p=0.38)
    assert next_status("ACTIVE", cold, cfg, survives_family=False) == "WEAKENING"
    assert next_status("WEAKENING", cold, cfg, survives_family=False) == "INVALIDATED"
    # Terminal — a dead idea stays dead (and stays on disk, in git).
    assert next_status("INVALIDATED", scored(), cfg, survives_family=True) == "INVALIDATED"


def test_weakening_can_recover(cfg):
    hot = scored(n=50, mean_r=0.35, t=2.1, p=0.02)
    assert next_status("WEAKENING", hot, cfg, survives_family=False) == "ACTIVE"


def test_negative_mean_r_never_activates(cfg):
    """A 'significant' negative edge is a reason to avoid the setup, not trade it."""
    s = scored(n=100, mean_r=-0.4, t=-3.0, p=0.999)
    assert next_status("CANDIDATE", s, cfg, survives_family=True) == "CANDIDATE"
