"""Insulin absorption and action in S2008, measured by euglycaemic clamp.

The audit's first entry found the model conservative about disposing of glucose by the
glucose-driven route, at about a third of the published human glucose effectiveness. That runs
against the residual rather than explaining it, and it leaves the insulin-driven route as the one
major flux this package has never measured against published data. It is also the route the loop
acts through, and the route that absorbed all three input-side perturbations tried against the
residual: weakening the correction factor, withholding meal boluses, and raising night intake.

So this reproduces the measurement the insulin literature is built on. A subject is clamped at its
own basal glucose by an infusion a proportional-integral controller titrates, a subcutaneous bolus
is given, and the infusion needed to hold the clamp for the next ten hours is the action profile of
that bolus. It is the same quantity a single-dose euglycaemic clamp measures in a person: how much
glucose has to be replaced, and when.

Three things come out, and they separate absorption from action. The plasma insulin curve gives
the time to peak concentration, which is absorption alone. The glucose infusion curve gives the
time to peak effect and the time to half-maximal effect on each side, which is absorption and
action together. And the area under the infusion curve gives the total effect of the dose.

Insulin sensitivity differs between the model's subjects and the healthy volunteers most clamp
studies recruit, so the height of the curve is not directly comparable. The timings are, because
they are properties of absorption and action rather than of how much glucose a unit disposes of.

Reference: Shiramoto M, Yoshihara T, Schmider W, et al., Pharmacokinetic and pharmacodynamic
similarity between SAR341402 insulin aspart and Japan-approved NovoRapid in healthy Japanese
subjects, Scientific Reports 2021;11:22931. Thirty-nine subjects, 0.3 U/kg of insulin aspart, a
ten-hour euglycaemic clamp: peak glucose infusion 8.70 mg/kg/min, total infusion over ten hours
2054 mg/kg, and time to peak infusion 2.35 to 2.82 hours by median.

    python examples/insulin_kinetics.py --subjects 40 --workers 13
"""
import argparse
import json
import os
import sys

import numpy as np
from concurrent.futures import ProcessPoolExecutor
from simglucose.patient.t1dpatient import Action as PAction

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance
from timsim.patient import varying as V
from timsim.population import names, params_for

OUT = os.path.join(MEASUREMENTS, "insulin_kinetics.json")

DOSE_U_PER_KG = 0.3            # the reference study's dose
SETTLE_MIN = 240               # clamped at basal before the bolus, so the start is a steady state
WATCH_MIN = 600                # ten hours after it, matching the reference clamp


def clamp_bolus(name, dose=DOSE_U_PER_KG):
    """One subject: settle at basal glucose, give a bolus, record the infusion holding the clamp."""
    p = V.from_population(name)
    q = p._params
    basal = q.u2ss * q.BW / 6000.0                      # U/min
    target = float(q.Gb)
    integ = 0.0
    gir, ins, act, delayed = [], [], [], []
    for m in range(SETTLE_MIN + WATCH_MIN):
        g = float(p.observation.Gsub)
        err = target - g
        integ = float(np.clip(integ + 0.05 * err, -20.0, 60.0))
        rate = float(np.clip(0.5 * err + integ, 0.0, 60.0))
        bolus = dose * q.BW if m == SETTLE_MIN else 0.0
        p.step(PAction(CHO=0.0, insulin=basal + bolus))
        p.state[3] += rate                              # mg/kg over one minute
        p._odesolver.set_initial_value(p.state, p._odesolver.t)
        if m >= SETTLE_MIN:
            gir.append(rate)
            # State 5 is plasma insulin in pmol/kg, state 6 is insulin action X, the quantity
            # multiplying Vmx in utilisation, and state 8 is the doubly delayed signal `Id` that
            # suppresses production. All three are recorded because they answer different
            # questions: how fast the dose arrives, how fast it acts on uptake, and how fast it
            # acts on the liver. Reading state 8 as plasma insulin gives a peak near 220 minutes,
            # which is the delay chain rather than the absorption.
            ins.append(float(p.state[5]))
            act.append(float(p.state[6]))
            delayed.append(float(p.state[8]))
        elif m == SETTLE_MIN - 1:
            baseline_gir = rate
    g = np.asarray(gir, float)
    # The clamp is already holding a steady infusion before the bolus, since basal insulin alone
    # needs some glucose to hold a subject at its own Gb. The bolus's effect is the rise above
    # that, so the baseline is subtracted rather than left in the area.
    g = g - baseline_gir
    i = np.asarray(ins, float)
    x = np.asarray(act, float)
    dly = np.asarray(delayed, float)
    peak = float(g.max())
    tmax = int(np.argmax(g))
    half = peak / 2.0
    above = np.flatnonzero(g >= half)
    early = int(above[0]) if len(above) else -1
    late = int(above[-1]) if len(above) else -1
    # Duration of action: when the effect has fallen back to a twentieth of its peak and stays
    # there. Quoted rather than "when it reaches zero" because the tail is asymptotic.
    tail = np.flatnonzero(g >= peak * 0.05)
    return {"name": name, "baseline_gir": float(baseline_gir),
            "gir_max": peak, "gir_tmax_min": tmax,
            "gir_auc_10h": float(g.sum()),               # mg/kg, one-minute steps
            "t_early_half_min": early, "t_late_half_min": late,
            "duration_min": int(tail[-1]) if len(tail) else -1,
            "ins_tmax_min": int(np.argmax(i)),
            "act_tmax_min": int(np.argmax(x)),
            "delayed_tmax_min": int(np.argmax(dly)),
            "gir_curve_hourly": [float(g[k:k + 60].mean())
                                 for k in range(0, WATCH_MIN, 60)]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 8)))
    ap.add_argument("--dose", type=float, default=DOSE_U_PER_KG)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    subs = names()[:a.subjects]
    print(f"{len(subs)} subjects, {a.dose} U/kg, {WATCH_MIN} min clamp, "
          f"{a.workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        rows = list(ex.map(clamp_bolus, subs))

    med = lambda k: float(np.median([r[k] for r in rows]))
    pct = lambda k, p: float(np.percentile([r[k] for r in rows], p))
    rec = {"provenance": provenance.stamp(), "n": len(rows), "dose_u_per_kg": a.dose,
           "settle_min": SETTLE_MIN, "watch_min": WATCH_MIN,
           "reference": {"study": "Shiramoto et al., Sci Rep 2021;11:22931",
                         "population": "39 healthy Japanese subjects, insulin aspart 0.3 U/kg",
                         "gir_max": 8.70, "gir_auc_10h": 2054.0,
                         "gir_tmax_hours": [2.35, 2.82]},
           "summary": {k: {"median": med(k), "p10": pct(k, 10), "p90": pct(k, 90)}
                       for k in ("gir_max", "gir_tmax_min", "gir_auc_10h",
                                 "t_early_half_min", "t_late_half_min", "duration_min",
                                 "ins_tmax_min", "act_tmax_min", "delayed_tmax_min",
                                 "baseline_gir")},
           "runs": rows}
    json.dump(rec, open(a.out, "w"), indent=1)

    print(f"\n{'quantity':28}{'median':>10}{'p10':>9}{'p90':>9}   reference")
    show = [("ins_tmax_min", "plasma insulin peak, min", "50-60 for aspart"),
            ("act_tmax_min", "uptake action peak, min", "not directly published"),
            ("delayed_tmax_min", "liver signal peak, min", "not directly published"),
            ("gir_tmax_min", "glucose infusion peak, min", "141 to 169"),
            ("t_early_half_min", "half-maximal, rising, min", "not reported"),
            ("t_late_half_min", "half-maximal, falling, min", "not reported"),
            ("duration_min", "back to a twentieth, min", "240-360 clinically"),
            ("gir_max", "peak infusion, mg/kg/min", "8.70 in healthy subjects"),
            ("gir_auc_10h", "total infusion, mg/kg", "2054 in healthy subjects")]
    for key, label, ref in show:
        print(f"{label:28}{med(key):>10.1f}{pct(key, 10):>9.1f}{pct(key, 90):>9.1f}   {ref}")

    hourly = np.asarray([r["gir_curve_hourly"] for r in rows], float)
    print(f"\nglucose infusion by hour after the bolus, mg/kg/min")
    print("  hour " + "".join(f"{h + 1:>7}" for h in range(hourly.shape[1])))
    print("  med  " + "".join(f"{v:>7.2f}" for v in np.median(hourly, axis=0)))
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
