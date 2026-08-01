"""The population generator is the part most able to produce plausible nonsense."""
import numpy as np
import pandas as pd
import pytest

from simperson.population import derive
from simperson.population.generate import screen


@pytest.fixture(scope="module")
def published():
    from simglucose.patient.t1dpatient import PATIENT_PARA_FILE
    return pd.read_csv(PATIENT_PARA_FILE)


def test_closure_reproduces_every_published_subject(published):
    """If the balance equations are right, closing a published subject's free parameters
    must return that subject. This is the load-bearing test of the whole generator."""
    assert derive.verify(published) < 1e-9


def test_closure_rejects_impossible_parameters(published):
    free = {k: published.iloc[0][k] for k in derive.FREE}
    free["EGPb"] = 0.5          # below insulin-independent uptake, so no steady state
    with pytest.raises(derive.NotViable):
        derive.close(free, "broken", 1)

    free = {k: published.iloc[0][k] for k in derive.FREE}
    free["kmin"] = free["kmax"] * 2
    with pytest.raises(derive.NotViable):
        derive.close(free, "broken", 1)


def test_generated_subjects_are_internally_consistent():
    from simperson import population
    if not population.available():
        pytest.skip("no population generated")
    p = population.patients()
    assert len(p) > 0
    assert np.allclose(p["x0_ 4"], p.Gb * p.Vg)
    assert np.allclose(p["x0_ 6"], p.Ib * p.Vi)
    assert np.allclose(p.kp1, p.EGPb + p.kp2 * p.Gpb + p.kp3 * p.Ib)
    assert (p.u2ss > 0).all()
    assert (p.Vm0 > 0).all()
    assert (p.Gtb > 0).all()


def test_every_shipped_subject_passes_its_own_screen():
    """A subject in the population must still pass the gate that admitted it."""
    from simperson import population
    if not population.available():
        pytest.skip("no population generated")
    p, q = population.patients(), population.therapy()
    for name in list(p.Name)[::17]:          # a spread of subjects, not all 100
        params = p.loc[p.Name == name].squeeze().to_dict()
        cr = float(q.loc[q.Name == name, "CR"].iloc[0])
        assert screen(params, cr) is None, f"{name} no longer passes"


def test_population_covers_the_three_classes():
    from simperson import population
    if not population.available():
        pytest.skip("no population generated")
    for klass in ("adult", "adolescent", "child"):
        assert len(population.names(klass)) > 0
