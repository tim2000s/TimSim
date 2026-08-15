"""Read the bench matrix into the tables the validation paper reports.

Three things are printed for each pairing, in this order deliberately.

Completion first, with the direction of every run that ended early. Runs stop when glucose
leaves the range the model is defined over, the runs that fail are the ones that went
furthest wrong, and every median below is therefore conditioned on survival. A completion
count that averages a hypoglycaemia failure with a hyperglycaemia one hides which way an arm
broke.

Then the arms themselves, paired over the subjects completing both arms of the comparison
being made, since an arm that loses different subjects describes a different population.

Then the distance to the real reference, in units of the spread between real people. A
simulated median two points from a reference whose people span forty points is close; the
same two points against a reference spanning four is not, and quoting the raw gap makes those
look alike.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np

MEASURES = [("tir_cgm", "Time in range 70-180, %", "tir"),
            ("tbr70_cgm", "Time below 70, %", "tbr70"),
            ("tbr54_cgm", "Time below 54, %", "tbr54"),
            ("tar180_cgm", "Time above 180, %", "tar180"),
            ("mean_cgm", "Mean sensor glucose, mg/dL", "mean"),
            ("cv_cgm", "Variability, CV %", "cv"),
            ("insulin_per_day", "Insulin, U/day", None),
            ("rescue_per_30d", "Rescue helpings per 30 d", None)]


def load():
    d = json.load(open(os.path.join(MEASUREMENTS, "bench_matrix.json")))
    runs = d["runs"]
    idx = {}
    for r in runs:
        idx.setdefault((r["cohort"], r["controller"]), {}).setdefault(r["bench"], {})[r["name"]] = r
    return d, idx


def references():
    """Per-person outcomes for each real population, on the same measures."""
    out = {}

    commons = json.load(open(os.path.join(MEASUREMENTS, "commons_cohort.json")))["users"]
    req = {r["user"] for r in
           json.load(open(os.path.join(MEASUREMENTS, "commons_requirement.json")))["users"]}
    out["commons"] = [r for r in commons if r["user"] in req]

    try:
        from timsim.validation import dclp3
        sp = dclp3.split()
        cal = set(sp["calibration"])
        rows = []
        for pid, segs in dclp3.traces(arm=dclp3.CLOSED_LOOP).items():
            if pid not in cal:
                continue
            g = np.concatenate([np.asarray(s, float)[1] for s in segs])
            g = g[np.isfinite(g)]
            if len(g) < 2000:
                continue
            rows.append({"tir": 100 * np.mean((g >= 70) & (g <= 180)),
                         "tbr70": 100 * np.mean(g < 70), "tbr54": 100 * np.mean(g < 54),
                         "tar180": 100 * np.mean(g > 180), "mean": g.mean(),
                         "cv": 100 * g.std(ddof=1) / g.mean()})
        out["dclp3"] = rows
    except Exception as exc:                       # the trial data is not redistributed
        print(f"(DCLP3 reference unavailable: {exc})")

    # CLOSE-IT publishes summaries rather than participants, so it carries a mean and a
    # standard deviation and cannot supply a per-person spread.
    out["close_it"] = {"tir": (66.0, 8.0), "tir_announced": (69.0, 13.0)}
    return out


def completions(arms, subjects):
    print(f"  {'arm':16} {'completed':>10}   terminations")
    for bench, by_name in arms.items():
        done = [n for n in subjects if by_name.get(n, {}).get("completed")]
        lost = []
        for n in subjects:
            r = by_name.get(n)
            if r is None or r.get("completed"):
                continue
            if r.get("error"):
                lost.append(f"{n}:error")
            else:
                lost.append(f"{n}:{'hyper' if r['final_bg'] > 250 else 'hypo'}")
        print(f"  {bench:16} {len(done):>4}/{len(subjects):<5}   "
              f"{', '.join(lost) if lost else 'none'}")


def paired(arms, a, b, subjects):
    keep = [n for n in subjects
            if arms.get(a, {}).get(n, {}).get("completed")
            and arms.get(b, {}).get(n, {}).get("completed")]
    return keep


def table(arms, a, b, subjects, ref, label):
    keep = paired(arms, a, b, subjects)
    print(f"\n  {label}   paired over {len(keep)} subjects")
    head = f"  {'Measure':28}{a:>16}{b:>16}{'paired diff':>18}"
    if ref:
        head += f"{'real':>12}{'gap/spread':>12}"
    print(head)
    for key, name, refkey in MEASURES:
        va = np.array([arms[a][n][key] for n in keep], float)
        vb = np.array([arms[b][n][key] for n in keep], float)
        d = vb - va
        d = d[np.isfinite(d)]
        h = 1.96 * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
        line = (f"  {name:28}{np.median(va):>16.2f}{np.median(vb):>16.2f}"
                f"{d.mean():>+11.2f} ±{h:<5.2f}")
        if ref and refkey and isinstance(ref, list) and ref:
            rv = np.array([r[refkey] for r in ref], float)
            spread = np.percentile(rv, 90) - np.percentile(rv, 10)
            gap = (np.median(vb) - np.median(rv)) / spread if spread else float("nan")
            line += f"{np.median(rv):>12.2f}{gap:>+12.2f}"
        print(line)


def main():
    d, idx = load()
    ref = references()
    print(f"population {d['population']}, {d['days']} days, seed {d['seed']}\n")

    for (cohort, controller), arms in idx.items():
        subjects = sorted({n for by in arms.values() for n in by})
        print("=" * 100)
        print(f"{cohort}  under  {controller}   ({len(subjects)} subjects)")
        completions(arms, subjects)
        r = ref.get(cohort)
        r = r if isinstance(r, list) else None
        table(arms, "bare", "layered_some", subjects, r, "bare S2008 against the layered bench")
        table(arms, "layered_always", "layered_never", subjects, None,
              "meal announcement withdrawn")
        print()


if __name__ == "__main__":
    main()
