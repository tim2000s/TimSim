"""Rank the closed-loop drivers on safety, on the panel and at the resolution the bench has.

Written 6 September 2026, once the fidelity work had reached the point of stating its bounds
rather than closing them (`docs/VALIDATION.md`, "What none of this establishes"). The bench was
built to compare algorithms, and what it can compare is closed loops of similar aggressiveness
against each other, paired per subject, with the bounds carried beside every number. This is that
comparison, run once on the shipped configuration so that a reader has the table the bench was
for rather than the fragments of it scattered through the fidelity measurements.

Forty titrated adults (`examples/panel.py`) run 28 days on the bench seed under each of four
drivers: the built-in trend loop, the Control-IQ stand-in (`controller/loop.py`), Boost through
its bridge and oref0 SMB through its bridge. All four see the same person, the same meals, the
same sensor and the same site failures, announced as the shipped default announces them. The
open-loop regimen is left out: `meal_yield_ranking.py` found its position depends on the meal
rise bound by 4 to 7 points of time in range, so a row for it would carry a caveat the size of
the row.

A fifth arm runs the trend loop again on `seeds.AA`, a second month for the same forty people.
The paired difference between that arm and the trend arm on the bench seed is the noise of this
design at this size, measured on the design itself rather than projected from twenty subjects
over 14 days (`docs/VALIDATION.md`, level 5, 3.88 points paired standard deviation). The
smallest resolvable difference is computed from it at 80 per cent power and a two-sided 5 per
cent level, and every pairwise difference below is read against that figure.

Outcomes are the trial set, on the sensor trace, per subject: time in range, time below 70 and
54 mg/dL, time above 180 and 250, mean glucose and its coefficient of variation, the low blood
glucose index, insulin per day and rescue carbohydrate per day. Each driver's column reports
median, mean and range over its completers, the way the trials report, with the number of
completers and every termination listed by direction. Each pair of drivers is compared on the
subjects that completed both, as the median paired difference with a bootstrap interval.

Registered before the run.

Reproduction. The first twenty subjects under trend, Boost and oref0 SMB were run on this seed
by `meal_yield_ranking.py` at a yield of 1.0 on 5 September 2026 (commit beaffe1), through the
same drivers and the same layers. Those sixty runs are expected to reproduce here to the
decimal, and the script prints the largest discrepancy on time in range. Agreement is expected
and is the check that the code path has not moved; a discrepancy would say the population,
the settings or the physiology had changed since, and the run would then be dated rather than
comparable.

Order. On time in range, oref0 SMB first, the Control-IQ stand-in second, and the trend loop
and Boost not separated. On time below 70 mg/dL the reverse: the trend loop and Boost lowest,
the stand-in between, oref0 SMB highest. The figures behind the expectation are 6.9 [3.2, 9.6]
points of time in range for oref0 SMB over trend and 5.0 [2.8, 8.0] over Boost on twenty
subjects, with Boost over trend at 1.0 [-0.9, 2.4] (`meal_yield_ranking.json`, yield 1.0), and
1.4 points for oref0 SMB over the stand-in on the 86-subject DCLP3-matched cohort, at a cost of
0.84 points below 70 mg/dL and 0.24 below 54 (`bench_matrix.json`, layered_always).

Sizes. oref0 SMB over trend and over Boost on time in range: intervals inside the twenty-subject
ones and clear of zero. oref0 SMB's time below 70 mg/dL above every other driver's by 2.0 to 2.9
points, and its low blood glucose index above every other driver's by more than the 0.23 A/A
floor at forty subjects (`ranking_power.json`). Boost against trend inside the floor on every
outcome. The stand-in against oref0 SMB: 1 to 3 points of time in range, 1 to 2 points below
70 mg/dL.

Floor. The A/A paired standard deviation on time in range between 3 and 5 points, giving a
smallest resolvable difference near 2 points at forty subjects.

Completion. 148 to 156 of the 160 driver runs completing, on the four terminations in 80 at
this yield on twenty subjects, with the hypoglycaemic terminations under oref0 SMB.

Result, 6 September 2026 (`docs/measurements/driver_ranking.json`, 200 runs in 51 minutes). The
fifty-eight completed runs shared with the yield ranking reproduced it to the decimal. Medians
over completers, then the pairs on the subjects that completed both:

    driver       n   TIR   TBR70  TBR54  TAR180  LBGI  U/day
    trend       40  77.3   1.30   0.24   20.7   0.46   55.9
    control-iq  39  81.4   2.49   0.63   15.5   0.68   59.6
    boost       40  79.5   1.35   0.21   19.5   0.44   55.1
    oref        38  86.1   3.92   0.99    9.8   1.10   65.9

    pair                      n   TIR                 TBR70               LBGI
    oref - trend             38   5.78 [4.38, 8.00]   2.54 [1.74, 3.14]   0.70 [0.44, 0.83]
    oref - boost             38   4.58 [2.98, 7.22]   2.58 [1.95, 3.05]   0.72 [0.57, 0.86]
    oref - control-iq        37   4.61 [0.93, 5.33]   1.05 [0.35, 1.72]   0.35 [0.14, 0.50]
    control-iq - trend       39   2.17 [1.30, 4.22]   1.07 [0.86, 1.69]   0.27 [0.21, 0.36]
    boost - control-iq       39  -1.18 [-3.37, -0.21] -1.08 [-1.51, -0.84] -0.28 [-0.35, -0.26]
    boost - trend            40   1.23 [0.61, 2.03]  -0.21 [-0.35, 0.06] -0.06 [-0.09, 0.01]

The A/A arm gives a paired median of +0.86 points of time in range [-2.49, 1.90] with a paired
standard deviation of 6.28, so the design resolves 2.78 points, 0.59 below 70 mg/dL, 0.25 below
54 and 0.14 on the index. The order came out as registered on both ranked outcomes, oref0 SMB
first on time in range and last on time below 70 mg/dL with the stand-in between, and the
oref0 SMB margins sit inside the twenty-subject intervals. The trend loop and Boost are not
separated on any outcome. Two registered figures missed: the stand-in's shortfall to oref0 SMB
on time in range is 4.6 points against the 1 to 3 carried over from the always-announced
DCLP3-matched cohort, and the floor's paired standard deviation is 6.28 against the 3 to 5
expected, wider than the twenty-subject, 14-day figure rather than narrower, and not driven by
outliers (6.13 from the median absolute deviation). Completion was 157 of 160, one above the
registered band, with the three terminations the yield run's two under oref0 SMB and one
hypoglycaemic under the stand-in. `docs/READING_A_RESULT.md` carries the table with the
residuals that belong beside it.

    python examples/rank_drivers.py
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from itertools import combinations

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "driver_ranking.json")
YIELD_RUN = os.path.join(MEASUREMENTS, "meal_yield_ranking.json")
WORKERS = 7
DRIVERS = ("trend", "control-iq", "boost", "oref")
AA_DRIVER = "trend"
OUTCOME = ("tir", "tbr70", "tbr54", "tar180", "tar250", "mean_cgm", "cv_cgm", "lbgi",
           "insulin_per_day", "rescue_g_per_day")
PAIRED = ("tir", "tbr70", "tbr54", "tar180", "lbgi", "insulin_per_day")
# Least is best for everything but time in range.
BEST_HIGH = ("tir",)


def job(args):
    """One subject under one driver on one seed, reduced in the worker."""
    name, driver, seed, days = args
    from timsim.analysis.safety import lbgi_hbgi
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    from examples.capability_table import driver_for
    prof = titrate.profile_for(name)
    ctrl = driver_for(name, driver, prof)
    t0 = time.time()
    try:
        r = simulate(name, days=days, seed=seed, layers=DEFAULT_LAYERS, controller=ctrl,
                     profile=prof)
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    cgm = np.asarray(r.cgm, float)
    ran = max(len(cgm) * float(r.sample_time) / 1440.0, 1e-9)
    lbgi, hbgi = lbgi_hbgi(cgm)
    out = {"completed": bool(r.completed), "days_ran": float(ran),
           "seconds": float(time.time() - t0), "termination": r.termination,
           "tir": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
           "tbr70": float(100.0 * np.mean(cgm < 70)),
           "tbr54": float(100.0 * np.mean(cgm < 54)),
           "tar180": float(100.0 * np.mean(cgm > 180)),
           "tar250": float(100.0 * np.mean(cgm > 250)),
           "mean_cgm": float(np.mean(cgm)),
           "cv_cgm": float(100.0 * np.std(cgm, ddof=1) / np.mean(cgm)),
           "lbgi": float(lbgi), "hbgi": float(hbgi),
           "insulin_per_day": float(r.insulin_units / ran),
           "rescue_g_per_day": float(r.rescue_grams / ran),
           "lowest_cgm": float(np.min(cgm)), "highest_cgm": float(np.max(cgm))}
    return name, driver, seed, out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--drivers", nargs="+", default=list(DRIVERS))
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    from examples.panel import dosable
    subs = dosable(a.subjects)
    arms = [(d, seeds.BENCH) for d in a.drivers] + [(AA_DRIVER, seeds.AA)]
    # The bridges are the slow runs and go first, so the pool does not end on a tail of them.
    order = sorted(arms, key=lambda x: x[0] not in ("oref", "boost"))
    jobs = [(n, d, s, a.days) for d, s in order for n in subs]
    print(f"{len(subs)} subjects, arms {arms}, {a.days} days, {len(jobs)} runs on "
          f"{a.workers} workers", flush=True)
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        results = pool.map(job, jobs, chunksize=1)
    print(f"{len(results)} runs in {(time.time() - t0) / 60:.1f} min", flush=True)

    got = {(n, d, s): o for n, d, s, o in results}

    def arm_key(d, s):
        return d if s == seeds.BENCH else f"{d}@aa"

    # Reproduction against the yield run on the subjects and drivers it shares with this one.
    repro = {"file": os.path.relpath(YIELD_RUN, REPO), "compared": 0, "max_abs_tir_diff": None}
    if os.path.exists(YIELD_RUN):
        prev = json.load(open(YIELD_RUN))
        ref = {(x["subject"], x["driver"]): x for x in prev["per_run"] if x["yield"] == 1.0}
        diffs = []
        for (n, d, s), o in got.items():
            if s == seeds.BENCH and (n, d) in ref and o["completed"]:
                diffs.append(abs(o["tir"] - ref[(n, d)]["tir"]))
        repro.update(compared=len(diffs),
                     max_abs_tir_diff=float(max(diffs)) if diffs else None,
                     yield_commit=prev["provenance"]["commit"][:7])
        print(f"reproduction against {repro['file']} ({repro['yield_commit']}): "
              f"{len(diffs)} shared completed runs, largest TIR discrepancy "
              f"{repro['max_abs_tir_diff']}", flush=True)

    rng = np.random.default_rng(20260906)

    def ci(d):
        d = np.asarray(d, float)
        b = np.array([np.median(rng.choice(d, size=d.size, replace=True))
                      for _ in range(10000)])
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    # Per arm: completion, terminations by direction, and median, mean and range over the
    # completers, the way the trials report.
    columns = {}
    print(f"\n{'arm':>14}{'n':>4}{'TIR':>7}{'TBR70':>7}{'TBR54':>7}{'TAR180':>8}{'TAR250':>8}"
          f"{'mean':>6}{'CV':>6}{'LBGI':>6}{'U/day':>7}{'resc g/d':>10}")
    for d, s in arms:
        key = arm_key(d, s)
        runs = [got[(n, d, s)] for n in subs]
        comp = [o for o in runs if o["completed"]]
        terms = [{"subject": n, **got[(n, d, s)]["termination"]} for n in subs
                 if not got[(n, d, s)]["completed"]]
        col = {"driver": d, "seed": s, "runs": len(runs), "completers": len(comp),
               "terminations": terms,
               "terminated_by_direction": {
                   k: sum(1 for t in terms if t.get("direction") == k)
                   for k in ("hypoglycaemic", "hyperglycaemic")},
               "seconds_per_run": float(np.median([o["seconds"] for o in runs]))}
        for k in OUTCOME:
            v = np.array([o[k] for o in comp], float)
            col[k] = {"median": float(np.median(v)), "mean": float(np.mean(v)),
                      "min": float(np.min(v)), "max": float(np.max(v))}
        columns[key] = col
        m = {k: col[k]["median"] for k in OUTCOME}
        print(f"{key:>14}{len(comp):>4}{m['tir']:>7.1f}{m['tbr70']:>7.2f}{m['tbr54']:>7.2f}"
              f"{m['tar180']:>8.1f}{m['tar250']:>8.2f}{m['mean_cgm']:>6.0f}{m['cv_cgm']:>6.1f}"
              f"{m['lbgi']:>6.2f}{m['insulin_per_day']:>7.1f}{m['rescue_g_per_day']:>10.1f}")
        for t in terms:
            print(f"    {t['subject']} {t.get('direction')} on day {t.get('day_ended')}")

    # The floor: the trend arm against itself on the second month, on the completers of both.
    both = [n for n in subs if got[(n, AA_DRIVER, seeds.BENCH)]["completed"]
            and got[(n, AA_DRIVER, seeds.AA)]["completed"]]
    from scipy import stats as sps
    floor = {"driver": AA_DRIVER, "seeds": [seeds.BENCH, seeds.AA], "subjects": len(both)}
    print(f"\nA/A floor, {AA_DRIVER} on {len(both)} subjects across two months:")
    for k in PAIRED:
        diff = np.array([got[(n, AA_DRIVER, seeds.AA)][k] - got[(n, AA_DRIVER, seeds.BENCH)][k]
                         for n in both], float)
        sd = float(diff.std(ddof=1))
        mdd = float((sps.norm.ppf(0.975) + sps.norm.ppf(0.8)) * sd / np.sqrt(len(both)))
        floor[k] = {"paired_median": float(np.median(diff)), "ci95": ci(diff),
                    "paired_sd": sd, "smallest_resolvable": mdd}
        print(f"  {k:>16}: median {np.median(diff):+.2f} {floor[k]['ci95']}, paired SD {sd:.2f}, "
              f"resolves {mdd:.2f}")

    # Every pair of drivers on the subjects that completed both. `resolved` reads the point
    # estimate against the floor for that outcome; the interval is there to be read as well.
    pairs = []
    print(f"\n{'pair':>24}{'n':>4}{'key':>16}{'diff':>8}{'95 per cent':>18}{'floor':>7}")
    for d1, d2 in combinations(a.drivers, 2):
        common = [n for n in subs if got[(n, d1, seeds.BENCH)]["completed"]
                  and got[(n, d2, seeds.BENCH)]["completed"]]
        for k in PAIRED:
            diff = [got[(n, d2, seeds.BENCH)][k] - got[(n, d1, seeds.BENCH)][k]
                    for n in common]
            lo, hi = ci(diff)
            med = float(np.median(diff))
            rec = {"pair": [d1, d2], "key": k, "subjects": len(common),
                   "paired_diff": med, "ci95": [lo, hi],
                   "floor": floor[k]["smallest_resolvable"],
                   "resolved": bool(abs(med) > floor[k]["smallest_resolvable"]
                                    and (lo > 0 or hi < 0))}
            pairs.append(rec)
            print(f"{d2 + ' - ' + d1:>24}{len(common):>4}{k:>16}{med:>8.2f}"
                  f"{f'[{lo:.2f}, {hi:.2f}]':>18}{rec['floor']:>7.2f}"
                  f"{'  resolved' if rec['resolved'] else ''}")

    # The order of the drivers on each outcome's median over completers, best first.
    order_by = {}
    for k in PAIRED:
        sign = -1.0 if k in BEST_HIGH else 1.0
        order_by[k] = [d for d in sorted(a.drivers, key=lambda d: sign * columns[d][k]["median"])]
        print(f"order on {k}, best first: {' > '.join(order_by[k])}")

    json.dump({"provenance": provenance.stamp(), "subjects": subs, "days": a.days,
               "seed": seeds.BENCH, "aa_seed": seeds.AA, "drivers": list(a.drivers),
               "aa_driver": AA_DRIVER, "reproduction": repro, "columns": columns,
               "floor": floor, "pairs": pairs, "order": order_by,
               "per_run": [{"subject": n, "arm": arm_key(d, s), "driver": d, "seed": s, **o}
                           for (n, d, s), o in sorted(got.items())]},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
