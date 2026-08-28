"""What the titration ladder returns when it is run under the open-loop regimen.

Titration runs under the built-in correction loop, and the reason given for that choice has
two parts. One is circularity, which needs no measurement: a ladder run under the algorithm
being benchmarked lets a controller that provokes hypoglycaemia be answered by the bench
weakening its subjects' settings until the hypoglycaemia stops. The other is exposure, and it
does need one. A regimen that never puts a subject below 70 mg/dL never exercises the settings,
so the search returns its own starting point and the store records a titration that did not
happen.

That second argument was carried for months as a figure written into a docstring, from a run on
a population and a settings store that no longer exist. This reruns the rejected design on the
current store: the same ladder, the same floors, the same subjects, driven by the open-loop
basal-bolus regimen instead of the correction loop.

The comparison is against the adopted store rather than against a target, since the question is
not whether the open-loop ladder produces good settings but whether it produces any answer at
all. Both are read on the sensor signal, which is what the consensus targets were set on.

    python examples/titration_reference.py --cohort dclp3 --workers 7
"""
import argparse
import concurrent.futures as futures
import json
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

DAYS = 28
OUT = os.path.join(MEASUREMENTS, "titration_reference.json")

# The regimen under test here, against the "trend" correction loop the store was built under.
DRIVER = "basal-bolus"


def one(job):
    name, days, seed = job
    from timsim.therapy import titrate
    t0 = time.time()
    try:
        r = titrate.titrate_subject(name, days=days, seed=seed, driver=DRIVER)
    except titrate.TitrationError as exc:
        return {"name": name, "fatal": True, "error": str(exc)[:200],
                "seconds": time.time() - t0}
    r["seconds"] = time.time() - t0
    return r


def first_rung(rec):
    """The physiological rung: scale 1.0 on an untouched basal, which every ladder tries."""
    for x in rec.get("trace", ()):
        if x.get("scale") == 1.0 and x.get("basal_scale") == 1.0:
            return x
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cohort", default="dclp3")
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--seed", type=int, default=seeds.TITRATION)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 7)))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    if rec.get("population") != titrate.population_fingerprint():
        raise SystemExit("cohorts.json was built against a different population.")
    subs = list(rec["cohorts"][a.cohort]["subjects"])
    print(f"{len(subs)} subjects of {a.cohort} under the {DRIVER} regimen "
          f"on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, [(n, a.days, a.seed) for n in subs]), 1):
            rows.append(r)
            if i % 10 == 0:
                print(f"  {i}/{len(subs)}", flush=True)

    json.dump({"provenance": provenance.stamp(), "cohort": a.cohort, "driver": DRIVER,
               "days": a.days, "seed": a.seed, "subjects": rows},
              open(a.out, "w"), indent=1)

    ok = [r for r in rows if not r.get("fatal")]
    fatal = len(rows) - len(ok)
    at_start = [r for r in ok if r.get("found") and r.get("scale") == 1.0
                and r.get("basal_scale") == 1.0]
    moved = [r for r in ok if r.get("found") and r not in at_start]
    never = [r for r in ok if not r.get("found")]
    print(f"\n{len(ok)} ladders ran, {fatal} faulted")
    print(f"  clear at the physiological settings, ladder returns its start : "
          f"{len(at_start)}/{len(ok)}")
    print(f"  weakened by the ladder                                        : {len(moved)}/{len(ok)}")
    print(f"  clear at no rung                                              : {len(never)}/{len(ok)}")

    # The exposure argument, on the physiological rung every subject ran.
    base = [first_rung(r) for r in ok]
    base = [x for x in base if x and "tbr70" in x]
    if base:
        med = lambda k: float(np.median([x[k] for x in base]))
        print(f"\nat the physiological rung, {len(base)} subjects, {DRIVER}")
        for k, lab in (("tbr70", "below 70 %"), ("tbr54", "below 54 %"), ("tir", "in range %"),
                       ("tar250", "above 250 %"), ("cv", "CV %")):
            v = [x[k] for x in base]
            print(f"  {lab:>12}  median {np.median(v):6.2f}  IQR "
                  f"{np.percentile(v, 25):6.2f} to {np.percentile(v, 75):6.2f}")
        fails = {}
        for x in base:
            for f in x.get("fails", ()):
                fails[f] = fails.get(f, 0) + 1
        print("  targets missed at that rung: " +
              ", ".join(f"{k} {v}/{len(base)}" for k, v in sorted(fails.items())))

    # The same subjects under the regimen the store was actually built under.
    store = titrate.load()
    if store:
        theirs = [store["subjects"][r["name"]] for r in ok if r["name"] in store["subjects"]]
        ref = [first_rung(x) for x in theirs]
        ref = [x for x in ref if x and "tbr70" in x]
        if ref:
            print(f"\nthe same rung under the correction loop the store was built under, "
                  f"{len(ref)} subjects")
            for k, lab in (("tbr70", "below 70 %"), ("tbr54", "below 54 %")):
                v = [x[k] for x in ref]
                print(f"  {lab:>12}  median {np.median(v):6.2f}  IQR "
                      f"{np.percentile(v, 25):6.2f} to {np.percentile(v, 75):6.2f}")
            held = sum(1 for x in theirs if x.get("found") and x.get("scale") == 1.0
                       and x.get("basal_scale") == 1.0)
            print(f"  clear at the physiological settings: {held}/{len(theirs)}")

    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
