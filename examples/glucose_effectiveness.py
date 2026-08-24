"""Glucose effectiveness in S2008, measured by clamp rather than derived from the equations.

Six candidate explanations of this package's residual against real cohorts have been refuted, and
what stands is that the model and the loop together absorb every input-side perturbation tried: a
2.7-fold weakening of the correction factor, a third of meal boluses withheld, and a 3.6-fold rise
in night intake each moved time in range by under half a point. Removing the loop entirely still
leaves glucose falling at 44 mg/dL per hour from a high. That points at the disposal side, and the
quantity it points at is glucose effectiveness: the disposal of glucose driven by glucose itself
rather than by insulin, through suppression of endogenous production and mass-action uptake.

Deriving it from the equations is possible and unreliable. The tissue compartment has to be
assumed at quasi-steady state, the assumption is wrong by exactly the utilisation being measured,
and the error runs in the direction that would flatter the hypothesis. So this reproduces the
human protocol instead. Insulin is held at basal replacement, glucose is walked up to a series of
plateaus by an infusion a proportional-integral controller titrates, and the infusion rate needed
to hold each plateau is the disposal at that glucose. That is the measurement a hyperglycaemic
basal-insulinaemic clamp makes in a person, computed identically on both sides.

Two quantities come out. The plateau disposal in mg/kg/min, decomposed into production, uptake
and renal loss, which says where the disposal comes from. And the fractional slope between
plateaus in min^-1, which is glucose effectiveness in the units the minimal-model literature
reports it in, so the model can be set beside published values.

The protocol departs from the human one in one way worth stating. A person's clamp uses
somatostatin to suppress the islet response and replaces basal insulin by infusion; the model has
no islet response to suppress, so basal replacement alone reproduces the intended state. That
makes the simulated measurement closer to glucose effectiveness at zero insulin than the human
figure it is compared against, and the comparison carries that.

    python examples/glucose_effectiveness.py --subjects 40 --workers 13
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
from timsim.population import names

OUT = os.path.join(MEASUREMENTS, "glucose_effectiveness.json")

# Plateaus spanning the range the residual lives in, all of them above the model's own fasting
# equilibrium. That equilibrium is near 150 mg/dL at basal insulin, and an infusion can only add
# glucose, so a target below it is unreachable: the first attempt at this used 120 and the
# controller sat at zero while glucose settled wherever the model wanted it. The plateaus bracket
# the excursion peaks the residual is about, where real excursions peak at a median 209 mg/dL and
# a ninetieth percentile of 290.
#
# The durations are long because the measurement is a steady state rather than a trajectory. At
# 180 minutes the flux balance still disagreed with the infusion by 0.6 mg/kg/min, which is a
# quarter of the quantity being measured and means glucose was still moving.
STEPS = [(160.0, 480), (210.0, 480), (260.0, 480), (310.0, 480)]
SETTLE = 120                            # minutes at the end of each plateau that are measured

# How far the infusion may sit from the flux balance before the plateau is reported as unsettled.
# At a true steady state the infusion equals utilisation plus renal loss plus the
# insulin-independent term minus production, so a gap between them is glucose still moving.
BALANCE_TOLERANCE = 0.15                # mg/kg/min


def egp(p):
    """Endogenous glucose production now, in mg/kg/min, as the model computes it."""
    q = p._params
    return float(max(q.kp1 - q.kp2 * p.state[3] - q.kp3 * p.state[8], 0.0))


def uptake(p):
    """Insulin-dependent glucose utilisation now, in mg/kg/min."""
    q = p._params
    return float((q.Vm0 + q.Vmx * p.state[6]) * p.state[4] / (q.Km0 + p.state[4]))


def renal(p):
    """Renal excretion now, in mg/kg/min."""
    q = p._params
    return float(max(q.ke1 * (p.state[3] - q.ke2), 0.0))


def clamp(name, steps=STEPS):
    """One subject through the protocol. Returns one row per plateau."""
    p = V.from_population(name)
    q = p._params
    basal = q.u2ss * q.BW / 6000.0                      # U/min, replacement only
    integ, rows = 0.0, []
    for target, minutes in steps:
        held = []
        for m in range(minutes):
            g = float(p.observation.Gsub)
            err = target - g
            integ = float(np.clip(integ + 0.05 * err, -8.0, 40.0))
            gir = float(np.clip(0.5 * err + integ, 0.0, 40.0))
            p.step(PAction(CHO=0.0, insulin=basal))
            p.state[3] += gir                           # mg/kg over one minute
            p._odesolver.set_initial_value(p.state, p._odesolver.t)
            if m >= minutes - SETTLE:
                held.append((g, egp(p), uptake(p), renal(p), gir, float(p.state[8])))
        a = np.asarray(held, dtype=float)
        # The infusion holding a plateau is the net disposal at that glucose, which is what the
        # human clamp reports. At a steady state it equals utilisation plus renal loss plus the
        # insulin-independent term minus production, so the gap between the two says whether the
        # plateau settled. A plateau that did not settle is reported as such rather than averaged
        # into the result, because a trajectory read as a steady state is the defect this
        # measurement exists to avoid.
        gir, egp_, upt, ren = (float(a[:, 4].mean()), float(a[:, 1].mean()),
                               float(a[:, 2].mean()), float(a[:, 3].mean()))
        balance = upt + ren + float(q.Fsnc) - egp_
        rows.append({"target": target, "glucose": float(a[:, 0].mean()),
                     "egp": egp_, "uptake": upt, "renal": ren, "gir": gir,
                     "gir_sd": float(a[:, 4].std()), "id": float(a[:, 5].mean()),
                     "balance": balance, "residual": gir - balance,
                     "settled": bool(abs(gir - balance) <= BALANCE_TOLERANCE
                                     and abs(a[:, 0].mean() - target) <= 5.0)})
    return rows


def _one(name):
    """Every input travels in the job, since macOS spawns rather than forks (issue 30)."""
    return clamp(name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 8)))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    subs = names()[:a.subjects]
    print(f"{len(subs)} subjects, {len(STEPS)} plateaus, on {a.workers} workers", flush=True)
    if a.workers > 1:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            out = list(ex.map(_one, subs))
    else:
        out = [_one(s) for s in subs]

    rec = {"provenance": provenance.stamp(), "subjects": subs, "n": len(subs),
           "steps": [t for t, _ in STEPS], "settle_min": SETTLE, "plateaus": [], "slopes": []}

    print(f"\n{'target':>7}{'held':>8}{'GIR':>8}{'EGP':>8}{'uptake':>8}{'renal':>8}"
          f"{'GIR p10':>9}{'GIR p90':>9}{'settled':>9}")
    for i, (t, _) in enumerate(STEPS):
        col = lambda k: np.asarray([o[i][k] for o in out], float)
        settled = int(sum(o[i]["settled"] for o in out))
        row = {"target": t, "glucose": float(np.median(col("glucose"))),
               "gir": float(np.median(col("gir"))), "egp": float(np.median(col("egp"))),
               "uptake": float(np.median(col("uptake"))),
               "renal": float(np.median(col("renal"))),
               "residual": float(np.median(col("residual"))),
               "gir_p10": float(np.percentile(col("gir"), 10)),
               "gir_p90": float(np.percentile(col("gir"), 90)),
               "settled": settled, "n": len(out)}
        rec["plateaus"].append(row)
        print(f"{t:>7.0f}{row['glucose']:>8.1f}{row['gir']:>8.2f}{row['egp']:>8.2f}"
              f"{row['uptake']:>8.2f}{row['renal']:>8.2f}"
              f"{row['gir_p10']:>9.2f}{row['gir_p90']:>9.2f}{f'{settled}/{len(out)}':>9}")
    if any(p["settled"] < p["n"] for p in rec["plateaus"]):
        print("\nnote: plateaus not settled in every subject. A plateau is settled when the "
              "infusion matches the flux balance to within "
              f"{BALANCE_TOLERANCE} mg/kg/min and glucose is within 5 mg/dL of target.")

    # Glucose effectiveness between consecutive plateaus, per subject, in min^-1. The disposal
    # is per kilogram and the glucose per decilitre, so dividing by the distribution volume Vg
    # turns mg/kg/min per mg/dL into a fractional rate.
    from timsim.population import params_for
    print(f"\n{'from':>6}{'to':>6}{'d(disposal)':>13}{'dG':>7}{'SG min^-1':>12}{'IQR':>20}")
    for i in range(len(STEPS) - 1):
        sg = []
        for name, o in zip(subs, out):
            vg = float(params_for(name)["Vg"])
            dn = o[i + 1]["gir"] - o[i]["gir"]
            dg = o[i + 1]["glucose"] - o[i]["glucose"]
            if dg > 1.0:
                sg.append(dn / dg / vg)
        sg = np.asarray(sg, float)
        row = {"from": STEPS[i][0], "to": STEPS[i + 1][0], "n": len(sg),
               "sg_median": float(np.median(sg)),
               "sg_iqr": [float(np.percentile(sg, 25)), float(np.percentile(sg, 75))]}
        rec["slopes"].append(row)
        dn = rec["plateaus"][i + 1]["gir"] - rec["plateaus"][i]["gir"]
        dg = rec["plateaus"][i + 1]["glucose"] - rec["plateaus"][i]["glucose"]
        iqr = f"{row['sg_iqr'][0]:.5f} to {row['sg_iqr'][1]:.5f}"
        print(f"{STEPS[i][0]:>6.0f}{STEPS[i + 1][0]:>6.0f}{dn:>13.2f}{dg:>7.1f}"
              f"{row['sg_median']:>12.5f}{iqr:>20}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
