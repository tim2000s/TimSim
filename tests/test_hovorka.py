"""The second body: steady state, direction of each input, and refusal of S2008-only options."""
import numpy as np
import pytest
from simglucose.patient.t1dpatient import Action

from timsim.patient.hovorka import HovorkaPatient, steady_state
from timsim.population import hovorka as pop


def _subject():
    p = {"Name": "hovorka#test", **pop.NOMINAL, "BW": 76.3, "Gb": pop.BASAL_GLUCOSE}
    for k, (mean, _, _) in pop.SF.items():
        p[k] = pop.SENSITIVITY_REDUCTION * mean
    p["u2ss"] = steady_state(p, p["Gb"])[1] * 6.0
    return p


def _run(p, minutes, insulin=None, meal_at=None, grams=0.0):
    _, u = steady_state(p, p["Gb"])
    basal = u * p["BW"] / 1000.0 if insulin is None else insulin
    patient = HovorkaPatient(p)
    out = []
    for m in range(minutes):
        cho = grams if m == meal_at else 0.0
        patient.step(Action(insulin=basal, CHO=cho))
        out.append(patient.observation.Gsub)
    return np.array(out)


def test_basal_holds_the_steady_state_for_a_day():
    g = _run(_subject(), 1440)
    assert np.abs(g - pop.BASAL_GLUCOSE).max() < 0.5


def test_insulin_lowers_and_carbohydrate_raises():
    p = _subject()
    _, u = steady_state(p, p["Gb"])
    basal = u * p["BW"] / 1000.0
    assert _run(p, 300, insulin=basal * 2.0)[-1] < pop.BASAL_GLUCOSE - 10.0
    assert _run(p, 300, meal_at=10, grams=40.0).max() > pop.BASAL_GLUCOSE + 40.0


def test_steady_state_matches_the_closed_form_basal():
    # At 115 mg/dL neither the low-glucose uptake term nor renal clearance is active, so
    # the balance reduces to EGP0 (1 - Sf3 I) = F01 + Sf1 I Q1 k2/(k12 + Sf2 I) exactly.
    p = _subject()
    x, u = steady_state(p, 115.0)
    i = u / (p["ke"] * p["VI"])
    q1 = 115.0 / 18.0 * p["VG"]
    lhs = p["EGP0"] * (1.0 - p["Sf3"] * i)
    rhs = p["F01"] + p["Sf1"] * i * q1 * (1.0 - p["k12"] / (p["k12"] + p["Sf2"] * i))
    assert lhs == pytest.approx(rhs, rel=1e-9)


def test_s2008_options_are_refused_for_a_hovorka_subject(monkeypatch):
    from timsim.simulation import run
    monkeypatch.setattr(run, "params_for", lambda name: __import__("pandas").Series(_subject()))
    with pytest.raises(ValueError, match="hypo_egp_defence"):
        run.simulate("hovorka#test", days=1, layers=(), hypo_egp_defence=0.1,
                     settings={"CF": 30.0, "CR": 8.0, "TDI": 40.0})


def test_store_follows_the_body():
    from timsim.therapy import titrate
    assert titrate.store_for("hovorka#001") == titrate.HOVORKA_STORE
    assert titrate.store_for("adult#001") == titrate.STORE


@pytest.mark.parametrize("factor", [0.5, 1.0, 2.0])
def test_a_meal_delivers_its_glucose_whatever_its_absorption_rate(factor):
    # Variation changes when a meal arrives, never how much: AG times the carbohydrate eaten.
    from timsim.patient import hovorka as h
    p = _subject()
    p["_tmaxG_meal"] = p["tmaxG"] / factor
    x = np.zeros(11)
    dose = 50.0 * h.GLUCOSE_MMOL_PER_G / p["BW"]
    absorbed, dt = 0.0, 0.25
    for k in range(int(1440 / dt)):
        d = dose if k < int(1 / dt) else 0.0
        # The meal's share of the model's own glucose derivative, read with the gut emptied.
        empty = x.copy()
        empty[h.D2] = 0.0
        absorbed += (h._rates(x, 0.0, 0.0, p, 1.0)[h.Q1]
                     - h._rates(empty, 0.0, 0.0, p, 1.0)[h.Q1]) * dt
        x = x + dt * h._rates(x, 0.0, d, p, 1.0)
    assert absorbed == pytest.approx(p["AG"] * dose, rel=0.01)


def test_one_unit_reaches_the_depot_as_1000_over_body_weight():
    from timsim.patient import hovorka as h
    p = _subject()
    patient = HovorkaPatient(p)
    before = patient.state[[h.S1, h.S2]].sum()
    patient.step(Action(insulin=1.0, CHO=0.0))
    gained = patient.state[[h.S1, h.S2]].sum() - before
    # A minute of elimination from the depot is under 2 per cent at tmaxI of 55 minutes.
    assert gained == pytest.approx(1000.0 / p["BW"], rel=0.02)


def test_each_branch_of_the_glucose_balance():
    from timsim.patient import hovorka as h
    p = _subject()
    p["_tmaxG_meal"] = p["tmaxG"]

    def dq1(g_mmol, x3):
        x = np.zeros(11)
        x[h.Q1] = g_mmol * p["VG"]
        x[h.X3] = x3
        return h._rates(x, 0.0, 0.0, p, 1.0)[h.Q1]

    # Below 4.5 mmol/L uptake scales with glucose; above 9 the kidney clears; production
    # floors at zero once insulin action passes one.
    assert dq1(3.0, 0.0) == pytest.approx(-p["F01"] * 3.0 / 4.5 + p["EGP0"])
    assert dq1(6.0, 0.0) == pytest.approx(-p["F01"] + p["EGP0"])
    assert dq1(12.0, 0.0) == pytest.approx(-p["F01"] - 0.003 * 3.0 * p["VG"] + p["EGP0"])
    assert dq1(6.0, 1.5) == pytest.approx(-p["F01"])


def test_the_activity_layer_is_refused_for_a_hovorka_subject(monkeypatch):
    from timsim.simulation import run
    monkeypatch.setattr(run, "params_for", lambda name: __import__("pandas").Series(_subject()))
    with pytest.raises(ValueError, match="activity"):
        run.simulate("hovorka#test", days=1, layers=("activity",),
                     settings={"CF": 30.0, "CR": 8.0, "TDI": 40.0})
