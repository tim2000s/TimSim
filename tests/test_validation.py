"""The validation suite decides whether anything else can be believed, so it is tested."""
import numpy as np
import pytest

from timsim import population
from timsim.validation import checks, minimum_detectable_difference

pytestmark = pytest.mark.skipif(not population.available(),
                                reason="no population generated")


class _Fake:
    """A stand-in Result carrying only what the level 4 and 5 checks read."""

    def __init__(self, tir):
        self.time_in_range = tir


def test_the_closure_check_passes():
    r = checks.check_steady_state_closure()
    assert r["pass"]
    assert r["value"] < 1e-9


def test_a_null_contrast_is_reported_as_null():
    rng = np.random.default_rng(0)
    base = rng.normal(70, 8, 40)
    a = [_Fake(v) for v in base]
    b = [_Fake(v + n) for v, n in zip(base, rng.normal(0, 3, 40))]
    assert checks.check_null_contrast_is_null(a, b)["pass"]


def test_a_real_difference_is_not_reported_as_null():
    """The null check has to be able to fail, or it is decoration."""
    rng = np.random.default_rng(1)
    base = rng.normal(70, 8, 40)
    a = [_Fake(v) for v in base]
    b = [_Fake(v + 10.0) for v in base]
    assert not checks.check_null_contrast_is_null(a, b)["pass"]


def test_detectable_difference_shrinks_with_more_subjects():
    rng = np.random.default_rng(2)
    base = rng.normal(70, 8, 40)
    a = [_Fake(v) for v in base]
    b = [_Fake(v + n) for v, n in zip(base, rng.normal(0, 3, 40))]
    small = minimum_detectable_difference(a, b, n_subjects=20)["value"]
    large = minimum_detectable_difference(a, b, n_subjects=100)["value"]
    assert large < small
    assert small / large == pytest.approx(np.sqrt(5), rel=0.01)


def test_the_known_answer_check_rejects_no_effect():
    same = [_Fake(70.0) for _ in range(20)]
    assert not checks.check_closing_the_loop_improves_time_in_range(same, same)["pass"]


def test_the_known_answer_check_rejects_an_implausible_effect():
    open_arm = [_Fake(30.0) for _ in range(20)]
    loop_arm = [_Fake(95.0) for _ in range(20)]
    assert not checks.check_closing_the_loop_improves_time_in_range(open_arm, loop_arm)["pass"]


def test_the_known_answer_check_accepts_a_plausible_effect():
    open_arm = [_Fake(68.0) for _ in range(20)]
    loop_arm = [_Fake(80.0) for _ in range(20)]
    assert checks.check_closing_the_loop_improves_time_in_range(open_arm, loop_arm)["pass"]


def test_the_sensor_layer_does_not_feed_back():
    name = population.names("adult")[0]
    assert checks.check_layers_are_isolated(name, days=2)["pass"]


def test_a_quiet_subject_holds_its_fasting_glucose():
    name = population.names("adult")[0]
    assert checks.check_quiet_subject_holds(name, days=1)["pass"]


def test_every_check_returns_the_same_shape():
    r = checks.check_steady_state_closure()
    assert set(r) == {"check", "level", "value", "target", "pass", "note"}
    assert isinstance(r["check"], str) and isinstance(r["level"], int)
