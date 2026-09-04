"""A carbohydrate estimate centred below the plate, measured against the whole table.

Pre-registered 4 September 2026, before the run. The commit that adds this file is the record
of what was predicted.

What is being tested. The person template announces a meal at `grams * CARB_ESTIMATE_BIAS *
lognormal`, with the bias at 1.0, so the estimate is centred on the plate and only its spread
is wrong. Two things say that centre is too high. The template's own meal schedule was set to
192 g a day where the real record logs 162, on the stated ground that logged grams under-state
eaten grams (`simulation/run.py`, above `DEFAULT_MEALS`), and the ratio between those is 0.84.
And the counting literature the template cites reports the direction as well as the spread:
Brazeau et al. (2013) and Meade and Rushton (2016) both find meals under-counted more often
than over-counted. So the assumption is already in the repository, applied to the plate and
not to the entry, and this arm applies it to the entry as well. The value is fixed at 0.84
from the schedule's own ratio and is not tuned to anything measured here. It is a modelling
choice: the ratio was set by holding intake at the old template's level, and no per-meal
record of plate against entry exists on the real side to measure the centre from.

Where the target statistic sits. Under oref0 SMB on the announced record at a 240 minute
window the covered rise reads 11.4 mg/dL per 10 entered grams against the real Loop 16.5
(`sim_meal_shape_announced_oref.json`, `real_meal_shape.json`).

Predictions, stated before the run.

1. Rise per entered 10 g rises by at least the denominator factor, 1 / 0.84, so from 11.4 to
   no less than 13.6 at 240 min, and by more than that because the bolus sized from the entry
   is 16 per cent smaller. The covered stratum moves; the uncovered stratum, which receives no
   bolus, moves only through the denominator on the few subjects who have one.
2. Rise per eaten 10 g rises by the bolus part alone, so by less than the entered rise does.
3. Time above 180 mg/dL rises and time below 70 falls, under the reference loop and under
   oref0 SMB, since less insulin is delivered against the same meals. Time in range falls.
4. On the signature table under the reference loop, glucose variability and the rise tail
   move up; the autocorrelations, the diurnal amplitude, the hypoglycaemia recovery and
   rebound, the compression rate and the sensor jitter move by less than their bootstrap
   intervals, because none of them reads the meal bolus directly.

What would count. The arm is adopted only if the covered rise at 240 min closes more than half
of its gap to real, so reads above 13.9, and no signature that is inside `REAL_RANGE` at a bias
of 1.0 leaves it at 0.84. Adopting it changes what the titration is made on, so adoption means
retitration, and the settings sweep and every benchmark bound to the store are repeated.
Prediction 1's floor is arithmetic and cannot fail; the test is in the size of the excess over
it and in predictions 3 and 4.

This file measures predictions 3 and 4 under the reference loop, paired per subject on the
first forty dosable adults. `examples/sim_meal_shape.py --carb-bias 0.84` measures predictions
1 to 3 under oref0 SMB, and `examples/meal_record_pairing.py` pairs its records.

    python examples/carb_bias.py --subjects 40 --days 28

Result, 4 September 2026, after the run. The predictions above are as they were written. The
base read at the time of writing, 11.4, was the whole-panel median; the paired panel of 32
subjects that completed both biases under oref0 SMB reads 11.2 covered at 240 min, so the
arithmetic floor for that panel is 13.3 and the adoption threshold stays at 13.9.

1. Covered rise per entered 10 g moved from 11.2 to 12.8, +1.8 [0.8, 2.8] paired on 32
   (`meal_bias_pairing_announced.json`). That is below the floor of 13.3, so the excess over
   the denominator was negative rather than positive: the smaller bolus did not add to the
   rise on this record. Grams entered per meal fell 4.3 [2.3, 5.7] from 50.8 as the bias
   requires.
2. Covered rise per eaten 10 g moved from 11.0 to 10.4, -0.2 [-0.7, 0.7] paired on 32
   (`meal_bias_pairing_eaten.json`). The prediction was a rise smaller than the entered one,
   and there was none. Under oref0 SMB the super micro boluses replace the 16 per cent the
   entry no longer asks for within the window, so the bolus part of prediction 1 was absent
   for the same reason.
3. Failed under both controllers. Reference loop, paired on 40 (`carb_bias.json`): time above
   180 mg/dL -0.09 [-0.48, 0.57] percentage points of 20.7, time below 70 -0.14 [-0.33,
   0.07] of 1.30, time in range +0.27 [-0.35, 0.43] of 77.3, insulin -0.48 U/day [-0.97,
   -0.04] of 55.9. oref0 SMB, paired on 33: time above 180 +0.43 [-0.21, 1.02] of 10.9, time
   below 70 -0.07 [-0.30, 0.20] of 3.90, time in range -0.27 [-1.25, 0.98], insulin -0.44
   U/day [-0.97, 0.17] of 69.1. The insulin fell by less than 1 per cent where the entry fell
   by 16, and nothing on the outcome side moved outside its interval. Under oref0 SMB the
   terminations changed rather than the outcome: adult#004 and adult#006 ended hyperglycaemic
   at 0.84 on days 19.9 and 36.8 having completed at 1.0, adult#017 ended low, and adult#039
   completed at 0.84 having ended at 1.0.
4. Held for the variability and tail and for most of the rest, in that no signature moved past
   the base bootstrap interval. Two crossed a range edge without a move that size: the
   hypoglycaemia rebound went from 28.5 per cent, inside the real range, to 37.7, outside it
   (base interval 21.7 to 39.2), and the diurnal amplitude went from 32.5, outside, to 32.7,
   inside.

Against the rule as registered the arm fails on both counts: 12.8 against 13.9, and one
signature inside the real range at 1.0 is outside it at 0.84. The parameter stays at 1.0 and
no retitration follows. The rise gap to the real record (issue 51) is not the estimate centre.
"""
import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from timsim.analysis import signatures

OUT = os.path.join(MEASUREMENTS, "carb_bias.json")
WORKERS = 7
BIASES = (1.0, 0.84)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--controller", default="reference")
    ap.add_argument("--biases", nargs="+", type=float, default=list(BIASES))
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from timsim.simulation.run import simulate_cohort, DEFAULT_LAYERS
    from timsim.therapy import titrate
    from examples.panel import dosable
    subs = dosable(a.subjects)

    rec = {"provenance": provenance.stamp(), "subjects": list(subs), "days": a.days,
           "seed": seeds.BENCH, "controller": a.controller, "biases": list(a.biases),
           "arms": {}}
    per = {}
    for b in a.biases:
        print(f"bias {b}: {len(subs)} subjects, {a.days} days, {a.controller}, "
              f"{a.workers} workers", flush=True)
        results = simulate_cohort(subs, days=a.days, seed=seeds.BENCH, layers=DEFAULT_LAYERS,
                                  controller=a.controller, profile_factory=titrate.profile_for,
                                  workers=a.workers, progress=False, carb_estimate_bias=b)
        done = [r for r in results if not r.termination]
        stats = signatures.evaluate(done)
        per[b] = {r.name: {"tir": float(r.time_in_range), "tbr": float(r.time_below_70),
                           "tbr54": float(100.0 * np.mean(r.cgm < 54)),
                           "tar": float(r.time_above_180),
                           "insulin_per_day": float(r.insulin_units / max(r.days_requested, 1)),
                           "rescues": int(r.rescue_events)}
                  for r in done}
        rec["arms"][str(b)] = {
            "signatures": {k: list(v) for k, v in stats.items()},
            "terminated": [r.name for r in results if r.termination],
            "per_subject": per[b]}
        print(signatures.report(stats))

    # Paired per subject on the panel every arm completed, so the difference is the bias
    # and not the membership.
    common = sorted(set.intersection(*[set(per[b]) for b in a.biases]))
    base = a.biases[0]
    rng = np.random.default_rng(20260904)

    def ci(d):
        bs = np.array([np.median(rng.choice(d, size=d.size, replace=True))
                       for _ in range(10000)])
        return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))

    rec["paired"] = []
    print(f"\npaired on {len(common)} subjects, each bias against {base}")
    print(f"{'bias':>6}{'metric':>16}{'at base':>9}{'at bias':>9}{'diff':>8}{'95 per cent':>16}")
    for b in a.biases[1:]:
        for key in ("tir", "tbr", "tbr54", "tar", "insulin_per_day", "rescues"):
            x = np.array([[per[base][n][key], per[b][n][key]] for n in common], float)
            d = x[:, 1] - x[:, 0]
            lo, hi = ci(d)
            rec["paired"].append({"bias": b, "metric": key, "subjects": len(common),
                                  "base": float(np.median(x[:, 0])),
                                  "value": float(np.median(x[:, 1])),
                                  "paired_diff": float(np.median(d)), "ci95": [lo, hi]})
            print(f"{b:>6}{key:>16}{np.median(x[:, 0]):>9.2f}{np.median(x[:, 1]):>9.2f}"
                  f"{np.median(d):>8.2f}{f'{lo:.2f} to {hi:.2f}':>16}")

    # Signature verdicts side by side, with the movement against the base's own interval.
    print(f"\n{'signature':<12}{'real range':>14}" + "".join(f"{b:>22}" for b in a.biases)
          + "  moved past the base interval")
    rec["signature_moves"] = []
    for key in signatures.REAL_RANGE:
        vals = [rec["arms"][str(b)]["signatures"].get(key) for b in a.biases]
        if any(v is None for v in vals):
            continue
        lo, hi = signatures.REAL_RANGE[key]
        v0, l0, h0 = vals[0]
        moved = [bool(v[0] < l0 or v[0] > h0) for v in vals[1:]]
        inside = [signatures.in_real_range(key, v[0]) for v in vals]
        rec["signature_moves"].append({"key": key, "values": [v[0] for v in vals],
                                       "inside": inside, "moved": moved})
        print(f"{key:<12}{f'{lo:.2f}-{hi:.2f}':>14}"
              + "".join(f"{f'{v[0]:.2f} ' + ('in' if i else 'OUT'):>22}"
                        for v, i in zip(vals, inside))
              + "  " + ", ".join("yes" if m else "no" for m in moved))

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
