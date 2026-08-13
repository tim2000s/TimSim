"""The settings titration procedure, and the targets it gates on.

The procedure exists so that a controller is judged on settings somebody arrived at rather
than on settings that happen to be in the population table, so the tests check the rules it
follows rather than the numbers one run produces.
"""
import numpy as np
import pytest

from timsim.therapy import titrate as T


def _trace(low_frac=0.0, very_low_frac=0.0, n=10000):
    """A synthetic sensor trace with a stated share below each threshold."""
    c = np.full(n, 120.0)
    n54 = int(n * very_low_frac)
    n70 = int(n * low_frac)
    c[:n54] = 45.0
    c[n54:n54 + n70] = 62.0
    return c


def test_report_reads_the_consensus_metrics():
    r = T.consensus_report(_trace(low_frac=0.03, very_low_frac=0.005))
    assert r["tbr54"] == pytest.approx(0.5, abs=0.05)
    assert r["tbr70"] == pytest.approx(3.5, abs=0.05)
    assert r["tir"] == pytest.approx(96.5, abs=0.1)


def test_floors_are_the_published_ones():
    """Battelino et al. 2019: below 54 mg/dL under 1 per cent, below 70 under 4."""
    assert (T.TBR54_LIMIT, T.TBR70_LIMIT) == (1.0, 4.0)
    assert (T.TIR_TARGET, T.TAR250_LIMIT, T.CV_LIMIT) == (70.0, 5.0, 36.0)


def test_only_hypoglycaemia_gates_the_titration():
    """Time in range and variability are reported and do not gate.

    A subject can miss either for reasons no settings change reaches, and weakening settings
    until time in range passes would loosen every subject past the point hypoglycaemia
    required.
    """
    r = T.consensus_report(_trace(low_frac=0.005))
    assert T.hypo_floors_met(r)
    assert "tir" in T.failures(T.consensus_report(np.full(1000, 200.0)))
    assert T.hypo_floors_met(T.consensus_report(np.full(1000, 200.0)))


def test_floors_reject_a_run_over_either_limit():
    assert not T.hypo_floors_met(T.consensus_report(_trace(low_frac=0.06)))
    assert not T.hypo_floors_met(T.consensus_report(_trace(very_low_frac=0.02)))


def test_search_returns_the_weakest_settings_that_clear_the_floors():
    """Settings looser than hypoglycaemia requires cost time in range, so the search stops
    at the first scale that clears rather than at the loosest available.
    """
    seen = []

    class FakeResult:
        completed = True

        def __init__(self, cgm):
            self.cgm = cgm

    def fake_sim(name, days, seed, layers, controller, profile):
        scale = float(np.mean(profile.isf)) / _BASE_ISF[name]
        seen.append(round(scale, 3))
        low = 0.10 if scale < 1.7 else 0.01
        return FakeResult(_trace(low_frac=low))

    from timsim.therapy import profile as profile_mod
    _BASE_ISF = {"adult#001": float(np.mean(profile_mod.for_subject("adult#001").isf))}

    out = T.titrate_subject("adult#001", simulate=fake_sim)
    assert out["found"] and out["scale"] == 1.75, out["scale"]
    assert seen == [1.0, 1.25, 1.5, 1.75], seen


def test_a_subject_that_cannot_be_titrated_is_reported_rather_than_assigned():
    """Assigning the loosest settings to a subject the floors never clear would present a
    failure of the model as a settings choice.
    """
    class FakeResult:
        completed = True
        cgm = _trace(low_frac=0.20)

    out = T.titrate_subject("adult#001",
                            simulate=lambda **kw: FakeResult())
    assert out["found"] is False and out["scale"] is None
    assert len(out["trace"]) == len(T.SCALES)


def test_titration_runs_under_a_fixed_reference_regimen():
    """Not under the controller being benchmarked, which would let a controller that
    provokes hypoglycaemia earn weaker settings from the bench that is judging it.
    """
    used = []

    class FakeResult:
        completed = True
        cgm = _trace(low_frac=0.005)

    def fake_sim(name, days, seed, layers, controller, profile):
        used.append(controller)
        return FakeResult()

    T.titrate_subject("adult#001", simulate=fake_sim)
    assert used == [T.REFERENCE_DRIVER]
