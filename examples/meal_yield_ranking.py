"""Whether a meal rise the size of the real one changes how the four drivers rank.

Written 5 September 2026, after `insulin_profile_rise.py` placed the meal rise gap in the
physiology and `docs/VALIDATION.md` recorded it as a bound: a covered meal rises 9.9 to 11.5
mg/dL per 10 entered grams here, depending on the driver, against 15.1 for adult Loop
participants. A bound is only worth stating with its consequence, and the consequence that
matters for a benchmark is whether the ordering of the algorithms, and the size of the
differences between them, would be different on meals that rise as real ones do.

The rise is raised through `f` in the published model, the fraction of absorbed carbohydrate
that reaches plasma (0.9 in every subject), which multiplies the rate of appearance and nothing
else. It is passed as a per-run parameter override, so the population on disk, the titrated
settings and the fingerprinted code are untouched; the controller is told the true grams, and
the person's behaviour is unchanged. Scaling `f` past 1.0 makes more glucose appear than was
eaten, which is a perturbation of the rise rather than a physiological claim, and it is the one
knob that raises the rise per gram without changing its timing (`meal_absorption_scale` scales
the rates and saturates, and the carbohydrate estimate bias changes what the controller is told).

Twenty titrated adults run 28 days under each of the four drivers of the capability table
(`examples/capability_table.py`), at three yields, paired per subject across drivers and
across yields:

    yield   f       what it is
    1.0     0.90    the shipped model
    1.3     1.17    the scale that brings the oref0 SMB rise to 15.1 if the rise is proportional
    1.5     1.35    past the gap, for the direction

The covered rise at 240 min on the announced record is read on every run through
`timsim/analysis/meal_shape.py`, so the yield that closes the gap is measured rather than
assumed, and a knob that failed to reach the body shows in that column. Outcomes are time in
range, time below 70 and 54 mg/dL, time above 180, mean glucose, insulin per day and rescue
helpings, per subject.

Registered before the run. The rise under oref0 SMB is expected at 14 to 15 mg/dL per 10 g at a
yield of 1.3, below proportional because the loop corrects more of a larger rise, and the
yield read against the gap is the one whose oref0 arm sits within 1.0 of 15.1. At that yield
the ranking is called robust to the bound if the order of the four drivers on median time in
range and on median time below 70 mg/dL is the order at 1.0, and no pair's paired difference
in time in range has moved by more than 2.0 percentage points, the A/A floor on this design
being a paired standard deviation of 3.88 points on 20 subjects (`docs/VALIDATION.md`, level
5). If the order holds and a difference moves by more than that, the ranking is robust and
the sizes are not, and the size of the movement is reported. If the order changes, the bound
is one a benchmark result depends on, and it is recorded as such beside the bound. The
expectation is that the order holds and the closed-loop drivers gain 2 to 4 points of time in
range on the open-loop arm, since a larger rise is more glucose for a correction to act on
and nothing for a fixed regimen to do.

    python examples/meal_yield_ranking.py
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
from itertools import combinations

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from timsim.analysis import meal_shape as ms

OUT = os.path.join(MEASUREMENTS, "meal_yield_ranking.json")
WORKERS = 7
DRIVERS = ("basal-bolus", "trend", "boost", "oref")
YIELDS = (1.0, 1.3, 1.5)
WINDOW = 240
BOLUS_FLOOR = 1.0
MIN_MEALS = 15
OUTCOME = ("tir", "tbr", "tbr54", "tar", "mean_cgm", "insulin_per_day", "rescues")
RANKED = ("tir", "tbr")
TIR_MOVE = 2.0


def job(args):
    """One subject under one driver at one yield, reduced in the worker."""
    name, driver, scale, days = args
    from timsim.population import params_for
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    from examples.capability_table import driver_for
    p = params_for(name).copy()
    p["f"] = float(p["f"]) * scale
    prof = titrate.profile_for(name)
    ctrl = driver_for(name, driver, prof)
    try:
        r = simulate(name, days=days, seed=seeds.BENCH, layers=DEFAULT_LAYERS,
                     controller=ctrl, profile=prof, params=p)
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    if r.termination:
        return name, driver, scale, None, r.termination
    minutes = np.asarray(r.minutes, float)
    cgm = np.asarray(r.cgm, float)
    bolus_u = np.asarray(r.bolus_series, float)
    meals = [(float(m), float(est)) for m, _, est in r.announced_log if est > 0]
    carbs = [m for m, _ in meals] + [float(x[1]) for x in r.rescue_log]
    recs, _ = ms.shapes(meals, carbs, minutes, cgm, window_min=WINDOW,
                        bolus_minutes=minutes[:len(bolus_u)], bolus_units=bolus_u)
    cov = [x for x in recs if x["bolus_u"] >= BOLUS_FLOOR]
    rise = [(x["peak_mgdl"] - x["trough_mgdl"]) / (x["grams"] / 10.0) for x in cov]
    out = {"covered": len(cov),
           "rise_per_10g": float(np.median(rise)) if len(cov) >= MIN_MEALS else None,
           "ttp": float(np.median([x["trough_to_peak_min"] for x in cov])) if cov else None,
           "tir": float(r.time_in_range), "tbr": float(r.time_below_70),
           "tbr54": float(100.0 * np.mean(cgm < 54)), "tar": float(r.time_above_180),
           "mean_cgm": float(np.mean(cgm)),
           "insulin_per_day": float(r.insulin_units / max(r.days_requested, 1)),
           "rescues": float(r.rescue_events / max(r.days_requested, 1))}
    return name, driver, scale, out, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--yields", nargs="+", type=float, default=list(YIELDS))
    ap.add_argument("--drivers", nargs="+", default=list(DRIVERS))
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    from examples.panel import dosable
    subs = dosable(a.subjects)
    # The slow runs (the two bridges) go first so the pool does not end on a tail of them.
    order = sorted(a.drivers, key=lambda d: d not in ("oref", "boost"))
    jobs = [(n, d, y, a.days) for y in a.yields for d in order for n in subs]
    print(f"{len(subs)} subjects, drivers {a.drivers}, yields {a.yields}, {a.days} days, "
          f"{len(jobs)} runs on {a.workers} workers", flush=True)
    with mp.Pool(a.workers) as pool:
        results = pool.map(job, jobs, chunksize=1)

    got, dropped = {}, []
    for name, d, y, out, term in results:
        if out is None:
            dropped.append({"subject": name, "driver": d, "yield": y, "termination": term})
        else:
            got[(name, d, y)] = out
    for x in dropped:
        print(f"  {x['subject']} {x['driver']} at {x['yield']} terminated: {x['termination']}")

    rng = np.random.default_rng(20260905)

    def ci(d):
        d = np.asarray(d, float)
        b = np.array([np.median(rng.choice(d, size=d.size, replace=True)) for _ in range(10000)])
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    def med(vals):
        return float(np.median(vals)) if len(vals) else float("nan")

    # Per driver and yield: completion, the rise (the knob check) and the outcome medians.
    rows = []
    print(f"\n{'yield':>6}{'driver':>12}{'n':>4}{'rise/10 g':>11}{'ttp':>6}{'TIR':>7}{'TBR':>7}"
          f"{'TBR54':>7}{'TAR':>7}{'mean':>7}{'U/day':>7}{'resc/d':>8}")
    for y in a.yields:
        for d in a.drivers:
            o = [got[(n, d, y)] for n in subs if (n, d, y) in got]
            if not o:
                continue
            row = {"yield": y, "driver": d, "subjects": len(o),
                   "rise_per_10g": med([x["rise_per_10g"] for x in o
                                        if x["rise_per_10g"] is not None]),
                   "ttp": med([x["ttp"] for x in o if x["ttp"] is not None]),
                   **{k: med([x[k] for x in o]) for k in OUTCOME}}
            rows.append(row)
            print(f"{y:>6.1f}{d:>12}{len(o):>4}{row['rise_per_10g']:>11.1f}{row['ttp']:>6.0f}"
                  f"{row['tir']:>7.1f}{row['tbr']:>7.2f}{row['tbr54']:>7.2f}{row['tar']:>7.1f}"
                  f"{row['mean_cgm']:>7.0f}{row['insulin_per_day']:>7.1f}{row['rescues']:>8.2f}")

    # The order of the drivers at each yield, best first, on the medians over that yield's
    # completers: most time in range, least time below 70 mg/dL.
    order_by = {}
    for k in RANKED:
        order_by[k] = {}
        for y in a.yields:
            here = [r for r in rows if r["yield"] == y]
            sign = 1.0 if k == "tbr" else -1.0
            order_by[k][str(y)] = [r["driver"] for r in sorted(here, key=lambda r: sign * r[k])]
            print(f"order on {k} at {y:.1f}, best first: {' > '.join(order_by[k][str(y)])}")

    # Every driver pair at every yield, paired on the subjects that completed both, and the
    # movement of each pair's difference from the shipped yield, paired on the subjects that
    # completed all four runs involved.
    pairs, moves = [], []
    print(f"\n{'yield':>6}{'pair':>24}{'n':>4}{'key':>8}{'diff':>8}{'95 per cent':>18}"
          f"{'move from 1.0':>16}{'95 per cent':>18}")
    base_y = a.yields[0]
    for y in a.yields:
        for d1, d2 in combinations(a.drivers, 2):
            common = [n for n in subs if (n, d1, y) in got and (n, d2, y) in got]
            if len(common) < 2:
                continue
            for k in OUTCOME:
                diff = [got[(n, d2, y)][k] - got[(n, d1, y)][k] for n in common]
                lo, hi = ci(diff)
                rec = {"yield": y, "pair": [d1, d2], "key": k, "subjects": len(common),
                       "paired_diff": float(np.median(diff)), "ci95": [lo, hi]}
                pairs.append(rec)
                line = (f"{y:>6.1f}{d2 + ' - ' + d1:>24}{len(common):>4}{k:>8}"
                        f"{rec['paired_diff']:>8.2f}{f'[{lo:.2f}, {hi:.2f}]':>18}")
                if y != base_y:
                    both = [n for n in common
                            if (n, d1, base_y) in got and (n, d2, base_y) in got]
                    if len(both) >= 2:
                        mv = [(got[(n, d2, y)][k] - got[(n, d1, y)][k])
                              - (got[(n, d2, base_y)][k] - got[(n, d1, base_y)][k])
                              for n in both]
                        mlo, mhi = ci(mv)
                        moves.append({"yield": y, "pair": [d1, d2], "key": k,
                                      "subjects": len(both), "move": float(np.median(mv)),
                                      "ci95": [mlo, mhi]})
                        line += f"{np.median(mv):>16.2f}{f'[{mlo:.2f}, {mhi:.2f}]':>18}"
                if k in ("tir", "tbr"):
                    print(line)

    json.dump({"provenance": provenance.stamp(), "subjects": subs, "days": a.days,
               "seed": seeds.BENCH, "drivers": list(a.drivers), "yields": list(a.yields),
               "window_min": WINDOW, "bolus_floor": BOLUS_FLOOR, "min_meals": MIN_MEALS,
               "tir_move_allowed": TIR_MOVE, "dropped": dropped, "rows": rows,
               "order": order_by, "pairs": pairs, "moves": moves,
               "per_run": [{"subject": n, "driver": d, "yield": y, **o}
                           for (n, d, y), o in sorted(got.items())]},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
