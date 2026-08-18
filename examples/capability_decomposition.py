"""Why the capability table fell from ten of ten to four of ten.

The table is the package's claim about what it can be used for: ten signatures, each measured
identically on simulated and real data, counted by how many medians land inside the range four
real cohorts span. It was reported at ten of ten. On the rebuilt population, with the defence
gain refitted and the panels moved onto titrated settings, it is four of ten.

Three changes could account for that and they arrived together, so none of them is attributable
without holding the others still. Each arm below changes exactly one thing from the current
configuration and everything else is held:

    current       titrated settings, defence gain 0.05, site layer on
    settings      the same with physiological settings, which is what the table used to run
    gain          the same with the defence gain at 0.20, the value fitted on 34 adults
    nosite        the same without the infusion site layer

The comparison is the count of signatures inside the real range, and the per-signature medians
beside it, because a count moving by one can hide two movements in opposite directions.

    python examples/capability_decomposition.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim import seeds
from timsim.analysis import signatures as S

OUT = os.path.join(MEASUREMENTS, "capability_decomposition.json")
SUBJECTS = [f"adult#{i:03d}" for i in range(1, 21)]
DRIVERS = ["basal-bolus", "trend", "boost", "oref"]
FULL = ("physiology", "behaviour", "sensor", "site")
DAYS, SEED = 28, seeds.BENCH

# One thing changed per arm, everything else held.
ARMS = {
    "current":  {"layers": FULL, "titrated": True,  "egp": None},
    "settings": {"layers": FULL, "titrated": False, "egp": None},
    "gain":     {"layers": FULL, "titrated": True,  "egp": 0.20},
    "nosite":   {"layers": ("physiology", "behaviour", "sensor"), "titrated": True, "egp": None},
}


def driver_for(name, d, prof):
    if d == "boost":
        from timsim.controller import boost_bridge
        return boost_bridge.BoostBridgeController(name, profile=prof)
    if d == "oref":
        from timsim.controller import oref
        return oref.OrefController(name, profile=prof)
    return d


def one(job):
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate, profile as profile_mod
    name, driver, arm = job
    spec = ARMS[arm]
    prof = (titrate.profile_for(name) if spec["titrated"]
            else profile_mod.for_subject(name))
    ctrl = driver_for(name, driver, prof)
    kw = {} if spec["egp"] is None else {"hypo_egp_defence": spec["egp"]}
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=spec["layers"],
                     controller=ctrl, profile=prof, **kw)
    except Exception as e:
        return {"name": name, "driver": driver, "arm": arm, "completed": False,
                "error": str(e)[:150]}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    packed = S.from_result(r)
    return {"name": name, "driver": driver, "arm": arm, "completed": bool(r.completed),
            "values": {k: float(fn(packed)) for k, _, fn in S.SIGS}}


def main(workers=10):
    jobs = [(n, d, a) for a in ARMS for d in DRIVERS for n in SUBJECTS]
    print(f"{len(ARMS)} arms x {len(DRIVERS)} drivers x {len(SUBJECTS)} subjects "
          f"= {len(jobs)} runs", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(one, jobs))

    errs = [r for r in rows if r.get("error")]
    if errs:
        print(f"\n  {len(errs)} runs errored, e.g. {errs[0]['name']}: {errs[0]['error'][:110]}")

    report, counts = {}, {}
    for arm in ARMS:
        ok = [r for r in rows if r["arm"] == arm and r.get("completed")]
        vals, inside = {}, 0
        for k, _, _ in S.SIGS:
            a = np.array([r["values"][k] for r in ok if k in r.get("values", {})], float)
            a = a[np.isfinite(a)]
            if not len(a):
                continue
            m = float(np.median(a))
            vals[k] = m
            inside += S.in_real_range(k, m)
        report[arm] = {"median": vals, "inside": inside, "completed": len(ok),
                       "n": sum(1 for r in rows if r["arm"] == arm)}
        counts[arm] = inside

    keys = [k for k, _, _ in S.SIGS]
    print(f"\n  {'signature':11}{'range':>15}" + "".join(f"{a:>11}" for a in ARMS))
    for k in keys:
        lo, hi = S.REAL_RANGE[k]
        cells = ""
        for a in ARMS:
            v = report[a]["median"].get(k)
            mark = "" if v is None else ("*" if S.in_real_range(k, v) else " ")
            cells += f"{'-' if v is None else f'{v:.2f}{mark}':>11}"
        print(f"  {k:11}{f'{lo}-{hi}':>15}{cells}")
    print(f"\n  {'inside range':26}" + "".join(f"{counts[a]:>11}" for a in ARMS))
    print(f"  {'completed':26}"
          + "".join(f"{report[a]['completed']}/{report[a]['n']:<7}" for a in ARMS))

    base = counts["current"]
    print("\n  attribution, against the current configuration:")
    for a in ARMS:
        if a == "current":
            continue
        print(f"    reverting {a:9} -> {counts[a]:>2}/10  ({counts[a]-base:+d})")
    print("\n  * marks a median inside the real range, with the 10 per cent padding applied")

    json.dump({"arms": {a: dict(ARMS[a], layers=list(ARMS[a]["layers"])) for a in ARMS},
               "report": report, "counts": counts, "runs": rows},
              open(OUT, "w"), indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
