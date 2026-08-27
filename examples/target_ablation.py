"""What the glucose target does to a benchmark, with the algorithm and the person held fixed.

A simulator asked to judge an insulin delivery algorithm reports a number, and that number depends
on inputs which are not the algorithm. The target is one of them and it is the least visible,
because it is usually inherited from whatever the population tables happen to carry rather than
chosen. This package ships 100 to 120 mg/dL. Tandem's Control-IQ holds 112.5 to 160 in its automatic
mode and corrects towards 110. Real users of open-source systems commonly set 100 to 110 and
frequently override it upward.

So a comparison between two published results measured at different targets is partly a comparison
of targets. This measures how much of one, by running one cohort under one algorithm at several
targets with everything else fixed: the same subjects, the same seed, the same titrated settings,
the same layers.

The target moves through the profile rather than through the controller, because that is where both
shipped algorithms read it from and because a target set on the controller would not reach the one
driven across a process boundary. `oref.py` reads `profile.target_lo` and `target_hi` unless given
an explicit override, and the built-in loop corrects towards its own constant, which is why the
built-in loop is not one of the arms here.

    python examples/target_ablation.py --cohort dclp3 --controller oref --workers 7
"""
import argparse
import concurrent.futures as futures
import dataclasses
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
SEED = seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
OUT = os.path.join(MEASUREMENTS, "target_ablation.json")

# (low, high) in mg/dL. The first is what this package ships, the last is Control-IQ's automatic
# range, and the two between are the settings open-source users most often choose.
TARGETS = ((100.0, 120.0), (100.0, 110.0), (110.0, 130.0), (112.5, 160.0))


def one(job):
    cohort, controller, name, lo, hi = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    t0 = time.time()
    prof = titrate.profile_for(name)
    prof = dataclasses.replace(prof, target_lo=float(lo), target_hi=float(hi))
    ctrl = controller
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl,
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"cohort": cohort, "controller": controller, "name": name,
                "target_lo": lo, "target_hi": hi, "completed": False,
                "error": str(exc)[:200], "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    out = {"cohort": cohort, "controller": controller, "name": name,
           "target_lo": float(lo), "target_hi": float(hi),
           "completed": bool(r.completed), "seconds": time.time() - t0,
           "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days),
           "termination": getattr(r, "termination", None)}
    out["tir_cgm"] = float(100.0 * np.mean((cgm >= 70) & (cgm <= 180)))
    out["tbr70_cgm"] = float(100.0 * np.mean(cgm < 70))
    out["tbr54_cgm"] = float(100.0 * np.mean(cgm < 54))
    out["tar180_cgm"] = float(100.0 * np.mean(cgm > 180))
    out["mean_cgm"] = float(np.mean(cgm))
    out["cv_cgm"] = float(100.0 * np.std(cgm) / np.mean(cgm))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cohort", default="dclp3")
    ap.add_argument("--controller", default="oref")
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 7)))
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    if rec.get("population") != titrate.population_fingerprint():
        raise SystemExit("cohorts.json was built against a different population.")
    titrated = set(titrate.titrated_subjects())
    subs = [s for s in rec["cohorts"][a.cohort]["subjects"] if s in titrated]
    jobs = [(a.cohort, a.controller, n, lo, hi) for lo, hi in TARGETS for n in subs]
    print(f"{len(subs)} subjects x {len(TARGETS)} targets = {len(jobs)} runs "
          f"on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 40 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    json.dump({"provenance": provenance.stamp(), "cohort": a.cohort,
               "controller": a.controller, "targets": [list(t) for t in TARGETS],
               "days": DAYS, "layers": list(LAYERS), "runs": rows},
              open(a.out, "w"), indent=1)

    print(f"\n{'target':>14}{'n':>5}{'TIR':>8}{'TAR180':>9}{'TBR70':>8}{'TBR54':>8}"
          f"{'meanG':>8}{'U/day':>8}")
    base = None
    for lo, hi in TARGETS:
        done = [r for r in rows if r.get("completed")
                and r["target_lo"] == lo and r["target_hi"] == hi]
        if not done:
            continue
        med = lambda k: float(np.median([r[k] for r in done]))
        if base is None:
            base = med("tbr70_cgm")
        print(f"{f'{lo:.0f}-{hi:.0f}':>14}{len(done):>5}{med('tir_cgm'):>8.1f}"
              f"{med('tar180_cgm'):>9.1f}{med('tbr70_cgm'):>8.2f}{med('tbr54_cgm'):>8.2f}"
              f"{med('mean_cgm'):>8.1f}{med('insulin_per_day'):>8.1f}")

    # Paired, since the between-subject spread is larger than the effect being measured.
    rng = np.random.default_rng(SEED)
    by = {}
    for r in rows:
        if r.get("completed"):
            by.setdefault(r["name"], {})[(r["target_lo"], r["target_hi"])] = r
    ref = TARGETS[0]
    print(f"\npaired against the shipped {ref[0]:.0f}-{ref[1]:.0f} target, over subjects "
          f"completing both")
    for t in TARGETS[1:]:
        both = [v for v in by.values() if ref in v and t in v]
        if len(both) < 10:
            continue
        line = f"  {t[0]:.0f}-{t[1]:.0f}: "
        for key, lab in (("tir_cgm", "TIR"), ("tbr70_cgm", "TBR70"), ("tar180_cgm", "TAR180")):
            d = np.array([v[t][key] - v[ref][key] for v in both])
            b = np.array([np.median(rng.choice(d, len(d), True)) for _ in range(2000)])
            line += (f"{lab} {np.median(d):+.2f} ({np.percentile(b, 2.5):+.2f} to "
                     f"{np.percentile(b, 97.5):+.2f})  ")
        print(line + f"n={len(both)}")
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
