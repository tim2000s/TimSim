"""How much of a pairing's distance from real is the controller rather than the person.

The bench matrix runs each cohort under the algorithm its reference population used, which is
what makes the comparison against real people fair and also means no arm ever varies the
controller alone. Two of those algorithms are not the same kind of object. oref0 SMB is the
shipped code, driven across a process boundary; the Control-IQ arm is a shape built from the
published description, and `controller/loop.py` records that the parameters driving its result
are the ones Tandem does not publish.

That matters because the two pairings disagree about how far this simulator sits from real
people. Against DCLP3 under the Control-IQ stand-in the gap in time in range is 9.5 percentage
points; against the OpenAPS Data Commons under oref0 it is 4.6. A person-side mechanism sized to
close the first will overshoot if half of it belongs to the controller.

This runs both cohorts under both controllers, so the controller varies with the person held
fixed. It needs no real reference, because the comparison is between two simulated arms of the
same subjects, and it is paired per subject for the same reason the bench matrix is: the
between-subject spread here is larger than the effect being measured.

    python examples/controller_crosscheck.py --workers 13
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
SEED = seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
COHORTS = ("dclp3", "commons")
CONTROLLERS = ("control-iq", "oref")
MEASURES = [("tir_cgm", "TIR %"), ("tar180_cgm", "TAR180 %"), ("tbr70_cgm", "TBR70 %"),
            ("tbr54_cgm", "TBR54 %"), ("mean_cgm", "Mean glucose"), ("cv_cgm", "CV %")]


def one(job):
    """One subject under one controller, on its adopted settings and all four layers."""
    cohort, controller, name = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    t0 = time.time()
    prof = titrate.profile_for(name)
    ctrl = controller
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl,
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"cohort": cohort, "controller": controller, "name": name,
                "completed": False, "error": str(exc)[:200], "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    out = {"cohort": cohort, "controller": controller, "name": name,
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


def paired(rows, cohort, key):
    """The per-subject difference between the two controllers, over subjects completing both."""
    by = {}
    for r in rows:
        if r["cohort"] == cohort and r.get("completed"):
            by.setdefault(r["name"], {})[r["controller"]] = r
    both = [v for v in by.values() if len(v) == 2]
    if not both:
        return None
    d = np.asarray([v["control-iq"][key] - v["oref"][key] for v in both], float)
    # Percentile interval over subjects, the same resampling the bench tables use.
    rng = np.random.default_rng(seeds.BENCH)
    boot = np.asarray([np.median(rng.choice(d, size=len(d), replace=True))
                       for _ in range(2000)], float)
    return {"n": len(d), "median": float(np.median(d)),
            "interval": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 8)))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "controller_crosscheck.json"))
    a = ap.parse_args()

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    current = titrate.population_fingerprint()
    if rec.get("population") != current:
        raise SystemExit(f"cohorts.json was built against population {rec['population']} and "
                         f"the population on disk is {current}. Rerun build_cohorts.py.")
    titrated = set(titrate.titrated_subjects())

    jobs = []
    for cohort in COHORTS:
        subs = [s for s in rec["cohorts"][cohort]["subjects"] if s in titrated]
        for controller in CONTROLLERS:
            jobs += [(cohort, controller, n) for n in subs]
        print(f"  {cohort:9} {len(subs)} subjects x {len(CONTROLLERS)} controllers", flush=True)
    print(f"{len(jobs)} runs on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    report = {"provenance": provenance.stamp(), "days": DAYS, "layers": list(LAYERS),
              "cohorts": list(COHORTS), "controllers": list(CONTROLLERS),
              "paired": {}, "runs": rows}

    for cohort in COHORTS:
        print(f"\n{'=' * 78}\n{cohort}")
        print(f"  {'measure':16}{'control-iq':>12}{'oref':>10}{'completed':>22}")
        for key, label in MEASURES:
            cell = []
            for c in CONTROLLERS:
                v = [r[key] for r in rows
                     if r["cohort"] == cohort and r["controller"] == c and r.get("completed")]
                cell.append(np.median(v) if v else float("nan"))
            done = "/".join(str(sum(1 for r in rows if r["cohort"] == cohort
                                    and r["controller"] == c and r.get("completed")))
                            for c in CONTROLLERS)
            print(f"  {label:16}{cell[0]:>12.1f}{cell[1]:>10.1f}{done:>22}")
        print(f"\n  paired difference, control-iq minus oref, same subjects")
        for key, label in MEASURES:
            p = paired(rows, cohort, key)
            if not p:
                continue
            report["paired"].setdefault(cohort, {})[key] = p
            print(f"    {label:16}{p['median']:>+8.2f}  95% {p['interval'][0]:+.2f} to "
                  f"{p['interval'][1]:+.2f}   n={p['n']}")

    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
