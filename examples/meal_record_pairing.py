"""Pair the eaten and the announced meal records per subject, for issue 51.

`examples/sim_meal_shape.py` measures the same runs two ways. `--record eaten` reads every meal
at the grams that reached the gut; `--record announced` reads the meals the person entered at the
grams they entered, which is the record the real side is forced to use. This pairs the two per
subject on the windows both admit, so the difference is the protocol alone, and writes the
medians with a bootstrap interval on the paired difference.

The two files have to be the same runs. Both are checked for the same subjects, days, seed and
controller, and the same terminations, since a termination is a property of the run rather than
of how it was read.

    python examples/meal_record_pairing.py
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
KEYS = ("rise_median", "rise_covered", "rise_uncovered", "median", "grams_median", "meals")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--eaten", default=EATEN)
    ap.add_argument("--announced", default=ANNOUNCED)
    ap.add_argument("--arm", default="stock", help="the arm to read from the eaten file")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    e, n = json.load(open(a.eaten)), json.load(open(a.announced))
    for key in ("subjects", "days", "seed", "controller"):
        if e[key] != n[key]:
            raise SystemExit(f"{key} differs: {e[key]} against {n[key]}")
    if n.get("record") != "announced":
        raise SystemExit("the announced file is not an announced record")
    term = lambda d, arm: sorted((x["subject"], x["termination"]["day_ended"])
                                 for x in d["dropped"] if x["arm"] == arm)
    if term(e, a.arm) != term(n, n["arms"][0]):
        raise SystemExit("the terminations differ, so these are not the same runs")

    rng = np.random.default_rng(20260904)

    def ci(d):
        b = np.array([np.median(rng.choice(d, size=d.size, replace=True)) for _ in range(10000)])
        return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))

    windows = sorted({p["window_min"] for p in n["per_subject"]})
    rows = []
    print(f"{'window':>7}{'key':>16}{'n':>4}{'eaten':>8}{'announced':>11}{'diff':>7}"
          f"{'95 per cent':>16}")
    for w in windows:
        E = {p["subject"]: p for p in e["per_subject"]
             if p["arm"] == a.arm and p["window_min"] == w}
        A = {p["subject"]: p for p in n["per_subject"] if p["window_min"] == w}
        for key in KEYS:
            pairs = [(E[s][key], A[s][key]) for s in sorted(set(E) & set(A))
                     if E[s].get(key) is not None and A[s].get(key) is not None]
            if len(pairs) < 2:
                continue
            x = np.asarray(pairs, float)
            d = x[:, 1] - x[:, 0]
            lo, hi = ci(d)
            rows.append({"window_min": w, "key": key, "subjects": len(pairs),
                         "eaten": float(np.median(x[:, 0])),
                         "announced": float(np.median(x[:, 1])),
                         "paired_diff": float(np.median(d)), "ci95": [lo, hi]})
            print(f"{w:>7}{key:>16}{len(pairs):>4}{np.median(x[:, 0]):>8.1f}"
                  f"{np.median(x[:, 1]):>11.1f}{np.median(d):>7.1f}{f'{lo:.1f} to {hi:.1f}':>16}")
    json.dump({"provenance": provenance.stamp(), "eaten": os.path.relpath(a.eaten, REPO),
               "announced": os.path.relpath(a.announced, REPO), "arm": a.arm, "rows": rows},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
