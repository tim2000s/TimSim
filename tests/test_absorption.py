"""Meal-to-meal absorption variation and the systematic slowing beside it.

simglucose's gastric emptying is deterministic given the meal, so the same 60 g absorbs
identically every time. Two things were measured against the OpenAPS Data Commons export and
each has its own parameter here: the spread between one meal and the next, and the level.

The spread. Across six users with at least fifteen isolated meals of 30 to 80 g eaten from a
starting glucose of 80 to 160 mg/dL, the within-person coefficient of variation of the time to
peak is 0.51 and of the rise per gram 0.68. TimSim without this reads 0.36 and 0.46.

The level. Those same real meals peak at 135 minutes and TimSim's at about 90, which is a bias
rather than a spread and is what `scale` exists for.
"""
import numpy as np
import pytest

from timsim.patient import varying as V


def _absorption(p):
    return float(p._params["kabs"]), float(p._params["kmax"]), float(p._params["kmin"])


def _feed(p, cho):
    from simglucose.patient.t1dpatient import Action
    basal = p._params.u2ss * p._params.BW / 6000.0
    p.step(Action(CHO=cho, insulin=basal))


def test_a_patient_without_this_is_untouched():
    """Opt-in, so a patient that never had `set_meal_variability` called behaves exactly as
    the stock one."""
    p = V.from_population("adult#001")
    before = _absorption(p)
    _feed(p, 60.0)
    assert _absorption(p) == before


def test_zero_spread_and_unit_scale_change_nothing():
    p = V.from_population("adult#001")
    before = _absorption(p)
    p.set_meal_variability(np.random.default_rng(0), cv=0.0, scale=1.0)
    _feed(p, 60.0)
    assert _absorption(p) == pytest.approx(before)


def test_each_meal_draws_its_own_factor():
    """The failure this guards is drawing once for the run, which would make a subject
    consistently fast or slow and add between-person spread instead of within-person."""
    p = V.from_population("adult#001")
    p.set_meal_variability(np.random.default_rng(1), cv=0.6)
    factors = []
    for meal in range(6):
        _feed(p, 60.0)                  # meal starts
        factors.append(p._params["kabs"] / p._kabs0)
        for _ in range(3):
            _feed(p, 0.0)               # and ends
    assert len(set(np.round(factors, 6))) == len(factors), "the same factor every meal"


def test_the_factor_holds_for_the_length_of_a_meal():
    """Redrawing every minute would average out inside one meal and produce no spread."""
    p = V.from_population("adult#001")
    p.set_meal_variability(np.random.default_rng(2), cv=0.6)
    _feed(p, 20.0)
    first = p._params["kabs"]
    for _ in range(5):
        _feed(p, 20.0)
        assert p._params["kabs"] == pytest.approx(first)


def test_the_spread_has_the_coefficient_of_variation_it_is_given():
    p = V.from_population("adult#001")
    p.set_meal_variability(np.random.default_rng(3), cv=0.5)
    seen = []
    for _ in range(400):
        _feed(p, 60.0)
        seen.append(p._params["kabs"] / p._kabs0)
        _feed(p, 0.0)
    seen = np.array(seen)
    assert seen.std() / seen.mean() == pytest.approx(0.5, rel=0.2)


def test_the_scale_slows_absorption_without_needing_any_spread():
    """The two are separate: real meals peak 45 minutes later than the model's, which is a
    level and not a variance."""
    p = V.from_population("adult#001")
    p.set_meal_variability(np.random.default_rng(4), cv=0.0, scale=0.5)
    _feed(p, 60.0)
    assert p._params["kabs"] == pytest.approx(p._kabs0 * 0.5)
    assert p._params["kmax"] == pytest.approx(p._kmax0 * 0.5)
    assert p._params["kmin"] == pytest.approx(p._kmin0 * 0.5)


def test_the_factor_is_bounded_so_a_tail_draw_cannot_stop_absorption():
    p = V.from_population("adult#001")
    p.set_meal_variability(np.random.default_rng(5), cv=1.5)
    lo, hi = V.MEAL_ABSORPTION_BOUNDS
    # The clamp is exact, and recovering the factor by dividing the clamped rate by the
    # unclamped one is not: for some subjects that division lands one unit in the last place
    # above the bound. A tolerance of 1e-9 is many orders below any draw this test could catch,
    # and without it the test fails on a subject whose kabs happens to divide unluckily rather
    # than on the behaviour it is checking.
    tol = 1e-9
    for _ in range(300):
        _feed(p, 60.0)
        assert lo - tol <= p._params["kabs"] / p._kabs0 <= hi + tol
        _feed(p, 0.0)


def test_all_three_rates_move_together():
    """Gastric emptying and intestinal absorption are one mechanism here. Moving only one
    would change the shape of a meal rather than its timing."""
    p = V.from_population("adult#002")
    p.set_meal_variability(np.random.default_rng(6), cv=0.7)
    _feed(p, 60.0)
    f = p._params["kabs"] / p._kabs0
    assert p._params["kmax"] / p._kmax0 == pytest.approx(f)
    assert p._params["kmin"] / p._kmin0 == pytest.approx(f)


def test_it_reaches_a_run_through_the_physiology_layer():
    from timsim import simulate
    from timsim.population import names
    n = names("adult")[0]
    a = simulate(n, days=5, seed=0, controller="trend", meal_absorption_cv=0.0)
    b = simulate(n, days=5, seed=0, controller="trend", meal_absorption_cv=0.9)
    assert not np.allclose(a.cgm, b.cgm), "the setting did not reach the run"
    # and it is part of physiology rather than a layer of its own
    c = simulate(n, days=5, seed=0, controller="trend", layers=("behaviour",),
                 meal_absorption_cv=0.9)
    d = simulate(n, days=5, seed=0, controller="trend", layers=("behaviour",),
                 meal_absorption_cv=0.0)
    assert np.allclose(c.cgm, d.cgm), "it acted with the physiology layer switched off"
