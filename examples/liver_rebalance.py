"""Rebalance the liver between its glucose brake and its insulin signal, and measure the surface.

`docs/measurements/liver_brake.json` established that postprandial suppression of production here
is carried almost entirely by `kp2*Gp`, the glucose term, and that it costs 6.1 mg/dL per 10 g of
meal rise on an unbolused meal. Human suppression is carried by insulin, which does not scale with
the excursion and so does not damp it.

Three parameters move that balance and they have to move together.

`ki_scale` multiplies the rate of the delay carrying insulin to the liver. `docs/PADOVA_AUDIT.md`
entry 3 measures the published value as far too slow, peaking at five hours where Edgerton's clamp
suppresses 75 per cent inside 30 minutes, so insulin barely acts within a meal and the glucose
term does the work by default.

`kp3_scale` multiplies the size of insulin's effect on production, where `ki_scale` sets only its
speed. Suppression tops out at 24.8 per cent against Hinshaw's 43.5 to 52.3 across every speed
tried, because a faster delay delivers the same gain sooner and the gain is the binding
constraint.

`kp2_scale` multiplies the glucose term. Weakening it alone would move the fasting equilibrium,
since basal production is `kp1 - kp2*Gp - kp3*Id` at steady state, so `kp1` is compensated to hold
basal production at the value the subject was closed at. Without that every subject drifts off its
own steady state and the run measures the drift.

Speeding insulin alone makes the meal rise smaller rather than larger, which is why this is a
surface and not a fit. Freezing the insulin term on a covered meal raised the rise by 0.7 mg/dL
per 10 g, so insulin's suppression already costs rise; adding more of it costs more. The
combination worth finding is one where insulin carries the suppression Hinshaw measures while the
part that scales with the excursion shrinks.

Four things are reported for every cell, because a liver change moves all of them.

    uncovered rise    against a real 14.0 / 23.6 / 34.7 mg/dL per 10 g
    covered rise      against a real 10.7 / 16.5 / 24.0, which settings dominate rather than the
                      liver, so it is a guard rather than a target
    suppression       postprandial fall in production on a covered meal, against Hinshaw's
                      43.5 to 52.3 per cent
    fasting glucose   which must not move, since the population is closed at its steady state
    clamp 30/60 min   suppression on Edgerton's protocol, the gate audit entry 3 rests on, which
                      asks for 65 to 85 per cent at 30 minutes and above 90 at 60. A cell that
                      satisfies the meal and fails this has moved the conflict rather than
                      resolved it

    python examples/liver_rebalance.py --subjects 20
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

OUT = os.path.join(MEASUREMENTS, "liver_rebalance.json")
SETTLE_MIN = 600
WINDOW_MIN = 360
GRAMS = 50.0
WORKERS = 7
REAL_UNCOVERED = (14.0, 23.6, 34.7)
REAL_COVERED = (10.7, 16.5, 24.0)
HINSHAW_SUPPRESSION = (43.5, 52.3)


def job(args):
    name, ki_scale, kp2_scale, kp3_scale, covered, grams, settle, window = args
    p = V.from_population(name)
    q = p._params
    bw = float(q.BW)
    basal = q.u2ss * bw / 6000.0
    kp1_0, kp2_0, kp3_0 = float(q["kp1"]), float(q["kp2"]), float(q["kp3"])

    if ki_scale != 1.0:
        p.set_liver_delay(ki_scale)
    for _ in range(settle):
        p.step(PAction(CHO=0.0, insulin=basal))
    gp_b = float(p.state[3])
    g0 = float(p.observation.Gsub)

    # Hold basal production where the subject was closed: with `kp2` scaled, `kp1` absorbs the
    # difference at the basal glucose, so the fasting steady state is unchanged and only the
    # response to a deviation from it moves.
    kp2 = kp2_0 * kp2_scale
    kp3 = kp3_0 * kp3_scale
    kp1 = kp1_0 + (kp2 - kp2_0) * gp_b + (kp3 - kp3_0) * float(p.state[8])
    q["kp2"], q["kp3"], q["kp1"] = kp2, kp3, kp1

    bolus = 0.0
    if covered:
        from timsim.therapy import titrate
        bolus = grams / float(titrate.profile_for(name).cr_at(12 * 60))

    # Re-settle on the rebalanced parameters before the meal, so the meal lands on a steady state
    # rather than on whatever the parameter change left behind.
    for _ in range(120):
        p.step(PAction(CHO=0.0, insulin=basal))
    g0 = float(p.observation.Gsub)
    egp_b = max(kp1 - kp2 * float(p.state[3]) - kp3 * float(p.state[8]), 0.0)

    peak, egp_sum = g0, 0.0
    for m in range(window):
        p.step(PAction(CHO=(grams if m == 0 else 0.0),
                       insulin=basal + (bolus if m == 0 else 0.0)))
        x = p.state
        egp_sum += max(kp1 - kp2 * x[3] - kp3 * x[8], 0.0)
        peak = max(peak, float(p.observation.Gsub))

    # Edgerton's clamp on the same parameters: glucose held at basal so the whole change in
    # production is insulin, and a step in plasma insulin at the same rate the audit used.
    cl = V.from_population(name)
    cq = cl._params
    if ki_scale != 1.0:
        cl.set_liver_delay(ki_scale)
    for _ in range(settle):
        cl.step(PAction(CHO=0.0, insulin=basal))
    gpb_c = float(cl.state[3])
    kp2_c = float(cq["kp2"]) * kp2_scale
    kp3_c = float(cq["kp3"]) * kp3_scale
    kp1_c = (float(cq["kp1"]) + (kp2_c - float(cq["kp2"])) * gpb_c
             + (kp3_c - float(cq["kp3"])) * float(cl.state[8]))
    cq["kp2"], cq["kp3"], cq["kp1"] = kp2_c, kp3_c, kp1_c
    target, integ = float(cq.Gb), 0.0
    clamp = {}
    egp_ref = None
    for m in range(300):
        g = float(cl.observation.Gsub)
        integ = float(np.clip(integ + 0.05 * (target - g), -30.0, 80.0))
        rate = float(np.clip(0.5 * (target - g) + integ, 0.0, 80.0))
        cl.step(PAction(CHO=0.0, insulin=basal))
        cl.state[3] += rate
        if m >= 120:
            cl.state[5] += 6.0
        cl._odesolver.set_initial_value(cl.state, cl._odesolver.t)
        e = max(kp1_c - kp2_c * cl.state[3] - kp3_c * cl.state[8], 0.0)
        if m == 119:
            egp_ref = e
        for mark in (30, 60):
            if m == 119 + mark:
                clamp[mark] = 100.0 * (1.0 - e / egp_ref) if egp_ref else float("nan")

    base_auc = egp_b * window
    return {"name": name, "ki_scale": ki_scale, "kp2_scale": kp2_scale,
            "clamp_30": clamp.get(30, float("nan")), "clamp_60": clamp.get(60, float("nan")),
            "kp3_scale": kp3_scale, "covered": bool(covered),
            "rise_per_10g": (peak - g0) / (grams / 10.0), "fasting_mgdl": g0,
            "egp_basal": egp_b,
            "suppression_pct": 100.0 * (base_auc - egp_sum) / base_auc if base_auc else float("nan")}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--ki-scales", nargs="+", type=float, default=[1.0, 4.0, 10.5])
    ap.add_argument("--kp2-scales", nargs="+", type=float, default=[1.0, 0.5])
    ap.add_argument("--kp3-scales", nargs="+", type=float, default=[1.0, 2.0, 4.0, 8.0])
    ap.add_argument("--grams", type=float, default=GRAMS)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, ki, k2, k3, cov, a.grams, SETTLE_MIN, WINDOW_MIN)
            for n in subs for ki in a.ki_scales for k2 in a.kp2_scales
            for k3 in a.kp3_scales for cov in (False, True)]
    print(f"{len(subs)} subjects, {len(jobs)} runs on {a.workers} workers")
    with mp.Pool(a.workers) as pool:
        rows = pool.map(job, jobs)

    by = {}
    for r in rows:
        by.setdefault((r["ki_scale"], r["kp2_scale"], r["kp3_scale"], r["covered"]),
                      []).append(r)
    q = lambda v, p: float(np.percentile(np.asarray(v, float), p))

    rec = {"provenance": provenance.stamp(), "n": len(subs), "grams": a.grams,
           "window_min": WINDOW_MIN, "real_uncovered": list(REAL_UNCOVERED),
           "real_covered": list(REAL_COVERED), "hinshaw_suppression": list(HINSHAW_SUPPRESSION),
           "cells": []}

    print(f"\n{'ki x':>6}{'kp2 x':>7}{'kp3 x':>7}{'uncovered rise':>18}{'covered rise':>16}"
          f"{'suppression %':>15}{'fasting':>9}{'clamp 30':>10}{'clamp 60':>10}")
    for ki in a.ki_scales:
      for k3 in a.kp3_scales:
        for k2 in a.kp2_scales:
            u = [r["rise_per_10g"] for r in by[(ki, k2, k3, False)]]
            c = [r["rise_per_10g"] for r in by[(ki, k2, k3, True)]]
            s = [r["suppression_pct"] for r in by[(ki, k2, k3, True)]]
            f = [r["fasting_mgdl"] for r in by[(ki, k2, k3, False)]]
            c30 = [r["clamp_30"] for r in by[(ki, k2, k3, False)]]
            c60 = [r["clamp_60"] for r in by[(ki, k2, k3, False)]]
            cell = {"ki_scale": ki, "kp2_scale": k2, "kp3_scale": k3,
                    "uncovered_rise": [q(u, 10), q(u, 50), q(u, 90)],
                    "covered_rise": [q(c, 10), q(c, 50), q(c, 90)],
                    "suppression_pct": [q(s, 10), q(s, 50), q(s, 90)],
                    "fasting_mgdl": [q(f, 10), q(f, 50), q(f, 90)],
                    "clamp_30": q(c30, 50), "clamp_60": q(c60, 50)}
            rec["cells"].append(cell)
            print(f"{ki:>6.1f}{k2:>7.2f}{k3:>7.1f}{q(u,50):>18.1f}{q(c,50):>16.1f}"
                  f"{q(s,50):>15.1f}{q(f,50):>9.1f}{q(c30,50):>10.1f}{q(c60,50):>10.1f}")
        print()
    print(f"{'real':>20}{REAL_UNCOVERED[1]:>18.1f}{REAL_COVERED[1]:>16.1f}"
          f"{f'{HINSHAW_SUPPRESSION[0]:.0f}-{HINSHAW_SUPPRESSION[1]:.0f}':>15}"
          f"{'':>9}{'65-85':>10}{'>90':>10}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
