"""Physical activity, tested on what it has to get right to be worth having.

The layer exists because three fidelity signatures say the model is too predictable and
exercise is the largest driver of real variability the model omits. It is also the one layer
in this package with no grounding in the local database, because the Nightscout records carry
no exercise events, so its schedule is a modelling choice and the tests below check the
mechanism behaves rather than that it reproduces a measurement.
"""
import numpy as np
import pytest

from timsim.patient import varying as V
from timsim.person import activity as A


def _sessions(n=3, start=600.0, gap=1440.0, minutes=60.0, intensity=0.7):
    return tuple((start + i * gap, minutes, intensity) for i in range(n))


# ------------------------------------------------------------------ the schedule
def test_nobody_exercises_when_the_rate_is_zero():
    s = A.draw_sessions(np.random.default_rng(0), 28, sessions_per_week=0.0)
    assert s == ()


def test_the_weekly_rate_is_held_for_the_person_rather_than_redrawn():
    """Somebody who trains often does so all month. A rate redrawn daily would give every
    subject the same amount of exercise and remove the between-person difference that is
    most of the point."""
    rates = []
    for seed in range(40):
        s = A.draw_sessions(np.random.default_rng(seed), 84, rate_cv=A.RATE_CV)
        rates.append(len(s) / 12.0)
    rates = np.array(rates)
    assert rates.std() / rates.mean() > 0.4, "the population all exercises the same amount"


def test_sessions_land_in_waking_hours():
    s = A.draw_sessions(np.random.default_rng(1), 200, sessions_per_week=7.0)
    hours = np.array([(m % 1440) / 60.0 for m, _, _ in s])
    assert hours.min() >= 5.0 and hours.max() <= 22.0


def test_sessions_are_ordered_and_do_not_sit_on_top_of_each_other():
    s = A.draw_sessions(np.random.default_rng(2), 60, sessions_per_week=7.0)
    starts = [m for m, _, _ in s]
    assert starts == sorted(starts)
    for (m0, d0, _), (m1, _, _) in zip(s, s[1:]):
        assert m1 >= m0, "sessions out of order"


# -------------------------------------------------------------------- the effect
def test_a_session_is_on_while_it_runs_and_off_afterwards():
    a = A.Activity(((600.0, 60.0, 0.8),))
    assert a.during(599.0) == 0.0
    assert a.during(630.0) == pytest.approx(0.8)
    assert a.during(661.0) == 0.0


def test_what_a_session_leaves_behind_decays():
    a = A.Activity(((600.0, 60.0, 1.0),))
    just_after = a.after(661.0)
    later = a.after(661.0 + A.AFTER_TAU_MIN)
    assert just_after > later > 0.0
    assert later == pytest.approx(just_after / np.e, rel=0.05)


def test_the_after_effect_does_not_run_away_over_a_week_of_training():
    a = A.Activity(_sessions(n=14, gap=720.0, intensity=1.0))
    assert a.after(14 * 720.0 + 1e4) <= 2.0


def test_nothing_before_the_first_session():
    a = A.Activity(((600.0, 60.0, 1.0),))
    assert a.after(100.0) == 0.0
    assert a.during(100.0) == 0.0


# ----------------------------------------------------------------- on the patient
def test_a_session_lowers_glucose_and_no_session_does_not():
    """The check that the mechanism reaches the model at all."""
    from simglucose.patient.t1dpatient import Action
    out = {}
    for label, sess in (("rest", ()), ("exercise", ((600.0, 60.0, 0.7),))):
        p = V.from_population("adult#001")
        if sess:
            p.set_activity(A.Activity(sess))
        basal = p._params.u2ss * p._params.BW / 6000.0
        g = [p.step(Action(CHO=0.0, insulin=basal)) or p.observation.Gsub
             for _ in range(900)]
        out[label] = np.asarray(g, float)
    assert out["rest"][600:].min() > out["exercise"][600:].min() + 5.0
    # and it comes back afterwards rather than staying down forever
    assert out["exercise"][-1] > out["exercise"][600:].min()


def test_a_patient_without_activity_is_untouched():
    """`set_activity` is opt-in, so a patient that never had it called must behave exactly
    as the stock one."""
    from simglucose.patient.t1dpatient import Action
    runs = []
    for _ in range(2):
        p = V.from_population("adult#002")
        basal = p._params.u2ss * p._params.BW / 6000.0
        runs.append([p.step(Action(CHO=0.0, insulin=basal)) or p.observation.Gsub
                     for _ in range(200)])
    assert np.allclose(runs[0], runs[1])


def test_the_insulin_independent_term_only_moves_during_a_session():
    """Exercise lowers glucose without insulin while it happens; what it leaves behind
    needs insulin on board to act. That is the difference between a low during a session
    and a low hours later, and it is carried by which parameter each moves."""
    p = V.from_population("adult#003")
    p.set_activity(A.Activity(((600.0, 60.0, 1.0),)))
    vm00 = p._vm00
    p._apply_activity(1.0)                       # t = 0, nothing happening
    assert p._params["Vm0"] == pytest.approx(vm00)
    p._odesolver.set_initial_value(p._odesolver.y, 630.0)
    assert p._apply_activity(1.0) > 1.0          # sensitivity raised during
    assert p._params["Vm0"] > vm00
    p._odesolver.set_initial_value(p._odesolver.y, 800.0)
    assert p._apply_activity(1.0) > 1.0          # still raised after
    assert p._params["Vm0"] == pytest.approx(vm00), "Vm0 raised outside a session"


def test_brain_uptake_is_left_alone():
    """`Fsnc` is brain and nerve uptake and does not move with exercise. It was the
    parameter this layer first reached for by mistake."""
    p = V.from_population("adult#004")
    before = float(p._params["Fsnc"])
    p.set_activity(A.Activity(((0.0, 60.0, 1.0),)))
    p._apply_activity(1.0)
    assert float(p._params["Fsnc"]) == pytest.approx(before)
