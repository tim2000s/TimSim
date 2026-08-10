"""The behaviour layer decides what the algorithm is told and what the person eats."""
import numpy as np
import pytest

from timsim.controller.loop import CorrectionLoop
from timsim.person.behaviour import (AdaptiveRatios, Person, P_ANNOUNCE_MAIN,
                                        RESCUE_REFRACTORY_MIN)


def test_unannounced_meals_are_reported_as_zero_carbohydrate():
    """An unannounced meal must reach the gut and not reach the algorithm."""
    rng = np.random.default_rng(0)
    p = Person(rng)
    announced = [p.announce(60.0, is_snack=False) for _ in range(400)]
    zeros = sum(1 for a in announced if a == 0.0)
    assert 0 < zeros < 400
    assert abs(1 - zeros / 400 - P_ANNOUNCE_MAIN) < 0.08


def test_announced_carbohydrate_is_mis_estimated_but_unbiased():
    rng = np.random.default_rng(1)
    p = Person(rng)
    seen = [a for a in (p.announce(60.0, False) for _ in range(4000)) if a > 0]
    assert abs(np.mean(seen) / 60.0 - 1.0) < 0.05
    assert 0.15 < np.std(seen) / np.mean(seen) < 0.40


def test_announcement_can_be_switched_off():
    p = Person(np.random.default_rng(0), announce=False)
    assert p.announce(60.0, False) == 60.0


def test_a_low_produces_carbohydrate_after_a_delay():
    p = Person(np.random.default_rng(2))
    p.observe(minute=100, cgm=62.0, fall_rate=-1.0)
    assert p.rescue_events == 1
    assert p.due(100, 1.0) == 0.0                    # not instant
    total = sum(p.due(m, 1.0) for m in range(100, 130))
    assert 14.0 <= total <= 50.0


def test_rescue_does_not_repeat_inside_the_refractory_window():
    p = Person(np.random.default_rng(3))
    p.observe(100, 60.0, -1.0)
    p.observe(100 + RESCUE_REFRACTORY_MIN - 1, 58.0, -1.0)
    assert p.rescue_events == 1
    p.observe(100 + RESCUE_REFRACTORY_MIN + 1, 58.0, -1.0)
    assert p.rescue_events == 2


def test_a_normal_glucose_produces_nothing():
    p = Person(np.random.default_rng(4))
    p.observe(100, 140.0, 0.0)
    assert p.rescue_events == 0
    assert p.due(100, 60.0) == 0.0


def test_rescue_can_be_switched_off():
    p = Person(np.random.default_rng(5), rescue=False)
    p.observe(100, 50.0, -3.0)
    assert p.rescue_events == 0


def test_running_high_tightens_the_sensitivity_setting():
    r = AdaptiveRatios(cf0=50.0, cr0=10.0)
    week = 7 * 24 * 60
    for minute in range(0, 2 * week, 5):
        r.observe(minute, cgm=220.0)
    assert r.cf < 50.0
    assert r.cr < 10.0


def test_a_setting_that_never_sees_error_does_not_drift():
    r = AdaptiveRatios(cf0=50.0, cr0=10.0)
    for minute in range(0, 3 * 7 * 24 * 60, 5):
        r.observe(minute, cgm=140.0)
    assert r.cf == pytest.approx(50.0)
    assert np.isfinite(r.weekly_cv())


def test_insulin_on_board_decays_to_nothing():
    loop = CorrectionLoop("trend")
    loop.add(0, 5.0)
    assert loop.iob(0) == pytest.approx(5.0)
    assert loop.iob(75) < 5.0
    assert loop.iob(301) == pytest.approx(0.0, abs=1e-9)


def test_the_loop_will_not_stack_beyond_its_bound():
    """The bound is on insulin still to act, so it releases as that insulin decays."""
    loop = CorrectionLoop("trend")
    loop.add(0, 6.0)
    assert loop.iob(0) == pytest.approx(6.0)
    assert loop.correction(0, cgm=300.0, cf=30.0) == 0.0        # at the bound
    assert loop.iob(60) < 6.0
    assert loop.correction(60, cgm=300.0, cf=30.0) > 0.0        # released as it decays


def test_the_loop_will_not_correct_a_glucose_that_is_not_high():
    loop = CorrectionLoop("trend")
    assert loop.correction(0, cgm=140.0, cf=30.0) == 0.0


def test_the_loop_respects_its_minimum_interval():
    loop = CorrectionLoop("trend")
    first = loop.correction(0, cgm=300.0, cf=30.0)
    assert first > 0.0
    assert loop.correction(2, cgm=300.0, cf=30.0) == 0.0
    assert loop.correction(10, cgm=300.0, cf=30.0) > 0.0


def test_the_loop_withdraws_basal_when_low():
    loop = CorrectionLoop("trend")
    assert loop.basal_scale(cgm=70.0, fall_rate=0.0) == 0.0
    assert loop.basal_scale(cgm=105.0, fall_rate=-2.0) == 0.0
    assert loop.basal_scale(cgm=150.0, fall_rate=0.0) == 1.0


# ------------------------------------------------- per-subject treating style
def test_treating_style_is_uniform_by_default():
    from timsim.person import behaviour as B
    assert B.rescue_style("adult#001") == (B.RESCUE_THRESHOLD, B.RESCUE_REFRACTORY_MIN)


def test_a_subject_keeps_its_treating_style_between_runs():
    from timsim.person import behaviour as B
    assert B.rescue_style("adult#001", 0.3) == B.rescue_style("adult#001", 0.3)
    assert B.rescue_style("adult#001", 0.3) != B.rescue_style("adult#002", 0.3)


def test_treating_style_stays_inside_clinically_plausible_bounds():
    import numpy as np
    from timsim.person import behaviour as B
    from timsim.population import names
    v = [B.rescue_style(n, 0.4) for n in names()]
    t = np.array([x[0] for x in v]); r = np.array([x[1] for x in v])
    assert B.RESCUE_THRESHOLD_BOUNDS[0] <= t.min() and t.max() <= B.RESCUE_THRESHOLD_BOUNDS[1]
    assert B.RESCUE_REFRACTORY_BOUNDS[0] <= r.min() and r.max() <= B.RESCUE_REFRACTORY_BOUNDS[1]
    assert abs(np.median(t) - B.RESCUE_THRESHOLD) < 5.0, "the centre moved"


def test_the_preemptive_trigger_follows_the_threshold():
    """Someone who treats late should not still be treating early on a fast fall."""
    import numpy as np
    from timsim.person.behaviour import Person, RESCUE_PREEMPT_BG, RESCUE_THRESHOLD
    p = Person(np.random.default_rng(0), rescue_threshold=60.0)
    assert p.rescue_preempt_bg == 60.0 + (RESCUE_PREEMPT_BG - RESCUE_THRESHOLD)


def test_a_higher_threshold_treats_more_often():
    import numpy as np
    from timsim.person.behaviour import Person
    counts = []
    for thr in (58.0, 85.0):
        p = Person(np.random.default_rng(0), rescue_threshold=thr,
                   rescue_refractory_min=45.0)
        for k in range(2000):
            p.observe(k * 5.0, 75.0, 0.0)
        counts.append(p.rescue_events)
    assert counts[1] > counts[0]


def test_the_spread_reaches_the_run_and_is_recorded():
    from timsim import simulate
    from timsim.population import names
    r = simulate(names("adult")[0], days=1, seed=0, behaviour_spread=0.3)
    assert r.meta["behaviour_spread"] == 0.3
    assert r.meta["rescue_threshold"] != simulate(
        names("adult")[1], days=1, seed=0, behaviour_spread=0.3).meta["rescue_threshold"]
