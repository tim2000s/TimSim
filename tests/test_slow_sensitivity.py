"""The multi-day sensitivity component, and why the daily one could not do its job.

`INTERDAY_CV` draws each day independently at 0.22, taken from Dalla Man et al. (2014).
Independent draws average out: a week's mean of seven of them has a coefficient of variation
of 0.22/sqrt(7), about 0.08, and less again once a loop absorbs part of it. Real life produces
runs of days that move together, from illness, a training block or the menstrual cycle, and a
week inside one differs from a week outside it by much more than averaging predicts.

The quantity that shows it is the week-to-week variation in total daily insulin, measured at a
median of 7.3% across 115 real users against 1.8% for the stock model and 4.0% with every
layer on. These tests cover the mechanism; the calibration against that figure is a separate
measurement recorded at the constant.
"""
import numpy as np
import pytest

from timsim.patient import varying as V


def _slow(seed=0, days=84, **kw):
    p = V.from_population("adult#001")
    p.set_sensitivity(np.random.default_rng(seed), days, **kw)
    return np.asarray(p._slow, float)


def test_it_is_off_by_default_and_leaves_a_flat_series():
    assert np.allclose(_slow(), 1.0)


def test_zero_is_the_same_as_off():
    assert np.allclose(_slow(slow_cv=0.0), 1.0)


def test_it_has_the_spread_it_is_given():
    s = _slow(slow_cv=0.30, days=4000)
    assert s.std() / s.mean() == pytest.approx(0.30, rel=0.15)


def test_it_is_centred_on_one_so_it_does_not_shift_average_sensitivity():
    """A term that moved the mean would change every subject's insulin requirement rather
    than only how much it varies, and would be a different claim entirely."""
    s = _slow(slow_cv=0.35, days=6000)
    assert s.mean() == pytest.approx(1.0, rel=0.05)


def test_consecutive_days_move_together():
    """The whole point. Independent draws would show no autocorrelation at one day and
    would average out over a week."""
    s = _slow(slow_cv=0.30, days=4000)
    r1 = np.corrcoef(s[:-1], s[1:])[0, 1]
    assert r1 > 0.8, "the slow term is not correlated day to day"


def test_the_correlation_time_is_the_one_asked_for():
    s = np.log(_slow(slow_cv=0.30, slow_tau_days=6.0, days=8000))
    lag = 6
    r = np.corrcoef(s[:-lag], s[lag:])[0, 1]
    assert r == pytest.approx(np.exp(-1.0), abs=0.12)


def test_it_survives_a_week_of_averaging_where_independent_draws_do_not():
    """The comparison that motivates the mechanism, made directly.

    Independent draws at a coefficient of variation of 0.30 average down to 0.30/sqrt(7),
    about 0.11, over seven days. The correlated term keeps about 0.27 of its 0.30, so the
    ratio is near 2.4. Anything above two is the mechanism working; equal would mean it is
    not correlated at all.
    """
    rng = np.random.default_rng(5)
    days = 7000
    independent = rng.lognormal(0.0, np.sqrt(np.log(1 + 0.30 ** 2)), days)
    correlated = _slow(slow_cv=0.30, days=days)[:days]
    weekly = lambda v: np.array([v[i:i + 7].mean() for i in range(0, len(v) - 7, 7)])
    wi, wc = weekly(independent), weekly(correlated)
    assert (wi.std() / wi.mean()) == pytest.approx(0.30 / np.sqrt(7), rel=0.25)
    assert (wc.std() / wc.mean()) > 2.0 * (wi.std() / wi.mean())


def test_it_multiplies_the_daily_term_rather_than_replacing_it():
    """Dalla Man's day-to-day figure is untouched: what is added is the thing it does not
    describe. If the slow term replaced it, the one-day spread would collapse."""
    p = V.from_population("adult#001")
    p.set_sensitivity(np.random.default_rng(7), 400, slow_cv=0.30)
    daily = np.asarray(p._interday, float)
    assert daily.std() / daily.mean() == pytest.approx(V.INTERDAY_CV, rel=0.25)


def test_sensitivity_stays_inside_its_bounds():
    p = V.from_population("adult#001")
    p.set_sensitivity(np.random.default_rng(8), 500, slow_cv=0.6)
    lo, hi = V.SENSITIVITY_BOUNDS
    for day in range(0, 500, 7):
        p._odesolver.set_initial_value(p._odesolver.y, day * 1440.0 + 300.0)
        assert lo <= p.sensitivity() <= hi


def test_it_reaches_a_run_and_only_with_the_physiology_layer():
    from timsim import simulate
    from timsim.population import names
    n = names("adult")[0]
    a = simulate(n, days=6, seed=0, controller="trend", si_slow_cv=0.0)
    b = simulate(n, days=6, seed=0, controller="trend", si_slow_cv=0.4)
    assert not np.allclose(a.cgm, b.cgm)
    c = simulate(n, days=6, seed=0, controller="trend", layers=("behaviour",), si_slow_cv=0.4)
    d = simulate(n, days=6, seed=0, controller="trend", layers=("behaviour",), si_slow_cv=0.0)
    assert np.allclose(c.cgm, d.cgm)
