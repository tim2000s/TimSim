"""Sensitivity detection, tested on the behaviour that decides whether it helps or harms.

This is the one part of the OpenAPS SMB arm that is reimplemented rather than shipped, so it
carries more test than the rest of the adapter. The tests are written against what the ratio
is for rather than against the arithmetic: a detector that gets the sign right and the
exclusion wrong reads every meal as insulin resistance and raises the dose of someone who is
eating normally.
"""
import pytest

from timsim.controller.autosens import (AUTOSENS_MAX, AUTOSENS_MIN, Autosens,
                                        percentile)

SENS = 50.0            # mg/dL per unit
CR = 10.0              # grams per unit
BASAL = 1.2            # U/hr


def drive(steps, delta=0.0, activity=0.0, iob=0.0, bg=140.0, carbs_at=None,
          carbs_g=0.0, start=0.0):
    """Feed a run of five-minute steps and return the detector.

    `delta` may be a number or a callable of the step index, which is how the tests that
    need a rise confined to part of the run express it.
    """
    a = Autosens()
    for k in range(steps):
        d = delta(k) if callable(delta) else delta
        b = bg(k) if callable(bg) else bg
        a.observe(minute=start + 5.0 * k, bg=b, delta=d,
                  activity_u_per_min=activity, iob=iob, sens=SENS, carb_ratio=CR,
                  current_basal=BASAL, carbs_g=carbs_g if k == carbs_at else 0.0)
    return a


def ratio_of(a, steps, start=0.0):
    return a.ratio(start + 5.0 * (steps - 1), SENS, BASAL)


# ------------------------------------------------------------------------ direction
def test_a_run_that_behaves_reads_as_normal():
    n = 400
    assert ratio_of(drive(n), n) == pytest.approx(1.0)


def test_glucose_falling_for_no_reason_reads_as_sensitivity():
    n = 400
    assert ratio_of(drive(n, delta=-1.0), n) < 1.0


def test_glucose_rising_for_no_reason_reads_as_resistance():
    n = 400
    assert ratio_of(drive(n, delta=+1.0), n) > 1.0


def test_a_fall_the_insulin_explains_is_not_sensitivity():
    """The deviation is what glucose did minus what the insulin on board predicts. A fall
    that the insulin accounts for is the system working, and reading it as sensitivity
    would cut the dose of someone who is perfectly in range."""
    n = 400
    activity = 0.01                       # U/min
    predicted = -activity * SENS * 5.0    # mg/dL over the step
    a = drive(n, delta=predicted, activity=activity)
    assert ratio_of(a, n) == pytest.approx(1.0)


def test_the_ratio_is_clamped_at_both_ends():
    n = 400
    assert ratio_of(drive(n, delta=-40.0), n) == pytest.approx(AUTOSENS_MIN)
    assert ratio_of(drive(n, delta=+40.0), n) == pytest.approx(AUTOSENS_MAX)


# ------------------------------------------------------------------------ exclusion
def test_a_rise_that_is_food_is_not_resistance():
    """The failure this guards is the one that matters. Without the exclusion every meal
    reads as insulin resistance, the ratio climbs to its clamp and stays there, and the
    algorithm raises the dose of someone who is simply eating."""
    n = 400
    # 60 g at step 20, and glucose rises only while it is absorbing
    rise = lambda k: 8.0 if 20 <= k < 70 else 0.0
    a = drive(n, delta=rise, carbs_at=20, carbs_g=60.0)
    assert ratio_of(a, n) == pytest.approx(1.0), "a meal was read as insulin resistance"


def test_the_first_45_minutes_after_a_carbohydrate_entry_are_excluded():
    """oref excludes them outright, because absorption has not started and the deviation
    that follows says nothing about sensitivity."""
    a = Autosens()
    a.observe(0.0, 140.0, 0.0, 0.0, 0.0, SENS, CR, BASAL, carbs_g=40.0)
    kinds = []
    for k in range(1, 12):
        a.observe(5.0 * k, 140.0, 0.0, 0.0, 0.0, SENS, CR, BASAL)
        kinds.append(a.kind)
    assert kinds[0] != "non-meal"
    assert "non-meal" not in kinds[:8], "a deviation counted inside the exclusion window"


def test_a_rise_while_insulin_is_high_is_treated_as_an_unannounced_meal():
    """oref reads it as food nobody entered rather than as resistance."""
    n = 200
    a = drive(n, delta=+5.0, iob=10.0 * BASAL)
    assert a.kind == "uam"
    assert ratio_of(a, n) == pytest.approx(1.0)


def test_a_rise_off_a_low_is_discarded_rather_than_read_as_resistance():
    """AndroidAPS drops positive deviations below 80 mg/dL. A rise there is rescue
    carbohydrate or counterregulation, and raising the dose in response would be the worst
    available answer."""
    n = 400
    low = drive(n, delta=+3.0, bg=70.0)
    ordinary = drive(n, delta=+3.0, bg=140.0)
    assert ratio_of(low, n) == pytest.approx(1.0)
    assert ratio_of(ordinary, n) > 1.0


# -------------------------------------------------------------------------- windows
def test_a_recent_change_is_caught_by_the_shorter_window():
    """Twenty-four hours of normal followed by eight of sensitivity. The long window is
    still near normal and the short one is not, and AndroidAPS takes the lower of the two
    because detecting sensitivity late is the more dangerous error."""
    n = 24 * 12 + 8 * 12
    recent = lambda k: -2.0 if k >= 24 * 12 else 0.0
    a = drive(n, delta=recent)
    assert ratio_of(a, n) < 0.95


def test_the_shorter_window_is_not_used_when_it_reads_higher():
    """The rule is asymmetric: the eight-hour figure is used only when it is the lower."""
    n = 24 * 12 + 8 * 12
    recent = lambda k: +2.0 if k >= 24 * 12 else 0.0
    a = drive(n, delta=recent)
    eight = [d for m, d in a.deviations if m > 5.0 * (n - 1) - 8 * 60][-96:]
    assert sum(eight) > 0, "the short window did see the rise"
    assert ratio_of(a, n) == pytest.approx(1.0), "the higher short-window ratio was used"


def test_too_little_data_is_damped_towards_no_change():
    """An hour of falling glucose should not swing the ratio to its clamp."""
    short = drive(12, delta=-4.0)
    long = drive(400, delta=-4.0)
    assert ratio_of(short, 12) > ratio_of(long, 400)


def test_deviations_older_than_the_longest_window_are_dropped():
    a = drive(24 * 12 * 3, delta=-1.0)
    assert len(a.deviations) < 24 * 12 * 3


# ----------------------------------------------------------------------- percentile
def test_the_median_interpolates_as_orefs_own_percentile_does():
    """A rounding difference here is the difference between reading sensitivity and reading
    resistance, because the test is against zero."""
    assert percentile([1.0, 2.0, 3.0], 0.50) == pytest.approx(2.0)
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.50) == pytest.approx(2.5)
    assert percentile([], 0.50) == 0.0
    assert percentile([7.0], 0.50) == pytest.approx(7.0)


# ------------------------------------------------------------------- in the adapter
def test_the_adapter_runs_detection_by_default_and_can_pin_it():
    from timsim.controller import oref as O
    if not O.available():
        pytest.skip("oref not gathered; run bridge/oref/build.sh")
    from timsim.population import names
    n = names("adult")[0]
    running = O.OrefController(n)
    pinned = O.OrefController(n, autosens=1.0)
    try:
        assert running.autosens is not None and running.pinned_autosens is None
        assert pinned.autosens is None and pinned.pinned_autosens == 1.0
    finally:
        running.close()
        pinned.close()
