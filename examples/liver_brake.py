"""Whether the liver's glucose-driven brake is what makes simulated meal excursions small.

Production in S2008 is `kp1 - kp2*Gp - kp3*Id`, floored at zero, so it falls as glucose rises.
The fall is largest exactly at the peak of a meal, which makes it a proportional brake on the
excursion driven by the excursion itself. Human suppression of production is driven by insulin,
which does not scale with how high the glucose went.

`docs/measurements/hinshaw_meal.json` measures both halves of that. On a 50 g meal the model
suppresses production 18.6 per cent against a measured 43.5 to 52.3, so it suppresses too little
in total, and adding a meal bolus takes suppression down to 12.8 per cent because the bolus lowers
glucose and releases the brake. Too little suppression overall, applied at the wrong moment.

This measures what the brake costs the rise. Three arms on the same subjects:

    stock        as it ships
    no_brake     `kp2*Gp` held at its pre-meal value, so production responds to insulin alone
    no_insulin   `kp3*Id` held at its pre-meal value, so production responds to glucose alone

each on an uncovered meal and on one covered from the subject's titrated ratio. The covered pair
is what makes `no_insulin` mean anything: with no bolus, plasma insulin never moves, the frozen
term equals the live one, and the arm is identical to stock by construction rather than by
finding. That is the signature `docs/ISSUES.md` names, and it was hit here on the first run.

The brake is removed by compensating in `kp1` each minute rather than by editing the model, since
`kp1 + kp2*(Gp - Gp_basal)` minus `kp2*Gp` is `kp1 - kp2*Gp_basal` exactly. The same trick as
`set_hypo_defence` uses on `kp3`, and it leaves every other flux untouched.

If the rise moves substantially towards the real one with the brake off, the liver is the reason
simulated meals are shallow and audit entries 3 and 5 are one problem. If it does not, the brake
is not load-bearing and the shortfall is somewhere this package has not looked.

    python examples/liver_brake.py --subjects 40
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

OUT = os.path.join(MEASUREMENTS, "liver_brake.json")
SETTLE_MIN = 600
WINDOW_MIN = 360
GRAMS = 50.0
ARMS = ("stock", "no_brake", "no_insulin")
WORKERS = 7
# Real per-person meal rise, `real_meal_shape.json`, Loop participants at a 240 min window,
# unbolused meals, tenth to ninetieth percentile of per-person medians, mg/dL per 10 g.
REAL_UNCOVERED = (14.0, 23.6, 34.7)


def job(args):
    name, arm, covered, grams, settle, window = args
    p = V.from_population(name)
    q = p._params
    bw = float(q.BW)
    basal = q.u2ss * bw / 6000.0
    kp1_0, kp2, kp3 = float(q["kp1"]), float(q["kp2"]), float(q["kp3"])
    bolus = 0.0
    if covered:
        from timsim.therapy import titrate
        bolus = grams / float(titrate.profile_for(name).cr_at(12 * 60))

    for _ in range(settle):
        p.step(PAction(CHO=0.0, insulin=basal))
    gp0, id0 = float(p.state[3]), float(p.state[8])
    g0 = float(p.observation.Gsub)

    peak, egp_sum = g0, 0.0
    for m in range(window):
        # Compensate in `kp1` before the step, so the frozen term applies to the interval that
        # follows it rather than the one before.
        if arm == "no_brake":
            q["kp1"] = kp1_0 + kp2 * (float(p.state[3]) - gp0)
        elif arm == "no_insulin":
            q["kp1"] = kp1_0 + kp3 * (float(p.state[8]) - id0)
        p.step(PAction(CHO=(grams if m == 0 else 0.0),
                       insulin=basal + (bolus if m == 0 else 0.0)))
        x = p.state
        egp_sum += max(float(q["kp1"]) - kp2 * x[3] - kp3 * x[8], 0.0)
        peak = max(peak, float(p.observation.Gsub))
    q["kp1"] = kp1_0
    return {"name": name, "arm": arm, "covered": bool(covered), "bolus_u": bolus,
            "rise_mgdl": peak - g0,
            "rise_per_10g": (peak - g0) / (grams / 10.0),
            "egp_auc": egp_sum, "baseline_mgdl": g0}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--grams", type=float, default=GRAMS)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, arm, cov, a.grams, SETTLE_MIN, WINDOW_MIN)
            for n in subs for arm in ARMS for cov in (False, True)]
    with mp.Pool(a.workers) as pool:
        rows = pool.map(job, jobs)
    by = {}
    for r in rows:
        by.setdefault((r["arm"], r["covered"]), {})[r["name"]] = r

    q = lambda v, p: float(np.percentile(np.asarray(v, float), p))
    rec = {"provenance": provenance.stamp(), "n": len(subs), "grams": a.grams,
           "window_min": WINDOW_MIN, "real_uncovered_rise_per_10g": list(REAL_UNCOVERED),
           "rows": rows, "arms": {}}

    print(f"{len(subs)} subjects, {a.grams:.0f} g uncovered meal, basal insulin, layers off\n")
    print(f"{'arm':>12}{'meal':>10}{'rise per 10 g, p10/50/90':>28}{'vs stock':>12}"
          f"{'production AUC':>18}")
    for cov in (False, True):
        base = [by[("stock", cov)][n]["rise_per_10g"] for n in subs]
        for arm in ARMS:
            v = [by[(arm, cov)][n]["rise_per_10g"] for n in subs]
            e = [by[(arm, cov)][n]["egp_auc"] for n in subs]
            d = np.median(np.array(v) - np.array(base))
            rec["arms"][f"{arm}|{'covered' if cov else 'uncovered'}"] = {
                "rise_per_10g": [q(v, 10), q(v, 50), q(v, 90)],
                "egp_auc": [q(e, 10), q(e, 50), q(e, 90)], "paired_vs_stock": float(d)}
            print(f"{arm:>12}{'covered' if cov else 'uncovered':>10}"
                  f"{f'{q(v,10):.1f} / {q(v,50):.1f} / {q(v,90):.1f}':>28}"
                  f"{d:>+12.1f}{f'{q(e,50):.0f}':>18}")
        print()
    print(f"{'real, Loop':>12}{'uncovered':>10}"
          f"{f'{REAL_UNCOVERED[0]:.1f} / {REAL_UNCOVERED[1]:.1f} / {REAL_UNCOVERED[2]:.1f}':>28}")
    print(f"{'real, Loop':>12}{'covered':>10}{'10.7 / 16.5 / 24.0':>28}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
