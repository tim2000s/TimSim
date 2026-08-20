"""How far does an answer move when only the participants change, per arm and per algorithm?

`examples/cohort_replicates.py` answers this by partitioning the population and rerunning, which
also re-matches each replicate to the reference and so captures the matching effect as well. It
is expensive, and it is run in one cell: the layered arm under the Control-IQ stand-in. A floor
measured there does not license a claim about the bare arm, or about oref0 SMB, and a difference
between two arms cannot be called real against a floor measured in only one of them.

This script measures the participant component alone, from the bench matrix already on disk. For
each arm, algorithm and cohort it repeatedly splits the completed subjects into two disjoint
halves, takes each half's median, and reports the distribution of the difference. Nothing is
simulated, so it costs nothing and can run beside a rebuild.

What it measures is narrower than the replicates and the two should not be substituted for one
another. Holding the seed fixed means each subject contributes the same month in both halves, so
the run-to-run component is inside the medians rather than between them, and the cohort is not
re-matched. The number is therefore a lower bound on the floor a simulated-to-real gap has to
clear, and it is reported in both raw units and in units of the reference population's own p10
to p90 spread, because that is the unit the distance table uses.

    python examples/group_floor.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np

from timsim import provenance, seeds

MATRIX = os.path.join(MEASUREMENTS, "bench_matrix.json")
DISTANCE = os.path.join(MEASUREMENTS, "distance_to_real.json")
OUT = os.path.join(MEASUREMENTS, "group_floor.json")

# The statistics the distance table reports, on the sensor trace, because comparisons against
# trial data go on `cgm` and `validation/compare.py` refuses the other pairing.
MEASURES = ("tir_cgm", "tar180_cgm", "tbr70_cgm", "tbr54_cgm", "mean_cgm", "cv_cgm")

# Enough splits that the 95th percentile is stable to the second decimal. Drawn from a stream
# seeded off the bench seed so the figure is reproducible without touching the run seeds.
SPLITS = 2000
MIN_SUBJECTS = 20


def split_half_spread(values, rng, splits=SPLITS):
    """The distribution of |median(A) - median(B)| over disjoint random halves.

    Disjoint rather than bootstrapped: a bootstrap can only draw subjects the cohort already
    contains and shares them between the two sides, which understates the group effect for the
    same reason `cohort_replicates.py` partitions instead of resampling.
    """
    v = np.asarray(values, float)
    n = len(v)
    half = n // 2
    diffs = np.empty(splits)
    for i in range(splits):
        idx = rng.permutation(n)
        diffs[i] = abs(np.median(v[idx[:half]]) - np.median(v[idx[half:2 * half]]))
    return {
        "median": float(np.median(diffs)),
        "p95": float(np.percentile(diffs, 95)),
        "max": float(diffs.max()),
    }


def main():
    matrix = json.load(open(MATRIX))
    runs = [r for r in matrix["runs"] if r.get("completed")]

    # The real spreads the distance table divides by, taken from its output rather than
    # recomputed, so the two documents cannot drift apart.
    spreads = {}
    if os.path.exists(DISTANCE):
        for pairing, block in json.load(open(DISTANCE)).get("pairings", {}).items():
            reference = pairing.split("|")[0]
            for key, row in block.items():
                if isinstance(row, dict) and "real_spread_p10_p90" in row:
                    spreads[(reference, key)] = float(row["real_spread_p10_p90"])

    # `distance_to_real` names its measures without the trace suffix.
    short = {m: m.replace("_cgm", "").replace("mean", "mean").replace("cv", "cv")
             for m in MEASURES}

    cells = {}
    for r in runs:
        cells.setdefault((r["bench"], r["controller"], r["cohort"]), []).append(r)

    rng = np.random.default_rng(seeds.BENCH)
    out = {"splits": SPLITS, "min_subjects": MIN_SUBJECTS,
           "measures": list(MEASURES), "provenance": provenance.stamp(), "cells": {}}

    for (bench, controller, cohort), rows in sorted(cells.items()):
        if len(rows) < MIN_SUBJECTS:
            continue
        reference = cohort.split("_")[0] if "_" in cohort else cohort
        cell = {"n": len(rows), "reference": reference, "measures": {}}
        for m in MEASURES:
            values = [r[m] for r in rows if r.get(m) is not None]
            if len(values) < MIN_SUBJECTS:
                continue
            row = split_half_spread(values, rng)
            spread = spreads.get((reference, short[m]))
            if spread:
                row["real_spread_p10_p90"] = spread
                row["p95_in_spreads"] = row["p95"] / spread
            cell["measures"][m] = row
        out["cells"][f"{bench}|{controller}|{cohort}"] = cell

    # The floor on the difference between two arms is not the floor on either arm. The arms
    # share subjects and share the seed, so a subject that runs low runs low in both and the
    # difference cancels most of what the per-arm figures contain. Measuring the arm difference
    # on each half is what licenses a claim that the layers moved something.
    out["arm_difference"] = {}
    for (bench_a, bench_b) in (("bare", "layered_some"),):
        for controller in sorted({r["controller"] for r in runs}):
            for cohort in sorted({r["cohort"] for r in runs}):
                a = {r["name"]: r for r in runs
                     if r["bench"] == bench_a and r["controller"] == controller
                     and r["cohort"] == cohort}
                b = {r["name"]: r for r in runs
                     if r["bench"] == bench_b and r["controller"] == controller
                     and r["cohort"] == cohort}
                shared = sorted(set(a) & set(b))
                if len(shared) < MIN_SUBJECTS:
                    continue
                reference = cohort.split("_")[0] if "_" in cohort else cohort
                cell = {"n": len(shared), "reference": reference,
                        "arms": [bench_a, bench_b], "measures": {}}
                for m in MEASURES:
                    pairs = [(a[n][m], b[n][m]) for n in shared
                             if a[n].get(m) is not None and b[n].get(m) is not None]
                    if len(pairs) < MIN_SUBJECTS:
                        continue
                    arr = np.asarray(pairs, float)
                    n_pairs = len(arr)
                    half = n_pairs // 2
                    diffs = np.empty(SPLITS)
                    for i in range(SPLITS):
                        idx = rng.permutation(n_pairs)
                        left = idx[:half]
                        right = idx[half:2 * half]
                        d_left = np.median(arr[left, 1]) - np.median(arr[left, 0])
                        d_right = np.median(arr[right, 1]) - np.median(arr[right, 0])
                        diffs[i] = abs(d_left - d_right)
                    row = {"observed_difference":
                           float(np.median(arr[:, 1]) - np.median(arr[:, 0])),
                           "p95": float(np.percentile(diffs, 95))}
                    spread = spreads.get((reference, short[m]))
                    if spread:
                        row["real_spread_p10_p90"] = spread
                        row["p95_in_spreads"] = row["p95"] / spread
                        row["observed_in_spreads"] = row["observed_difference"] / spread
                        row["resolvable"] = bool(
                            abs(row["observed_difference"]) > row["p95"])
                    cell["measures"][m] = row
                out["arm_difference"][f"{controller}|{cohort}"] = cell

    json.dump(out, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}\n")

    header = f"{'cell':46s} " + " ".join(f"{m.replace('_cgm',''):>9s}" for m in MEASURES)
    print(header)
    for name, cell in out["cells"].items():
        vals = []
        for m in MEASURES:
            row = cell["measures"].get(m)
            if row is None:
                vals.append(f"{'-':>9s}")
            elif "p95_in_spreads" in row:
                vals.append(f"{row['p95_in_spreads']:9.2f}")
            else:
                vals.append(f"{row['p95']:8.2f}*")
        print(f"{name[:46]:46s} " + " ".join(vals))
    print("\np95 of |median(A) - median(B)| over disjoint halves, in units of the reference's")
    print("p10 to p90 spread. An asterisk marks a cell with no matching reference spread, where")
    print("the figure is in the measure's own units instead.")

    print("\n\nLayered minus bare, paired on subject and seed. Observed difference against the")
    print("floor on that difference, both in spreads. 'yes' means the difference exceeds it.")
    print(f"\n{'cell':28s} " + " ".join(f"{m.replace('_cgm',''):>18s}" for m in MEASURES))
    for name, cell in out["arm_difference"].items():
        vals = []
        for m in MEASURES:
            row = cell["measures"].get(m)
            if row is None or "p95_in_spreads" not in row:
                vals.append(f"{'-':>18s}")
            else:
                mark = "yes" if row["resolvable"] else "no"
                vals.append(f"{row['observed_in_spreads']:+7.2f}/{row['p95_in_spreads']:5.2f} {mark:>3s}")
        print(f"{name[:28]:28s} " + " ".join(vals))


if __name__ == "__main__":
    main()
