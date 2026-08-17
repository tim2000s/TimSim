"""The therapy profile and the delivery limits, which sit between an algorithm and the body."""
import numpy as np
import pytest

from timsim import population, therapy
from timsim.therapy import Enforcer, PumpLimits
from timsim.therapy.insulin import iob, iob_fraction

pytestmark = pytest.mark.skipif(not population.available(),
                                reason="no population generated")


@pytest.fixture(scope="module")
def subject():
    return population.names("adult")[0]


def test_a_flat_profile_is_the_subjects_own_basal_at_every_hour(subject):
    p = therapy.for_subject(subject)
    assert len(set(np.round(p.basal_u_per_hour, 9))) == 1
    assert p.basal_at(0) == pytest.approx(p.basal_at(13 * 60))


def test_a_diurnal_profile_peaks_before_breakfast_and_holds_its_daily_total(subject):
    flat = therapy.for_subject(subject)
    dawn = therapy.for_subject(subject, diurnal=True)
    assert dawn.basal_u_per_hour.sum() == pytest.approx(flat.basal_u_per_hour.sum())
    assert int(np.argmax(dawn.basal_u_per_hour)) == 6
    # a unit does less when sensitivity is lowest, so the factor moves the other way
    assert dawn.isf[6] < dawn.isf[18]


def test_the_profile_serialises_to_what_an_adapter_needs(subject):
    d = therapy.for_subject(subject).as_dict()
    assert len(d["basal_schedule_u_per_hour"]) == 24
    assert d["target_lo"] < d["target_hi"]
    assert d["max_iob_u"] > 0 and d["max_bolus_u"] > 0


def test_insulin_on_board_decays_over_the_duration_of_action():
    assert iob_fraction(0) == 1.0
    assert iob_fraction(1000) == 0.0
    ages = np.arange(0, 300, 10)
    fractions = [iob_fraction(a) for a in ages]
    assert all(b <= a for a, b in zip(fractions, fractions[1:]))
    assert iob(100, [(0, 2.0), (60, 1.0)]) > 0


def test_the_bolus_ceiling_binds():
    e = Enforcer(PumpLimits(max_basal_u_per_hour=3.0, max_bolus_u=5.0, max_iob_u=100.0))
    _, bolus = e.apply(0, 0.01, 20.0, 0.01, 5.0)
    assert bolus == pytest.approx(5.0)
    assert e.bound["bolus"] == 1


def test_the_basal_ceiling_binds_and_quantises():
    e = Enforcer(PumpLimits(max_basal_u_per_hour=2.0, max_bolus_u=10.0, max_iob_u=100.0))
    basal, _ = e.apply(0, 1.0, 0.0, 0.01, 5.0)
    assert basal * 60 == pytest.approx(2.0)
    assert e.bound["basal"] == 1


def test_the_insulin_on_board_ceiling_stops_stacking():
    e = Enforcer(PumpLimits(max_basal_u_per_hour=3.0, max_bolus_u=10.0, max_iob_u=6.0))
    given = [e.apply(t, 0.01, 4.0, 0.01, 5.0)[1] for t in (0, 5, 10, 15)]
    assert sum(given) <= 6.0 + 1e-6
    assert e.bound["iob"] > 0


def test_basal_at_or_below_schedule_does_not_count_towards_insulin_on_board():
    e = Enforcer(PumpLimits(max_basal_u_per_hour=3.0, max_bolus_u=10.0, max_iob_u=6.0))
    for t in range(0, 600, 5):
        e.apply(t, 0.02, 0.0, 0.02, 5.0)
    assert e.iob(600) == pytest.approx(0.0)


def test_the_insulin_on_board_ceiling_also_bounds_basal_above_schedule():
    """The gap this catches: a ceiling that only ever looked at boluses.

    An algorithm holding its basal at the maximum delivers insulin the ceiling never saw,
    so insulin on board climbed past the declared limit while every bolus was compliant.
    """
    lim = PumpLimits(max_basal_u_per_hour=6.0, max_bolus_u=10.0, max_iob_u=4.0)
    e = Enforcer(lim)
    for t in range(0, 600, 5):
        e.apply(t, 6.0 / 60.0, 0.0, 1.0 / 60.0, 5.0)
    assert e.peak_iob_u <= lim.max_iob_u + 1e-6
    assert e.bound["iob"] > 0


def test_peak_insulin_on_board_never_exceeds_the_ceiling_under_a_greedy_algorithm():
    lim = PumpLimits(max_basal_u_per_hour=6.0, max_bolus_u=10.0, max_iob_u=5.0)
    e = Enforcer(lim)
    for t in range(0, 1200, 5):
        e.apply(t, 1.0, 20.0, 1.0 / 60.0, 5.0)
    assert e.peak_iob_u <= lim.max_iob_u + 1e-6


# ------------------------------------------------------------------ settings conservatism
def test_scaling_the_correction_factor_changes_the_setting_and_not_the_body():
    """`isf_scale` models a person with conservative settings, not a different person."""
    from timsim.population import names
    from timsim.therapy import profile as P
    name = names("adult")[0]
    a = P.for_subject(name)
    b = P.for_subject(name, isf_scale=2.4)
    assert b.isf_at(720) == pytest.approx(a.isf_at(720) * 2.4)
    assert b.cr_at(720) == pytest.approx(a.cr_at(720))
    assert b.basal_at(0) == pytest.approx(a.basal_at(0))


def test_the_default_leaves_the_measured_settings_alone():
    from timsim.population import names
    from timsim.therapy import profile as P
    name = names("adult")[0]
    a, b = P.for_subject(name), P.for_subject(name, isf_scale=1.0, cr_scale=1.0)
    assert a.isf_at(0) == b.isf_at(0) and a.cr_at(0) == b.cr_at(0)


def test_conservative_settings_reach_the_run_and_leave_more_glucose_high():
    """The whole point is that a weaker correction factor under-corrects a high."""
    from timsim import simulate
    from timsim.population import names
    name = names("adult")[0]
    a = simulate(name, days=5, seed=0)
    b = simulate(name, days=5, seed=0, isf_scale=2.4)
    assert a.meta["isf_scale"] == 1.0 and b.meta["isf_scale"] == 2.4
    assert b.time_above_180 > a.time_above_180


# ----------------------------------------------------- per-subject settings divergence
def test_settings_spread_is_off_by_default():
    from timsim.population import names
    from timsim.therapy import profile as P
    name = names("adult")[0]
    assert P.accuracy_for(name) == (1.0, 1.0)
    assert P.for_subject(name).isf_at(0) == P.for_subject(name, settings_spread=0.0).isf_at(0)


def test_a_subject_keeps_the_same_settings_between_runs():
    """Keyed on the name, so a cohort is stable without regenerating the population."""
    from timsim.population import names
    from timsim.therapy import profile as P
    name = names("adult")[0]
    assert P.accuracy_for(name, 0.3) == P.accuracy_for(name, 0.3)
    assert P.for_subject(name, settings_spread=0.3).isf_at(720) == \
        P.for_subject(name, settings_spread=0.3).isf_at(720)


def test_different_subjects_get_different_settings():
    from timsim.population import names
    from timsim.therapy import profile as P
    drawn = {P.accuracy_for(n, 0.3) for n in names("adult")[:10]}
    assert len(drawn) == 10


def test_the_spread_has_the_size_asked_for_and_no_bias():
    import numpy as np
    from timsim.population import names
    from timsim.therapy import profile as P
    v = np.array([P.accuracy_for(n, 0.3)[0] for n in names()])
    assert abs(np.median(v) - 1.0) < 0.12, "the centre moved, which isf_scale is for"
    assert 0.2 < v.std() < 0.45


def test_the_spread_reaches_the_run_and_is_recorded():
    from timsim import simulate
    from timsim.population import names
    r = simulate(names("adult")[0], days=1, seed=0, settings_spread=0.3)
    assert r.meta["settings_spread"] == 0.3
    assert simulate(names("adult")[0], days=1, seed=0).meta["settings_spread"] == 0.0


def test_the_basal_ceiling_holds_when_it_is_not_on_an_increment_boundary():
    """Quantising after the clamp could round back through the ceiling.

    `_to_nearest` rounds up as readily as down, so a ceiling of 2.03 U/h on a 0.05 increment
    returned 2.05. The bolus path already rounded down for exactly this reason.
    """
    lim = PumpLimits(max_basal_u_per_hour=2.03, max_bolus_u=10.0, max_iob_u=100.0)
    e = Enforcer(lim)
    basal, _ = e.apply(0, 5.0 / 60.0, 0.0, 0.5 / 60.0, 5.0)
    assert basal * 60.0 <= lim.max_basal_u_per_hour + 1e-9


def test_the_insulin_on_board_ceiling_never_withholds_scheduled_basal():
    """The ceiling bounds what the algorithm adds, not the person's own background insulin.

    Rounding the capped rate down landed below the schedule whenever the scheduled rate did
    not sit on an increment boundary: 0.62 U/h came back as 0.60.
    """
    lim = PumpLimits(max_basal_u_per_hour=10.0, max_bolus_u=10.0, max_iob_u=0.0)
    e = Enforcer(lim)
    scheduled = 0.62 / 60.0
    basal, _ = e.apply(0, 3.0 / 60.0, 0.0, scheduled, 5.0)
    assert basal >= scheduled - 1e-12
