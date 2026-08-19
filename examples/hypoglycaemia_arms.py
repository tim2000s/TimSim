"""Do the production floor and the rescue absorption scale move the outcome, not just the clamp?

The clamp is where the defect was found and the matrix is where it matters. A subject producing
0.3 mg/kg/min instead of nothing at a clamp may still fall just as far during a spontaneous low,
because the insulin driving one is about half the clamp's.

Three arms, paired on the subject, on the cohorts the bench matrix uses:

    base        the shipped configuration
    floor       plus the production floor
    floor+bio   plus the rescue absorption scale, on top of the floor

The order is fixed by `docs/DESIGN_HYPOGLYCAEMIA.md` and it is not arbitrary. The floor changes
how deep lows get, which changes how much rescue carbohydrate is eaten, which is what the second
mechanism acts on, so the second has to be measured against a bench that already has the first.

    python examples/hypoglycaemia_arms.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import time
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "rescue_bio_alone.json")
DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")

# The rescue scale is the ratio of the real carbohydrate response to the simulated one: real
# 15.9 to 19.7 mg/dL per logged 10 g against a simulated 21.1 to 21.6, so the midpoints give
# about 0.83. It is a bioavailability, so the person still eats what the record says.
RESCUE_BIO = 0.83

# Every arm states every mechanism explicitly, including the control. Leaving the control to
# inherit module defaults is what made an earlier run compare a configuration with itself.
ARMS = {
    "base":      {"hypo_egp_floor": 0.0, "rescue_bioavailability": 1.0},
    "bio":       {"hypo_egp_floor": 0.0, "rescue_bioavailability": RESCUE_BIO},
}


def one(job):
    cohort, controller, name, arm = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    ctrl, t0 = controller, time.time()
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl,
                     profile=prof, announcement="some", **ARMS[arm])
    except Exception as exc:
        return {"cohort": cohort, "controller": controller, "arm": arm, "name": name,
                "completed": False, "error": str(exc)[:200]}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    from timsim.analysis import signatures as S
    packed = S.from_result(r)
    return {"cohort": cohort, "controller": controller, "arm": arm, "name": name,
            "completed": bool(r.completed),
            "tir": float(100 * np.mean((cgm >= 70) & (cgm <= 180))),
            "tbr70": float(100 * np.mean(cgm < 70)),
            "tbr54": float(100 * np.mean(cgm < 54)),
            "mean": float(np.mean(cgm)),
            "cv": float(100 * np.std(cgm, ddof=1) / np.mean(cgm)),
            "rescue_per_30d": float(30.0 * r.rescue_events / days),
            "rescue_g_per_day": float(r.rescue_grams / days),
            "hypo_rec": float(S._hypo(packed)[0]),
            "hypo_reb": float(100 * S._hypo(packed)[1])}


def boot(d, n=5000, seed=0):
    d = np.asarray([x for x in d if np.isfinite(x)], float)
    if len(d) < 3:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main():
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    from timsim.therapy import titrate
    tit = set(titrate.titrated_subjects())
    pairings = [("dclp3", "control-iq"), ("dclp3", "oref"), ("commons", "oref")]
    jobs = []
    for cohort, controller in pairings:
        subs = [s for s in rec["cohorts"][cohort]["subjects"] if s in tit]
        for arm in ARMS:
            jobs += [(cohort, controller, s, arm) for s in subs]
    print(f"{len(jobs)} runs, {len(ARMS)} arms across {len(pairings)} pairings", flush=True)

    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=int(os.environ.get("WORKERS", "12"))) as ex:
        for i, row in enumerate(ex.map(one, jobs), 1):
            rows.append(row)
            if i % 40 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} done, {(time.time()-t0)/60:.1f} min", flush=True)

    idx = {}
    for r in rows:
        idx.setdefault((r["cohort"], r["controller"]), {}).setdefault(r["arm"], {})[r["name"]] = r

    MEAS = [("tbr54","Time below 54 %"),("tbr70","Time below 70 %"),("hypo_reb","Rebound %"),
            ("hypo_rec","Recovery min"),("tir","Time in range %"),("cv","Variability %"),
            ("rescue_g_per_day","Rescue g/day")]
    report = {}
    for key, arms in sorted(idx.items()):
        base = arms.get("base", {})
        for arm in ("bio",):
            other = arms.get(arm, {})
            keep = [n for n in base
                    if base[n].get("completed") and other.get(n, {}).get("completed")]
            if len(keep) < 10:
                continue
            print(f"\n=== {key[0]} / {key[1]} : {arm} against base, paired over {len(keep)} ===")
            print(f"  {'measure':18}{'base':>9}{arm:>11}{'paired difference':>26}")
            for k, lab in MEAS:
                x = np.array([base[n][k] for n in keep], float)
                y = np.array([other[n][k] for n in keep], float)
                m, lo, hi = boot(y - x)
                flag = "" if lo <= 0 <= hi else "  *"
                report[f"{key[0]}|{key[1]}|{arm}|{k}"] = {"base": float(np.nanmedian(x)),
                                                          "arm": float(np.nanmedian(y)),
                                                          "diff": m, "lo": lo, "hi": hi}
                print(f"  {lab:18}{np.nanmedian(x):>9.2f}{np.nanmedian(y):>11.2f}"
                      f"{f'{m:+.2f} [{lo:+.2f},{hi:+.2f}]':>26}{flag}")

    for key, arms in sorted(idx.items()):
        line = "  ".join(f"{a} {sum(1 for v in arms.get(a, {}).values() if v.get('completed'))}"
                         f"/{len(arms.get(a, {}))}" for a in ARMS)
        print(f"\n  completion {key[0]}/{key[1]}: {line}")

    json.dump({"arms": ARMS, "rescue_bio": RESCUE_BIO, "runs": rows, "report": report,
               "provenance": provenance.stamp()}, open(OUT, "w"), indent=1)
    print(f"\n  * marks a difference whose interval excludes zero")
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
