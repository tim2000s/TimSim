"""The settings titration procedure, and the targets it gates on.

The procedure exists so that a controller is judged on settings somebody arrived at rather
than on settings that happen to be in the population table, so the tests check the rules it
follows rather than the numbers one run produces.
"""
import numpy as np
import pytest

from timsim import population
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


class _FakeResult:
    completed = True

    def __init__(self, cgm):
        self.cgm = cgm


def _recorder(clears):
    """A fake simulate that clears the floors exactly when `clears(isf, basal)` says so."""
    seen = []
    from timsim.therapy import profile as profile_mod
    base = {}

    def fake_sim(name, days, seed, layers, controller, profile):
        import numpy as np
        if name not in base:
            p0 = profile_mod.for_subject(name)
            base[name] = (float(np.mean(p0.isf)), float(np.mean(p0.basal_u_per_hour)))
        i0, b0 = base[name]
        isf = round(float(np.mean(profile.isf)) / i0, 3)
        bas = round(float(np.mean(profile.basal_u_per_hour)) / b0, 3)
        seen.append((isf, bas, controller))
        return _FakeResult(_trace(low_frac=0.005 if clears(isf, bas) else 0.10))

    return seen, fake_sim


def test_basal_is_tried_before_the_correction_factor():
    """A subject whose lows come from basal keeps its correction factor.

    Weakening the correction factor to cover a basal problem leaves the subject unable to
    correct, which under an algorithm that sizes microboluses from that factor produces a
    runaway high rather than a fixed low.
    """
    seen, fake = _recorder(lambda isf, bas: bas <= 0.9)
    out = T.titrate_subject("adult#001", simulate=fake)
    assert out["found"] and out["lever"] == "basal"
    assert out["basal_scale"] == 0.9 and out["scale"] == 1.0
    assert [b for _, b, _ in seen] == [1.0, 0.95, 0.9]
    assert {i for i, _, _ in seen} == {1.0}, "the correction factor must not move first"


def test_the_correction_factor_moves_only_when_basal_cannot_clear():
    seen, fake = _recorder(lambda isf, bas: isf >= 1.5 and bas <= 0.8)
    out = T.titrate_subject("adult#001", simulate=fake)
    assert out["found"] and out["lever"] == "basal and correction factor"
    assert out["scale"] == 1.5 and out["basal_scale"] == 0.8
    assert [b for _, b, _ in seen[:5]] == list(T.BASAL_SCALES)
    assert all(b == 0.8 for _, b, _ in seen[5:]), "basal stays at its floor while ISF moves"


def test_the_weakest_clearing_combination_is_taken():
    """Settings looser than hypoglycaemia requires cost time in range, so the search stops at
    the first combination that clears rather than the loosest available.
    """
    seen, fake = _recorder(lambda isf, bas: bas <= 0.95)
    out = T.titrate_subject("adult#001", simulate=fake)
    assert out["basal_scale"] == 0.95 and len(seen) == 2


def test_basal_reduction_is_bounded():
    """Basal here is the subject's own steady-state requirement, so a reduction beyond a fifth
    says the steady state is wrong rather than that the basal needs trimming.
    """
    assert min(T.BASAL_SCALES) == 0.8


def test_a_subject_that_cannot_be_titrated_is_reported_rather_than_assigned():
    """Assigning the loosest settings to a subject the floors never clear would present a
    failure of the model as a settings choice.
    """
    seen, fake = _recorder(lambda isf, bas: False)
    out = T.titrate_subject("adult#001", simulate=fake)
    assert out["found"] is False and out["scale"] is None and out["basal_scale"] is None
    assert len(seen) == len(T.BASAL_SCALES) + len(T.SCALES) - 1


def test_titration_runs_under_a_fixed_reference_regimen():
    """Not under the controller being benchmarked, which would let a controller that
    provokes hypoglycaemia earn weaker settings from the bench that is judging it.
    """
    seen, fake = _recorder(lambda isf, bas: True)
    T.titrate_subject("adult#001", simulate=fake)
    assert {c for _, _, c in seen} == {T.REFERENCE_DRIVER}


# ------------------------------------------------------- what the store is trusted for
def _store_with(tmp_path, name, **overrides):
    """A one-subject store carrying the current population's fingerprint."""
    import json
    rec = {"name": name, "scale": 1.0, "basal_scale": 1.0, "found": True}
    rec.update(overrides)
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(
        {"meta": {"population": T.population_fingerprint()}, "subjects": {name: rec}}))
    return str(path)


@pytest.mark.parametrize("field,value", [
    ("scale", -1.0), ("scale", 0.0), ("scale", float("nan")), ("scale", None),
    ("basal_scale", -0.5), ("basal_scale", 0.0),
])
def test_a_settings_multiplier_at_or_below_zero_is_refused(tmp_path, field, value):
    """These reach a body, so they are checked before they get there.

    A negative scale gives a negative correction factor and an algorithm dosing against it
    corrects in the wrong direction on every cycle, with every number in the output finite
    and plausible. Zero gives an infinite correction, or a subject on no basal at all.
    """
    name = population.names("adult")[0]
    path = _store_with(tmp_path, name, **{field: value})
    with pytest.raises(RuntimeError, match="titrated settings"):
        T.profile_for(name, path=path)


def test_a_basal_scale_of_zero_is_not_read_as_unscaled(tmp_path):
    """`x or 1.0` treats a stored zero as missing, which is the opposite of what it means."""
    name = population.names("adult")[0]
    with pytest.raises(RuntimeError):
        T.profile_for(name, path=_store_with(tmp_path, name, basal_scale=0.0))
    # absent and null both mean unscaled, and still do
    for override in ({}, {"basal_scale": None}):
        prof = T.profile_for(name, path=_store_with(tmp_path, name, **override))
        assert float(np.median(prof.basal_u_per_hour)) > 0


def test_the_store_is_written_atomically(tmp_path):
    """A titration takes hours; a half-written store would lose all of it."""
    import os
    path = str(tmp_path / "s.json")
    T.save([{"name": "x", "found": True, "scale": 1.0, "basal_scale": 1.0}],
           path=path, meta={"population": T.population_fingerprint()})
    assert os.path.exists(path)
    assert not os.path.exists(path + ".partial")
