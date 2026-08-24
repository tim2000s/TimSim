"""Fit the liver insulin delay to the measured human suppression curve, and to nothing else.

`docs/PADOVA_AUDIT.md` entry 3 measures S2008's suppression of endogenous glucose production
peaking five hours after a subcutaneous bolus and persisting past ten, against a human response
that falls 75 per cent within 30 minutes of hyperinsulinaemia and is complete by 60 (Edgerton DS
et al., Diabetes 2010;59(11):2766-2775). The pathway is `ki`, whose two-stage delay puts the
liver signal's peak at 280 minutes.

This is the fit, on the protocol the human figure comes from: a step in insulin at constant
glucose, with production read directly. Glucose is clamped so that `kp2*Gp` cannot move and
whatever production does is insulin's doing, which is what the tracer studies isolate.

The gate is fixed in the audit before this runs. At the adopted value, suppression at 30 minutes
must land between 65 and 85 per cent and suppression at 60 minutes above 90. Nothing downstream is
worth running otherwise, and the value is chosen against this curve rather than against any
glucose outcome in any cohort.

    python examples/liver_delay_fit.py --subjects 20
"""
import argparse
import json
import os
import sys

import numpy as np
from simglucose.patient.t1dpatient import Action as PAction

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance
from timsim.patient import varying as V
from timsim.population import names

OUT = os.path.join(MEASUREMENTS, "liver_delay_fit.json")

# Edgerton et al., hepatic glucose output under a step to hyperinsulinaemia.
TARGET_30 = 75.0               # per cent suppressed at 30 minutes
TARGET_60 = 99.0               # per cent suppressed at 60 minutes
GATE_30 = (65.0, 85.0)
GATE_60_MIN = 90.0

SETTLE_MIN = 300               # clamped at basal before the step, so the start is a steady state
WATCH_MIN = 180
# The step goes straight into the plasma compartment, in pmol/kg/min, because the human protocol
# infuses insulin intravenously. simglucose routes `action.insulin` through the two subcutaneous
# compartments, whose slow path has a time constant of 288 minutes, so a subcutaneous step takes
# hours to raise plasma insulin and measures absorption rather than the liver. This rate holds
# plasma insulin near 500 pmol/L, which is what a standard 1 mU/kg/min clamp reaches.
IV_PMOL_KG_MIN = 6.0


def suppression(name, scale, marks=(15, 30, 60, 90, 120, 180)):
    """Percentage suppression of production at each mark after a step in insulin.

    Glucose is held at the subject's own basal throughout, so `kp2*Gp` is constant and the whole
    of the change in production is insulin acting through `kp3`.
    """
    p = V.from_population(name)
    if scale != 1.0:
        p.set_liver_delay(scale)
    q = p._params
    basal = q.u2ss * q.BW / 6000.0
    target = float(q.Gb)
    integ, base, out = 0.0, None, {}
    plasma = []
    for m in range(SETTLE_MIN + WATCH_MIN):
        g = float(p.observation.Gsub)
        err = target - g
        integ = float(np.clip(integ + 0.05 * err, -30.0, 80.0))
        rate = float(np.clip(0.5 * err + integ, 0.0, 80.0))
        step_on = m >= SETTLE_MIN
        p.step(PAction(CHO=0.0, insulin=basal))
        p.state[3] += rate
        if step_on:
            p.state[5] += IV_PMOL_KG_MIN
        p._odesolver.set_initial_value(p.state, p._odesolver.t)
        egp = max(float(q.kp1 - q.kp2 * p.state[3] - q.kp3 * p.state[8]), 0.0)
        if m == SETTLE_MIN - 1:
            base = egp
        if step_on:
            t = m - SETTLE_MIN + 1
            plasma.append(float(p.state[5]) / float(q.Vi))
            if t in marks:
                out[t] = 100.0 * (1.0 - egp / base) if base > 0 else float("nan")
    out["plasma_pmol_l"] = float(np.median(plasma))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--scales", nargs="+", type=float,
                    default=[1.0, 2.0, 4.0, 6.0, 8.0, 12.0])
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    subs = names()[:a.subjects]
    marks = (15, 30, 60, 90, 120, 180)
    rec = {"provenance": provenance.stamp(), "n": len(subs),
           "reference": {"study": "Edgerton et al., Diabetes 2010;59(11):2766-2775",
                         "suppression_30_min": TARGET_30, "suppression_60_min": TARGET_60},
           "gate": {"at_30": list(GATE_30), "at_60_min": GATE_60_MIN}, "scales": []}

    print(f"{len(subs)} subjects, step to hyperinsulinaemia at constant glucose\n")
    print(f"{'ki scale':>9}{'ki':>10}" + "".join(f"{m:>8}" for m in marks) + "   gate")
    print(f"{'':>19}" + "".join(f"{'min':>8}" for _ in marks))
    for s in a.scales:
        curves = [suppression(n, s, marks) for n in subs]
        med = {m: float(np.median([c[m] for c in curves])) for m in marks}
        plasma = float(np.median([c["plasma_pmol_l"] for c in curves]))
        ok = (GATE_30[0] <= med[30] <= GATE_30[1]) and med[60] >= GATE_60_MIN
        ki = float(np.median([float(V.from_population(n)._params["ki"]) for n in subs])) * s
        rec["scales"].append({"scale": s, "ki_median": ki, "plasma_pmol_l": plasma,
                              "suppression": med, "passes_gate": bool(ok)})
        print(f"{s:>9.1f}{ki:>10.5f}" + "".join(f"{med[m]:>8.1f}" for m in marks)
              + f"   {'pass' if ok else 'fail'}")
    print(f"\nhuman reference: {TARGET_30:.0f} per cent at 30 minutes, "
          f"complete by 60. Gate: {GATE_30[0]:.0f} to {GATE_30[1]:.0f} at 30, "
          f"above {GATE_60_MIN:.0f} at 60.")

    passing = [r for r in rec["scales"] if r["passes_gate"]]
    if passing:
        # The smallest passing scale, since the change to a published model should be the least
        # one the human curve supports rather than the one that fits it best.
        best = min(passing, key=lambda r: r["scale"])
        rec["adopted"] = best
        print(f"\nsmallest scale clearing the gate: {best['scale']:.1f}, "
              f"ki {best['ki_median']:.5f}, "
              f"{best['suppression'][30]:.0f} per cent at 30 min and "
              f"{best['suppression'][60]:.0f} at 60")
    else:
        rec["adopted"] = None
        print("\nno scale clears the gate. The delay is not the whole story on this protocol "
              "and entry 3 should not proceed to a cohort run.")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
