"""Pair two meal-shape files per subject: one record against another, or one bias against another.

`examples/sim_meal_shape.py` measures the same runs two ways. `--record eaten` reads every meal
at the grams that reached the gut; `--record announced` reads the meals the person entered at the
grams they entered, which is the record the real side is forced to use. This pairs two of its
files per subject on the windows both admit and writes the medians with a bootstrap interval on
the paired difference. With the default files the pair is the two records of one run, for issue
51, and the difference is the protocol alone. With `--base` and `--other` pointing at two biases
on one record, for `examples/carb_bias.py`, the difference is the bias on the subjects both
runs completed.

Both files are checked for the same subjects, days, seed and controller. When they carry the
same carbohydrate bias they are the same runs and the terminations have to agree, since a
termination is a property of the run rather than of how it was read; across biases the runs
differ and the panel is whoever completed both.

    python examples/meal_record_pairing.py
    python examples/meal_record_pairing.py --base sim_meal_shape_announced_oref.json \
        --other sim_meal_shape_bias084_announced_oref.json --out meal_bias_pairing_announced.json
"""
import argparse
import json
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance

EATEN = os.path.join(MEASUREMENTS, "sim_meal_shape_asym_oref.json")
ANNOUNCED = os.path.join(MEASUREMENTS, "sim_meal_shape_announced_oref.json")
OUT = os.path.join(MEASUREMENTS, "meal_record_pairing.json")
KEYS = ("rise_median", "rise_covered", "rise_uncovered", "median", "grams_median", "meals",
        "covered_meals", "uncovered_meals")
OUTCOME = ("tir", "tbr", "tbr54", "tar", "insulin_per_day", "rescues")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=EATEN, help="the file the difference is taken from")
    ap.add_argument("--other", default=ANNOUNCED)
    ap.add_argument("--arm", default="stock", help="the arm to read from both files")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    for path in ("base", "other"):
        v = getattr(a, path)
        if not os.path.isabs(v) and not os.path.exists(v):
            setattr(a, path, os.path.join(MEASUREMENTS, v))
    if not os.path.isabs(a.out) and os.sep not in a.out:
        a.out = os.path.join(MEASUREMENTS, a.out)
    e, n = json.load(open(a.base)), json.load(open(a.other))
    for key in ("subjects", "days", "seed", "controller"):
        if e[key] != n[key]:
            raise SystemExit(f"{key} differs: {e[key]} against {n[key]}")
    term = lambda d: sorted((x["subject"], x["termination"]["day_ended"])
                            for x in d["dropped"] if x["arm"] == a.arm)
    same_runs = e.get("carb_bias") == n.get("carb_bias")
    if same_runs and term(e) != term(n):
        raise SystemExit("the terminations differ, so these are not the same runs")
    if not same_runs:
        print(f"bias {e.get('carb_bias')} against {n.get('carb_bias')}, records "
              f"{e.get('record', 'eaten')} and {n.get('record', 'eaten')}; "
              f"{len(term(e))} and {len(term(n))} terminations")

    rng = np.random.default_rng(20260904)

    def ci(d):
        b = np.array([np.median(rng.choice(d, size=d.size, replace=True)) for _ in range(10000)])
        return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))

    windows = sorted({p["window_min"] for p in n["per_subject"]})
    rows = []
    print(f"{'window':>7}{'key':>16}{'n':>4}{'base':>8}{'other':>11}{'diff':>7}"
          f"{'95 per cent':>16}")
    for w in windows:
        E = {p["subject"]: p for p in e["per_subject"]
             if p["arm"] == a.arm and p["window_min"] == w}
        A = {p["subject"]: p for p in n["per_subject"]
             if p["arm"] == a.arm and p["window_min"] == w}
        for key in KEYS:
            pairs = [(E[s][key], A[s][key]) for s in sorted(set(E) & set(A))
                     if E[s].get(key) is not None and A[s].get(key) is not None]
            if len(pairs) < 2:
                continue
            x = np.asarray(pairs, float)
            d = x[:, 1] - x[:, 0]
            lo, hi = ci(d)
            rows.append({"window_min": w, "key": key, "subjects": len(pairs),
                         "base": float(np.median(x[:, 0])),
                         "other": float(np.median(x[:, 1])),
                         "paired_diff": float(np.median(d)), "ci95": [lo, hi]})
            print(f"{w:>7}{key:>16}{len(pairs):>4}{np.median(x[:, 0]):>8.1f}"
                  f"{np.median(x[:, 1]):>11.1f}{np.median(d):>7.1f}{f'{lo:.1f} to {hi:.1f}':>16}")
    # The whole-run outcome travels on every window row of a subject, so it is read once, from
    # the first window. Files written before the column existed carry no outcome and get none.
    outcome = []
    E = {p["subject"]: p.get("outcome") for p in e["per_subject"]
         if p["arm"] == a.arm and p["window_min"] == windows[0]}
    A = {p["subject"]: p.get("outcome") for p in n["per_subject"]
         if p["arm"] == a.arm and p["window_min"] == windows[0]}
    common = sorted(s for s in set(E) & set(A) if E[s] and A[s])
    for key in OUTCOME if len(common) >= 2 else ():
        x = np.array([(E[s][key], A[s][key]) for s in common], float)
        d = x[:, 1] - x[:, 0]
        lo, hi = ci(d)
        outcome.append({"key": key, "subjects": len(common), "base": float(np.median(x[:, 0])),
                        "other": float(np.median(x[:, 1])),
                        "paired_diff": float(np.median(d)), "ci95": [lo, hi]})
        print(f"{'run':>7}{key:>16}{len(common):>4}{np.median(x[:, 0]):>8.2f}"
              f"{np.median(x[:, 1]):>11.2f}{np.median(d):>7.2f}{f'{lo:.2f} to {hi:.2f}':>16}")
    json.dump({"provenance": provenance.stamp(), "base": os.path.relpath(a.base, REPO),
               "other": os.path.relpath(a.other, REPO), "arm": a.arm,
               "same_runs": same_runs, "rows": rows, "outcome": outcome},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
