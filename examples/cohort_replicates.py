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
import collections
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim.population import cohort, names as all_names
from timsim.therapy import titrate

from timsim import provenance, seeds

DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
CONTROLLER = "control-iq"
OUT = os.path.join(MEASUREMENTS, "cohort_replicates.json")

# The floor this measures is a property of the arm and the algorithm, not of the bench. It was
# measured in one cell, the layered arm under the Control-IQ stand-in, and quoted for the bare
# arm and for oref0 SMB as well. Read off the bench matrix, the floor on time below 54 mg/dL
# ranges from 0.34 to 2.83 spreads across the sixteen cells the matrix contains, so one cell
# does not stand for another. `--controller` and `--arm` select the cell and the output is
# suffixed with it, leaving the default invocation writing where it always did.
ARMS = {"layered": ("physiology", "behaviour", "sensor", "site"), "bare": ()}

# Below this many completed runs the replicate medians are not worth writing down. The real
# cells complete between 78 and 84 of 90 per replicate, so this only fires on a cell that has
# gone wrong rather than on one that lost a few subjects.
MIN_COMPLETED = 30
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
    """Every input a run needs travels in the job, and comes back out with its result.

    The arm and the algorithm used to be module globals assigned by `main`, under a comment
    saying the workers inherited them at fork. macOS starts subprocesses by spawn, so each
    worker re-imported this module and read the defaults at the bottom of it. `--arm bare` and
    `--controller oref` reached the metadata written beside the results and never reached a
    single run. The bare cell measured on 20 August 2026 was the layered cell to every decimal
    of all 247 runs, and said `"arm": "bare"` at the top of the file.

    So the values are passed per job, which no start method can strip, and each row carries the
    arm it was actually measured under so that `main` can refuse to write a mislabelled file.

    `oref` is not a name `simulate` accepts. It is the real algorithm behind a bridge and has to
    be built per subject and closed afterwards, which is what `bench_matrix.py` does. Passing the
    string straight through raised on all 247 runs the first time the option reached a run at
    all, the defect above having stopped it reaching one before that.
    """
    name, replicate, layers, controller = job
    from timsim.simulation.run import simulate
    prof = titrate.profile_for(name)
    ctrl = controller
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=layers, controller=ctrl,
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"replicate": replicate, "name": name, "completed": False,
                "layers": list(layers), "controller": controller,
                "error": str(exc)[:160]}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    cgm = np.asarray(r.cgm, float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    return {"replicate": replicate, "name": name, "completed": bool(r.completed),
            "layers": list(layers), "controller": controller,
            "tir_cgm": float(100 * np.mean((cgm >= 70) & (cgm <= 180))),
            "tbr70_cgm": float(100 * np.mean(cgm < 70)),
            "tbr54_cgm": float(100 * np.mean(cgm < 54)),
            "tar180_cgm": float(100 * np.mean(cgm > 180)),
            "mean_cgm": float(np.mean(cgm)),
            "cv_cgm": float(100 * np.std(cgm, ddof=1) / np.mean(cgm)),
            "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--controller", default=CONTROLLER,
                    help="algorithm the replicates run under")
    ap.add_argument("--arm", default="layered", choices=sorted(ARMS),
                    help="bench arm; the floor differs between them by up to eightfold")
    ap.add_argument("--replicates", type=int, default=4)
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--plan-only", action="store_true",
                    help="print the cohorts and what they would need, and stop")
    a = ap.parse_args()
    layers, controller = ARMS[a.arm], a.controller
    out_path = OUT
    if (a.controller, a.arm) != (CONTROLLER, "layered"):
        out_path = OUT.replace(".json", f"_{a.controller}_{a.arm}.json")

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
        # A separate file from the results. The plan used to be written to the results path,
        # which is harmless inside the rebuild because the plan runs first and the results
        # overwrite it, and destructive anywhere else: running `--plan-only` after a completed
        # replicate set replaces 247 runs with a list of subject names. That happened on
        # 20 August 2026 and cost a 39-minute rerun.
        plan_path = out_path.replace(".json", "_plan.json")
        json.dump({"replicates": [{"subjects": list(n), "match": i} for n, i in reps],
                   "need_titration": sorted(need), "provenance": provenance.stamp()},
                  open(plan_path, "w"), indent=1)
        print(f"wrote the plan to {plan_path}")
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

    jobs = [(n, i, layers, controller) for i, names in enumerate(usable) for n in names]
    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for k, row in enumerate(ex.map(one, jobs), 1):
            rows.append(row)
            if k % 20 == 0 or k == len(jobs):
                print(f"  {k}/{len(jobs)} done, {(time.time()-t0)/60:.1f} min", flush=True)

    # What the rows say they were measured under, against what was asked for. The arm reached
    # the header of the output and not the runs once, and the file was indistinguishable from a
    # real measurement of a cell it had never visited.
    wrong = [r for r in rows if tuple(r.get("layers", ())) != tuple(layers)
             or r.get("controller") != controller]
    if wrong:
        raise SystemExit(
            f"{len(wrong)} of {len(rows)} runs were measured under "
            f"{wrong[0].get('controller')} with layers {wrong[0].get('layers')}, against the "
            f"{controller} {a.arm} arm this was asked for. Nothing is written.")

    # A cell where every run raised took three seconds, printed a table of NaN and exited zero,
    # so the harness driving it recorded OK. Refusing to write is what makes that visible, since
    # the completion time was the only other signal and nothing reads it.
    done = [r for r in rows if r.get("completed")]
    if len(done) < MIN_COMPLETED:
        # A run that raised and a run that finished early fail differently and are worth
        # separating, since the first is usually a defect here and the second is the subject.
        raised = [r for r in rows if r.get("error")]
        worst = collections.Counter(r["error"] for r in raised).most_common(1)
        detail = (f"{len(raised)} raised, most commonly: {worst[0][0]}" if worst
                  else "none raised, so the runs started and stopped short")
        raise SystemExit(
            f"only {len(done)} of {len(rows)} runs completed, below the {MIN_COMPLETED} needed "
            f"for a median to mean anything, so nothing is written. {detail}")

    # Two statistics per measure, because they answer different questions and comparing one
    # against the other misled once. The range of the replicate medians is the spread across
    # disjoint groups actually drawn. The split-half is the same statistic the real baseline
    # in `cohort_variation.py` reports, the 95th percentile of the gap between two random
    # halves, computed here on each replicate's own runs so the two sides can be read against
    # each other like for like. A range over k groups sits near 1.7 sigma for k of three
    # while a split-half 95th percentile sits near 2.8, so quoting the first against the
    # second overstates the trial's variability relative to the bench. Group sizes matter
    # too and are printed: a median over more people is steadier for that reason alone.
    def split_half_95(values, draws=5000, seed=0):
        v = np.asarray(values, float)
        v = v[np.isfinite(v)]
        if len(v) < 8:
            return float("nan")
        rng_ = np.random.default_rng(seed)
        gaps = []
        for _ in range(draws):
            idx = rng_.permutation(len(v))
            half = len(v) // 2
            gaps.append(abs(np.median(v[idx[:half]]) - np.median(v[idx[half:]])))
        return float(np.percentile(gaps, 95))

    half_sizes = sorted({len([r for r in rows if r["replicate"] == i and r.get("completed")])
                         for i in range(len(reps))})
    print(f"\n  completed group sizes {half_sizes}; split halves are half of each. The real "
          f"baseline's halves are half of its cohort, so compare at the sizes printed.")
    print(f"\n  {'measure':22}" + "".join(f"{f'rep {i}':>10}" for i in range(len(reps)))
          + f"{'range':>9}{'split95':>9}")
    summary = {}
    for key, label in MEASURES:
        meds, halves = [], []
        for i in range(len(reps)):
            v = [r[key] for r in rows if r["replicate"] == i and r.get("completed")]
            meds.append(float(np.median(v)) if v else float("nan"))
            halves.append(split_half_95(v, seed=i))
        rng = float(np.nanmax(meds) - np.nanmin(meds))
        sh = float(np.nanmedian(halves))
        summary[key] = {"medians": meds, "range": rng,
                        "split_half_95_per_replicate": halves,
                        "split_half_95": sh}
        print(f"  {label:22}" + "".join(f"{m:>10.2f}" for m in meds)
              + f"{rng:>9.2f}{sh:>9.2f}")

    json.dump({"population": titrate.population_fingerprint(), "controller": controller,
               "arm": a.arm, "layers": list(layers),
               "provenance": provenance.stamp(),
               "replicates": [{"subjects": list(n), "match": i} for n, i in reps],
               "runs": rows, "summary": summary}, open(out_path, "w"), indent=1)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
