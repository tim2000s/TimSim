"""How much of the simulator's excess time in range is the correction factor it is dosed from.

The titration ladder in `therapy/titrate.py` searches basal first and reaches the correction
factor only for subjects that basal alone cannot make safe. Across the store that is 42 of 295
subjects, so 253 keep the correction factor their own physiology implies. That value has a median
near 19 mg/dL per unit against the 40.0 the DCLP3 participants ran, so most benchmarked subjects
correct a high with roughly twice the insulin a real person's settings would ask for.

This runs one cohort under one algorithm at a series of multipliers applied on top of whatever
titration adopted, and reports what each does to time in range, time above 180 and both
hypoglycaemia measures. A multiplier of 1.0 reproduces the benchmark arm, so the sweep contains
its own control and the curve can be read against a figure already published rather than against
a rerun.

It answers a question the arms in `docs/BASELINE.md` cannot, because every one of them holds the
settings fixed at what titration adopted. The layers and the settings are separate explanations
for the same gap, and nothing so far has separated them on the current population.

    python examples/settings_sweep.py --cohort dclp3 --controller control-iq
    python examples/settings_sweep.py --scales 1.0 1.5 2.0 2.5 --workers 13
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


def one(job):
    """One subject at one multiplier, on the titrated profile with the factor rescaled."""
    cohort, controller, name, scale = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    t0 = time.time()
    # The multiplier goes on top of the adopted profile rather than through
    # `profile.for_subject(isf_scale=...)`, because the adopted profile also carries a basal
    # scale, and rebuilding it from the population table would silently discard that and
    # measure two changes at once.
    prof = titrate.profile_for(name)
    prof = dataclasses.replace(prof, isf=prof.isf * float(scale))
    ctrl = controller
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl,
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"cohort": cohort, "controller": controller, "name": name, "scale": scale,
                "completed": False, "error": str(exc)[:200], "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    out = {"cohort": cohort, "controller": controller, "name": name, "scale": float(scale),
           "completed": bool(r.completed), "seconds": time.time() - t0,
           "isf_mean": float(np.mean(prof.isf)),
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
    ap.add_argument("--controller", default="control-iq")
    ap.add_argument("--scales", nargs="+", type=float,
                    default=[1.0, 1.5, 2.0, 2.5])
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 8)))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "settings_sweep.json"))
    a = ap.parse_args()

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    current = titrate.population_fingerprint()
    if rec.get("population") != current:
        raise SystemExit(f"cohorts.json was built against population {rec['population']} and "
                         f"the population on disk is {current}. Rerun build_cohorts.py.")
    titrated = set(titrate.titrated_subjects())
    subjects = [s for s in rec["cohorts"][a.cohort]["subjects"] if s in titrated]
    jobs = [(a.cohort, a.controller, n, s) for s in a.scales for n in subjects]
    print(f"{len(subjects)} subjects x {len(a.scales)} scales = {len(jobs)} runs "
          f"on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    json.dump({"provenance": provenance.stamp(), "cohort": a.cohort,
               "controller": a.controller, "scales": a.scales, "days": DAYS,
               "layers": list(LAYERS), "runs": rows},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}\n")

    print(f"{'scale':>7}{'CF':>8}{'n':>6}{'TIR':>8}{'TAR180':>9}{'TBR70':>8}"
          f"{'TBR54':>8}{'meanG':>8}{'U/day':>8}")
    for s in a.scales:
        done = [r for r in rows if r["scale"] == s and r.get("completed")]
        if not done:
            print(f"{s:>7.2f}   no completed runs")
            continue
        med = lambda k: np.median([r[k] for r in done])
        print(f"{s:>7.2f}{med('isf_mean'):>8.1f}{len(done):>6}{med('tir_cgm'):>8.1f}"
              f"{med('tar180_cgm'):>9.1f}{med('tbr70_cgm'):>8.1f}{med('tbr54_cgm'):>8.1f}"
              f"{med('mean_cgm'):>8.1f}{med('insulin_per_day'):>8.1f}")


if __name__ == "__main__":
    main()
