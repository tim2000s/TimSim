"""How much of a simulated cohort's answer is the cohort rather than the bench.

Every comparison in this package reports a simulated median beside a real one and calls the
difference a gap. That is only meaningful once it is known how far the simulated median moves
when nothing changes except which subjects were drawn. A gap smaller than that is not evidence
about the simulator.

Two baselines are measured here and they answer different questions.

The first is sampling variation within a drawn cohort: the subjects are resampled with
replacement and the median recomputed, which gives the interval the median would occupy if the
same matching procedure had happened to select different people from the same pool. It costs
nothing, since it reuses runs already made.

The second is inter-group variation on the real side, taken from splitting the trial in two.
That is the same quantity measured on people rather than on subjects, and it is the number the
simulated interval should be read against.

Both are reported in units of the real between-person spread, so they can be set beside the
gaps in `examples/bench_tables.py` without conversion.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np

DRAWS = 5000
MEASURES = [("tir_cgm", "tir", "Time in range, %"),
            ("tbr70_cgm", "tbr70", "Time below 70, %"),
            ("tbr54_cgm", "tbr54", "Time below 54, %"),
            ("tar180_cgm", "tar180", "Time above 180, %"),
            ("mean_cgm", "mean", "Mean glucose, mg/dL"),
            ("cv_cgm", "cv", "Variability, CV %")]
OUT = os.path.join(MEASUREMENTS, "cohort_variation.json")


def real_reference(cohort):
    """Per-person outcomes for the real population a cohort is compared against."""
    if cohort == "commons":
        users = json.load(open(os.path.join(MEASUREMENTS, "commons_cohort.json")))["users"]
        keep = {r["user"] for r in
                json.load(open(os.path.join(MEASUREMENTS,
                                            "commons_requirement.json")))["users"]}
        return [r for r in users if r["user"] in keep]
    if cohort in ("dclp3", "close_it"):
        from timsim.validation import dclp3
        rows = []
        for pid, segs in dclp3.traces(arm=dclp3.CLOSED_LOOP).items():
            g = np.concatenate([np.asarray(s, float)[1] for s in segs])
            g = g[np.isfinite(g)]
            if len(g) < 2000:
                continue
            rows.append({"tir": 100 * np.mean((g >= 70) & (g <= 180)),
                         "tbr70": 100 * np.mean(g < 70), "tbr54": 100 * np.mean(g < 54),
                         "tar180": 100 * np.mean(g > 180), "mean": float(g.mean()),
                         "cv": 100 * g.std(ddof=1) / g.mean()})
        return rows
    return []


def bootstrap_median(values, draws=DRAWS, seed=0):
    rng = np.random.default_rng(seed)
    v = np.asarray(values, float)
    v = v[np.isfinite(v)]
    if len(v) < 3:
        return float("nan"), float("nan"), float("nan")
    picks = rng.integers(0, len(v), size=(draws, len(v)))
    meds = np.median(v[picks], axis=1)
    return float(np.median(v)), float(np.percentile(meds, 2.5)), \
        float(np.percentile(meds, 97.5))


def split_half(rows, key, draws=DRAWS, seed=0):
    """How far the median moves when a real population is split at random in two."""
    rng = np.random.default_rng(seed)
    v = np.asarray([r[key] for r in rows], float)
    v = v[np.isfinite(v)]
    if len(v) < 8:
        return float("nan")
    gaps = []
    for _ in range(draws):
        idx = rng.permutation(len(v))
        half = len(v) // 2
        gaps.append(abs(np.median(v[idx[:half]]) - np.median(v[idx[half:]])))
    return float(np.percentile(gaps, 95))


def main():
    matrix = json.load(open(os.path.join(MEASUREMENTS, "bench_matrix.json")))
    runs = [r for r in matrix["runs"] if r.get("completed")]
    print(f"population {matrix['population']}, {len(runs)} completed runs\n")

    report = {"population": matrix["population"], "arms": {}, "real": {}}
    for cohort in ("dclp3", "commons"):
        real = real_reference(cohort)
        if not real:
            continue
        spread = {k: float(np.percentile([r[k] for r in real], 90)
                           - np.percentile([r[k] for r in real], 10))
                  for _, k, _ in MEASURES}
        report["real"][cohort] = {
            "n": len(real),
            "split_half_95": {k: split_half(real, k) for _, k, _ in MEASURES},
            "spread": spread}
        print(f"=== {cohort}: {len(real)} real people ===")
        print(f"  {'measure':22}{'split-half 95%':>16}{'in spreads':>12}")
        for _, key, label in MEASURES:
            s = report["real"][cohort]["split_half_95"][key]
            print(f"  {label:22}{s:>16.2f}{s / spread[key]:>12.2f}")
        print()

    for (cohort, controller, bench) in [("dclp3", "control-iq", "layered_some"),
                                        ("dclp3", "oref", "layered_some"),
                                        ("commons", "oref", "layered_some")]:
        sel = [r for r in runs if r["cohort"] == cohort and r["controller"] == controller
               and r["bench"] == bench]
        if len(sel) < 5:
            continue
        spread = report["real"].get(cohort, {}).get("spread", {})
        print(f"=== {cohort} under {controller}, {bench}: {len(sel)} subjects ===")
        print(f"  {'measure':22}{'median':>10}{'95% interval':>22}{'width in spreads':>18}")
        arm = {}
        for key, refkey, label in MEASURES:
            med, lo, hi = bootstrap_median([r[key] for r in sel])
            width = hi - lo
            sp = spread.get(refkey)
            arm[refkey] = {"median": med, "lo": lo, "hi": hi,
                           "width_in_spreads": (width / sp) if sp else None}
            tail = f"{width / sp:>18.2f}" if sp else f"{'-':>18}"
            print(f"  {label:22}{med:>10.2f}{f'{lo:.2f} to {hi:.2f}':>22}{tail}")
        report["arms"][f"{cohort}|{controller}|{bench}"] = arm
        print()

    json.dump(report, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
