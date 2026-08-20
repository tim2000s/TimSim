"""Fit the unpublished half of Control-IQ to DCLP3, and report on data it never saw.

Tandem publish the cadence, the thresholds and the correction fraction: a correction at most
hourly when glucose is predicted above 180 mg/dL half an hour out, at 60 per cent of a
correction towards 110, with basal suspended below 70, reduced below 112.5, raised from 160
and at its ceiling above 180. Those are fixed here and not fitted.

What they do not publish is what actually drives the result: how far basal may be raised, how
large a single automatic correction may be, and how much insulin on board the loop will
tolerate. Leaving them at guessed values gives a controller that is not Control-IQ. Fitting
them to DCLP3 gives one that is, at the cost of DCLP3 no longer being able to validate the
person, since the pair would then have been tuned to it.

So the trial is split. The cohort is matched to the calibration half's participants, the free
parameters are chosen against the calibration half's outcomes, and every number reported
afterwards is against the held-out half, which nothing here has seen. The gap between the two
is what says whether the fit found Control-IQ or found the calibration half.

Both variants are kept. The published-description one says what Tandem's description alone
buys; the fitted one says what the remaining freedom is worth.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import time
import itertools
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor

from timsim.controller.loop import CONTROL_IQ
from timsim.population import cohort
from timsim.therapy import titrate
from timsim.validation import dclp3

from timsim import provenance, seeds

DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
N_SUBJECTS = 20
OUT = os.path.join(MEASUREMENTS, "control_iq_fit.json")
DCLP3_DIR = os.path.expanduser(os.environ.get("DCLP3_DIR", "~/Downloads/dclp3/Data Files"))

# The three quantities Tandem do not publish. The grid brackets the guessed values rather
# than searching far from them, since a controller fitted to outcomes will happily reach a
# configuration no product would ship.
GRID = {"max_basal_scale": (2.0, 3.0, 4.0),
        "max_correction_u": (3.0, 6.0),
        "max_iob_u": (4.0, 8.0)}

MEASURES = ("tir", "tbr70", "tbr54", "tar180", "mean", "cv")


def trial_outcomes(participants):
    rows = []
    for pid, segs in dclp3.traces(arm=dclp3.CLOSED_LOOP).items():
        if pid not in participants:
            continue
        g = np.concatenate([np.asarray(s, float)[1] for s in segs])
        g = g[np.isfinite(g)]
        if len(g) < 2000:
            continue
        rows.append({"tir": 100 * np.mean((g >= 70) & (g <= 180)),
                     "tbr70": 100 * np.mean(g < 70), "tbr54": 100 * np.mean(g < 54),
                     "tar180": 100 * np.mean(g > 180), "mean": float(g.mean()),
                     "cv": 100 * g.std(ddof=1) / g.mean()})
    return rows


def trial_traits(participants):
    def read(name):
        d = pd.read_csv(os.path.join(DCLP3_DIR, name), sep="|", encoding="utf-16")
        d.columns = [c.strip() for c in d.columns]
        return d
    screen, pump = read("DiabScreening_a.txt"), read("InsulinPumpSettings_a.txt")
    age = pd.to_numeric(screen.set_index("PtID")["AgeAtEnrollment"], errors="coerce")
    tdd = pd.to_numeric(pump[pump.PtID.isin(participants)]
                        .groupby("PtID")["CurrTotInsDaily"].median(), errors="coerce")
    out = [(age.get(p), tdd.get(p)) for p in sorted(participants)]
    return [(float(a), float(t)) for a, t in out if pd.notna(a) and pd.notna(t) and t > 0]


def summarise(rows):
    return {m: float(np.median([r[m] for r in rows])) for m in MEASURES}


def spread(rows):
    return {m: float(np.percentile([r[m] for r in rows], 90)
                     - np.percentile([r[m] for r in rows], 10)) for m in MEASURES}


def distance(sim, real_median, real_spread):
    """Mean squared gap across the measures, each in units of the real spread."""
    gaps = [(sim[m] - real_median[m]) / real_spread[m] for m in MEASURES
            if real_spread[m] > 0]
    return float(np.mean(np.square(gaps))), {m: (sim[m] - real_median[m]) / real_spread[m]
                                             for m in MEASURES if real_spread[m] > 0}


def one(job):
    name, params = job
    from dataclasses import replace
    from timsim.simulation.run import simulate
    prof = titrate.profile_for(name)
    shape = replace(CONTROL_IQ, **params)
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=shape,
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"name": name, "completed": False, "error": str(exc)[:160]}
    cgm = np.asarray(r.cgm, float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    return {"name": name, "completed": bool(r.completed),
            "tir": float(100 * np.mean((cgm >= 70) & (cgm <= 180))),
            "tbr70": float(100 * np.mean(cgm < 70)),
            "tbr54": float(100 * np.mean(cgm < 54)),
            "tar180": float(100 * np.mean(cgm > 180)),
            "mean": float(np.mean(cgm)), "cv": float(100 * np.std(cgm, ddof=1) / np.mean(cgm)),
            "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days)}


def main():
    sp = dclp3.split()
    cal, held = set(sp["calibration"]), set(sp["held_out"])
    roster = dclp3.roster()
    closed = set(roster.loc[roster.trtGroup == dclp3.CLOSED_LOOP, "PtID"])
    cal, held = cal & closed, held & closed
    cal_out, held_out = trial_outcomes(cal), trial_outcomes(held)
    print(f"DCLP3 closed loop: {len(cal_out)} calibration participants, "
          f"{len(held_out)} held out")

    cal_med, cal_spread = summarise(cal_out), spread(cal_out)
    held_med, held_spread = summarise(held_out), spread(held_out)
    print(f"  calibration TIR {cal_med['tir']:.2f}  mean {cal_med['mean']:.1f}")
    print(f"  held out    TIR {held_med['tir']:.2f}  mean {held_med['mean']:.1f}")

    names, info = cohort.matched_on_traits(trial_traits(cal), n=N_SUBJECTS, seed=0)
    titrated = set(titrate.titrated_subjects())
    names = [n for n in names if n in titrated]
    print(f"cohort matched to the calibration half: {len(names)} titrated subjects, "
          f"match distance {info['median_distance']:.3f}")
    if len(names) < 8:
        raise SystemExit("too few titrated subjects in the calibration-matched cohort; "
                         "rerun examples/titrate_cohort.py over this cohort first")

    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    print(f"\nfitting {len(combos)} configurations on the calibration half\n")
    results, t0 = [], time.time()
    for k, params in enumerate(combos, 1):
        with ProcessPoolExecutor(max_workers=10) as ex:
            rows = list(ex.map(one, [(n, params) for n in names]))
        done = [r for r in rows if r.get("completed")]
        if len(done) < max(6, len(names) // 2):
            print(f"  {k:2d}/{len(combos)} {params}  only {len(done)}/{len(names)} completed, skipped")
            continue
        sim = summarise(done)
        d, gaps = distance(sim, cal_med, cal_spread)
        results.append({"params": params, "distance": d, "gaps": gaps, "sim": sim,
                        "completed": len(done), "n": len(names)})
        print(f"  {k:2d}/{len(combos)} basal x{params['max_basal_scale']:.1f} "
              f"corr {params['max_correction_u']:.0f}U iob {params['max_iob_u']:.0f}U  "
              f"-> d={d:.3f}  TIR {sim['tir']:.1f}  mean {sim['mean']:.1f}  "
              f"{len(done)}/{len(names)} completed  [{(time.time()-t0)/60:.1f} min]",
              flush=True)

    if not results:
        raise SystemExit("no configuration produced enough completed runs to score")
    results.sort(key=lambda r: r["distance"])
    best = results[0]
    print(f"\nbest on the calibration half: {best['params']}  d={best['distance']:.3f}")

    print("\nrunning the fitted configuration against the held-out half")
    with ProcessPoolExecutor(max_workers=10) as ex:
        rows = list(ex.map(one, [(n, best["params"]) for n in names]))
    done = [r for r in rows if r.get("completed")]
    sim = summarise(done)
    d_held, gaps_held = distance(sim, held_med, held_spread)
    published = [r for r in results
                 if r["params"] == {"max_basal_scale": 3.0, "max_correction_u": 6.0,
                                    "max_iob_u": 6.0}]
    print(f"  fitted, held out:      d={d_held:.3f}")
    print(f"  fitted, calibration:   d={best['distance']:.3f}")
    print(f"\n  {'measure':10}{'sim':>10}{'held out':>10}{'gap/spread':>12}")
    for m in MEASURES:
        print(f"  {m:10}{sim[m]:>10.2f}{held_med[m]:>10.2f}{gaps_held[m]:>+12.2f}")

    json.dump({"population": titrate.population_fingerprint(),
               "provenance": provenance.stamp(),
               "cohort": names, "grid": {k: list(v) for k, v in GRID.items()},
               "calibration": {"n": len(cal_out), "median": cal_med, "spread": cal_spread},
               "held_out": {"n": len(held_out), "median": held_med, "spread": held_spread},
               "results": results, "best": best["params"],
               "held_out_distance": d_held, "held_out_gaps": gaps_held,
               "held_out_sim": sim, "held_out_completed": len(done)},
              open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
