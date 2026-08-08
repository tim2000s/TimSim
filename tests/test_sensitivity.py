"""The two diurnal insulin-sensitivity patterns, and what each is faithful to.

Visentin et al. (2015) publish class probabilities, a low-to-high ratio and transition
times. Those are checkable, and they are checked here, because a model taken from a paper
that quietly drifts from the paper is worse than no model from a paper at all.
"""
import numpy as np
import pytest

from timsim.patient import varying as V


def test_the_class_mix_reproduces_the_published_probabilities():
    rng = np.random.default_rng(0)
    drawn = [V.draw_si_pattern(rng, 3)[0] for _ in range(20000)]
    for cls, p in V.SI_CLASS_PROBABILITY.items():
        assert abs(drawn.count(cls) / len(drawn) - p) < 0.015, cls


def test_the_probabilities_are_a_distribution():
    assert sum(V.SI_CLASS_PROBABILITY.values()) == pytest.approx(1.0)
    assert set(V.SI_CLASS_PROBABILITY) == set(V.SI_CLASSES)


def test_every_class_is_a_distinct_pattern_of_three_meals():
    """Seven classes rather than eight, and the reason is worth pinning down.

    Levels are relative to each subject's own maximum, so all-low says the same thing as
    all-high: no pattern. Those two collapse into one class. Every other pattern stands on
    its own, including a pair like h-l-l and l-h-h, which are opposite shapes rather than
    the same shape described twice.
    """
    patterns = list(V.SI_CLASSES.values())
    assert len(patterns) == len(set(patterns)) == 7
    for pattern in patterns:
        assert len(pattern) == 3 and set(pattern) <= {"h", "l"}
    flat = [p for p in patterns if len(set(p)) == 1]
    assert flat == [("h", "h", "h")]


def test_the_low_level_sits_near_the_published_fraction_of_the_high():
    rng = np.random.default_rng(1)
    ratios = []
    for _ in range(4000):
        _, levels, _ = V.draw_si_pattern(rng, 3, normalise=False)
        lo, hi = float(np.min(levels)), float(np.max(levels))
        if hi > lo:
            ratios.append(lo / hi)
    assert abs(np.mean(ratios) - V.SI_LOW_FRACTION) < 0.05


def test_normalising_preserves_the_ratio_between_segments():
    """The rescaling exists to keep the titration; it must not change what was measured."""
    rng = np.random.default_rng(2)
    for _ in range(200):
        state = rng.bit_generator.state
        _, raw, _ = V.draw_si_pattern(rng, 3, normalise=False)
        rng.bit_generator.state = state
        _, norm, _ = V.draw_si_pattern(rng, 3, normalise=True)
        assert np.allclose(raw / raw.max(), norm / norm.max())
        assert float(np.dot(norm, V.SI_SEGMENT_HOURS)) / 24.0 == pytest.approx(1.0)


def test_the_segments_start_at_the_published_transition_times():
    levels = np.array([0.5, 1.0, 1.5])          # breakfast, lunch, dinner
    # well inside each segment, away from the blend
    assert V.si_at(7.0, levels) == pytest.approx(0.5)
    assert V.si_at(14.0, levels) == pytest.approx(1.0)
    assert V.si_at(21.0, levels) == pytest.approx(1.5)
    assert V.si_at(1.0, levels) == pytest.approx(1.5)     # dinner wraps past midnight
    assert V.SI_EDGES == (4.0, 11.0, 17.0)


def test_the_transitions_are_blended_rather_than_stepped():
    """A true step is a discontinuity in the right-hand side of a differential equation."""
    levels = np.array([0.5, 1.0, 1.5])
    assert V.si_at(4.0, levels) == pytest.approx(1.0)     # midway between 1.5 and 0.5
    grid = np.linspace(0, 24, 4000, endpoint=False)
    vals = np.array([V.si_at(h, levels) for h in grid])
    assert np.abs(np.diff(vals)).max() < 0.02


def test_the_segment_hours_add_up_to_a_day():
    assert sum(V.SI_SEGMENT_HOURS) == 24.0


def test_visentin_varies_between_subjects_where_the_cosine_does_not():
    """This is the whole point of the change, so it is the thing to test."""
    rng = np.random.default_rng(3)
    at_noon = []
    for _ in range(2000):
        _, levels, _ = V.draw_si_pattern(rng, 3)
        at_noon.append(V.si_at(12.0, levels))
    assert np.std(at_noon) > 0.2
    cosine = [1.0 - V.DIURNAL_AMPLITUDE * np.cos(2 * np.pi * (12 - 6) / 24)] * 100
    assert np.std(cosine) == 0.0


def test_an_unset_patient_is_the_stock_patient():
    from timsim.population import names, params_for
    import pandas as pd
    p = V.VaryingPatient(pd.Series(params_for(names("adult")[0])))
    assert p.sensitivity() == 1.0


def test_an_unknown_pattern_is_refused():
    from timsim.population import names, params_for
    import pandas as pd
    p = V.VaryingPatient(pd.Series(params_for(names("adult")[0])))
    with pytest.raises(ValueError):
        p.set_sensitivity(np.random.default_rng(0), 2, pattern="dawn")


def test_the_pattern_choice_reaches_the_run_and_is_recorded():
    from timsim import simulate
    from timsim.population import names
    r = simulate(names("adult")[0], days=1, seed=0, si_pattern="visentin")
    assert r.meta["si_pattern"] == "visentin"
    assert r.meta["si_class"] in V.SI_CLASSES
