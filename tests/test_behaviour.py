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
