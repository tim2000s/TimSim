"""The model's response to an uncovered meal, measured rather than quoted.

A single meal is given on basal alone, with no bolus and no correction, and the rise above
the pre-meal baseline and the time to the peak are read off the underlying glucose. This is
a property of the metabolic model, so it is measured on the bare patient with no layers.

The comparison it is destined for is against real unbolused meals, so nothing here may
depend on the sensor: `Result.bg` carries no sensor error and is what is read.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from timsim import provenance
from timsim import seeds
from simglucose.controller.base import Action


GRAMS = (30.0, 50.0, 70.0)
MEAL_HOUR = 36.0                     # midday on the second day, after the run has settled
DAYS = 3
WINDOW_MIN = 720.0                   # twelve hours, so a late peak is never truncated
OUT = os.path.join(MEASUREMENTS, "meal_response.json")


class BasalOnly:
    """Delivers the subject's own basal and nothing else, so the meal is uncovered."""

    def __init__(self, profile):
        self.profile = profile

    def policy(self, observation, reward, done, **info):
        minute = float(info.get("clock_minutes", 0.0))
        return Action(basal=self.profile.basal_at(minute), bolus=0.0)

    def reset(self):
        pass


def _trace(name, prof, meals):
    """The glucose trace and the clock it sits on.

    The clock travels with it because the run is primed with one step before its loop, so
    sample `i` is at minute `(i + 1) * step` rather than `i * step`. Locating the meal by
    array position assumed the other convention and read the window one sample late.
    """
    from timsim.simulation.run import simulate
    r = simulate(name, days=DAYS, seed=seeds.BENCH, layers=(), controller=BasalOnly(prof),
                 profile=prof, meals=meals)
    return np.asarray(r.bg, float), np.asarray(r.minutes, float)


def one(name, grams):
    """The meal's own contribution, against the same subject eating nothing.

    On basal alone a subject is not at steady state and drifts, so the rise measured from a
    pre-meal reading confounds the meal with the drift and puts the peak wherever the drift
    happens to turn over. Differencing against the counterfactual removes it.
    """
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    with_meal, minutes = _trace(name, prof, [(MEAL_HOUR, grams, False)])
    without, _ = _trace(name, prof, [])
    n = min(len(with_meal), len(without), len(minutes))
    # Located on the clock rather than by position, so the answer does not depend on where
    # the series happens to be numbered from.
    meal_at = MEAL_HOUR * 60.0
    i0 = int(np.searchsorted(minutes[:n], meal_at))
    if i0 >= n:
        return None
    i1 = int(np.searchsorted(minutes[:n], meal_at + WINDOW_MIN))
    i1 = min(max(i1, i0 + 1), n)
    delta = with_meal[i0:i1] - without[i0:i1]
    peak_i = int(np.argmax(delta))
    return {"name": name, "grams": grams,
            "baseline": float(without[i0]),
            "peak_absolute": float(with_meal[i0:i1][peak_i]),
            "rise": float(delta[peak_i]),
            "rise_per_10g": float(delta[peak_i] / (grams / 10.0)),
            "time_to_peak_min": float(minutes[i0 + peak_i] - minutes[i0]),
            "counterfactual_drift": float(without[i1 - 1] - without[i0])}


def _job(args):
    return one(*args)


def main():
    from timsim.therapy import titrate
    subjects = sorted(titrate.titrated_subjects())
    print(f"{len(subjects)} titrated subjects, {len(GRAMS)} meal sizes", flush=True)
    rows = []
    for g in GRAMS:
        with ProcessPoolExecutor(max_workers=10) as ex:
            got = list(ex.map(_job, [(n, g) for n in subjects]))
        rows += [r for r in got if r]
        sel = [r for r in rows if r["grams"] == g]
        rp = np.array([r["rise_per_10g"] for r in sel])
        tp = np.array([r["time_to_peak_min"] for r in sel])
        pk = np.array([r["peak_absolute"] for r in sel])
        print(f"{g:.0f} g, n={len(sel)}: rise {np.median(rp):.2f} mg/dL per 10 g "
              f"(IQR {np.percentile(rp,25):.2f} to {np.percentile(rp,75):.2f}); "
              f"peak at {np.median(tp):.0f} min "
              f"(IQR {np.percentile(tp,25):.0f} to {np.percentile(tp,75):.0f}); "
              f"absolute peak {np.median(pk):.0f} mg/dL", flush=True)
    json.dump({"rows": rows, "provenance": provenance.stamp()},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
