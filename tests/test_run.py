"""End-to-end: a run must produce a coherent record, and layers must actually do work."""
import numpy as np
import pytest

from simperson import LAYERS, population, simulate

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
    from simperson.analysis import signatures as S
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
