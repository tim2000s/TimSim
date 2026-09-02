"""The simulated meal shape, per subject and per meal, against the real measurement.

`examples/real_meal_shape.py` measures 964 real people over 193,696 meals and separates the two
components of the spread. Within-person variation is the larger of them: at a 240 minute window a
Loop participant's own meals span an interquartile range of 90 minutes, where participants differ
from each other by 50 minutes across the tenth to ninetieth percentile of their medians.

The simulated side had none of it. `examples/meal_with_bolus.py` gives each subject a single 60 g
meal at midday on a fixed seed with no layers, so every simulated meal is the same meal and the
whole simulated spread is between-subject physiology. This runs each subject for weeks with the
person's own layers on, takes every meal the schedule produces, and measures both components the
way the real side measures them, through the shared definition in `timsim/analysis/meal_shape.py`.

Four things are matched to the real side deliberately. Meals are read off `cgm` rather than `bg`,
because the real side can only be a sensor and sensor error moves where a minimum and a maximum
fall. Rescue carbohydrate breaks isolation, because a real person logging 15 g for a low files it
in the same field as a meal. The peak is located on the absolute trace. And the window is swept
rather than chosen, because the window sets the answer: on the real side the pooled median runs
70 minutes at 180 and 135 at 720.

The controller is selectable and it matters more than anything else measured here. Tim's point,
2 September 2026: the built-in correction loop is a substrate rather than part of the person, so a
meal flattened by it says nothing about the bench. The arms that are benchmarked run the
Control-IQ stand-in and oref0 SMB, and `basal-bolus` is open-loop therapy with no modulation at
all, so the three together separate what the model does from what a controller does to it.

    python examples/sim_meal_shape.py --subjects 40 --days 42
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from timsim.analysis import meal_shape as ms

OUT = os.path.join(MEASUREMENTS, "sim_meal_shape.json")
REAL = os.path.join(MEASUREMENTS, "real_meal_shape.json")

# Stock against the whole of the gain on the fast delay, which is the configuration the sweep in
# `liver_two_timescale.py` adopted and which is a single-timescale liver at 10.5 times the
# published rate rather than a two-timescale one.
# (label, fast fraction, fast ki scale, liver delay scale, kp2 scale, kp3 scale). The arms are
# run through this pipeline rather than against the raw patient because the real reference is
# measured on CGM through the shared definition at the same window, and a clean trace measured on
# a different protocol is not comparable to it. `rise_sensor_inflation.json` puts that difference
# at 4.0 mg/dL per 10 g, which is the size of the gap being argued about.
ARMS = (("stock", 0.0, 1.0, None, 1.0, 1.0),
        ("no_brake", 0.0, 1.0, None, 0.0, 1.0),
        ("rebalanced", 0.0, 1.0, 8.0, 0.5, 1.75))
WORKERS = 7


def job(args):
    """One subject in one arm, reduced to its meal records inside the worker.

    The trace is tens of thousands of readings and the records are tens of meals, so the
    reduction happens here rather than sending the trace back. macOS spawns, so this is at
    module level and everything it needs travels in the tuple.
    """
    name, arm, fraction, ki_scale, delay, kp2, kp3, days, windows, controller = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    r = simulate(name, days=days, seed=seeds.BENCH, layers=DEFAULT_LAYERS,
                 controller=controller,
                 liver_fast_fraction=fraction, liver_fast_ki_scale=ki_scale,
                 liver_delay=delay, liver_kp2_scale=kp2, liver_kp3_scale=kp3)
    if r.termination:
        return name, arm, None, r.termination
    minutes = np.asarray(r.minutes, float)
    cgm = np.asarray(r.cgm, float)
    meals = [(float(m), float(g)) for m, g in r.meal_log]
    # Bolus alone, from `bolus_series` rather than reconstructed by subtracting an assumed basal
    # from the total. Corrections appear in it as they do in the real bolus table, so the same
    # floor separates the strata on both sides.
    bolus_u = np.asarray(r.bolus_series, float)
    bolus_min = minutes[:len(bolus_u)]
    # Rescue carbohydrate breaks isolation and is never an index meal. `rescue_log` carries
    # (decided_at, eaten_at, grams, trigger) and the eaten minute is the one that reaches the gut.
    rescues = [float(x[1]) for x in r.rescue_log]
    carbs = [m for m, _ in meals] + rescues
    out = {}
    for w in windows:
        recs, rej = ms.shapes(meals, carbs, minutes, cgm, window_min=w,
                              bolus_minutes=bolus_min, bolus_units=bolus_u)
        out[w] = {"ttp": [x["trough_to_peak_min"] for x in recs],
                  "hours": [x["hour"] for x in recs],
                  # Rise per 10 g, the quantity the excursion decomposition points at: simulated
                  # excursions above 180 mg/dL end after 40 min against the trial's 60 while
                  # falling at the same rate, so they are shorter because they peak lower.
                  "rise_per_10g": [(x["peak_mgdl"] - x["trough_mgdl"]) / (x["grams"] / 10.0)
                                   for x in recs],
                  # Kept per meal so a size-matched comparison is analysis on stored data rather
                  # than another run. Simulated meals admitted to the 30 to 90 g band centre above
                  # the real ones, whose quartiles are 35 / 41 / 55, and rise per gram is not
                  # constant in size.
                  "grams": [x["grams"] for x in recs],
                  "bolus_u": [x["bolus_u"] for x in recs],
                  # The fall, where a short absorption tail would show without touching the peak.
                  "fullness": [x["fullness"] for x in recs],
                  "peak_to_return_min": [x["peak_to_return_min"] for x in recs],
                  "returned": [x["returned"] for x in recs],
                  "trough_at_index": int(sum(x["trough_at_index"] for x in recs)),
                  "rejected": rej}
    return name, arm, out, None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=42)
    ap.add_argument("--windows", nargs="+", type=int, default=list(ms.WINDOWS))
    ap.add_argument("--min-meals", type=int, default=20)
    ap.add_argument("--controller", default="trend",
                    help="trend and reference are the built-in loop, control-iq is the "
                         "benchmark stand-in, basal-bolus is open loop")
    ap.add_argument("--band", nargs=2, type=float, default=[40.0, 55.0],
                    help="grams band for the size-matched rise, the real interquartile range")
    ap.add_argument("--bolus-floor", type=float, default=1.0,
                    help="units within 30 min of the meal for it to count as covered")
    ap.add_argument("--band-min", type=int, default=8,
                    help="meals a subject needs inside the band to contribute to it")
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects)

    jobs = [(n, arm, fr, ks, dl, k2, k3, a.days, tuple(a.windows), a.controller)
            for n in subs for arm, fr, ks, dl, k2, k3 in ARMS]
    print(f"{len(subs)} subjects, {len(ARMS)} arms, {a.days} days each, "
          f"controller {a.controller}, on {a.workers} workers")
    with mp.Pool(a.workers) as pool:
        results = pool.map(job, jobs)

    got, dropped = {}, []
    for name, arm, out, term in results:
        if out is None:
            dropped.append({"subject": name, "arm": arm, "termination": term})
            continue
        got[(name, arm)] = out

    real = json.load(open(REAL)) if os.path.exists(REAL) else {"rows": []}
    real_by = {(r["study"], r["window_min"]): r for r in real["rows"]}

    rec = {"provenance": provenance.stamp(), "subjects": list(subs), "days": a.days,
           "seed": seeds.BENCH, "controller": a.controller,
           "arms": [a_[0] for a_ in ARMS], "min_meals": a.min_meals,
           "dropped": dropped, "arm_spec": [list(x) for x in ARMS],
           "rows": [], "per_subject": []}

    # Per subject, per arm, per window, kept in the record. Summarising to medians and throwing
    # the subjects away is what stopped `liver_two_timescale.py` being able to answer whether two
    # rungs described the same people, which is issue 45.
    cells = {}
    for arm, *_ in ARMS:
        for w in a.windows:
            for n in subs:
                cell = got.get((n, arm))
                if not cell:
                    continue
                p = ms.per_person(cell[w]["ttp"], a.min_meals)
                if p:
                    r_ = ms.per_person(cell[w]["rise_per_10g"], a.min_meals)
                    g_ = np.asarray(cell[w]["grams"], float)
                    band = np.asarray(cell[w]["rise_per_10g"], float)[
                        (g_ >= a.band[0]) & (g_ <= a.band[1])]
                    bu_ = np.asarray(cell[w]["bolus_u"], float)
                    rr_ = np.asarray(cell[w]["rise_per_10g"], float)
                    cov = rr_[bu_ >= a.bolus_floor]
                    unc = rr_[bu_ < a.bolus_floor]
                    p = dict(p, rise_median=r_["median"], rise_iqr=r_["iqr"],
                             grams_median=float(np.median(g_)),
                             rise_median_band=(float(np.median(band)) if band.size >= a.band_min
                                               else None),
                             band_meals=int(band.size),
                             rise_covered=(float(np.median(cov)) if cov.size >= a.band_min
                                           else None),
                             rise_uncovered=(float(np.median(unc)) if unc.size >= a.band_min
                                             else None),
                             covered_meals=int(cov.size), uncovered_meals=int(unc.size),
                             fullness=float(np.nanmedian(cell[w]["fullness"])),
                             peak_to_return=float(np.nanmedian(cell[w]["peak_to_return_min"]))
                             if np.any(np.isfinite(cell[w]["peak_to_return_min"]))
                             else float("nan"),
                             returned_share=float(np.mean(cell[w]["returned"])))
                    cells[(arm, w, n)] = p
                    rec["per_subject"].append(dict(p, arm=arm, window_min=w, subject=n))

    arms = [x[0] for x in ARMS]
    for w in a.windows:
        # The common panel: subjects reaching the threshold in every arm. The fast arm admits
        # fewer meals, so an arm-by-arm panel is a different set of people in each column and a
        # difference between columns is partly the membership.
        common = sorted(set.intersection(*[{n for n in subs if (arm, w, n) in cells}
                                           for arm in arms])) if arms else []
        rec.setdefault("common_panel", {})[w] = common

    for arm, *_ in ARMS:
        print(f"\n{arm}")
        print(f"{'window':>7}{'common':>8}{'own':>5}{'meals':>7}{'per-person median':>20}"
              f"{'within-person IQR':>20}{'rise per 10 g':>20}"
              f"{'same, 40-55 g only':>22}"
              f"{'covered rise':>20}{'uncovered rise':>20}"
              f"{'fullness':>20}{'peak to return':>20}{'ret':>6}")
        for w in a.windows:
            common = rec["common_panel"][w]
            per = [cells[(arm, w, n)] for n in common]
            own = len([n for n in subs if (arm, w, n) in cells])
            hours, at_index, tot = [], 0, 0
            for n in common:
                c = got[(n, arm)][w]
                hours.extend(c["hours"]); at_index += c["trough_at_index"]; tot += len(c["ttp"])
            if not per:
                print(f"{w:>7}{0:>8}{own:>5}{0:>7}   no subject reaches {a.min_meals} meals "
                      f"in every arm")
                rec["rows"].append({"arm": arm, "window_min": w, "subjects": 0, "own": own})
                continue
            s_ = ms.summarise(per)
            q = lambda v, pp: float(np.percentile(np.asarray(v, float), pp))
            rm = [x["rise_median"] for x in per]
            s_["rise_per_10g_between_person"] = [q(rm, 10), q(rm, 50), q(rm, 90)]
            h = np.asarray(hours)
            evening = float(np.mean((h >= 16) & (h <= 21)))
            bp, wp = s_["between_person_median"], s_["within_person_iqr"]
            rr = s_["rise_per_10g_between_person"]
            bandv = [x["rise_median_band"] for x in per if x["rise_median_band"] is not None]
            s_["grams_median"] = float(np.median([x["grams_median"] for x in per]))
            s_["rise_per_10g_size_matched"] = ([q(bandv, 10), q(bandv, 50), q(bandv, 90)]
                                               if bandv else None)
            s_["size_matched_subjects"] = len(bandv)
            for label in ("covered", "uncovered"):
                vv = [x[f"rise_{label}"] for x in per if x[f"rise_{label}"] is not None]
                s_[f"rise_{label}"] = ([q(vv, 10), q(vv, 50), q(vv, 90)] if vv else None)
                s_[f"{label}_subjects"] = len(vv)
                s_[f"{label}_meals"] = int(sum(x[f"{label}_meals"] for x in per))
            for key in ("fullness", "peak_to_return"):
                vv = [x[key] for x in per if np.isfinite(x[key])]
                s_[key] = [q(vv, 10), q(vv, 50), q(vv, 90)] if vv else [float("nan")] * 3
            s_["returned_share"] = float(np.median([x["returned_share"] for x in per]))
            fl, pr = s_["fullness"], s_["peak_to_return"]
            cv = s_["rise_covered"] or [float("nan")] * 3
            uc = s_["rise_uncovered"] or [float("nan")] * 3
            bs = s_["rise_per_10g_size_matched"] or [float("nan")] * 3
            rec["rows"].append(dict(s_, arm=arm, window_min=w, own_subjects=own,
                                    evening_share=evening,
                                    trough_at_index_share=(at_index / tot if tot else
                                                           float("nan"))))
            print(f"{w:>7}{s_['subjects']:>8}{own:>5}{s_['meals']:>7}"
                  f"{f'{bp[0]:.0f} / {bp[1]:.0f} / {bp[2]:.0f}':>20}"
                  f"{f'{wp[0]:.0f} / {wp[1]:.0f} / {wp[2]:.0f}':>20}"
                  f"{f'{rr[0]:.1f} / {rr[1]:.1f} / {rr[2]:.1f}':>20}"
                  f"{f'{bs[0]:.1f} / {bs[1]:.1f} / {bs[2]:.1f}':>22}"
                  f"{f'{cv[0]:.1f} / {cv[1]:.1f} / {cv[2]:.1f}':>20}"
                  f"{f'{uc[0]:.1f} / {uc[1]:.1f} / {uc[2]:.1f}':>20}"
                  f"{f'{fl[0]:.2f} / {fl[1]:.2f} / {fl[2]:.2f}':>20}"
                  f"{f'{pr[0]:.0f} / {pr[1]:.0f} / {pr[2]:.0f}':>20}"
                  f"{s_['returned_share']:>6.2f}")

    # Paired, per subject, on the common panel, since the arms differ by one mechanism and the
    # subject is the strongest thing to hold fixed.
    print(f"\npaired on the common panel: duration, and rise per 10 g, against stock")
    print(f"{'window':>7}{'subj':>6}{'duration diff':>16}{'95 per cent':>22}"
          f"{'rise diff':>12}{'95 per cent':>22}")
    rng = np.random.default_rng(20260830)
    for w in a.windows:
        common = rec["common_panel"][w]
        if not common:
            continue
        dm = np.array([cells[("rebalanced", w, n)]["median"] - cells[("stock", w, n)]["median"]
                       for n in common])
        di = np.array([cells[("rebalanced", w, n)]["rise_median"]
                       - cells[("stock", w, n)]["rise_median"] for n in common])
        def ci(d):
            b = np.array([np.median(rng.choice(d, size=d.size, replace=True))
                          for _ in range(10000)])
            return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))
        cm, ciq = ci(dm), ci(di)
        rec.setdefault("paired", []).append(
            {"window_min": w, "subjects": len(common),
             "median_diff": float(np.median(dm)), "median_ci95": list(cm),
             "iqr_diff": float(np.median(di)), "iqr_ci95": list(ciq)})
        print(f"{w:>7}{len(common):>6}{np.median(dm):>14.1f}"
              f"{f'{cm[0]:.1f} to {cm[1]:.1f}':>22}{np.median(di):>12.1f}"
              f"{f'{ciq[0]:.1f} to {ciq[1]:.1f}':>22}")

    if dropped:
        print(f"\n{len(dropped)} subject-arms terminated early and are excluded")
    print("\nreal, Loop, for comparison")
    print(f"{'window':>7}{'subj':>6}{'meals':>7}{'per-person median':>20}"
          f"{'within-person IQR':>20}{'rise per 10 g':>20}"
          f"{'covered':>20}{'uncovered':>20}{'fullness':>20}{'peak to return':>20}")
    for w in a.windows:
        r = real_by.get(("Loop", w))
        if not r:
            continue
        bp, wp = r["between_person_median"], r["within_person_iqr"]
        rr = r.get("rise_per_10g_between_person", [float("nan")] * 3)
        st = r.get("strata", {})
        rcv = st.get("covered", {}).get("rise_per_10g", [float("nan")] * 3)
        runc = st.get("uncovered", {}).get("rise_per_10g", [float("nan")] * 3)
        rfl = r.get("fullness", [float("nan")] * 3)
        rpr = r.get("peak_to_return_min", [float("nan")] * 3)
        print(f"{w:>7}{r['subjects']:>6}{r['meals']:>7}"
              f"{f'{bp[0]:.0f} / {bp[1]:.0f} / {bp[2]:.0f}':>20}"
              f"{f'{wp[0]:.0f} / {wp[1]:.0f} / {wp[2]:.0f}':>20}"
              f"{f'{rr[0]:.1f} / {rr[1]:.1f} / {rr[2]:.1f}':>20}"
              f"{f'{rcv[0]:.1f} / {rcv[1]:.1f} / {rcv[2]:.1f}':>20}"
              f"{f'{runc[0]:.1f} / {runc[1]:.1f} / {runc[2]:.1f}':>20}"
              f"{f'{rfl[0]:.2f} / {rfl[1]:.2f} / {rfl[2]:.2f}':>20}"
              f"{f'{rpr[0]:.0f} / {rpr[1]:.0f} / {rpr[2]:.0f}':>20}")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
