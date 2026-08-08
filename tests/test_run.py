"""End-to-end: a run must produce a coherent record, and layers must actually do work."""
import numpy as np
import pytest

from timsim import LAYERS, population, simulate

pytestmark = pytest.mark.skipif(not population.available(),
                                reason="no population generated")


@pytest.fixture(scope="module")
def subject():
    return population.names("adult")[0]


def test_a_short_run_produces_a_coherent_record(subject):
    r = simulate(subject, days=2, seed=0)
    assert len(r.cgm) > 500
    assert np.all(r.cgm > 0)
    assert r.sample_time > 0
    assert 0 <= r.time_in_range <= 100
    assert set(r.layers) <= set(LAYERS)
    assert set(r.summary()) >= {"name", "cv", "tir", "tbr"}


def test_no_layers_means_no_behaviour(subject):
    r = simulate(subject, days=2, seed=0, layers=())
    assert r.rescue_events == 0
    assert r.meals_unannounced == 0
    assert r.compression_events == 0
    assert not np.isfinite(r.isf_weekly_cv)


def test_the_behaviour_layer_produces_unannounced_meals_and_rescues(subject):
    r = simulate(subject, days=7, seed=0, layers=("behaviour",))
    assert r.meals_unannounced > 0
    assert r.meals_announced > 0
    assert r.rescue_events >= 0


def test_the_sensor_layer_adds_jitter_that_no_other_layer_adds(subject):
    from timsim.analysis import signatures as S
    quiet = simulate(subject, days=7, seed=0, layers=("physiology", "behaviour"))
    noisy = simulate(subject, days=7, seed=0, layers=("physiology", "behaviour", "sensor"))
    jitter = next(fn for k, _, fn in S.SIGS if k == "noise")
    assert jitter(S.from_result(noisy)) > jitter(S.from_result(quiet)) + 1.5


def test_the_same_seed_reproduces_the_same_run(subject):
    a = simulate(subject, days=2, seed=7)
    b = simulate(subject, days=2, seed=7)
    assert np.array_equal(a.cgm, b.cgm)


def test_different_seeds_do_not(subject):
    a = simulate(subject, days=2, seed=7)
    b = simulate(subject, days=2, seed=8)
    assert not np.array_equal(a.cgm[:min(len(a.cgm), len(b.cgm))],
                              b.cgm[:min(len(a.cgm), len(b.cgm))])


def test_the_runner_defaults_to_the_five_minute_grid_real_sensors_report_on(subject):
    r = simulate(subject, days=1, seed=0)
    assert r.sample_time == 5.0
    assert r.meta["sample_minutes"] == 5.0


def test_an_external_controller_switches_the_loop_layer_off(subject):
    from simglucose.controller.base import Action, Controller

    class Fixed(Controller):
        def __init__(self):
            pass

        def policy(self, observation, reward, done, **info):
            return Action(basal=0.01, bolus=0.0)

    with pytest.warns(UserWarning, match="loop layer"):
        r = simulate(subject, days=1, seed=0, controller=Fixed(), layers=LAYERS)
    assert "loop" not in r.layers
    assert "loop" in r.meta["requested_layers"]


def test_insulin_is_recorded_whichever_controller_delivered_it(subject):
    from simglucose.controller.base import Action, Controller

    class Fixed(Controller):
        def __init__(self):
            pass

        def policy(self, observation, reward, done, **info):
            return Action(basal=0.02, bolus=0.0)

    r = simulate(subject, days=1, seed=0, layers=(), controller=Fixed())
    assert np.isfinite(r.insulin_units) and r.insulin_units > 0
    assert len(r.insulin_series) == len(r.cgm)
    assert r.insulin_series.sum() == pytest.approx(r.insulin_units)


def test_the_recorded_trace_is_the_one_the_algorithm_acted_on(subject):
    """The failure this catches is a sensor layer bolted on after the run."""
    from simglucose.controller.base import Action, Controller

    class Watcher(Controller):
        def __init__(self):
            self.seen = []

        def policy(self, observation, reward, done, **info):
            self.seen.append(observation.CGM)
            return Action(basal=0.01, bolus=0.0)

    w = Watcher()
    r = simulate(subject, days=2, seed=0, layers=("sensor",), controller=w)
    assert np.allclose(np.array(w.seen[:len(r.cgm)]), r.cgm)


def test_a_therapy_profile_reaches_the_algorithm(subject):
    from simglucose.controller.base import Action, Controller

    class Reader(Controller):
        def __init__(self):
            self.rates = set()

        def policy(self, observation, reward, done, **info):
            p = info["profile"]
            self.rates.add(round(p.basal_at(info["clock_minutes"]), 6))
            return Action(basal=p.basal_at(info["clock_minutes"]), bolus=0.0)

    flat, dawn = Reader(), Reader()
    simulate(subject, days=1, seed=0, layers=(), controller=flat)
    simulate(subject, days=1, seed=0, layers=(), controller=dawn, diurnal_basal=True)
    assert len(flat.rates) == 1
    assert len(dawn.rates) > 1


def test_a_custom_controller_is_driven_in_place_of_the_builtin(subject):
    from simglucose.controller.base import Action, Controller

    class Fixed(Controller):
        def __init__(self):
            self.calls = 0

        def policy(self, observation, reward, done, **info):
            self.calls += 1
            return Action(basal=0.0, bolus=0.0)

    c = Fixed()
    r = simulate(subject, days=1, seed=0, controller=c)
    assert c.calls > 100
    assert len(r.cgm) > 100


def test_a_meal_is_bolused_the_same_whether_or_not_the_behaviour_layer_is_on(subject):
    """The units bug this catches under-bolused every run with behaviour switched off.

    simglucose reports `info["meal"]` as grams per minute averaged over the step, while the
    behaviour layer's scenario accumulates grams. Passing the first through as though it
    were the second divides every meal bolus by the step length, so the bare arms of an
    ablation ran on a fifth of the insulin they should have had.
    """
    meal = [(8.0, 60, False)]
    bare = simulate(subject, days=2, seed=0, layers=(), meals=meal)
    behaviour = simulate(subject, days=2, seed=0, layers=("behaviour",), meals=meal)
    # the behaviour layer may fail to announce, so it can dose less, never five times less
    assert bare.insulin_units == pytest.approx(behaviour.insulin_units, rel=0.25)
    assert bare.cgm.max() < behaviour.cgm.max() + 25.0
