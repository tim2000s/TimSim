"""Comparing arms on a common population, and saying why runs ended.

Both rules exist because breaking them produced a wrong answer that looked right: arms
summarised over their own survivors compare different people, and a completion count averages
a hypoglycaemia failure with a hyperglycaemia one.
"""
import numpy as np
import pytest

from timsim.analysis import cohort as C


class _Run:
    def __init__(self, bg, completed=False, meta=None, insulin=None, rescues=()):
        self.bg = np.asarray(bg, float)
        self.cgm = self.bg
        self.completed = completed
        self.sample_time = 5.0
        self.meta = meta or {}
        self.insulin_series = np.asarray(insulin if insulin is not None else [], float)
        self.rescue_log = rescues


def test_paired_subjects_takes_only_those_completing_every_arm():
    rows = [{"name": "a", "arm": "x", "completed": True},
            {"name": "b", "arm": "x", "completed": True},
            {"name": "a", "arm": "y", "completed": True},
            {"name": "b", "arm": "y", "completed": False}]
    common, arms = C.paired_subjects(rows, key=lambda r: r["arm"])
    assert common == ["a"] and arms == ["x", "y"]


def test_no_common_completer_is_an_error_rather_than_a_partial_comparison():
    """Producing a comparison from partial overlap would invent a population."""
    rows = [{"name": "a", "arm": "x", "completed": True},
            {"name": "b", "arm": "y", "completed": True}]
    with pytest.raises(ValueError, match="no subject completed every arm"):
        C.paired_subjects(rows, key=lambda r: r["arm"])


def test_a_completed_run_has_no_termination():
    assert C.classify_termination(_Run([120, 130], completed=True)) is None


def test_a_run_leaving_from_below_is_read_as_hypoglycaemic():
    t = C.classify_termination(_Run([120, 80, 40, 12]))
    assert t["direction"] == "hypoglycaemic"
    assert t["final_bg"] == 12.0 and t["lowest_bg"] == 12.0


def test_a_run_leaving_from_above_is_read_as_hyperglycaemic():
    """The failure modes are opposites and a completion count cannot separate them."""
    t = C.classify_termination(_Run([120, 300, 500, 599]))
    assert t["direction"] == "hyperglycaemic"
    assert t["highest_bg"] == 599.0


def test_a_site_failing_at_the_end_is_named_in_the_reason():
    t = C.classify_termination(_Run([120, 400, 599], meta={
        "site_failures": 2, "site_units_lost": 90.0,
        "site_failed_minutes": 600.0, "site_failing_at_end": True}))
    assert t["site_failing_at_end"] is True
    assert "not absorbing" in t["reason"]
    assert t["site_failed_hours"] == 10.0


def test_the_report_separates_the_two_directions_per_arm():
    runs = [{"name": "a", "arm": "oref", "completed": True},
            {"name": "b", "arm": "oref", "completed": False,
             "termination": {"direction": "hyperglycaemic", "site_failing_at_end": True}},
            {"name": "c", "arm": "oref", "completed": False,
             "termination": {"direction": "hypoglycaemic"}}]
    r = C.failure_report(runs)["oref"]
    assert (r["completed"], r["hyperglycaemic"], r["hypoglycaemic"]) == (1, 1, 1)
    assert r["with_site_failing"] == 1
    text = C.format_failure_report(C.failure_report(runs))
    assert "1 ended low" in text and "1 ended high" in text


def test_a_scheduled_set_change_bounds_a_failure_nobody_noticed():
    """The only route by which a masked failure ends.

    Detection needs the reading above a threshold for a sustained period, so a controller
    that partially compensates keeps the person unaware and the set runs to its scheduled
    replacement. That replacement is therefore what bounds the exposure, and it has to be
    specifiable so a comparison can state the interval it assumed.
    """
    import numpy as np
    from timsim.therapy.site import InfusionSite

    site = InfusionSite(np.random.default_rng(3), set_life_days=3.0,
                        failures_per_30_days=60.0)
    assert site.set_life_days == (3.0, 3.0)
    failing = 0
    for minute in range(0, 14 * 1440, 5):
        if site.absorbed_fraction(float(minute)) < 1.0:
            failing += 1
        # Never report a high reading, so nothing is ever noticed by the person.
        site.observe(float(minute), 110.0, 5.0)
    rep = site.report()
    assert rep["site_routine_changes"] == 4, rep
    assert rep["site_set_changes"] == rep["site_routine_changes"], "nothing was noticed"
    # No single failure can outlast a set, so exposure is bounded by the interval given.
    assert failing * 5 <= rep["site_failures"] * 3.0 * 1440.0


def test_the_set_interval_reaches_the_run():
    import inspect
    from timsim.simulation.run import simulate
    assert "set_life_days" in inspect.signature(simulate).parameters


def test_a_controller_dosing_against_different_settings_is_refused():
    """The rig delivers against one profile and the algorithm doses against another.

    Both bridge controllers fall back to the population's untitrated settings when none is
    passed, so a harness that titrates the run but constructs the controller without the
    profile produces exactly this, silently. It once put a published comparison's claim that
    two algorithms received the same settings out of agreement with what they were given.
    """
    from timsim.simulation.run import _require_matching_profile
    from timsim.therapy import profile as P

    class _Ctrl:
        pass

    run_profile = P.for_subject("adult#001")
    c = _Ctrl()
    c.profile = P.for_subject("adult#001", isf_scale=2.0)
    with pytest.raises(ValueError, match="differs from the profile this run was given"):
        _require_matching_profile(c, run_profile)

    c.profile = P.for_subject("adult#001")
    _require_matching_profile(c, run_profile)      # an equal profile is fine
    _require_matching_profile(_Ctrl(), run_profile)  # a controller without one is fine
