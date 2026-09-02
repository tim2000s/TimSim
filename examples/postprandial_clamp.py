"""Disposal measured where a meal actually sits: glucose and insulin both raised at once.

Two clamps exist in this repository and each varies one thing. Study 17 measured glucose
effectiveness on a hyperglycaemic clamp at basal insulin, and insulin action on a euglycaemic
clamp at 0.3 U/kg. A meal with a bolus raises both together, and Brunasso et al. (Diabetologia
2026;69:1301-1316) state that the difference matters: uptake at euglycaemic hyperinsulinaemia
"may not fully capture the postprandial hepatic glucose extraction deficit, which requires both
hyperglycaemia and hyperinsulinaemia for maximal expression". That cell has never been measured
here, and it is the cell the meal rise gap lives in.

The state is taken from Hinshaw et al. (Diabetes 2013;62:2223-2229) rather than invented, by
arithmetic on the table this package already cites. Over their six-hour window, mean glucose is
the baseline plus the incremental area divided by the window, 8.4 + 1657.5/360 = 13.0 mmol/L, and
mean insulin is 120.1 + 11808/360 = 152.9 pmol/L. Their whole-body disposal averages 8392.1/360 =
23.3 micromol/kg of fat-free mass per minute, which on their cohort's 53.6 kg against 74.7 kg of
weight is 3.01 mg/kg of body weight per minute.

So the question is narrow and answerable: held at the glucose and insulin real people had after a
meal, does this model dispose of glucose at the rate they did?

Two cells, because a single one cannot separate a wrong level from a wrong slope. The basal cell
holds 151 mg/dL and 120 pmol/L, which is where Hinshaw's participants started, against a disposal
of about 2.40 mg/kg/min implied by their 50.8 per cent rise. The postprandial cell holds 234 mg/dL
and 152.9 pmol/L against 3.01.

Glucose is held by a variable infusion as a clamp does, insulin by setting the plasma compartment
each minute, and both are held long enough for insulin action to reach steady state rather than
read off a trajectory. Disposal is `Uii + Uid`, which is what Rd means; renal excretion is
reported separately because Rd does not include it.

    python examples/postprandial_clamp.py --subjects 40
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np
from simglucose.patient.t1dpatient import Action as PAction

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance
from timsim.patient import varying as V

OUT = os.path.join(MEASUREMENTS, "postprandial_clamp.json")
SETTLE_MIN = 600
HOLD_MIN = 300
READ_LAST = 60
WORKERS = 7

# (label, glucose mg/dL, insulin pmol/L, Hinshaw's disposal in mg/kg body weight per minute)
CELLS = (("basal", 151.3, 120.1, 2.40),
         ("postprandial", 234.2, 152.9, 3.01))


def job(args):
    name, label, g_target, i_target, hold, read_last, km_scale = args
    p = V.from_population(name)
    q = p._params
    bw, Vg, Vi = float(q.BW), float(q["Vg"]), float(q["Vi"])
    basal = q.u2ss * bw / 6000.0
    for _ in range(SETTLE_MIN):
        p.step(PAction(CHO=0.0, insulin=basal))
    if km_scale != 1.0:
        p.set_disposal_curvature(km_scale)
        for _ in range(120):
            p.step(PAction(CHO=0.0, insulin=basal))

    gp_target = g_target * Vg              # mg/kg, the plasma compartment the clamp holds
    ip_target = i_target * Vi              # pmol/kg
    integ, out = 0.0, []
    for m in range(hold):
        p.step(PAction(CHO=0.0, insulin=basal))
        x = p.state
        # Insulin held by setting the plasma compartment, so the remote signal and the action
        # state equilibrate to it over the hold rather than being forced.
        x[5] = ip_target
        # Glucose held by a variable infusion, the clamp's own instrument. Proportional plus
        # integral, clipped, and the infusion is recorded because it is the measurable quantity
        # a real clamp reports.
        err = gp_target - float(x[3])
        integ = float(np.clip(integ + 0.05 * err, -60.0, 200.0))
        rate = float(np.clip(0.5 * err + integ, 0.0, 200.0))
        x[3] += rate
        p._odesolver.set_initial_value(x, p._odesolver.t)
        if m >= hold - read_last:
            uii = float(q.Fsnc)
            uid = float((q.Vm0 + q.Vmx * x[6]) * x[4] / (q.Km0 + x[4]))
            egp = max(float(q.kp1 - q.kp2 * x[3] - q.kp3 * x[8]), 0.0)
            ren = float(q.ke1 * (x[3] - q.ke2)) if float(x[3]) > float(q.ke2) else 0.0
            out.append((uii + uid, uid, egp, ren, rate, float(p.observation.Gsub)))
    a = np.asarray(out, float)
    return {"name": name, "cell": label,
            "rd": float(a[:, 0].mean()), "uid": float(a[:, 1].mean()),
            "egp": float(a[:, 2].mean()), "renal": float(a[:, 3].mean()),
            "infusion": float(a[:, 4].mean()), "held_mgdl": float(a[:, 5].mean()),
            "km_scale": km_scale}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--hold", type=int, default=HOLD_MIN)
    ap.add_argument("--km-scales", nargs="+", type=float, default=[1.0])
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, lab, g, i, a.hold, READ_LAST, k)
            for n in subs for lab, g, i, _ in CELLS for k in a.km_scales]
    with mp.Pool(a.workers) as pool:
        rows = pool.map(job, jobs)

    q = lambda v, p: float(np.percentile(np.asarray(v, float), p))
    rec = {"provenance": provenance.stamp(), "n": len(subs), "hold_min": a.hold,
           "cells": [list(c) for c in CELLS], "rows": rows, "summary": {}}

    print(f"{len(subs)} subjects, held {a.hold} min, read over the last {READ_LAST}\n")
    print(f"{'cell':>20}{'held mg/dL':>12}{'disposal p10/50/90':>26}{'Hinshaw':>10}"
          f"{'ratio':>8}{'production':>12}{'renal':>8}")
    for km in a.km_scales:
      for lab, g, i, ref in CELLS:
        r = [x for x in rows if x["cell"] == lab and x["km_scale"] == km]
        rd = [x["rd"] for x in r]
        rec["summary"][f"{lab}|km{km}"] = {"held_mgdl": q([x["held_mgdl"] for x in r], 50),
                               "rd": [q(rd, 10), q(rd, 50), q(rd, 90)], "reference": ref,
                               "ratio": q(rd, 50) / ref,
                               "egp": q([x["egp"] for x in r], 50),
                               "renal": q([x["renal"] for x in r], 50),
                               "infusion": q([x["infusion"] for x in r], 50)}
        s = rec["summary"][f"{lab}|km{km}"]
        print(f"{f'{lab} km{km}':>20}{s['held_mgdl']:>12.0f}"
              f"{f'{s[chr(114)+chr(100)][0]:.2f} / {s[chr(114)+chr(100)][1]:.2f} / {s[chr(114)+chr(100)][2]:.2f}':>26}"
              f"{ref:>10.2f}{s['ratio']:>8.2f}{s['egp']:>12.2f}{s['renal']:>8.2f}")
    print(f"\n{'km scale':>10}{'rise basal to postprandial, %':>32}{'target':>10}")
    for km in a.km_scales:
        b = rec["summary"][f"basal|km{km}"]; pp = rec["summary"][f"postprandial|km{km}"]
        print(f"{km:>10.2f}{100*(pp['rd'][1]/b['rd'][1]-1):>32.0f}{100*(3.01/2.40-1):>10.0f}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
