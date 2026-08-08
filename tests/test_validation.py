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


def test_the_sensor_layer_changes_the_reading_and_not_the_body():
    name = population.names("adult")[0]
    r = checks.check_the_sensor_layer_is_a_reading_and_not_a_glucose(name, days=2)
    assert r["pass"]


def test_delivery_limits_bind_on_an_algorithm_that_asks_for_too_much():
    name = population.names("adult")[0]
    assert checks.check_delivery_limits_bind(name, days=1)["pass"]


def test_a_quiet_subject_holds_its_fasting_glucose():
    name = population.names("adult")[0]
    assert checks.check_quiet_subject_holds(name, days=1)["pass"]


def test_every_check_returns_the_same_shape():
    r = checks.check_steady_state_closure()
    assert set(r) == {"check", "level", "value", "target", "pass", "note"}
    assert isinstance(r["check"], str) and isinstance(r["level"], int)


def test_the_dclp3_split_is_reproducible_and_fingerprinted():
    """The held-out set has to be recoverable, or it cannot be scored once at the end."""
    from timsim.validation import dclp3
    if not dclp3.available():
        import pytest as _p
        _p.skip("DCLP3 not present; set DCLP3_DIR")
    a, b = dclp3.split(), dclp3.split()
    assert a["fingerprint"] == b["fingerprint"] == dclp3.SPLIT_FINGERPRINT
    assert a["held_out"] == b["held_out"]
    assert not set(a["calibration"]) & set(a["held_out"])
    # a different seed must give a different sealed set, or the seal means nothing
    assert dclp3.split(seed=1)["fingerprint"] != a["fingerprint"]


def test_the_dclp3_known_answer_matches_the_trial():
    """Level 4's reference is now a randomised effect rather than a literature estimate."""
    from timsim.validation import dclp3
    k = dclp3.KNOWN_ANSWER
    assert 8.0 < k["difference"] < 20.0
    assert k["mann_whitney_p"] < 0.001
    assert abs(k["difference"] - k["trial_reported"]) < 5.0


def test_the_dclp3_reference_disagrees_where_it_is_recorded_as_disagreeing():
    """Kept as a test so the disagreement cannot quietly drift out of the documentation."""
    from timsim.analysis import signatures as S
    from timsim.validation import dclp3
    for key in dclp3.DISAGREEMENTS:
        median = dclp3.REFERENCE["CLC"][key][0]
        lo, hi = S.REAL_RANGE[key]
        assert not (lo <= median <= hi), f"{key} no longer disagrees"


def test_the_real_window_builder_matches_the_recorded_marginals():
    """`real_windows` feeds the arbiter, so its features have to be the recorded ones."""
    import numpy as np
    from timsim.validation import dclp3, replication
    if not dclp3.available():
        pytest.skip("DCLP3 not present; set DCLP3_DIR")
    w, g = replication.real_windows()
    assert len(np.unique(g)) == dclp3.REFERENCE["CLC"]["participants"]
    full, _ = replication.real_windows(max_days=None)
    # The capped sample has to stand in for the whole record, which is why it is taken from
    # the middle: the opening month reads about 2.8 mg/dL low while people settle in.
    for name in ("mean", "pct_above_180", "acf30", "acf60", "jitter"):
        i = replication.FEATURE_NAMES.index(name)
        a, b = float(np.median(w[:, i])), float(np.median(full[:, i]))
        assert abs(a - b) < max(0.02 * abs(b), 0.02), (name, a, b)


def test_capping_the_real_side_actually_caps_it():
    """Without the cap the real side outnumbers a simulated cohort about ten to one."""
    import numpy as np
    from timsim.validation import dclp3, replication
    if not dclp3.available():
        pytest.skip("DCLP3 not present; set DCLP3_DIR")
    capped, _ = replication.real_windows(max_days=28.0)
    short, _ = replication.real_windows(max_days=7.0)
    assert len(short) < len(capped)
    # a week at a twelve-hour stride is about thirteen windows a participant
    assert len(short) < 20 * dclp3.REFERENCE["CLC"]["participants"]
