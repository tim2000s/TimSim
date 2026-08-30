"""Fit the two-timescale liver against the clamp and the meal it has to satisfy together.

`docs/PADOVA_AUDIT.md` entry 3 established that no single value of `ki` works. Reproducing
Edgerton's suppression curve needs about eleven times the published rate; the meal response the
parameter was identified on is lost above twice it. The requirements do not overlap, so the
divergence is structural and the recommendation was a two-timescale liver rather than a retuned
one.

This fits that liver. Insulin reaches production through two delays: a fast one carrying a
fraction of the gain, and a slow one at the published rate carrying the rest. Two numbers have to
be chosen and they are chosen against two different measurements, in this order.

The fast rate comes from the clamp alone, on the protocol the human figure was measured on, and
never from a glucose outcome. The fraction is then swept, and the pair is judged against the two
gates the audit fixed before any of this was written: suppression at 30 minutes between 65 and 85
per cent with 60 minutes above 90, and the meal trough-to-peak within 20 minutes of the real 112.

The point of the sweep is that a fraction below one leaves part of the gain on the slow path, so
the meal response keeps whatever the slow path was carrying while the clamp sees a liver that
responds in tens of minutes. Whether any fraction satisfies both is the question, and a negative
answer is a result: it would say the divergence is not reachable by splitting the pathway either.

    python examples/liver_two_timescale.py --subjects 20
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

OUT = os.path.join(MEASUREMENTS, "liver_two_timescale.json")

# The gates, copied from the audit rather than restated, so they cannot drift with the answer.
GATE_30 = (65.0, 85.0)
GATE_60_MIN = 90.0
REAL_MEAL_TROUGH_TO_PEAK = 112.0
MEAL_TOLERANCE_MIN = 20.0

SETTLE_MIN = 300
WATCH_MIN = 180
IV_PMOL_KG_MIN = 6.0
MARKS = (15, 30, 60, 90, 120, 180)


def _clamped_patient(name, fraction, ki_scale):
    p = V.from_population(name)
    if fraction > 0.0:
        p.set_liver_two_timescale(fraction, ki_scale)
    return p


def suppression(name, fraction, ki_scale, marks=MARKS):
    """Percentage suppression of production at each mark after a step in insulin.

    Glucose is held at the subject's own basal throughout, so `kp2*Gp` is constant and the whole
    of the change in production is insulin acting through the liver. Production is read from the
    parameters the step left behind, so it includes the two-timescale correction rather than
    recomputing the published expression and missing it.
    """
    p = _clamped_patient(name, fraction, ki_scale)
    q = p._params
    kp1_pub = float(q["kp1"])          # before any correction the mechanism writes into it
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
        # Production computed from the two signals directly rather than from the patched `kp1`.
        # The patch carries a correction built at the start of the step and `state[8]` is read
        # at the end, so combining them mixes two instants: on one subject that read 77 per cent
        # suppression at 30 minutes where an equivalent plain `ki` change reads 66. Both delays
        # are advanced to the end of the step, so reading both here is consistent.
        fast_now = float(p.state[14]) if len(p.state) > 14 else float(p.state[8])
        slow_now = float(p.state[8])
        signal = fraction * fast_now + (1.0 - fraction) * slow_now
        egp = max(float(kp1_pub - q["kp2"] * p.state[3] - q["kp3"] * signal), 0.0)
        if m == SETTLE_MIN - 1:
            base = egp
        if step_on:
            t = m - SETTLE_MIN + 1
            plasma.append(float(p.state[5]) / float(q["Vi"]))
            if t in marks:
                out[t] = 100.0 * (1.0 - egp / base) if base else float("nan")
    out["plasma_pmol_l"] = float(np.median(plasma))
    return out


def meal_shape(name, fraction, ki_scale):
    """Trough to peak for a covered meal, on the protocol the audit's gate was set against.

    Delegated to `meal_with_bolus.one` rather than reimplemented. A hand-rolled version of this
    read 67 minutes for the stock model where that producer reads 102, because it settled for a
    different period, used a physiological rather than a titrated carbohydrate ratio, and took the
    peak off the absolute trace rather than off the meal's own contribution. A gate calibrated
    against one protocol says nothing about a number produced by another.
    """
    from examples.meal_with_bolus import one as meal_one
    r = meal_one(name, fast=(fraction if fraction > 0 else None),
                 fast_scale=ki_scale)
    if not r:
        return None
    return {"trough_to_peak_min": r["trough_to_peak_min"],
            "rise_per_10g": r["rise_per_10g"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--ki-scales", nargs="+", type=float, default=[10.5])
    ap.add_argument("--fractions", nargs="+", type=float,
                    default=[0.0, 0.25, 0.5, 0.7, 0.85, 1.0])
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    subs = names()[:a.subjects]
    rec = {"provenance": provenance.stamp(), "n": len(subs),
           "gate": {"at_30": list(GATE_30), "at_60_min": GATE_60_MIN,
                    "meal_trough_to_peak": REAL_MEAL_TROUGH_TO_PEAK,
                    "meal_tolerance_min": MEAL_TOLERANCE_MIN},
           "rows": []}

    print(f"{len(subs)} subjects. The fast rate is fitted on the clamp and the fraction is swept "
          f"against both gates.\n")
    print(f"{'ki x':>6}{'frac':>6}" + "".join(f"{m:>7}" for m in MARKS)
          + f"{'gate 1':>9}{'meal':>8}{'gate 2':>9}{'both':>7}")

    for ks in a.ki_scales:
        for fr in a.fractions:
            sup = [suppression(n, fr, ks) for n in subs]
            med = {m: float(np.median([c[m] for c in sup])) for m in MARKS}
            meal = [m for m in (meal_shape(n, fr, ks) for n in subs) if m]
            ttp = float(np.median([x["trough_to_peak_min"] for x in meal]))
            per10 = float(np.median([x["rise_per_10g"] for x in meal]))
            g1 = (GATE_30[0] <= med[30] <= GATE_30[1]) and med[60] >= GATE_60_MIN
            g2 = abs(ttp - REAL_MEAL_TROUGH_TO_PEAK) <= MEAL_TOLERANCE_MIN
            rec["rows"].append({"ki_scale": ks, "fraction": fr, "suppression": med,
                                "meal_trough_to_peak": ttp, "meal_rise_per_10g": per10,
                                "gate_1_clamp": bool(g1), "gate_2_meal": bool(g2),
                                "both": bool(g1 and g2)})
            print(f"{ks:>6.1f}{fr:>6.2f}" + "".join(f"{med[m]:>7.1f}" for m in MARKS)
                  + f"{'pass' if g1 else 'fail':>9}{ttp:>8.0f}"
                  + f"{'pass' if g2 else 'fail':>9}{'YES' if g1 and g2 else '':>7}")

    both = [r for r in rec["rows"] if r["both"]]
    print(f"\ngate 1: suppression at 30 min in {GATE_30[0]:.0f} to {GATE_30[1]:.0f} per cent "
          f"and at 60 min above {GATE_60_MIN:.0f}")
    print(f"gate 2: meal trough to peak within {MEAL_TOLERANCE_MIN:.0f} min of the real "
          f"{REAL_MEAL_TROUGH_TO_PEAK:.0f}")
    if both:
        best = min(both, key=lambda r: abs(r["meal_trough_to_peak"]
                                           - REAL_MEAL_TROUGH_TO_PEAK))
        print(f"\n{len(both)} of {len(rec['rows'])} combinations satisfy both. Closest on the "
              f"meal: fast fraction {best['fraction']} at {best['ki_scale']} times the published "
              f"rate, suppressing {best['suppression'][30]:.0f} per cent at 30 minutes with a "
              f"meal trough to peak of {best['meal_trough_to_peak']:.0f} min.")
        rec["adopted"] = best
    else:
        print(f"\nNo combination satisfies both gates. Splitting the pathway does not reach the "
              f"divergence either, and the finding is that the model cannot represent it.")
        rec["adopted"] = None

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
