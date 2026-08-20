"""Read the bench matrix into the tables the validation paper reports.

Three things are printed for each pairing, in this order deliberately.

Completion first, with the direction of every run that ended early. Runs stop when glucose
leaves the range the model is defined over, the runs that fail are the ones that went
furthest wrong, and every median below is therefore conditioned on survival. A completion
count that averages a hypoglycaemia failure with a hyperglycaemia one hides which way an arm
broke.

Then the arms themselves, paired over the subjects completing both arms of the comparison
being made, since an arm that loses different subjects describes a different population. The
same comparison is printed a second time without the completion requirement, using each run's
statistics over the period it survived, because the runs that stop are not a random sample:
under the Control-IQ stand-in all thirteen layered terminations were hypoglycaemia while the
bare arm lost nobody, so restricting to completers measures the layered arm on the subjects
that avoided a severe low. The completers table understates the hypoglycaemia gap and the
as-observed table cannot see what a terminated run would have done with its remaining days.
Both are printed because neither is the answer alone.

Every figure is a median with a bootstrap percentile interval, and the difference is the
difference of the two medians beside it, resampled at the subject level so the pairing
survives. Reporting a mean difference next to two median columns, which this did previously,
gives a row a reader cannot add up: on time below 54 mg/dL the two disagreed by a factor of
two, because a third of subjects sit at zero and the measure has no symmetric interval to
speak of.

Then the distance to the real reference, in units of the spread between real people. That
column is secondary and is kept for one purpose, which is comparing measures carried in
different units and supporting the fraction-closed statistic. It is a poor primary unit: the
p10 to p90 spread of time below 54 mg/dL is 0.41 points in the trial and 1.75 in the
do-it-yourself population, so the same difference in percentage points reads four times larger
against one reference than the other.
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


BOOTSTRAP = 5000


def _ci(sample, rng, statistic=np.median, reps=BOOTSTRAP):
    """Percentile interval on a statistic, resampling the units it is computed over.

    A normal approximation was used here previously. It is not defensible on these measures:
    time below 54 mg/dL is zero for a large minority of subjects, so the difference between
    arms is skewed and piled up at a bound, and a symmetric interval around a mean describes
    neither the centre nor the tails of it.
    """
    v = np.asarray(sample, float)
    v = v[np.isfinite(v)]
    if len(v) < 2:
        return float("nan"), float("nan")
    draws = statistic(v[rng.integers(0, len(v), size=(reps, len(v)))], axis=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def _paired_median_difference(va, vb, rng, reps=BOOTSTRAP):
    """Difference of medians, with a paired percentile interval.

    The difference of medians is reported rather than the mean of the differences, because the
    two arm columns beside it are medians and a reader is entitled to subtract them. The two
    quantities are not close on a skewed measure: on time below 54 mg/dL under the Control-IQ
    stand-in they were 0.61 and 0.31 percentage points.

    Resampling is at the subject level and carries both arms together, so the pairing that
    makes the comparison sensitive is preserved.
    """
    ok = np.isfinite(va) & np.isfinite(vb)
    va, vb = va[ok], vb[ok]
    if len(va) < 2:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, len(va), size=(reps, len(va)))
    draws = np.median(vb[idx], axis=1) - np.median(va[idx], axis=1)
    return (float(np.median(vb) - np.median(va)),
            float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)))


def paired(arms, a, b, subjects, require_complete=True):
    """Subjects with a record in both arms, optionally only where both ran to term."""
    keep = []
    for n in subjects:
        ra, rb = arms.get(a, {}).get(n), arms.get(b, {}).get(n)
        if ra is None or rb is None:
            continue
        if require_complete and not (ra.get("completed") and rb.get("completed")):
            continue
        keep.append(n)
    return keep


def _fmt(value, lo, hi):
    return f"{value:.2f} [{lo:.2f},{hi:.2f}]"


def table(arms, a, b, subjects, ref, label, rng, require_complete=True):
    keep = paired(arms, a, b, subjects, require_complete)
    survived = "completers only" if require_complete else "as observed, including early stops"
    print(f"\n  {label}   paired over {len(keep)} subjects, {survived}")
    head = f"  {'Measure':28}{a:>24}{b:>24}{'difference':>24}"
    if ref:
        head += f"{'real':>24}{'gap/spread':>12}"
    print(head)
    for key, name, refkey in MEASURES:
        va = np.array([arms[a][n][key] for n in keep], float)
        vb = np.array([arms[b][n][key] for n in keep], float)
        diff, dlo, dhi = _paired_median_difference(va, vb, rng)
        alo, ahi = _ci(va, rng)
        blo, bhi = _ci(vb, rng)
        line = (f"  {name:28}{_fmt(np.median(va), alo, ahi):>24}"
                f"{_fmt(np.median(vb), blo, bhi):>24}"
                f"{_fmt(diff, dlo, dhi):>24}")
        if ref and refkey and isinstance(ref, list) and ref:
            rv = np.array([r[refkey] for r in ref], float)
            rlo, rhi = _ci(rv, rng)
            spread = np.percentile(rv, 90) - np.percentile(rv, 10)
            gap = (np.median(vb) - np.median(rv)) / spread if spread else float("nan")
            line += f"{_fmt(np.median(rv), rlo, rhi):>24}{gap:>+12.2f}"
        print(line)


def main():
    from timsim import seeds

    d, idx = load()
    ref = references()
    rng = np.random.default_rng(seeds.BENCH)
    print(f"population {d['population']}, {d['days']} days, seed {d['seed']}")
    print(f"medians with {BOOTSTRAP}-sample bootstrap percentile intervals; differences are "
          f"paired at the subject level\n")

    for (cohort, controller), arms in idx.items():
        subjects = sorted({n for by in arms.values() for n in by})
        print("=" * 130)
        print(f"{cohort}  under  {controller}   ({len(subjects)} subjects)")
        completions(arms, subjects)
        r = ref.get(cohort)
        r = r if isinstance(r, list) else None
        table(arms, "bare", "layered_some", subjects, r,
              "bare S2008 against the layered bench", rng)

        # Runs that stop early are dropped from the comparison above, and they do not stop at
        # random: under the Control-IQ stand-in every layered termination was hypoglycaemia
        # while the bare arm lost nobody. Excluding them measures the layered arm on the
        # subjects that did not have a severe low, which understates exactly the gap the
        # comparison is about. The runs carry statistics over the period they survived, so the
        # same table computed without the completion requirement bounds the effect from the
        # other side. Neither is the right answer on its own; the pair is the honest report.
        lost = [n for n in subjects
                if not paired(arms, "bare", "layered_some", [n], require_complete=True)
                and paired(arms, "bare", "layered_some", [n], require_complete=False)]
        if lost:
            print(f"\n  {len(lost)} subjects dropped above for stopping early in one arm. "
                  f"The same comparison including them, at the duration each survived:")
            table(arms, "bare", "layered_some", subjects, r,
                  "bare S2008 against the layered bench", rng, require_complete=False)

        table(arms, "layered_always", "layered_never", subjects, None,
              "meal announcement withdrawn", rng)
        print()


if __name__ == "__main__":
    main()
