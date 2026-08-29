"""The far end of the hypoglycaemia distribution, simulated and real, and what survival selects.

The usual hypoglycaemia statistics are computed over the body of the distribution: time below 70
mg/dL, time below 54. A simulated population can match those and still be wrong about how far its
lows go, because a share of readings says nothing about the depth of the worst one, and the run
that goes deepest is also the run most likely to stop before it finishes. Both failures hide from
the figures a bench normally reports.

Three quantities are measured on each side.

    the deepest reading each person reaches, which both sensors floor, so it is reported
      knowing that and the frequency below is what carries the information
    the share of readings at or below 40 and at or below 54 mg/dL
    on the simulated side only, the deepest underlying glucose, which has no floor and which
      no real record contains, so it is compared with nothing

Completion is read alongside, with the direction of every early stop, because a cohort figure
from this simulator is conditioned on survival and survival selects on the variable the
hypoglycaemia statistics measure. Arms are paired over subjects completing both.

The real side reuses the Commons reader, so the window, the coverage floor and the clamp are the
ones every other Commons figure here is built on.

    python examples/extreme_tail.py --real-only        # the real side alone, seconds
    python examples/extreme_tail.py --workers 7
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
LAYERED = ("physiology", "behaviour", "sensor", "site")
CONTROLLERS = ("control-iq", "oref")
OUT = os.path.join(MEASUREMENTS, "extreme_tail.json")

# Nightscout clamps a reading at 39 and the simulated sensor floors at 40, so neither side's
# minimum is a physiological quantity. The thresholds are read at or below 40 to sit above both
# floors, and at or below 54 as the consensus severe level.
DEEP = 40.0
SEVERE = 54.0


def tail(series):
    """The tail statistics for one glucose series, simulated or real."""
    g = np.asarray(series, float)
    g = g[np.isfinite(g)]
    if not len(g):
        return {}
    return {"n": int(len(g)),
            "lowest": float(np.min(g)),
            "at_or_below_40_pct": float(100.0 * np.mean(g <= DEEP)),
            "at_or_below_54_pct": float(100.0 * np.mean(g <= SEVERE)),
            "below_70_pct": float(100.0 * np.mean(g < 70.0))}


def one(job):
    controller, bench, name, days, seed = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    t0 = time.time()
    prof = titrate.profile_for(name)
    layers = LAYERED if bench == "layered" else ()
    ctrl = controller
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=days, seed=seed, layers=layers, controller=ctrl,
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"controller": controller, "bench": bench, "name": name, "completed": False,
                "error": str(exc)[:200], "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    out = {"controller": controller, "bench": bench, "name": name,
           "completed": bool(r.completed), "seconds": time.time() - t0,
           "termination": getattr(r, "termination", None),
           "final_bg": float(np.asarray(r.bg, float)[-1]) if len(r.bg) else float("nan"),
           "days_run": float(len(r.cgm) * 5.0 / 1440.0)}
    # The sensor reading, which is what a real record contains and what the real side is
    # computed on. `Result.bg` carries no sensor error and no real record holds its equivalent,
    # so its tail is reported beside nothing real.
    out["cgm"] = tail(r.cgm)
    out["bg"] = tail(r.bg)
    return out


def real_side():
    """The same statistics on the Commons users, over the window every other figure uses."""
    import glob
    from examples.commons_cohort import ROOT, user_series, window, MIN_COVERAGE
    users = sorted(d for d in glob.glob(os.path.join(ROOT, "*")) if os.path.isdir(d))
    rows, skipped = [], {"no_cgm": 0, "short_record": 0, "sparse_window": 0}
    for d in users:
        a = user_series(d)
        if a is None or not len(a):
            skipped["no_cgm"] += 1
            continue
        sel, cov = window(a)
        if sel is None:
            skipped["short_record"] += 1
            continue
        if cov < MIN_COVERAGE:
            skipped["sparse_window"] += 1
            continue
        t = tail(sel[:, 1])
        t["user"] = os.path.basename(d)
        t["coverage"] = float(cov)
        rows.append(t)
    return rows, skipped, len(users)


def describe(label, rows, key):
    vals = {k: np.array([r[key][k] if key else r[k] for r in rows if (r[key] if key else r)],
                        float)
            for k in ()}
    return vals


def report(label, stats):
    """One block of medians and percentiles for a set of per-person tail statistics."""
    print(f"\n  {label}, {len(stats)} people")
    for k, name in (("lowest", "deepest reading, mg/dL"),
                    ("at_or_below_40_pct", "readings at or below 40, %"),
                    ("at_or_below_54_pct", "readings at or below 54, %"),
                    ("below_70_pct", "readings below 70, %")):
        v = np.array([s[k] for s in stats if k in s], float)
        v = v[np.isfinite(v)]
        if not len(v):
            continue
        print(f"    {name:34} median {np.median(v):7.2f}   p10 to p90 "
              f"{np.percentile(v, 10):7.2f} to {np.percentile(v, 90):7.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cohort", default="dclp3")
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 7)))
    ap.add_argument("--real-only", action="store_true",
                    help="compute the real side and stop, which needs no simulation")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    print("reading the Commons export", flush=True)
    real, skipped, scanned = real_side()
    print(f"  {scanned} user directories, {len(real)} usable, skipped {skipped}")
    report("real users, sensor reading", real)
    if a.real_only:
        return

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    if rec.get("population") != titrate.population_fingerprint():
        raise SystemExit("cohorts.json was built against a different population.")
    titrated = set(titrate.titrated_subjects())
    subs = [s for s in rec["cohorts"][a.cohort]["subjects"] if s in titrated]
    jobs = [(c, b, n, a.days, SEED)
            for c in CONTROLLERS for b in ("bare", "layered") for n in subs]
    print(f"\n{len(subs)} subjects x 2 benches x {len(CONTROLLERS)} controllers = "
          f"{len(jobs)} runs on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 30 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    print(f"\n{'=' * 78}\ncompletion, and the direction of every early stop\n")
    print(f"  {'controller':13}{'bench':10}{'completed':>12}{'ended low':>11}{'ended high':>12}")
    for c in CONTROLLERS:
        for b in ("bare", "layered"):
            s = [r for r in rows if r["controller"] == c and r["bench"] == b]
            done = [r for r in s if r.get("completed")]
            low = sum(1 for r in s if not r.get("completed")
                      and np.isfinite(r.get("final_bg", np.nan)) and r["final_bg"] < 70)
            high = sum(1 for r in s if not r.get("completed")
                       and np.isfinite(r.get("final_bg", np.nan)) and r["final_bg"] > 180)
            print(f"  {c:13}{b:10}{len(done):>7}/{len(s):<4}{low:>11}{high:>12}")

    print(f"\n{'=' * 78}\nthe tail, over completed runs")
    for c in CONTROLLERS:
        for b in ("bare", "layered"):
            done = [r for r in rows if r["controller"] == c and r["bench"] == b
                    and r.get("completed") and r.get("cgm")]
            if done:
                report(f"{c}, {b}, sensor reading", [r["cgm"] for r in done])
                report(f"{c}, {b}, underlying glucose, nothing real to compare",
                       [r["bg"] for r in done])

    json.dump({"provenance": provenance.stamp(), "cohort": a.cohort, "days": a.days,
               "seed": SEED, "controllers": list(CONTROLLERS), "layers": list(LAYERED),
               "thresholds": {"deep": DEEP, "severe": SEVERE},
               "real": {"scanned": scanned, "skipped": skipped, "users": real},
               "runs": rows}, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
