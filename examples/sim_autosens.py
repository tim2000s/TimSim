"""How far oref's sensitivity ratio moves in the simulated person, and whether it can see why.

The simulated half of the comparison registered in `examples/real_autosens.py`, whose
docstring carries the question, the expectation and the rule. Read that first.

Forty titrated adults (`examples/panel.py`) run 28 days on the bench seed under oref0 SMB
through its bridge, with the shipped layers, in two arms paired per subject:

    shipped    the person as shipped, day-to-day sensitivity CV 0.22 and a multi-day
               term of CV 0.15 with a nine-day correlation time (`patient/varying.py`)
    no_drift   both of those terms at zero, the diurnal shape kept

The second arm is the ablation that tests whether the statistic can see the mechanism it is
meant to compare. Autosens exists to follow a sensitivity that drifts over hours to days, so
removing the drift ought to narrow the ratio's spread and reduce the day-to-day standard
deviation of its daily mean. A statistic that does not move between the arms by more than its
paired interval cannot see the sensitivity terms and is void for the comparison, whatever it
reads against the real users.

The ratio is the one oref received on each cycle, as the controller records it
(`OrefController.ratios`), clipped at 0.7 and 1.2 as oref clips it. The first day of each run is
dropped from the ratio statistics because the arm starts with no history and autosens reads 1.0
until its windows fill; the real windows are taken from the middle of long records and carry
no such start.

Reproduction. The shipped arm is the oref0 SMB arm of `examples/rank_drivers.py` on the same
subjects, seed and configuration, so its time in range is expected to reproduce
`driver_ranking.json` to the decimal, and the script prints the largest discrepancy. A
discrepancy would say the code path had moved since 6 September 2026.

    python examples/sim_autosens.py
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "sim_autosens.json")
REAL = os.path.join(MEASUREMENTS, "real_autosens.json")
RANKING = os.path.join(MEASUREMENTS, "driver_ranking.json")
WORKERS = 7
ARMS = {"shipped": {}, "no_drift": {"si_interday_cv": 0.0, "si_slow_cv": 0.0}}
CLIP = (0.7, 1.2)
WARM_CYCLES = 288
STATS = ("resistant_pct", "sensitive_pct", "at_one_pct", "p10", "p50", "p90",
         "width_p10_p90", "daily_sd")


def ratio_stats(ratios, sample_min):
    r = np.clip(np.asarray([x for x in ratios if x is not None], float), *CLIP)
    r = r[WARM_CYCLES:]
    per_day = int(round(1440 / sample_min))
    day = np.arange(r.size) // per_day
    daily = np.array([r[day == d].mean() for d in np.unique(day) if (day == d).sum() >= per_day // 2])
    return {"cycles": int(r.size),
            "resistant_pct": float(100.0 * np.mean(r > 1.0)),
            "sensitive_pct": float(100.0 * np.mean(r < 1.0)),
            "at_one_pct": float(100.0 * np.mean(r == 1.0)),
            "p10": float(np.percentile(r, 10)), "p50": float(np.percentile(r, 50)),
            "p90": float(np.percentile(r, 90)),
            "width_p10_p90": float(np.percentile(r, 90) - np.percentile(r, 10)),
            "daily_sd": float(daily.std(ddof=1)) if daily.size > 2 else None}


def job(args):
    name, arm, seed, days = args
    from timsim.controller import oref
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    ctrl = oref.OrefController(name, profile=prof)
    t0 = time.time()
    try:
        r = simulate(name, days=days, seed=seed, layers=DEFAULT_LAYERS, controller=ctrl,
                     profile=prof, **ARMS[arm])
        ratios = list(ctrl.ratios)
    finally:
        ctrl.close()
    cgm = np.asarray(r.cgm, float)
    ran = max(len(cgm) * float(r.sample_time) / 1440.0, 1e-9)
    out = {"completed": bool(r.completed), "days_ran": float(ran),
           "termination": r.termination, "seconds": float(time.time() - t0),
           "tir": float(100.0 * np.mean((cgm >= 70) & (cgm <= 180))),
           "tbr70": float(100.0 * np.mean(cgm < 70)),
           "tar180": float(100.0 * np.mean(cgm > 180)),
           "insulin_per_day": float(r.insulin_units / ran)}
    out.update(ratio_stats(ratios, float(r.sample_time)))
    return name, arm, out


def summary(values):
    v = np.asarray([x for x in values if x is not None], float)
    return {"n": int(v.size), "median": float(np.median(v)), "mean": float(np.mean(v)),
            "min": float(v.min()), "max": float(v.max()),
            "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=WORKERS)
    a = ap.parse_args()
    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, arm, seeds.BENCH, a.days) for arm in ARMS for n in subs]
    print(f"{len(subs)} subjects, arms {list(ARMS)}, {a.days} days, {len(jobs)} runs on "
          f"{a.workers} workers", flush=True)
    t0 = time.time()
    with mp.Pool(a.workers) as pool:
        results = pool.map(job, jobs, chunksize=1)
    print(f"{len(results)} runs in {(time.time() - t0) / 60:.1f} min", flush=True)
    got = {(n, arm): o for n, arm, o in results}

    repro = {"file": os.path.relpath(RANKING, REPO), "compared": 0, "max_abs_tir_diff": None}
    if os.path.exists(RANKING):
        prev = json.load(open(RANKING))
        ref = {x["subject"]: x for x in prev["per_run"] if x["arm"] == "oref"}
        diffs = [abs(got[(n, "shipped")]["tir"] - ref[n]["tir"]) for n in subs
                 if n in ref and ref[n]["completed"] and got[(n, "shipped")]["completed"]]
        repro.update(compared=len(diffs), max_abs_tir_diff=float(max(diffs)) if diffs else None)
        print(f"reproduction against {repro['file']}: {len(diffs)} runs, largest TIR "
              f"discrepancy {repro['max_abs_tir_diff']}", flush=True)

    # Ratio statistics are read on every run with at least a week past the warm-up, completed
    # or not, since a termination ends the record rather than invalidating what came before.
    usable = {arm: [n for n in subs if got[(n, arm)]["cycles"] >= 7 * 288] for arm in ARMS}
    stats = {arm: {k: summary(got[(n, arm)][k] for n in usable[arm]) for k in STATS}
             for arm in ARMS}

    rng = np.random.default_rng(20260925)

    def ci(d):
        d = np.asarray(d, float)
        b = np.array([np.median(rng.choice(d, size=d.size, replace=True)) for _ in range(10000)])
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    both = [n for n in subs if n in usable["shipped"] and n in usable["no_drift"]]
    ablation = {}
    for k in STATS:
        diff = [got[(n, "shipped")][k] - got[(n, "no_drift")][k] for n in both
                if got[(n, "shipped")][k] is not None and got[(n, "no_drift")][k] is not None]
        lo, hi = ci(diff)
        ablation[k] = {"subjects": len(diff), "paired_median": float(np.median(diff)),
                       "ci95": [lo, hi], "sees_mechanism": bool(lo > 0 or hi < 0)}

    verdicts = {}
    if os.path.exists(REAL):
        real = json.load(open(REAL))["stats"]
        for k in STATS:
            if k not in real:
                continue
            sim_med = stats["shipped"][k]["median"]
            lo, hi = real[k]["p10"], real[k]["p90"]
            place = "inside" if lo <= sim_med <= hi else ("below" if sim_med < lo else "above")
            verdicts[k] = {"sim_median": sim_med, "real_median": real[k]["median"],
                           "real_p10": lo, "real_p90": hi, "place": place,
                           "void": not ablation[k]["sees_mechanism"]}

    print(f"\n{'statistic':>16}{'shipped':>10}{'no_drift':>10}{'ablation':>10}{'95 per cent':>20}"
          f"{'real median':>13}{'real p10-p90':>16}  verdict")
    for k in STATS:
        ab = ablation[k]
        v = verdicts.get(k, {})
        band = f"{v['real_p10']:.3f}-{v['real_p90']:.3f}" if v else ""
        print(f"{k:>16}{stats['shipped'][k]['median']:>10.3f}{stats['no_drift'][k]['median']:>10.3f}"
              f"{ab['paired_median']:>10.3f}{f'[{ab['ci95'][0]:.3f}, {ab['ci95'][1]:.3f}]':>20}"
              f"{v.get('real_median', float('nan')):>13.3f}{band:>16}  "
              f"{v.get('place', '')}{' (void)' if v.get('void') else ''}")

    json.dump({"provenance": provenance.stamp(), "subjects": subs, "days": a.days,
               "seed": seeds.BENCH, "arms": ARMS, "warm_cycles": WARM_CYCLES,
               "reproduction": repro, "usable": usable, "stats": stats,
               "ablation": ablation, "verdicts": verdicts,
               "per_run": [{"subject": n, "arm": arm, **o} for (n, arm), o in sorted(got.items())]},
              open(OUT, "w"), indent=1)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
