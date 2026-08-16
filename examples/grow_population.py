"""Grow the population, generating the classes side by side.

The hypoglycaemia comparison is the one this bench cannot currently settle. The gap between
simulated and real time below 54 mg/dL is about two of the real between-person spread, and the
interval on a median computed over fifteen subjects is about the same size, so the difference
cannot be separated from which subjects were drawn. The interval narrows as the square root of
the cohort, and the sizes that would make each gap establishable at half its width are:

    DCLP3 / Control-IQ        below 70: 61     below 54: 51
    DCLP3 / oref0 SMB         below 70: 20     below 54: 26
    Commons / oref0 SMB       below 70: 68     below 54: 87

So about ninety subjects per cohort. Three disjoint cohorts at that size, which is what the
group effect needs, is 270 matched subjects, and matching to a trial that is 72 per cent adult
from a population that is 34 per cent adult needs several times that to draw from.

Generation is per class and each class has its own seeded stream and its own block of row
indices, so the three run as separate processes and are concatenated. Nothing about the result
depends on that: a class's draws are the same whether or not another class is being drawn at
the same time.

Growing is append-only. The subjects already generated keep their names and their parameters,
so a larger population costs nothing already measured; only analyses wanting the larger cohorts
have to run again.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor

import pandas as pd

from timsim.population.generate import CLASSES, generate

PARAMS = os.path.join(REPO, "timsim", "population", "params")


def _one_class(job):
    klass, count, seed = job
    t0 = time.time()
    rows, therapy, report = generate(n=count, seed=seed, split={klass: count}, verbose=False)
    return {"klass": klass, "rows": rows, "therapy": therapy, "report": report,
            "seconds": time.time() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--adult-share", type=float, default=0.5,
                    help="the reference trials are majority adult and the classes are equal "
                         "by default, which is what makes adults the binding constraint on "
                         "how many disjoint matched cohorts the population supports")
    a = ap.parse_args()

    adults = int(round(a.n * a.adult_share))
    rest = a.n - adults
    split = {"adult": adults,
             "adolescent": rest // 2 + rest % 2,
             "child": rest // 2}
    print(f"growing to {a.n} subjects: " + ", ".join(f"{k} {v}" for k, v in split.items()))
    print("three classes in parallel, each with its own stream\n", flush=True)

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=len(CLASSES)) as ex:
        out = list(ex.map(_one_class, [(k, v, a.seed) for k, v in split.items()]))

    rows, therapy = [], []
    for r in sorted(out, key=lambda r: CLASSES.index(r["klass"])):
        rows += r["rows"]
        therapy += r["therapy"]
        rep = r["report"]
        print(f"  {r['klass']:11} {len(r['rows']):3d} accepted from "
              f"{rep.get('candidates', '?')} candidates in {r['seconds'] / 60:.1f} min")

    pd.DataFrame(rows).to_csv(os.path.join(PARAMS, "vpop_params.csv"), index=False)
    pd.DataFrame(therapy).to_csv(os.path.join(PARAMS, "vpop_quest.csv"), index=False)
    json.dump({"requested": a.n, "accepted": len(rows), "seed": a.seed, "split": split,
               "per_class": {r["klass"]: r["report"] for r in out}},
              open(os.path.join(PARAMS, "vpop_report.json"), "w"), indent=1)
    print(f"\n{len(rows)} subjects written in {(time.time() - t0) / 60:.1f} min")

    from timsim.therapy import titrate
    print(f"population fingerprint is now {titrate.population_fingerprint()}; the titration "
          f"store is stale and will be refused until it is rerun")


if __name__ == "__main__":
    main()
