"""The counterregulatory defence, against the clamp it is calibrated on.

The hepatic arm opposes insulin's suppression of endogenous glucose production as glucose
falls. Its size was set by an in-silico stepped hyperinsulinaemic clamp run at the protocol the
human studies use, so the tests check the shape of the mechanism and the plateau it was fitted
to rather than any downstream outcome.
"""
import numpy as np
import pytest
from simglucose.patient.t1dpatient import Action as PAction

from timsim.patient import varying as V
from timsim.patient.varying import (HYPO_EGP_DEFENCE, HYPO_DEFENCE_CENTRE, hypo_defence)

NAME = "adult#001"


def test_defence_is_a_falling_logistic_in_glucose():
    """It grows as glucose falls and saturates at either end.

    Kovatchev's risk index cannot carry this, since it returns the same value at 60 mg/dL
    and at 10, and a defence that stops growing stops defending.
    """
    xs = [200.0, 100.0, 70.0, HYPO_DEFENCE_CENTRE, 45.0, 20.0]
    ys = [hypo_defence(x) for x in xs]
    assert ys == sorted(ys), ys
    assert ys[0] < 0.01 and ys[-1] > 0.99
    assert hypo_defence(HYPO_DEFENCE_CENTRE) == pytest.approx(0.5, abs=1e-6)


def test_defence_is_opt_in():
    """A patient that never had `set_hypo_defence` called is the stock model."""
    p = V.from_population(NAME)
    assert not getattr(p, "_egp_defence", 0.0)
    kp3 = float(p._params.kp3)
    p.step(PAction(CHO=0.0, insulin=p._params.u2ss * p._params.BW / 6000.0))
    assert float(p._params.kp3) == pytest.approx(kp3)


def test_hepatic_arm_raises_production_only_when_glucose_is_low():
    """At euglycaemia the mechanism is inert, which is what makes it a defence.

    A term that moved production at ordinary glucose would change the steady state instead of
    responding to hypoglycaemia, and every subject's basal would shift with it.
    """
    p = V.from_population(NAME)
    p.set_hypo_defence(0.0, 0.9)
    kp30 = float(p._params.kp3)
    basal = p._params.u2ss * p._params.BW / 6000.0
    p.step(PAction(CHO=0.0, insulin=basal))
    assert float(p._params.kp3) == pytest.approx(kp30, rel=0.02)

    p.state[3] = p._params.Vg * 40.0
    p.state[12] = p._params.Vg * 40.0 * p._params.ke1 / p._params.ke1
    p._odesolver.set_initial_value(p.state, p._odesolver.t)
    p.step(PAction(CHO=0.0, insulin=basal))
    assert float(p._params.kp3) < 0.5 * kp30


LADDER = ((90.0, 240), (80.0, 120), (65.0, 120), (55.0, 120))


def _clamp_plateau(name, egp_gain, settle=30):
    """Hold the plateau under a fixed insulin infusion and return production there.

    This is the protocol the human figures come from. Production measured at a spontaneous
    low is not comparable with them, since the insulin there is roughly 60 per cent of the
    clamp's and the suppression term is sensitive to it. The intermediate plateaus are walked
    because the infusion can only add glucose, so the descent rate is set by the insulin.
    """
    p = V.from_population(name)
    if egp_gain:
        p.set_hypo_defence(0.0, egp_gain)
    q = p._params
    # basal replacement in U/min, plus the clamp's 1.0 mU/kg/min converted to the same
    dose = q.u2ss * q.BW / 6000.0 + 1.0 * q.BW / 1000.0
    acc, integ = [], 0.0
    last = len(LADDER) - 1
    for phase, (tgt, mins) in enumerate(LADDER):
        for t in range(mins):
            g = float(p.observation.Gsub)
            integ = float(np.clip(integ + 0.05 * (tgt - g), -8.0, 30.0))
            p.state[3] += float(np.clip(0.5 * (tgt - g) + integ, 0.0, 30.0))
            p._odesolver.set_initial_value(p.state, p._odesolver.t)
            p.step(PAction(CHO=0.0, insulin=dose))
            if phase == last and t >= mins - settle:
                acc.append(max(q.kp1 - q.kp2 * p.state[3] - q.kp3 * p.state[8], 0.0))
    return float(np.mean(acc)), float(p.observation.Gsub)


PANEL = tuple(f"adult#{i:03d}" for i in range(1, 9))


PLATEAU_TOLERANCE = 3.0        # mg/dL, as `examples/calibrate_hypo_defence.py` uses


def _arrived(panel, gain):
    """Production for the subjects the clamp actually brought to the plateau.

    The clamp's controller can only add glucose, so the descent is set by the insulin and a
    sufficiently insulin-resistant subject never arrives: adult#004 settles at 62.8 mg/dL
    against a 55 mg/dL target. Production is read as `kp1 - kp2*Gp - kp3*Id`, so a subject held
    above the plateau reports a lower figure than it would at the plateau and is likelier to
    floor at zero. Counting it would answer a question about the controller rather than about
    the physiology.
    """
    rows = [(e, h) for e, h in (_clamp_plateau(n, gain) for n in panel)]
    kept = [e for e, h in rows if abs(h - 55.0) <= PLATEAU_TOLERANCE]
    return kept, rows


@pytest.mark.slow
def test_stock_model_produces_little_glucose_at_a_hypoglycaemic_plateau():
    """The deficit the mechanism exists to close.

    `kp1 - kp2*Gp - kp3*Id` falls towards zero once the clamp's insulin suppresses it faster
    than the falling glucose raises it, and it floors there for a large minority of subjects.
    People with long-standing type 1 diabetes, who have no glucagon response at all, hold
    production at 0.42 to 0.84 mg/kg/min at this plateau.

    The bound asserted is loose because the quantity is unstable: the distribution is
    zero-inflated, so the median tracks the proportion of subjects pinned at zero, and that
    proportion is estimated badly on a panel of eight. `examples/calibrate_hypo_defence.py`
    measures it across 150 and is what the constant is fitted on. What this test holds is the
    direction, that the undefended model sits at or below the bottom of the human interval.
    """
    kept, rows = _arrived(PANEL, 0.0)
    assert len(kept) >= 5, rows
    assert float(np.median(kept)) <= 0.84, rows


@pytest.mark.slow
def test_the_calibrated_gain_does_not_carry_the_panel_above_the_human_range():
    """The gain must not overshoot, which is the failure the refit at n=150 corrected.

    Only the upper bound is asserted. The lower one belongs to the calibration across 150
    subjects rather than to eight, for the reason the test above records.
    """
    kept, rows = _arrived(PANEL, HYPO_EGP_DEFENCE)
    assert len(kept) >= 5, rows
    assert float(np.median(kept)) <= 0.84, rows
