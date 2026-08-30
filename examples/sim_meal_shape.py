"""The simulated meal shape, per subject and per meal, against the real measurement.

`examples/real_meal_shape.py` measures 964 real people over 193,696 meals and separates the two
components of the spread. Within-person variation is the larger of them: at a 240 minute window a
Loop participant's own meals span an interquartile range of 90 minutes, where participants differ
from each other by 50 minutes across the tenth to ninetieth percentile of their medians.

The simulated side had none of it. `examples/meal_with_bolus.py` gives each subject a single 60 g
meal at midday on a fixed seed with no layers, so every simulated meal is the same meal and the
whole simulated spread is between-subject physiology. This runs each subject for weeks with the
person's own layers on, takes every meal the schedule produces, and measures both components the
way the real side measures them, through the shared definition in `timsim/analysis/meal_shape.py`.

Four things are matched to the real side deliberately. Meals are read off `cgm` rather than `bg`,
because the real side can only be a sensor and sensor error moves where a minimum and a maximum
fall. Rescue carbohydrate breaks isolation, because a real person logging 15 g for a low files it
in the same field as a meal. The peak is located on the absolute trace. And the window is swept
rather than chosen, because the window sets the answer: on the real side the pooled median runs
70 minutes at 180 and 135 at 720.

The controller is the built-in correction loop. The real reference brackets that choice rather
than matching it, since Loop is a closed loop and ReplaceBG a sensor-augmented pump, and the two
agree on the per-person median at 80 minutes.

    python examples/sim_meal_shape.py --subjects 40 --days 42
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from timsim.analysis import meal_shape as ms

OUT = os.path.join(MEASUREMENTS, "sim_meal_shape.json")
REAL = os.path.join(MEASUREMENTS, "real_meal_shape.json")

# Stock against the whole of the gain on the fast delay, which is the configuration the sweep in
# `liver_two_timescale.py` adopted and which is a single-timescale liver at 10.5 times the
# published rate rather than a two-timescale one.
ARMS = (("stock", 0.0, 1.0), ("fast", 1.0, 10.5))
WORKERS = 7


def job(args):
    """One subject in one arm, reduced to its meal records inside the worker.

    The trace is tens of thousands of readings and the records are tens of meals, so the
    reduction happens here rather than sending the trace back. macOS spawns, so this is at
    module level and everything it needs travels in the tuple.
    """
    name, arm, fraction, ki_scale, days, windows = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    r = simulate(name, days=days, seed=seeds.BENCH, layers=DEFAULT_LAYERS,
                 liver_fast_fraction=fraction, liver_fast_ki_scale=ki_scale)
    if r.termination:
        return name, arm, None, r.termination
    minutes = np.asarray(r.minutes, float)
    cgm = np.asarray(r.cgm, float)
    meals = [(float(m), float(g)) for m, g in r.meal_log]
    # Rescue carbohydrate breaks isolation and is never an index meal. `rescue_log` carries
    # (decided_at, eaten_at, grams, trigger) and the eaten minute is the one that reaches the gut.
    rescues = [float(x[1]) for x in r.rescue_log]
    carbs = [m for m, _ in meals] + rescues
    out = {}
    for w in windows:
        recs, rej = ms.shapes(meals, carbs, minutes, cgm, window_min=w)
        out[w] = {"ttp": [x["trough_to_peak_min"] for x in recs],
                  "hours": [x["hour"] for x in recs],
                  "trough_at_index": int(sum(x["trough_at_index"] for x in recs)),
                  "rejected": rej}
    return name, arm, out, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=42)
    ap.add_argument("--windows", nargs="+", type=int, default=list(ms.WINDOWS))
    ap.add_argument("--min-meals", type=int, default=20)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects)

    jobs = [(n, arm, fr, ks, a.days, tuple(a.windows)) for n in subs for arm, fr, ks in ARMS]
    print(f"{len(subs)} subjects, {len(ARMS)} arms, {a.days} days each, on {a.workers} workers")
    with mp.Pool(a.workers) as pool:
        results = pool.map(job, jobs)

    got, dropped = {}, []
    for name, arm, out, term in results:
        if out is None:
            dropped.append({"subject": name, "arm": arm, "termination": term})
            continue
        got[(name, arm)] = out

    real = json.load(open(REAL)) if os.path.exists(REAL) else {"rows": []}
    real_by = {(r["study"], r["window_min"]): r for r in real["rows"]}

    rec = {"provenance": provenance.stamp(), "subjects": list(subs), "days": a.days,
           "seed": seeds.BENCH, "arms": [a_[0] for a_ in ARMS], "min_meals": a.min_meals,
           "dropped": dropped, "rows": []}

    for arm, _, _ in ARMS:
        print(f"\n{arm}")
        print(f"{'window':>7}{'subj':>6}{'meals':>7}{'per-person median':>20}"
              f"{'within-person IQR':>20}{'evening':>9}{'trough at index':>17}")
        for w in a.windows:
            per, hours, at_index, tot = [], [], 0, 0
            for n in subs:
                cell = got.get((n, arm))
                if not cell:
                    continue
                v = cell[w]["ttp"]
                hours.extend(cell[w]["hours"])
                at_index += cell[w]["trough_at_index"]
                tot += len(v)
                p = ms.per_person(v, a.min_meals)
                if p:
                    per.append(p)
            if not per:
                print(f"{w:>7}{0:>6}{tot:>7}   no subject reaches {a.min_meals} meals")
                rec["rows"].append({"arm": arm, "window_min": w, "subjects": 0, "meals": tot})
                continue
            s = ms.summarise(per)
            h = np.asarray(hours)
            evening = float(np.mean((h >= 16) & (h <= 21)))
            bp, wp = s["between_person_median"], s["within_person_iqr"]
            row = dict(s, arm=arm, window_min=w, evening_share=evening,
                       trough_at_index_share=(at_index / tot if tot else float("nan")),
                       real=real_by.get(("Loop", w), {}).get("within_person_iqr"))
            rec["rows"].append(row)
            print(f"{w:>7}{s['subjects']:>6}{s['meals']:>7}"
                  f"{f'{bp[0]:.0f} / {bp[1]:.0f} / {bp[2]:.0f}':>20}"
                  f"{f'{wp[0]:.0f} / {wp[1]:.0f} / {wp[2]:.0f}':>20}"
                  f"{evening:>9.2f}{row['trough_at_index_share']:>17.2f}")

    if dropped:
        print(f"\n{len(dropped)} subject-arms terminated early and are excluded")
    print("\nreal, Loop, for comparison")
    print(f"{'window':>7}{'subj':>6}{'meals':>7}{'per-person median':>20}{'within-person IQR':>20}"
          f"{'evening':>9}")
    for w in a.windows:
        r = real_by.get(("Loop", w))
        if not r:
            continue
        bp, wp = r["between_person_median"], r["within_person_iqr"]
        print(f"{w:>7}{r['subjects']:>6}{r['meals']:>7}"
              f"{f'{bp[0]:.0f} / {bp[1]:.0f} / {bp[2]:.0f}':>20}"
              f"{f'{wp[0]:.0f} / {wp[1]:.0f} / {wp[2]:.0f}':>20}"
              f"{r['hour_share']['16-21']:>9.2f}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
