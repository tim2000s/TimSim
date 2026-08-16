"""Run the same algorithm on several disjoint groups of subjects, to size the group effect.

Every comparison here reports one simulated cohort against one real population. How much of
the difference is the bench and how much is which twenty-five subjects happened to be drawn is
not answerable from a single cohort, and resampling inside one understates it, because a
bootstrap can only draw subjects the cohort already contains.

So the population is partitioned. Each replicate is matched to the same reference and shares
no subject with any other, which is the in-silico equivalent of running the same protocol on a
different group of participants. The spread of the replicate medians is then the group effect,
and it is the quantity a simulated-to-real gap has to exceed before it says anything about the
simulator.

Matching degrades as the pool empties, and the achieved distance is recorded per replicate so
that a late replicate matched to a thinner pool is not read as a group effect.

The real counterpart is `examples/cohort_variation.py`, which splits a trial in two and
measures the same thing on people.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import time
import argparse
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim.population import cohort, names as all_names
from timsim.therapy import titrate

DAYS, SEED = 28, 11
LAYERS = ("physiology", "behaviour", "sensor", "site")
CONTROLLER = "control-iq"
OUT = os.path.join(MEASUREMENTS, "cohort_replicates.json")
MEASURES = [("tir_cgm", "Time in range, %"), ("tbr70_cgm", "Time below 70, %"),
            ("tbr54_cgm", "Time below 54, %"), ("tar180_cgm", "Time above 180, %"),
            ("mean_cgm", "Mean glucose, mg/dL"), ("cv_cgm", "Variability, CV %")]


def disjoint(reference, k=4, n=25, seed=0):
    """`k` cohorts matched to the same reference, sharing no subject."""
    pool = sorted(all_names())
    out = []
    for i in range(k):
        if len(pool) < n:
            break
        names, info = cohort.matched_on_traits(reference, n=n, seed=seed + i, subjects=pool)
        out.append((names, info))
        pool = [p for p in pool if p not in set(names)]
    return out


def one(job):
    name, replicate = job
    from timsim.simulation.run import simulate
    prof = titrate.profile_for(name)
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=CONTROLLER,
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"replicate": replicate, "name": name, "completed": False,
                "error": str(exc)[:160]}
    cgm = np.asarray(r.cgm, float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    return {"replicate": replicate, "name": name, "completed": bool(r.completed),
            "tir_cgm": float(100 * np.mean((cgm >= 70) & (cgm <= 180))),
            "tbr70_cgm": float(100 * np.mean(cgm < 70)),
            "tbr54_cgm": float(100 * np.mean(cgm < 54)),
            "tar180_cgm": float(100 * np.mean(cgm > 180)),
            "mean_cgm": float(np.mean(cgm)),
            "cv_cgm": float(100 * np.std(cgm, ddof=1) / np.mean(cgm)),
            "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replicates", type=int, default=4)
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--plan-only", action="store_true",
                    help="print the cohorts and what they would need, and stop")
    a = ap.parse_args()

    from examples.build_cohorts import dclp3_traits
    reference = dclp3_traits()
    reps = disjoint(reference, k=a.replicates, n=a.n)
    titrated = set(titrate.titrated_subjects())

    print(f"{len(reps)} disjoint cohorts of {a.n}, matched to {len(reference)} DCLP3 "
          f"closed-loop participants\n")
    print(f"  {'rep':>4}{'match':>9}{'age':>8}{'<18':>7}{'TDI':>8}{'titrated':>10}{'new':>6}")
    need = []
    for i, (names, info) in enumerate(reps):
        tr = cohort.traits(names)
        age = np.array([v[0] for v in tr.values()])
        tdi = np.array([v[1] for v in tr.values()])
        have = [n for n in names if n in titrated]
        new = [n for n in names if n not in titrated]
        need += new
        print(f"  {i:>4}{info['median_distance']:>9.3f}{np.median(age):>8.1f}"
              f"{100*np.mean(age<18):>6.0f}%{np.median(tdi):>8.1f}"
              f"{len(have):>10}{len(new):>6}")
    ref_age = np.array([p[0] for p in reference])
    ref_tdi = np.array([p[1] for p in reference])
    print(f"  {'real':>4}{'':>9}{np.median(ref_age):>8.1f}"
          f"{100*np.mean(ref_age<18):>6.0f}%{np.median(ref_tdi):>8.1f}")
    print(f"\n{len(need)} subjects need titrating before these can run")
    if a.plan_only:
        json.dump({"replicates": [{"subjects": list(n), "match": i} for n, i in reps],
                   "need_titration": sorted(need)}, open(OUT, "w"), indent=1)
        print(f"wrote the plan to {OUT}")
        return
    # A subject whose settings never clear the consensus floors is excluded rather than run at
    # the loosest available, which is the same rule the main arms follow. It is a selection
    # effect and is reported per replicate rather than absorbed.
    usable = [[n for n in names if n in titrated] for names, _ in reps]
    lost = [[n for n in names if n not in titrated] for names, _ in reps]
    if any(lost):
        print("\nexcluded, no settings clear the hypoglycaemia floors:")
        for i, names in enumerate(lost):
            if names:
                print(f"  replicate {i}: {', '.join(names)}")
    print("\nrunning " + ", ".join(f"{len(u)}" for u in usable) + " subjects per replicate")

    jobs = [(n, i) for i, names in enumerate(usable) for n in names]
    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for k, row in enumerate(ex.map(one, jobs), 1):
            rows.append(row)
            if k % 20 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)} done, {(time.time()-t0)/60:.1f} min", flush=True)

    print(f"\n  {'measure':22}" + "".join(f"{f'rep {i}':>10}" for i in range(len(reps)))
          + f"{'spread':>10}")
    summary = {}
    for key, label in MEASURES:
        meds = []
        for i in range(len(reps)):
            v = [r[key] for r in rows if r["replicate"] == i and r.get("completed")]
            meds.append(float(np.median(v)) if v else float("nan"))
        rng = float(np.nanmax(meds) - np.nanmin(meds))
        summary[key] = {"medians": meds, "range": rng}
        print(f"  {label:22}" + "".join(f"{m:>10.2f}" for m in meds) + f"{rng:>10.2f}")

    json.dump({"population": titrate.population_fingerprint(), "controller": CONTROLLER,
               "replicates": [{"subjects": list(n), "match": i} for n, i in reps],
               "runs": rows, "summary": summary}, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
