"""Whether per-subject engagement supplies the population's missing tail.

The configured simulator has no badly controlled subjects. Against the OpenAPS Data Commons its
best-controlled tenth already carries slightly more time above 180 mg/dL than its real
counterpart, and the shortfall then grows at every percentile above it, reaching 8.8 points at
the ninetieth. Against DCLP3 the same shape sits on top of a displacement. So what is absent is a
group of people who do badly rather than a worse day for everybody, which is what
`docs/DESIGN_ALIGNMENT.md` section D proposes to supply.

This runs each cohort under the algorithm its reference population used, with the mechanism off
and on, paired per subject. The off arm is rerun rather than taken from `validation.json` so that
both arms come from one code version and one settings store, which is the difference between a
comparison and two measurements that happen to sit near each other.

The criteria it is judged against were fixed before it was built and are in the design document.
They are about the shape of the distribution rather than its centre, because a mechanism that
adds spread should be judged on the spread it adds.

    python examples/engagement_arm.py --workers 13
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
# Each cohort under the algorithm its own reference population ran, as the bench matrix does.
PAIRINGS = (("dclp3", "control-iq"), ("commons", "oref"))
# The literature figure, from the review recorded in `person/behaviour.py`. Zero is the mechanism
# off and reproduces every arm measured before it existed.
ENGAGEMENT = (0.0, 0.76)
MEASURES = [("tir_cgm", "TIR %"), ("tar180_cgm", "TAR180 %"), ("tbr70_cgm", "TBR70 %"),
            ("tbr54_cgm", "TBR54 %"), ("mean_cgm", "Mean glucose"), ("cv_cgm", "CV %")]


def one(job):
    cohort, controller, name, cv = job
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
                     profile=prof, announcement="some", engagement_cv=cv)
    except Exception as exc:
        return {"cohort": cohort, "controller": controller, "name": name, "engagement_cv": cv,
                "completed": False, "error": str(exc)[:200], "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    out = {"cohort": cohort, "controller": controller, "name": name, "engagement_cv": float(cv),
           "completed": bool(r.completed), "seconds": time.time() - t0,
           "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days),
           "announced_meals": int(getattr(r, "meals_announced", 0)),
           "unannounced_meals": int(getattr(r, "meals_unannounced", 0)),
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
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 8)))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "engagement_arm.json"))
    a = ap.parse_args()

    from examples.bench_tables import references
    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    if rec.get("population") != titrate.population_fingerprint():
        raise SystemExit("cohorts.json was built against a different population. "
                         "Rerun build_cohorts.py.")
    titrated = set(titrate.titrated_subjects())
    refs = references()

    jobs = []
    for cohort, controller in PAIRINGS:
        subs = [s for s in rec["cohorts"][cohort]["subjects"] if s in titrated]
        for cv in ENGAGEMENT:
            jobs += [(cohort, controller, n, cv) for n in subs]
        print(f"  {cohort:9} {controller:11} {len(subs)} subjects x {len(ENGAGEMENT)} arms",
              flush=True)
    print(f"{len(jobs)} runs on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 25 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    report = {"provenance": provenance.stamp(), "days": DAYS, "layers": list(LAYERS),
              "engagement": list(ENGAGEMENT), "runs": rows, "summary": {}}

    for cohort, controller in PAIRINGS:
        ref = refs.get(cohort) or []
        print(f"\n{'=' * 84}\n{cohort} under {controller}")
        done = {cv: [r for r in rows if r["cohort"] == cohort
                     and r["engagement_cv"] == cv and r.get("completed")]
                for cv in ENGAGEMENT}
        print(f"  {'measure':14}{'off':>10}{'on':>10}{'real':>10}   "
              f"{'sd off':>8}{'sd on':>8}{'sd real':>9}")
        for key, label in MEASURES:
            rk = key.replace("_cgm", "")
            rv = np.asarray([x[rk] for x in ref if rk in x and np.isfinite(x[rk])], float)
            cells, sds = [], []
            for cv in ENGAGEMENT:
                v = np.asarray([r[key] for r in done[cv]], float)
                cells.append(np.median(v) if len(v) else float("nan"))
                sds.append(np.std(v, ddof=1) if len(v) > 1 else float("nan"))
            rmed = np.median(rv) if len(rv) else float("nan")
            rsd = np.std(rv, ddof=1) if len(rv) > 1 else float("nan")
            print(f"  {label:14}{cells[0]:>10.1f}{cells[1]:>10.1f}{rmed:>10.1f}   "
                  f"{sds[0]:>8.2f}{sds[1]:>8.2f}{rsd:>9.2f}")
            report["summary"].setdefault(cohort, {})[key] = {
                "median_off": cells[0], "median_on": cells[1], "real_median": float(rmed),
                "sd_off": sds[0], "sd_on": sds[1], "real_sd": float(rsd),
                "spread_ratio_off": float(sds[0] / rsd) if rsd else None,
                "spread_ratio_on": float(sds[1] / rsd) if rsd else None}

        print(f"\n  time above 180 mg/dL by percentile")
        print(f"  {'':14}" + "".join(f"{p:>9}" for p in (10, 25, 50, 75, 90)))
        for lab, v in (("off", [r["tar180_cgm"] for r in done[ENGAGEMENT[0]]]),
                       ("on", [r["tar180_cgm"] for r in done[ENGAGEMENT[1]]]),
                       ("real", [x["tar180"] for x in ref if "tar180" in x])):
            if not len(v):
                continue
            q = np.percentile(np.asarray(v, float), [10, 25, 50, 75, 90])
            print(f"  {lab:14}" + "".join(f"{x:>9.1f}" for x in q))
            report["summary"].setdefault(cohort, {}).setdefault("tar180_percentiles", {})[lab] = \
                [float(x) for x in q]

        for cv in ENGAGEMENT:
            n = len(done[cv])
            run = len([r for r in rows if r["cohort"] == cohort and r["engagement_cv"] == cv])
            ann = [r["announced_meals"] / max(r["announced_meals"] + r["unannounced_meals"], 1)
                   for r in done[cv]]
            print(f"  engagement {cv}: completed {n}/{run}, announced share "
                  f"median {np.median(ann):.2f}, range {min(ann):.2f} to {max(ann):.2f}")

    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
