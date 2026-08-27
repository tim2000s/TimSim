"""Three candidate explanations for a meal-timing discrepancy, each swept and each measured.

Study 07 rests on refusing three mechanisms: that simulated meals peak at the wrong time because
absorption is too fast, because the bolus arrives at the wrong moment, or because the dose is the
wrong size. Those refutations were recorded in a source comment in `person/behaviour.py` and had
no producer, so they could not be reproduced and had drifted several configurations out of date.
This is the producer.

Two of the three are swept here. Absorption is scaled through `meal_absorption_scale`, which
multiplies gastric emptying and intestinal absorption together, so a scale below one slows the meal
and a scale above one speeds it. Dose size is scaled through the carbohydrate estimate the
algorithm is told about, which is what a person under-counting a meal produces.

The third, bolus timing, is not a sweep. It is a measurement of when real people actually bolus
relative to their carbohydrate entry, and it lives in the extraction over the Nightscout records
rather than in the simulator.

The measurement is the uncovered meal response as `meal_response.py` computes it, differenced
against the same subject eating nothing so the counterfactual drift is removed. Both time to peak
and rise per gram are reported, because a mechanism that moves the peak by changing how much
glucose the meal produces has not explained the timing.

    python examples/meal_mechanisms.py --subjects 40 --workers 7
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from examples.meal_response import MEAL_HOUR, WINDOW_MIN, DAYS, BasalOnly

OUT = os.path.join(MEASUREMENTS, "meal_mechanisms.json")
GRAMS = 50.0
ABSORPTION = (0.33, 0.5, 1.0, 2.0)
BIAS = (0.7, 0.8, 0.9, 1.0)


def _trace(name, prof, meals, absorption, bias):
    """One run. The physiology layer is on because that is where absorption lives.

    `meal_absorption_scale` is applied inside the physiology block in `simulation/run.py`, on the
    reasoning that meal-to-meal absorption variation is a property of the gut. So a run with no
    layers ignores the argument entirely, and the first version of this sweep returned the same
    time to peak at every scale from 0.33 to 2.0, which is the signature of a parameter that never
    reached the worker rather than a mechanism that does nothing.

    Turning the layer on brings sensitivity variation with it, which is unwanted here. The
    variation is switched off by setting its coefficients to zero rather than by leaving the layer
    off, so absorption is the only thing that differs between arms.
    """
    from timsim.simulation.run import simulate
    r = simulate(name, days=DAYS, seed=seeds.BENCH, layers=("physiology",),
                 controller=BasalOnly(prof), profile=prof, meals=meals,
                 meal_absorption_scale=absorption, meal_absorption_cv=0.0,
                 si_slow_cv=0.0, si_interday_cv=0.0)
    return np.asarray(r.bg, float), np.asarray(r.minutes, float)


def one(job):
    """One subject at one absorption scale and one dose scale."""
    name, absorption, bias = job
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    # The dose the algorithm is told about scales, not the food. That is what a person
    # under-counting produces: the gut receives the meal and the bolus covers less of it.
    grams = GRAMS
    with_meal, minutes = _trace(name, prof, [(MEAL_HOUR, grams, False)], absorption, bias)
    without, _ = _trace(name, prof, [], absorption, bias)
    n = min(len(with_meal), len(without), len(minutes))
    i0 = int(np.searchsorted(minutes[:n], MEAL_HOUR * 60.0))
    if i0 >= n:
        return None
    i1 = min(max(int(np.searchsorted(minutes[:n], MEAL_HOUR * 60.0 + WINDOW_MIN)), i0 + 1), n)
    delta = with_meal[i0:i1] - without[i0:i1]
    k = int(np.argmax(delta))
    return {"name": name, "absorption": absorption, "bias": bias,
            "time_to_peak_min": float(minutes[i0 + k] - minutes[i0]),
            "rise": float(delta[k]),
            "rise_per_10g": float(delta[k] / (grams / 10.0))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 7)))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects, "adult")
    jobs = [(n, s, 1.0) for s in ABSORPTION for n in subs]
    print(f"{len(subs)} subjects, {len(ABSORPTION)} absorption scales, "
          f"{len(jobs)} runs on {a.workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        rows = [r for r in ex.map(one, jobs) if r]

    rec = {"provenance": provenance.stamp(), "grams": GRAMS, "n_subjects": len(subs),
           "absorption_scales": list(ABSORPTION), "rows": rows}
    print(f"\n{'absorption':>11}{'n':>5}{'time to peak':>14}{'IQR':>16}{'rise per 10 g':>15}")
    for s in ABSORPTION:
        v = [r for r in rows if r["absorption"] == s]
        if not v:
            continue
        tp = np.array([r["time_to_peak_min"] for r in v])
        rp = np.array([r["rise_per_10g"] for r in v])
        print(f"{s:>11.2f}{len(v):>5}{np.median(tp):>14.0f}"
              f"{f'{np.percentile(tp,25):.0f}-{np.percentile(tp,75):.0f}':>16}"
              f"{np.median(rp):>15.2f}")
    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
