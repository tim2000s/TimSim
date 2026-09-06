"""The clamp-fitted liver on the matched cohorts, paired per subject against the published one.

`docs/PADOVA_AUDIT.md` entry 3 measures the delay carrying plasma insulin to the liver as an
order of magnitude too slow against Edgerton's clamp, and `liver_delay_fit.json` fits the scale
that reproduces the human curve at 12.0 times the published rate, where suppression reads 76.9
per cent at 30 minutes and 100 at 60. What that liver does to a cohort against the people it is
compared with has not been measured. The runs that existed at a fast value carried a weakened
glucose brake as well and terminated 17 and 22 subject-arms of 40 hypoglycaemic, which is the
brake's doing (audit entry 5), so nothing about the residual could be read from them.

This runs the delay alone. `kp1`, `kp2` and `kp3` keep their published values, the fast fraction
stays at zero, and `ki` is scaled through `set_liver_delay`. Two arms on each of the two cohorts
that carry a per-person reference, 28 days each on the shipped layers at the default announcement
condition, the arms differing in nothing but the scale.

    dclp3     control-iq   86 titrated subjects against the DCLP3 closed-loop arm
    commons   oref         70 titrated subjects against the OpenAPS Data Commons users

Registered before the run, on 6 September 2026. The residual this is tested against is the
optimism on time in range: 12.0 points above the DCLP3 arm and 4.8 above the Commons at the
default condition (`docs/BASELINE.md`, `validation.json`, on the settings of 25 August). The
candidate has produced something if the paired difference in median time in range on CGM, fast
minus published, is negative, exceeds the A/A floor at the cohort's paired size, and its
bootstrap interval clears zero. The floor is taken from `driver_ranking.json`, whose paired
standard deviation of 6.28 points on 40 adults gives 2.78 there and scales as one over the square
root of the number paired: 1.90 at 86 and 2.10 at 70, under the assumption that the spread on a
matched cohort is the one measured on adults under the trend loop. Mean glucose and time above
180 mg/dL are read the same way, and the verdict is read only where the fast arm completes at
least nine tenths of the subjects the published arm completes, since a comparison conditioned on
a different set of survivors is a comparison of survivors.

The expectation on record is that it does not. A faster delay releases the liver as soon as it
suppresses it, so the persistent late suppression the published liver carries after every bolus
goes, which should move time below 70 mg/dL down and time above 180 up by amounts under the
floor. On the meal, `liver_rebalance.json` found that speeding insulin alone makes the rise
smaller, and the audit found time to peak falling below the real tenth percentile on a single
meal, so the covered rise and trough to peak per person on the announced record are read as
well, at the 240 minute window, and are expected to move away from the real figures rather than
towards them.

    python examples/liver_delay_cohort.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import argparse
import json
import multiprocessing as mp
import time

import numpy as np

from timsim import provenance, seeds

DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
ANNOUNCEMENT = "some"
PAIRINGS = [("dclp3", "control-iq"), ("commons", "oref")]
# The published delay and the one `liver_delay_fit.json` adopted against Edgerton's clamp.
ARMS = (("published", 1.0), ("fast", 12.0))
WINDOW_MIN = 240
BOLUS_FLOOR_U = 1.0   # the floor sim_meal_shape.py and the real side use
MEASURES = (("tir", "tir_cgm"), ("tbr70", "tbr70_cgm"), ("tbr54", "tbr54_cgm"),
            ("tar180", "tar180_cgm"), ("mean", "mean_cgm"), ("cv", "cv_cgm"),
            ("insulin_per_day", "insulin_per_day"),
            ("rise_covered", "rise_covered"), ("rise_uncovered", "rise_uncovered"),
            ("ttp_covered", "ttp_covered"))
OUT = os.path.join(MEASUREMENTS, "liver_delay_cohort.json")
WORKERS = 7


def job(args):
    """One subject in one arm on one cohort, reduced inside the worker.

    Everything the run needs travels in the tuple, since macOS spawns and a module global set in
    `main` reaches no worker. The controller is built here because the bridges hold state that
    cannot be pickled.
    """
    cohort, controller, arm, delay, name = args
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    from timsim.analysis import meal_shape as ms
    prof = titrate.profile_for(name)
    ctrl, t0 = controller, time.time()
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl,
                     profile=prof, announcement=ANNOUNCEMENT, liver_delay=delay)
    except Exception as exc:
        return {"cohort": cohort, "controller": controller, "arm": arm, "name": name,
                "completed": False, "error": str(exc)[:200], "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    cgm = np.asarray(r.cgm, float)
    bg = np.asarray(r.bg, float)
    days = max(len(bg) * 5.0 / 1440.0, 1e-9)
    out = {"cohort": cohort, "controller": controller, "arm": arm, "name": name,
           "completed": bool(r.completed), "days": float(days),
           "seconds": time.time() - t0, "termination": getattr(r, "termination", None),
           "insulin_per_day": float(r.insulin_units / days),
           "rescue_per_30d": float(30.0 * getattr(r, "rescue_events", 0) / days),
           "lowest_bg": float(bg.min()), "highest_bg": float(bg.max())}
    for sig, lab in ((cgm, "cgm"), (bg, "bg")):
        out[f"tir_{lab}"] = float(100.0 * np.mean((sig >= 70) & (sig <= 180)))
        out[f"tbr70_{lab}"] = float(100.0 * np.mean(sig < 70))
        out[f"tbr54_{lab}"] = float(100.0 * np.mean(sig < 54))
        out[f"tar180_{lab}"] = float(100.0 * np.mean(sig > 180))
        out[f"mean_{lab}"] = float(np.mean(sig))
        out[f"cv_{lab}"] = float(100.0 * np.std(sig, ddof=1) / np.mean(sig))
    # The meal on the announced record, the way `sim_meal_shape.py` reads it: entered meals at
    # entered grams, rescue carbohydrate breaking isolation, the bolus from the bolus series.
    minutes = np.asarray(r.minutes, float)
    meals = [(float(m), float(est)) for m, _, est in r.announced_log if est > 0]
    rescues = [float(x[1]) for x in r.rescue_log]
    bolus_u = np.asarray(r.bolus_series, float)
    recs, _ = ms.shapes(meals, [m for m, _ in meals] + rescues, minutes, cgm,
                        window_min=WINDOW_MIN, bolus_minutes=minutes[:len(bolus_u)],
                        bolus_units=bolus_u)
    rise = np.array([(x["peak_mgdl"] - x["trough_mgdl"]) / (x["grams"] / 10.0) for x in recs])
    ttp = np.array([x["trough_to_peak_min"] for x in recs])
    bol = np.array([x["bolus_u"] for x in recs])
    cov, unc = bol >= BOLUS_FLOOR_U, bol < BOLUS_FLOOR_U
    out["meals"] = int(len(recs))
    out["covered_meals"] = int(cov.sum())
    out["rise_covered"] = float(np.median(rise[cov])) if cov.sum() >= 5 else float("nan")
    out["rise_uncovered"] = float(np.median(rise[unc])) if unc.sum() >= 5 else float("nan")
    out["ttp_covered"] = float(np.median(ttp[cov])) if cov.sum() >= 5 else float("nan")
    return out


def summarise(rows, refs, floor_sd, rng):
    """Per pairing: each arm's medians over its completers, the pairs, and the gap to real."""
    from examples.bench_tables import _paired_median_difference
    out = {}
    for cohort, controller in PAIRINGS:
        here = [r for r in rows if r["cohort"] == cohort]
        by_arm = {a: {r["name"]: r for r in here if r["arm"] == a} for a, _ in ARMS}
        names = sorted(by_arm["published"])
        rec = {"controller": controller, "subjects": len(names), "arms": {}, "pairs": {}}
        for arm, _ in ARMS:
            done = [r for r in by_arm[arm].values() if r.get("completed")]
            term = [r for r in by_arm[arm].values() if not r.get("completed")]
            cols = {}
            for key, col in MEASURES:
                v = np.array([r.get(col, float("nan")) for r in done], float)
                v = v[np.isfinite(v)]
                cols[key] = {"n": int(v.size), "median": float(np.median(v)) if v.size else None,
                             "mean": float(np.mean(v)) if v.size else None,
                             "min": float(np.min(v)) if v.size else None,
                             "max": float(np.max(v)) if v.size else None}
            rec["arms"][arm] = {
                "completed": len(done), "terminated": len(term),
                "terminations": {d: sum(1 for r in term if (r.get("termination") or {})
                                        .get("direction") == d) for d in ("low", "high")},
                "errors": sum(1 for r in term if r.get("error")),
                "columns": cols}
        both = [n for n in names if by_arm["published"][n].get("completed")
                and by_arm["fast"].get(n, {}).get("completed")]
        rec["paired_n"] = len(both)
        rec["completion_ratio"] = (rec["arms"]["fast"]["completed"]
                                   / max(rec["arms"]["published"]["completed"], 1))
        ref = refs.get(cohort)
        for key, col in MEASURES:
            va = np.array([by_arm["published"][n].get(col, float("nan")) for n in both], float)
            vb = np.array([by_arm["fast"][n].get(col, float("nan")) for n in both], float)
            med, lo, hi = _paired_median_difference(va, vb, rng)
            entry = {"fast_minus_published": med, "ci95": [lo, hi]}
            sd = floor_sd.get(key)
            if sd is not None and len(both) > 1:
                entry["floor"] = float(2.8016 * sd / np.sqrt(len(both)))
                entry["clears_floor"] = bool(abs(med) > entry["floor"] and (lo > 0 or hi < 0))
            if isinstance(ref, list) and ref and key in ref[0]:
                rm = float(np.median([x[key] for x in ref]))
                entry["real_median"] = rm
                entry["gap_published"] = float(np.nanmedian(va) - rm)
                entry["gap_fast"] = float(np.nanmedian(vb) - rm)
            rec["pairs"][key] = entry
        out[cohort] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--subjects", type=int, default=None,
                    help="cap per cohort, for a smoke test only")
    a = ap.parse_args()

    from timsim.therapy import titrate
    from examples.bench_tables import references
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    current = titrate.population_fingerprint()
    if rec.get("population") != current:
        raise SystemExit(f"cohorts.json was built against population {rec['population']} and "
                         f"the population on disk is {current}. Rerun build_cohorts.py.")
    titrated = set(titrate.titrated_subjects())
    jobs = []
    for cohort, controller in PAIRINGS:
        subjects = [s for s in rec["cohorts"][cohort]["subjects"] if s in titrated]
        if a.subjects:
            subjects = subjects[:a.subjects]
        for arm, delay in ARMS:
            jobs += [(cohort, controller, arm, delay, n) for n in subjects]
        print(f"  {cohort:9} {controller:11} {len(subjects)} titrated subjects", flush=True)
    print(f"{len(jobs)} runs of {DAYS} days on {a.workers} workers", flush=True)

    # The floor, from the A/A pair on the ranking run, rescaled to each cohort's paired size.
    dr = json.load(open(os.path.join(MEASUREMENTS, "driver_ranking.json")))
    floor_sd = {k: v["paired_sd"] for k, v in dr["floor"].items() if isinstance(v, dict)}

    rows, t0 = [], time.time()
    with mp.Pool(a.workers) as pool:
        for i, row in enumerate(pool.imap_unordered(job, jobs, chunksize=1), 1):
            rows.append(row)
            if i % 20 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} done, {(time.time() - t0) / 60:.1f} min", flush=True)
            if row.get("error"):
                print(f"  ! {row['cohort']} {row['arm']} {row['name']}: {row['error'][:110]}",
                      flush=True)
    refs = references()
    summary = summarise(rows, refs, floor_sd, np.random.default_rng(20260906))
    for cohort, rec in summary.items():
        print(f"\n{cohort} under {rec['controller']}, {rec['subjects']} subjects, "
              f"{rec['paired_n']} paired")
        for arm in rec["arms"]:
            s = rec["arms"][arm]
            print(f"  {arm:10} completed {s['completed']}, terminated {s['terminated']} "
                  f"(low {s['terminations']['low']}, high {s['terminations']['high']})")
        print(f"  {'measure':16}{'published':>11}{'fast':>9}{'diff':>9}{'ci95':>18}"
              f"{'floor':>8}{'real':>8}")
        for key, _ in MEASURES:
            p = rec["pairs"][key]
            pm = rec["arms"]["published"]["columns"][key]["median"]
            fm = rec["arms"]["fast"]["columns"][key]["median"]
            fl = p.get("floor")
            fmt = lambda x, w, d=2: f"{'':>{w}}" if x is None or not np.isfinite(x) else f"{x:>{w}.{d}f}"
            print(f"  {key:16}{fmt(pm, 11)}{fmt(fm, 9)}{fmt(p['fast_minus_published'], 9)}"
                  f"  [{fmt(p['ci95'][0], 6)}, {fmt(p['ci95'][1], 6)}]"
                  f"{fmt(fl, 8)}{fmt(p.get('real_median'), 8, 1)}")
    json.dump({"provenance": provenance.stamp(), "days": DAYS, "seed": SEED,
               "layers": list(LAYERS), "announcement": ANNOUNCEMENT,
               "arms": [{"name": n, "liver_delay": d} for n, d in ARMS],
               "pairings": [{"cohort": c, "controller": k} for c, k in PAIRINGS],
               "window_min": WINDOW_MIN, "bolus_floor_u": BOLUS_FLOOR_U,
               "floor_sd_from": "driver_ranking.json", "summary": summary, "per_run": rows},
              open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out} after {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
