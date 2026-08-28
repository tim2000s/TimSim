"""Whether a fidelity statistic responds to the mechanism it claims to measure.

The signature set carries a statistic named `drift`, reported as the week-to-week movement of
insulin sensitivity and used as the only quantitative evidence for the layer that varies
sensitivity. It is not computed from the simulated person. It is read from the learned correction
factor of the built-in controller, which adapts to glucose sitting away from target, so it is
undefined whenever any other algorithm drives and it responds to ordinary excursions rather than
to the person.

A statistic is evidence only if it moves when the mechanism is removed. That is checkable, and
this checks it, for `drift` and for the replacement proposed alongside it: the week-to-week
coefficient of variation of total daily insulin, computed identically on the simulated and the
real side.

Three arms per driver, differing only in the sensitivity terms.

    varies       the shipped configuration, day-to-day CV 0.22 and a multi-day term at 0.15
    no_interday  the day-to-day term removed, the multi-day and diurnal terms left alone
    flat         both stochastic terms removed, leaving only the deterministic diurnal shape

The diurnal shape is never removed, because it is what the `diurnal` signature measures and this
is about the terms that move between days.

Every arm runs with the physiology layer enabled and varies only the coefficients inside it. A
run given `si_interday_cv` without that layer accepts the argument and ignores it, which is the
defect that produced a wrong refutation in study 07, so `--probe` asserts the ablation reached the
simulation before the full run is worth starting.

    python examples/drift_ablation.py --probe
    python examples/drift_ablation.py --subjects 40 --workers 7
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
DRIVERS = ("basal-bolus", "trend", "boost", "oref")
OUT = os.path.join(MEASUREMENTS, "drift_ablation.json")

# (name, si_interday_cv, si_slow_cv). None keeps the shipped value.
ARMS = (("varies", None, None),
        ("no_interday", 0.0, None),
        ("flat", 0.0, 0.0))


def _controller(driver, name, prof):
    if driver == "boost":
        from timsim.controller import boost_bridge
        return boost_bridge.BoostBridgeController(name, profile=prof)
    if driver == "oref":
        from timsim.controller import oref
        return oref.OrefController(name, profile=prof)
    return driver


def one(job):
    driver, arm, interday, slow, name, days, seed = job
    from timsim.simulation.run import simulate
    from timsim.analysis.signatures import insulin_weekly_cv
    from timsim.therapy import titrate
    t0 = time.time()
    prof = titrate.profile_for(name)
    ctrl = _controller(driver, name, prof)
    try:
        r = simulate(name, days=days, seed=seed, layers=LAYERS, controller=ctrl,
                     profile=prof, announcement="some",
                     si_interday_cv=interday, si_slow_cv=slow)
    except Exception as exc:
        return {"driver": driver, "arm": arm, "name": name, "completed": False,
                "error": str(exc)[:200], "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    days_run = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    return {"driver": driver, "arm": arm, "name": name,
            "completed": bool(r.completed), "seconds": time.time() - t0,
            # The statistic under test, defined only when the built-in loop is driving.
            "isf_weekly_cv": float(getattr(r, "isf_weekly_cv", float("nan"))),
            # The replacement, defined under every driver.
            "insulin_weekly_cv": float(insulin_weekly_cv(getattr(r, "insulin_series", []))),
            "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days_run),
            "tir_cgm": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
            "cv_cgm": float(100.0 * np.std(cgm) / np.mean(cgm)),
            "mean_cgm": float(np.mean(cgm))}


def probe(workers):
    """Assert the ablation reaches the simulation before spending hours on it.

    Two subjects under the built-in loop at the two extreme arms. The day-to-day term is a
    multiplier drawn per day, so removing it has to change delivered insulin; an arm that
    returns the same insulin to the unit has not been applied.
    """
    from examples.panel import dosable
    names = dosable(2, quiet=True)
    jobs = [("trend", arm, iv, sv, n, 14, SEED)
            for arm, iv, sv in (ARMS[0], ARMS[2]) for n in names]
    with futures.ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
        rows = list(pool.map(one, jobs))
    by = {}
    for r in rows:
        by.setdefault(r["name"], {})[r["arm"]] = r
    ok = True
    for name, arms in sorted(by.items()):
        a, b = arms.get("varies"), arms.get("flat")
        if not a or not b or not a.get("completed") or not b.get("completed"):
            print(f"  {name}: a probe arm did not complete, cannot tell")
            ok = False
            continue
        d = abs(a["insulin_per_day"] - b["insulin_per_day"])
        same = d < 1e-9
        print(f"  {name}: insulin {a['insulin_per_day']:.3f} against "
              f"{b['insulin_per_day']:.3f} U/day, difference {d:.4f}"
              f"{'   IDENTICAL' if same else ''}")
        ok = ok and not same
    print("\nthe ablation reaches the simulation" if ok else
          "\nthe arms are identical to the unit, so the ablation did not reach the "
          "simulation. This is the issue 41 signature and the full run would measure nothing.")
    return 0 if ok else 1


def summarise(rows, rng):
    by = {}
    for r in rows:
        if r.get("completed"):
            by.setdefault((r["driver"], r["name"]), {})[r["arm"]] = r
    out = {}
    for stat, label in (("isf_weekly_cv", "drift, from the controller's learned factor"),
                        ("insulin_weekly_cv", "insulin week-to-week %CV")):
        print(f"\n{'=' * 78}\n{label}\n")
        print(f"  {'driver':13}{'arm':13}{'median':>9}{'n':>5}"
              f"{'paired against varies':>28}")
        out[stat] = {}
        for driver in DRIVERS:
            base = [v for (d, _), v in by.items() if d == driver]
            for arm, _, _ in ARMS:
                vals = [v[arm][stat] for v in base if arm in v
                        and np.isfinite(v[arm][stat])]
                line = f"  {driver:13}{arm:13}"
                line += f"{np.median(vals):>9.2f}" if vals else f"{'-':>9}"
                line += f"{len(vals):>5}"
                if arm != "varies":
                    pairs = [(v["varies"][stat], v[arm][stat]) for v in base
                             if "varies" in v and arm in v
                             and np.isfinite(v["varies"][stat]) and np.isfinite(v[arm][stat])]
                    if len(pairs) >= 10:
                        d = np.array([b - a for a, b in pairs])
                        boot = np.array([np.median(rng.choice(d, len(d), True))
                                         for _ in range(4000)])
                        lo, hi = np.percentile(boot, [2.5, 97.5])
                        line += (f"{np.median(d):>+14.2f} [{lo:+.2f},{hi:+.2f}]"
                                 f"{'  responds' if (lo > 0 or hi < 0) else ''}")
                        out[stat].setdefault(driver, {})[arm] = {
                            "difference": float(np.median(d)),
                            "interval": [float(lo), float(hi)],
                            "n": len(pairs),
                            "responds": bool(lo > 0 or hi < 0)}
                    else:
                        line += f"{len(pairs)} pairs, too few".rjust(28)
                print(line)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=DAYS)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 7)))
    ap.add_argument("--probe", action="store_true",
                    help="check the ablation reaches the simulation, then stop")
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    if a.probe:
        raise SystemExit(probe(a.workers))

    from examples.panel import dosable
    names = dosable(a.subjects)
    jobs = [(d, arm, iv, sv, n, a.days, SEED)
            for d in DRIVERS for arm, iv, sv in ARMS for n in names]
    print(f"{len(names)} subjects x {len(ARMS)} arms x {len(DRIVERS)} drivers = "
          f"{len(jobs)} runs on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 30 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    rng = np.random.default_rng(SEED)
    summary = summarise(rows, rng)
    json.dump({"provenance": provenance.stamp(), "days": a.days, "seed": SEED,
               "layers": list(LAYERS), "drivers": list(DRIVERS),
               "arms": [{"name": n, "si_interday_cv": i, "si_slow_cv": s} for n, i, s in ARMS],
               "subjects": names, "summary": summary, "runs": rows},
              open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
