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


def test_the_loop_is_a_controller_and_not_a_layer_of_a_person(subject):
    """It was listed among the layers once, and that is a category error worth guarding."""
    assert "loop" not in LAYERS
    with pytest.raises(ValueError, match="not a layer of a person"):
        simulate(subject, days=1, seed=0, layers=("physiology", "loop"))


def test_an_unknown_layer_is_refused_rather_than_ignored(subject):
    with pytest.raises(ValueError, match="unknown layers"):
        simulate(subject, days=1, seed=0, layers=("physiology", "exercise"))


def test_the_run_records_what_drove_it(subject):
    from simglucose.controller.base import Action, Controller

    class Fixed(Controller):
        def __init__(self):
            pass

        def policy(self, observation, reward, done, **info):
            return Action(basal=0.01, bolus=0.0)

    assert simulate(subject, days=1, seed=0).controller == "trend"
    assert simulate(subject, days=1, seed=0,
                    controller="basal-bolus").controller == "basal-bolus"
    # "reference" means whatever the baseline currently is, not a frozen choice
    assert simulate(subject, days=1, seed=0,
                    controller="reference").controller == "trend"
    r = simulate(subject, days=1, seed=0, controller=Fixed(), layers=LAYERS)
    assert r.controller == "Fixed" and r.meta["controller"] == "Fixed"


def test_an_unusable_controller_is_refused(subject):
    with pytest.raises(ValueError, match="unknown controller"):
        simulate(subject, days=1, seed=0, controller="openaps")
    with pytest.raises(TypeError, match="policy"):
        simulate(subject, days=1, seed=0, controller=object())


def test_closing_the_loop_is_a_change_of_controller_not_of_person(subject):
    open_loop = simulate(subject, days=5, seed=0, controller="basal-bolus")
    closed = simulate(subject, days=5, seed=0, controller="trend")
    assert open_loop.layers == closed.layers
    assert closed.time_in_range > open_loop.time_in_range


def test_the_two_loop_shapes_differ_in_the_way_they_are_meant_to(subject):
    """One corrects every five minutes by bolus; the other hourly, mostly through basal."""
    from timsim.controller.loop import CONTROL_IQ, TREND
    assert CONTROL_IQ.min_interval_min == 60.0 and TREND.min_interval_min == 5.0
    assert CONTROL_IQ.predict_min == 30.0 and TREND.predict_min == 0.0
    assert CONTROL_IQ.max_basal_scale > 1.0 and TREND.max_basal_scale == 1.0
    a = simulate(subject, days=7, seed=0, controller="control-iq")
    b = simulate(subject, days=7, seed=0, controller="trend")
    assert a.time_above_180 < b.time_above_180


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


def test_an_unknown_loop_shape_is_refused():
    from timsim.controller.loop import CorrectionLoop
    with pytest.raises(ValueError, match="unknown loop shape"):
        CorrectionLoop("openaps")


def test_the_control_iq_shape_matches_the_published_thresholds():
    """Copied from Tandem's description; a drift here makes the baseline unciteable."""
    from timsim.controller.loop import CONTROL_IQ as s
    assert (s.correct_above, s.target, s.correction_fraction) == (180.0, 110.0, 0.6)
    assert (s.min_interval_min, s.predict_min) == (60.0, 30.0)
    assert (s.suspend_below, s.reduce_below) == (70.0, 112.5)
    assert (s.boost_above, s.max_basal_above) == (160.0, 180.0)


def test_basal_follows_the_published_bands():
    from timsim.controller.loop import CorrectionLoop
    loop = CorrectionLoop("control-iq")
    assert loop.basal_scale(60.0, 0.0) == 0.0            # suspended below 70
    assert loop.basal_scale(100.0, 0.0) == 0.5           # reduced below 112.5
    assert loop.basal_scale(140.0, 0.0) == 1.0           # usual through 160
    assert loop.basal_scale(170.0, 0.0) > 1.0            # raised from 160
    assert loop.basal_scale(200.0, 0.0) > loop.basal_scale(170.0, 0.0)


def test_a_correction_cannot_exceed_the_insulin_on_board_ceiling():
    from timsim.controller.loop import CorrectionLoop
    loop = CorrectionLoop("control-iq")
    loop.add(0.0, 5.9)
    loop.correction(5.0, 400.0, 10.0)
    assert loop.iob(5.0) <= loop.s.max_iob_u + 1e-9


def test_the_trend_is_fitted_because_a_single_delta_is_mostly_noise():
    """A five-minute difference at a thirty-minute horizon is unusable.

    The sensor's error has a standard deviation near 12 mg/dL, so a difference between
    consecutive readings carries about 17, which is over 100 mg/dL once extrapolated half
    an hour. The first version of this loop predicted that way and delivered 76 U a day
    against the trial's 47.
    """
    import numpy as np
    from timsim.controller.loop import CorrectionLoop
    rng = np.random.default_rng(0)
    naive, fitted = [], []
    for _ in range(400):
        loop = CorrectionLoop("control-iq")
        vals = 150.0 + rng.normal(0, 12, 7)          # a flat truth, seen through noise
        for k, v in enumerate(vals):
            loop.observe(k * 5.0, v)
        d = (vals[-1] - vals[-2]) / 5.0
        naive.append(d * 30.0)
        fitted.append(loop.trend(d) * 30.0)
    assert np.std(fitted) < np.std(naive) / 4


def test_the_trend_recovers_a_real_slope():
    from timsim.controller.loop import CorrectionLoop
    loop = CorrectionLoop("control-iq")
    for k in range(7):
        loop.observe(k * 5.0, 100.0 + 2.0 * k * 5.0)   # 2 mg/dL per minute
    assert loop.trend(0.0) == pytest.approx(2.0, rel=1e-6)


def test_a_reactive_loop_does_not_fit_a_trend_it_never_uses():
    from timsim.controller.loop import CorrectionLoop
    loop = CorrectionLoop("trend")
    for k in range(7):
        loop.observe(k * 5.0, 100.0 + 3.0 * k * 5.0)
    assert loop.trend(0.7) == pytest.approx(0.7)
    assert loop.predicted(150.0, 0.7) == 150.0        # no horizon, no extrapolation


def test_the_loop_default_matches_the_simulator_default():
    """These drifted apart once, and nothing would have reported the difference."""
    from timsim.controller import loop
    from timsim.simulation.run import DEFAULT_CONTROLLER
    assert loop.DEFAULT_SHAPE == DEFAULT_CONTROLLER
    assert DEFAULT_CONTROLLER in loop.SHAPES
