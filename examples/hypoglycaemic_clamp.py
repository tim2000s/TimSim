"""A stepped hyperinsulinaemic hypoglycaemic clamp, run in silico.

Endogenous glucose production in this model is `kp1 - kp2*Gp - kp3*Id`, so a figure for it
means nothing without the insulin it was measured at. The human references come from clamps,
which hold insulin high while glucose is walked down to successive plateaus, and a spontaneous
low under a closed loop is the opposite state, reached because the algorithm withdrew insulin.
Comparing the two gives a model producing four times the human figure when it in fact produces
none, which is why this reproduces the protocol rather than reading production off a run.

Insulin is infused at a fixed rate on top of basal replacement. Glucose goes into the plasma
compartment, as in the human protocol rather than as a meal, at a rate titrated by a
proportional-integral controller standing in for the operator. The last `SETTLE` minutes of
each plateau are measured, and the descent is gradual because the infusion can only add
glucose: how fast the model falls between plateaus is set by the insulin.

Run it to reproduce the calibration of `HYPO_EGP_DEFENCE` in `timsim/patient/varying.py`:

    python examples/hypoglycaemic_clamp.py

Reference: Rickels MR et al., Restoration of Glucose Counterregulation by Islet
Transplantation in Long-standing Type 1 Diabetes, Diabetes 2015;64(5):1713-1718. Twelve people
with long-standing type 1 diabetes and severe hypoglycaemia gave endogenous glucose production
of 0.59 +/- 0.12 mg/kg/min at the hypoglycaemic plateau against 1.42 +/- 0.14 in non-diabetic
controls, with no discernible glucagon response in the diabetic group.
"""
import numpy as np
from simglucose.patient.t1dpatient import Action as PAction

from timsim.patient import varying as V
from timsim.population import names

INSULIN_MU_KG_MIN = 1.0                 # the clamp's fixed insulin, on top of basal
STEPS = [(90.0, 240), (80.0, 120), (65.0, 120), (55.0, 120), (45.0, 120)]
SETTLE = 30                             # minutes at the end of each plateau that are measured
GAINS = [(0.0, 0.0), (0.0, 0.15), (0.0, 0.25), (0.0, 0.30)]

# Rickels et al., long-standing type 1 diabetes at the hypoglycaemic plateau.
HUMAN_EGP = (0.42, 0.84)
HUMAN_GIR = 3.1


def egp(p):
    """Endogenous glucose production now, in mg/kg/min, as the model computes it."""
    q = p._params
    return float(max(q.kp1 - q.kp2 * p.state[3] - q.kp3 * p.state[8], 0.0))


def uptake(p):
    """Insulin-dependent glucose utilisation now, in mg/kg/min."""
    q = p._params
    return float((q.Vm0 + q.Vmx * p.state[6]) * p.state[4] / (q.Km0 + p.state[4]))


def clamp(name, defence_gain=0.0, egp_gain=0.0, steps=STEPS, egp_floor=0.0):
    """One subject through the protocol. Returns one row per plateau.

    `egp_floor` is the minimum production during hypoglycaemia, in mg/kg/min. It is
    the one mechanism here that is not a scaling, so it is passed separately.
    """
    p = V.from_population(name)
    if defence_gain or egp_gain:
        p.set_hypo_defence(defence_gain, egp_gain)
    if egp_floor:
        p.set_egp_floor(egp_floor)
    q = p._params
    basal = q.u2ss * q.BW / 6000.0                      # U/min
    extra = INSULIN_MU_KG_MIN * q.BW / 1000.0           # mU/kg/min to U/min
    integ, rows = 0.0, []
    for target, minutes in steps:
        held = []
        for m in range(minutes):
            g = float(p.observation.Gsub)
            err = target - g
            integ = float(np.clip(integ + 0.05 * err, -8.0, 30.0))
            gir = float(np.clip(0.5 * err + integ, 0.0, 30.0))
            p.step(PAction(CHO=0.0, insulin=basal + extra))
            p.state[3] += gir                           # mg/kg over one minute
            p._odesolver.set_initial_value(p.state, p._odesolver.t)
            if m >= minutes - SETTLE:
                held.append((g, egp(p), uptake(p), gir, float(p.state[8])))
        a = np.asarray(held, dtype=float)
        rows.append({"target": target, "glucose": a[:, 0].mean(), "egp": a[:, 1].mean(),
                     "uptake": a[:, 2].mean(), "gir": a[:, 3].mean(), "id": a[:, 4].mean()})
    return rows


def main(n=20):
    subs = [s for s in names() if s.startswith("adult")][:n]
    for gain, eg in GAINS:
        out = [clamp(s, gain, eg) for s in subs]
        print(f"\nuptake defence {gain}, hepatic defence {eg}, {len(subs)} subjects")
        print(f"  {'target':>7} {'held at':>8} {'EGP':>7} {'uptake':>7} {'GIR':>7} "
              f"{'Id':>7} {'EGP p10':>8} {'EGP p90':>8} {'n zero':>7}")
        for i, (t, _) in enumerate(STEPS):
            col = lambda k: np.asarray([o[i][k] for o in out], dtype=float)
            e = col("egp")
            print(f"  {t:7.0f} {np.median(col('glucose')):8.1f} {np.median(e):7.2f} "
                  f"{np.median(col('uptake')):7.2f} {np.median(col('gir')):7.2f} "
                  f"{np.median(col('id')):7.1f} {np.percentile(e, 10):8.2f} "
                  f"{np.percentile(e, 90):8.2f} {int((e <= 0).sum()):4d}/{len(e)}")
    print(f"\n  human, long-standing type 1 diabetes: EGP {HUMAN_EGP[0]} to {HUMAN_EGP[1]}, "
          f"glucose infusion {HUMAN_GIR}, both mg/kg/min at the plateau")


if __name__ == "__main__":
    main()
