"""The meal-linked rise in liver production (`patient/varying.py`, MEAL_GLUCAGON_GAIN).

At gain 0 nothing may change. Switched on, a meal must raise glucose above the stock response,
`kp1` must return to its value once the pulse has passed, and intake below the gate must start no
pulse. The last guards the separation from the hypoglycaemic response, which is modelled elsewhere.
"""
import numpy as np
import pandas as pd
from simglucose.patient.t1dpatient import Action

from timsim.patient.varying import VaryingPatient
from timsim.population import params_for

NAME = "adult#034"


def run(gain, meal_g=60.0, minutes=480, basal=None, start_bg_drop=False):
    p = VaryingPatient(pd.Series(params_for(NAME)))
    if gain is not None:
        p.set_meal_glucagon(gain)
    kp1 = float(p._params["kp1"])
    u = float(params_for(NAME)["u2ss"]) * float(params_for(NAME)["BW"]) / 6000.0 if basal is None else basal
    bg, extra = [], []
    for m in range(minutes):
        cho = meal_g if m == 30 else 0.0
        p.step(Action(CHO=cho, insulin=u))
        bg.append(float(p.observation.Gsub))
        extra.append(getattr(p, "meal_glucagon_extra", 0.0))
    return p, kp1, np.array(bg), np.array(extra)


def test_gain_zero_is_stock():
    _, _, stock, _ = run(None)
    _, _, zero, _ = run(0.0)
    assert np.array_equal(stock, zero)


def test_meal_raises_glucose_and_kp1_returns():
    _, _, stock, _ = run(None)
    p, kp1, on, extra = run(1.0)
    assert on.max() > stock.max() + 5.0
    # peak of the pulse 30 min after intake, at EGPb * 60/50 for gain 1
    k = int(np.argmax(extra))
    assert 55 <= k <= 65
    assert abs(extra[k] - float(params_for(NAME)["EGPb"]) * 60.0 / 50.0) < 0.01
    assert abs(float(p._params["kp1"]) - kp1) < 1e-3 * kp1
    assert p.meal_glucagon_grams == 60.0


def test_intake_below_gate_starts_no_pulse():
    p = VaryingPatient(pd.Series(params_for(NAME)))
    p.set_meal_glucagon(1.0, min_bg=1000.0)
    for m in range(120):
        p.step(Action(CHO=20.0 if m == 5 else 0.0, insulin=0.01))
    assert p.meal_glucagon_grams == 0.0
    assert p.meal_glucagon_extra == 0.0
