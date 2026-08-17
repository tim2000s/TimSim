"""Every simulated arm the validation paper needs, in one run.

The question each pairing answers is the same: holding one algorithm fixed, how far does the
simulated population sit from the real population running that algorithm, on the bare S2008
patient and on the layered bench? So the algorithm never varies inside a pairing and the
bench does.

    dclp3     control-iq   against the closed-loop arm of the DCLP3 trial
    dclp3     oref         the same cohort under a shipped algorithm
    commons   oref         against OpenAPS Data Commons users, who run this algorithm
    close_it  oref         against the CLOSE-IT trial, which randomised meal announcement

Announcement is a property of the person, so it only varies on the layered bench: the bare
patient has no behaviour layer and announces everything by construction. That gives four arms
per pairing rather than six.

Cohorts come from docs/measurements/cohorts.json and settings from the titration store, both
of which are stamped with the population they were built against, so a stale one raises
rather than quietly dosing a subject on another body's settings.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import argparse
import json
import time
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim import provenance

from timsim import seeds

DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
OUT = os.path.join(MEASUREMENTS, "bench_matrix.json")

PAIRINGS = [("dclp3", "control-iq"), ("dclp3", "oref"),
            ("commons", "oref"), ("close_it", "oref")]
BENCHES = [("bare", (), "some"), ("layered_always", LAYERS, "always"),
           ("layered_some", LAYERS, "some"), ("layered_never", LAYERS, "never")]


def one(job):
    cohort, controller, bench, name, layers, announcement = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    arm = f"{cohort}|{controller}|{bench}"
    prof = titrate.profile_for(name)
    ctrl, t0 = controller, time.time()
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=layers, controller=ctrl,
                     profile=prof, announcement=announcement)
    except Exception as exc:
        return {"arm": arm, "cohort": cohort, "controller": controller, "bench": bench,
                "name": name, "completed": False, "error": str(exc)[:200],
                "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    bg = np.asarray(r.bg, dtype=float)
    days = max(len(bg) * 5.0 / 1440.0, 1e-9)
    out = {"arm": arm, "cohort": cohort, "controller": controller, "bench": bench,
           "name": name, "completed": bool(r.completed), "days": float(days),
           "seconds": time.time() - t0,
           "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days),
           "rescue_per_30d": float(30.0 * getattr(r, "rescue_events", 0) / days),
           "final_bg": float(bg[-1]), "lowest_bg": float(np.min(bg)),
           "highest_bg": float(np.max(bg))}
    for sig, lab in ((cgm, "cgm"), (bg, "bg")):
        out[f"tir_{lab}"] = float(100.0 * np.mean((sig >= 70) & (sig <= 180)))
        out[f"tbr70_{lab}"] = float(100.0 * np.mean(sig < 70))
        out[f"tbr54_{lab}"] = float(100.0 * np.mean(sig < 54))
        out[f"tar180_{lab}"] = float(100.0 * np.mean(sig > 180))
        out[f"mean_{lab}"] = float(np.mean(sig))
        out[f"cv_{lab}"] = float(100.0 * np.std(sig, ddof=1) / np.mean(sig))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", default="1/1",
                    help="run one slice of the run list, as i/n. Slices are taken by "
                         "position after the list is built, so every machine builds the same "
                         "list from the same cohorts and takes a disjoint part of it.")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    # Named so nothing later can shadow them. They were `i` and `n`, and both were: the
    # progress loop rebound `i` to the completed-row count and the per-pairing print rebound
    # `n` to the last cohort's size, so the shard stamp recorded neither the index nor the
    # count. `merge_shards.py` reads that stamp to check it has every shard exactly once.
    shard_index, shard_count = (int(x) for x in a.shard.split("/"))

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    current = titrate.population_fingerprint()
    if rec.get("population") and rec["population"] != current:
        raise SystemExit(f"cohorts.json was built against population {rec['population']} and "
                         f"the population on disk is {current}. Rerun build_cohorts.py.")
    titrated = set(titrate.titrated_subjects())

    jobs = []
    for cohort, controller in PAIRINGS:
        subjects = [s for s in rec["cohorts"][cohort]["subjects"] if s in titrated]
        for bench, layers, announcement in BENCHES:
            jobs += [(cohort, controller, bench, n, layers, announcement) for n in subjects]
    total = len(jobs)
    if shard_count > 1:
        jobs = jobs[shard_index - 1::shard_count]
        print(f"shard {shard_index} of {shard_count}: {len(jobs)} of {total} runs", flush=True)
    print(f"{len(PAIRINGS)} pairings, {len(BENCHES)} benches, {len(jobs)} runs", flush=True)
    for cohort, controller in PAIRINGS:
        n_titrated = len([s for s in rec["cohorts"][cohort]["subjects"] if s in titrated])
        print(f"  {cohort:9} {controller:11} {n_titrated} titrated subjects", flush=True)

    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=int(os.environ.get("WORKERS", "10"))) as ex:
        for i, row in enumerate(ex.map(one, jobs), 1):
            rows.append(row)
            if i % 20 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} done, {(time.time()-t0)/60:.1f} min", flush=True)
            if row.get("error"):
                print(f"  ! {row['arm']} {row['name']}: {row['error'][:110]}", flush=True)
    json.dump({"population": current, "days": DAYS, "seed": SEED,
               "shard": {"index": shard_index, "of": shard_count,
                         "runs_in_shard": len(jobs), "runs_total": total},
               "provenance": provenance.stamp(), "runs": rows},
              open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out} after {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
