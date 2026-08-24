"""The meal response with the meal covered, which is where the liver delay is visible.

`examples/meal_response.py` gives a subject a meal on basal alone and differences it against the
same subject eating nothing. That is the right measurement for what an uncovered meal does, and it
is blind to `ki`. With a constant basal, plasma insulin never moves, so the delayed signal driving
hepatic production reaches the same steady state whatever the delay is, and two arms differing only
in `ki` come out identical to every decimal. They did.

`ki` was identified on a triple-tracer meal protocol in healthy subjects, where insulin rises with
the meal. Reproducing that condition needs insulin that moves, so the meal here is covered by a
bolus from the subject's own carbohydrate ratio. That is also the condition a person with a pump is
in, so the measurement is the one that matters for whether a change to `ki` breaks what the model
was fitted for.

Two quantities, both computed the way `docs/FIDELITY.md` computes them on the real side, since the
comparison is the point. Trough to peak is the duration of the rise itself, measured from the
minimum after the bolus rather than from the meal, because the real data clocks from a carbohydrate
entry that can precede the food by fifteen or twenty minutes and the two are not the same event.
Rise per 10 g is the peak above the counterfactual.

    real, 5,189 meals    trough to peak 112 min (70 to 165)
    real, uncovered      rise 15.9 to 19.7 mg/dL per 10 g

    python examples/meal_with_bolus.py --subjects 40 --delays 1 11
"""
import argparse
import json
import os
import sys

import numpy as np
from concurrent.futures import ProcessPoolExecutor

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "meal_with_bolus.json")

DAYS = 3
MEAL_HOUR = 36.0               # midday on the second day, after the run has settled
GRAMS = 60.0
WINDOW_MIN = 720.0

REAL_TROUGH_TO_PEAK = 112.0
REAL_RISE_PER_10G = (15.9, 19.7)


class BolusAtMeal:
    """Basal, plus one bolus covering the meal from the subject's own carbohydrate ratio."""

    def __init__(self, profile, grams, at_minute):
        self.profile = profile
        self.grams = float(grams)
        self.at = float(at_minute)
        self.given = False

    def policy(self, observation, reward, done, **info):
        from simglucose.controller.base import Action
        # `clock_minutes`, which is the key the runner supplies. `minute` is not a key it sets,
        # so reading that gave zero on every cycle and the bolus was never due.
        minute = float(info.get("clock_minutes", 0.0))
        bolus = 0.0
        if not self.given and minute >= self.at:
            bolus = self.grams / float(self.profile.cr_at(minute))
            self.given = True
        return Action(basal=self.profile.basal_at(minute), bolus=bolus)

    def reset(self):
        self.given = False


def _trace(name, prof, meals, liver_delay, controller):
    from timsim.simulation.run import simulate
    r = simulate(name, days=DAYS, seed=seeds.BENCH, layers=(), controller=controller,
                 profile=prof, meals=meals, liver_delay=liver_delay)
    return np.asarray(r.bg, float), np.asarray(r.minutes, float)


def one(name, liver_delay=None, grams=GRAMS):
    """The covered meal's own contribution, against the same subject eating nothing."""
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    at = MEAL_HOUR * 60.0
    with_meal, minutes = _trace(name, prof, [(MEAL_HOUR, grams, False)], liver_delay,
                                BolusAtMeal(prof, grams, at))
    # The counterfactual gets the same bolus, so the difference is the meal and not the insulin.
    without, _ = _trace(name, prof, [], liver_delay, BolusAtMeal(prof, grams, at))
    n = min(len(with_meal), len(without), len(minutes))
    i0 = int(np.searchsorted(minutes[:n], at))
    if i0 >= n:
        return None
    i1 = min(max(int(np.searchsorted(minutes[:n], at + WINDOW_MIN)), i0 + 1), n)
    delta = with_meal[i0:i1] - without[i0:i1]
    peak_i = int(np.argmax(delta))
    # Trough to peak, on the absolute trace rather than the difference, because that is what is
    # measurable on a real trace where no counterfactual exists.
    seg = with_meal[i0:i1]
    trough_i = int(np.argmin(seg[:peak_i + 1])) if peak_i > 0 else 0
    return {"name": name, "liver_delay": liver_delay, "grams": grams,
            "rise": float(delta[peak_i]),
            "rise_per_10g": float(delta[peak_i] / (grams / 10.0)),
            "meal_to_peak_min": float(minutes[i0 + peak_i] - minutes[i0]),
            "trough_to_peak_min": float(minutes[i0 + peak_i] - minutes[i0 + trough_i]),
            "peak_absolute": float(seg[peak_i]),
            "trough_absolute": float(seg[trough_i])}


def _job(a):
    return one(*a)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--delays", nargs="+", type=float, default=[1.0, 11.0])
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 13)))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from timsim.therapy import titrate
    subs = sorted(titrate.titrated_subjects())[:a.subjects]
    rec = {"provenance": provenance.stamp(), "grams": GRAMS, "n": len(subs),
           "real": {"trough_to_peak_min": REAL_TROUGH_TO_PEAK,
                    "rise_per_10g": list(REAL_RISE_PER_10G)}, "arms": {}}

    print(f"{len(subs)} subjects, {GRAMS:.0f} g covered by the subject's own ratio\n")
    print(f"{'liver delay':>12}{'n':>5}{'trough to peak':>16}{'meal to peak':>14}"
          f"{'rise/10 g':>11}{'peak':>8}")
    for d in a.delays:
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            rows = [r for r in ex.map(_job, [(n, d) for n in subs]) if r]
        ttp = np.array([r["trough_to_peak_min"] for r in rows])
        mtp = np.array([r["meal_to_peak_min"] for r in rows])
        rp = np.array([r["rise_per_10g"] for r in rows])
        pk = np.array([r["peak_absolute"] for r in rows])
        rec["arms"][str(d)] = {"n": len(rows), "trough_to_peak": float(np.median(ttp)),
                               "meal_to_peak": float(np.median(mtp)),
                               "rise_per_10g": float(np.median(rp)),
                               "peak_absolute": float(np.median(pk)),
                               "rows": rows}
        print(f"{d:>12.1f}{len(rows):>5}{np.median(ttp):>16.0f}{np.median(mtp):>14.0f}"
              f"{np.median(rp):>11.2f}{np.median(pk):>8.0f}")

    print(f"\nreal: trough to peak {REAL_TROUGH_TO_PEAK:.0f} min (70 to 165), "
          f"rise {REAL_RISE_PER_10G[0]:.1f} to {REAL_RISE_PER_10G[1]:.1f} mg/dL per 10 g")
    base = rec["arms"].get(str(a.delays[0]))
    for d in a.delays[1:]:
        arm = rec["arms"][str(d)]
        same = (abs(arm["trough_to_peak"] - base["trough_to_peak"]) < 1e-9
                and abs(arm["rise_per_10g"] - base["rise_per_10g"]) < 1e-9)
        if same:
            print(f"\nliver delay {d} is identical to {a.delays[0]} on every figure, so the "
                  f"parameter is not reaching this measurement. Fix that before reading it.")
    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
