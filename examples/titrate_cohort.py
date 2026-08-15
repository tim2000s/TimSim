"""Titrate every subject's settings, and record what the procedure found.

Run this before benchmarking anything. A controller scored on settings nobody titrated is
being judged partly on the settings: across this population the physiological correction
factor is well below the median of 40.0 mg/dL per unit recorded in the pump settings of the
112 DCLP3 closed-loop participants, and handing oref0 SMB the physiological value doubles its
time below 70 mg/dL against handing it the real one.

    python examples/titrate_cohort.py [--subjects 20] [--days 28] [--workers 6]

The result is written beside the population and is not committed, since it derives from the
published parameter tables in the same way the population does.
"""
import argparse
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim.therapy import titrate


def _one(job):
    name, days, seed = job
    return titrate.titrate_subject(name, days=days, seed=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--cohort", default="adults",
                    help="'adults' for adult#001 upward, 'dclp3' for a cohort whose age "
                         "distribution follows the DCLP3 closed-loop arm, or 'recorded' for "
                         "the union of the cohorts in docs/measurements/cohorts.json")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    if a.cohort == "recorded":
        import json, os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "docs", "measurements", "cohorts.json")
        rec = json.load(open(path))
        stamped = rec.get("population")
        current = titrate.population_fingerprint()
        if stamped and current and stamped != current:
            raise SystemExit(f"cohorts.json was built against population {stamped} and the "
                             f"population on disk is {current}. Rerun examples/build_cohorts.py.")
        names = list(rec["union"])
        print(f"titrating the union of {', '.join(sorted(rec['cohorts']))}: {len(names)} subjects")
    elif a.cohort == "dclp3":
        from timsim.validation import dclp3
        from timsim.population import cohort
        names, short = cohort.matched(dclp3.ages(), n=a.subjects, seed=a.seed)
        names = [str(n) for n in names]
        print(f"DCLP3-matched cohort: {cohort.describe(names)}")
        if short:
            print(f"  age bins that could not supply their share: {short}")
    else:
        names = [f"adult#{i:03d}" for i in range(1, a.subjects + 1)]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        out = list(ex.map(_one, [(n, a.days, a.seed) for n in names]))

    found = [r for r in out if r["found"]]
    path = titrate.save(out, meta={"days": a.days, "seed": a.seed,
                                   "driver": titrate.REFERENCE_DRIVER,
                                   "scales": list(titrate.SCALES)})
    print(f"{len(found)}/{len(out)} subjects titrated, written to {path}\n")
    print(f"{'subject':>15}{'basal':>7}{'ISF x':>7}{'ISF':>7}{'TBR70':>8}{'TBR54':>8}"
          f"{'TIR':>7}{'CV':>7}  remaining misses")
    for r in out:
        if not r["found"]:
            print(f"{r['name']:>15}{'none':>7}   floors not met at any combination")
            continue
        last = r["trace"][-1]
        print(f"{r['name']:>15}{r['basal_scale']:>7.2f}{r['scale']:>7.2f}"
              f"{last.get('isf', float('nan')):>7.1f}{last['tbr70']:>8.2f}"
              f"{last['tbr54']:>8.2f}{last['tir']:>7.1f}{last['cv']:>7.1f}  "
              f"{', '.join(last['fails']) or 'none'}")
    if found:
        levers = {}
        for r in found:
            levers[r["lever"]] = levers.get(r["lever"], 0) + 1
        print("\nlever used: " + ", ".join(f"{k} {v}" for k, v in sorted(levers.items())))
        bs = np.array([r["basal_scale"] for r in found], float)
        print(f"basal scale: median {np.median(bs):.2f}, range {bs.min():.2f} to {bs.max():.2f}")
        sc = np.array([r["scale"] for r in found], float)
        isf = np.array([r["trace"][-1]["isf"] for r in found], float)
        print(f"\nscale: median {np.median(sc):.2f}, range {sc.min():.2f} to {sc.max():.2f}")
        print(f"correction factor: median {np.median(isf):.1f} mg/dL per unit, "
              f"range {isf.min():.1f} to {isf.max():.1f}   "
              f"(DCLP3 participants ran a median of 40.0)")


if __name__ == "__main__":
    main()
