"""The signatures decide every verdict this package produces, so they are pinned."""
import numpy as np
import pytest

from timsim.analysis import signatures as S


def _flat(level=120.0, days=7):
    n = int(days * 24 * 12)
    t = np.arange(n) * 300.0
    return dict(t=t, bg=np.full(n, level), hour=(t / 3600.0) % 24)


def _sine(amp=40.0, period_h=24.0, days=7, level=140.0):
    n = int(days * 24 * 12)
    t = np.arange(n) * 300.0
    bg = level + amp * np.sin(2 * np.pi * t / (period_h * 3600.0))
    return dict(t=t, bg=bg, hour=(t / 3600.0) % 24)


def test_a_flat_trace_has_no_variability_and_no_events():
    d = _flat()
    cv = next(fn for k, _, fn in S.SIGS if k == "cv")(d)
    assert cv == pytest.approx(0.0, abs=1e-9)
    compress = next(fn for k, _, fn in S.SIGS if k == "compress")(d)
    assert compress == 0.0


def test_diurnal_amplitude_recovers_a_known_daily_swing():
    amp = next(fn for k, _, fn in S.SIGS if k == "diurnal")(_sine(amp=40.0))
    assert 75.0 < amp < 82.0          # peak-to-trough is twice the amplitude


def test_autocorrelation_is_high_for_a_smooth_curve():
    d = _sine(amp=40.0, period_h=24.0)
    acf30 = next(fn for k, _, fn in S.SIGS if k == "acf30")(d)
    assert acf30 > 0.95


def test_every_signature_has_a_real_range_and_a_unit():
    # `drift` and `insulin_cv` are not computed from the glucose dict the others take, so
    # they are named here rather than discovered from SIGS. Both come off the run: `drift`
    # off the driving controller, which is why it cannot see the person, and `insulin_cv`
    # off the delivery record, which is why it can.
    keys = {k for k, _, _ in S.SIGS} | {"drift", "insulin_cv"}
    assert keys == set(S.REAL_RANGE)
    assert keys == set(S.UNITS)


def test_in_real_range_respects_the_stated_tolerance():
    lo, hi = S.REAL_RANGE["cv"]
    assert S.in_real_range("cv", (lo + hi) / 2)
    assert not S.in_real_range("cv", lo - 0.5 * (hi - lo))
    assert S.in_real_range("cv", lo - 0.05 * (hi - lo))     # inside the 10% pad


def test_bootstrap_interval_brackets_the_point_estimate():
    v, lo, hi = S.boot_ci([1.0, 2.0, 3.0, 4.0, 5.0], seed=0)
    assert lo <= v <= hi


def test_report_names_every_signature():
    stats = {k: (float(np.mean(S.REAL_RANGE[k])), 0.0, 0.0) for k in S.REAL_RANGE}
    text = S.report(stats)
    for k in S.REAL_RANGE:
        assert k in text
    assert "OUT" not in text


# ------------------------------------------------- week-to-week insulin variation
# This signature replaces `drift` as the one that is meant to detect a person whose insulin
# sensitivity moves. `drift` could not: switching the person's weekly variation off entirely
# left it reading 5.77 %CV against 8.69 with it on, because it reads the built-in
# controller's learned correction factor rather than anything about the person. The tests
# below are the ones that failure would have been caught by.
class TestInsulinWeeklyCV:

    def _steady(self, days=28, per_step=0.2):
        return np.full(288 * days, per_step)

    def test_a_person_whose_requirement_never_moves_reads_zero(self):
        assert S.insulin_weekly_cv(self._steady()) == pytest.approx(0.0, abs=1e-9)

    def test_a_step_change_in_requirement_shows_up(self):
        v = self._steady()
        v[288 * 14:] *= 1.3
        assert S.insulin_weekly_cv(v) > 8.0

    def test_it_scales_with_the_size_of_the_change(self):
        small, large = self._steady(), self._steady()
        small[288 * 14:] *= 1.1
        large[288 * 14:] *= 1.4
        assert S.insulin_weekly_cv(large) > 2 * S.insulin_weekly_cv(small)

    def test_day_to_day_noise_is_not_read_as_weekly_variation(self):
        """The statistic is about the week the person is having, not about one bad day."""
        rng = np.random.default_rng(0)
        v = self._steady() * rng.uniform(0.7, 1.3, 28)[
            np.repeat(np.arange(28), 288)]
        assert S.insulin_weekly_cv(v) < 8.0

    def test_a_run_too_short_to_have_weeks_returns_not_a_number(self):
        assert not np.isfinite(S.insulin_weekly_cv(self._steady(days=6)))
        assert not np.isfinite(S.insulin_weekly_cv([]))

    def test_the_real_range_is_the_one_measured(self):
        lo, hi = S.REAL_RANGE["insulin_cv"]
        assert (lo, hi) == (4.5, 11.1), "115 real users, matched 28-day windows"
        assert S.in_real_range("insulin_cv", 7.3), "the real median has to pass"

    def test_it_travels_with_a_result_rather_than_being_asserted(self):
        """`drift` was read off the driving controller, so it was undefined for any
        algorithm that was not the built-in one. This comes off the delivery record, which
        every run has whatever drove it."""
        from timsim import simulate
        from timsim.population import names
        r = simulate(names("adult")[0], days=21, seed=0, controller="basal-bolus")
        out = S.evaluate([r])
        assert "insulin_cv" in out
        assert np.isfinite(out["insulin_cv"][0])
