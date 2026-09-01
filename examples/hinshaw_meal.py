"""Hinshaw's triple-tracer mixed meal, reproduced in silico, flux by flux.

`docs/measurements/meal_appearance.json` found the simulated liver absorbing more of a meal than
the tissues do, and asked whether that is what a human liver does. Hinshaw et al. (Diabetes 2013;
62:2223-2229) is the measurement, in the right population and with all three fluxes: 19 people
with type 1 diabetes, identical mixed meals at breakfast, lunch and dinner in a Latin square,
triple tracer, six-hour windows. This package already cites it for the diurnal insulin sensitivity
figures in `docs/FIDELITY.md` and had never used the rest of the table.

The protocol is matched rather than approximated, at the second attempt. The first version used
the paper's 10 kcal/kg meal at 55 per cent carbohydrate, which is the standardisation meal eaten
between 17:00 and 17:30 on the evening before the first study day. The study meals are breakfast,
lunch and dinner with about 50 g of carbohydrate each, and that is what is given here. Every
quantity is integrated over six hours.

Fluxes are converted to the paper's normalisation rather than compared across two of them. The
tracer is dosed per kilogram of fat-free mass and Hinshaw's companion paper states the rates are
expressed that way, so the reference figures are divided into per-kilogram-of-body-weight terms
using the study's own mean, 53.6 kg of fat-free mass against 74.7 kg of weight. That ratio is a
cohort mean applied to every subject, since S2008 has no body composition, and it carries the
spread of a cohort whose fat-free mass ran 32.8 to 72.7 kg. It is the largest assumption in the
comparison and it moves every reference number by 28 per cent. The subject is on basal
insulin alone, as `meal_appearance.py` runs it, where Hinshaw's participants took their customary
insulin to carbohydrate ratio. That difference is the main reason to read the comparison as
directional, and it is stated with the result rather than buried.

Three quantities, defined as the paper defines them. Meal appearance and whole-body glucose
disappearance as areas under the curve over the six hours. Endogenous production as an area, and
as the percentage it falls below what the pre-meal rate would have produced over the same six
hours, which is the paper's "decrease from baseline".

Reported in the paper's units, micromoles per kilogram, so the numbers can be read against the
table without conversion. Glucose is 180.156 g/mol.

    python examples/hinshaw_meal.py --subjects 40
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np
from simglucose.patient.t1dpatient import Action as PAction

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance
from timsim.patient import varying as V

OUT = os.path.join(MEASUREMENTS, "hinshaw_meal.json")
SETTLE_MIN = 600
WINDOW_MIN = 360               # the paper's six hours
GRAMS = 50.0                   # the study meals, not the 10 kcal/kg run-in
FFM_OVER_BW = 53.6 / 74.7      # Hinshaw's cohort mean, to put the reference on body weight
MW_GLUCOSE = 180.156           # mg per mmol, so mg/kg divided by this is mmol/kg
WORKERS = 7

# Hinshaw et al., Diabetes 2013;62:2223-2229, table of model-based least squares means across
# 19 subjects with type 1 diabetes, at breakfast, lunch and dinner. Copied rather than restated so
# they cannot drift with the answer. Units micromol/kg unless noted.
HINSHAW = {
    "egp_baseline_umol_kg_min": (16.2, 19.5, 17.4),
    "egp_auc_umol_kg_6h": (2961.4, 2888.7, 2650.3),
    "egp_decrease_from_baseline_pct": (43.5, 52.3, 52.0),
    "mra_auc_umol_kg_6h": (6149.9, 6135.3, 6412.0),
    "rd_auc_umol_kg_6h": (8392.1, 8535.1, 8502.2),
    "rd_increase_from_baseline_pct": (50.8, 33.7, 47.0),
    "si_1e4_dl_kg_min_per_mu_ml": (5.1, 7.5, 7.2),
}
# The same table on body weight, which is what this model reports. Everything except the
# percentages, which are ratios and do not carry the normalisation.
HINSHAW_BW = {k: tuple(x * FFM_OVER_BW for x in v) if not k.endswith("pct") else v
              for k, v in HINSHAW.items() if k != "si_1e4_dl_kg_min_per_mu_ml"}


def _run(name, grams, settle, window, bolus_u=0.0):
    """One subject over the window, with every flux read from the state each minute.

    `bolus_u` is delivered in the first minute, as a pump would give it. Hinshaw's participants
    took their customary insulin to carbohydrate ratio with the meal, so an arm without one is
    measuring a different protocol and its glucose disappearance is not comparable.
    """
    p = V.from_population(name)
    q = p._params
    bw, f, kabs = float(q.BW), float(q["f"]), float(q["kabs"])
    basal = q.u2ss * bw / 6000.0
    for _ in range(settle):
        p.step(PAction(CHO=0.0, insulin=basal))

    ra, egp, uii, uid, ren = [], [], [], [], []
    for m in range(window):
        p.step(PAction(CHO=(grams if m == 0 else 0.0),
                       insulin=basal + (bolus_u if m == 0 else 0.0)))
        x = p.state
        ra.append(f * kabs * float(x[2]) / bw)
        egp.append(max(float(q.kp1 - q.kp2 * x[3] - q.kp3 * x[8]), 0.0))
        uii.append(float(q.Fsnc))
        uid.append(float((q.Vm0 + q.Vmx * x[6]) * x[4] / (q.Km0 + x[4])))
        ren.append(float(q.ke1 * (x[3] - q.ke2)) if float(x[3]) > float(q.ke2) else 0.0)
    return bw, [np.asarray(v, float) for v in (ra, egp, uii, uid, ren)]


def job(args):
    name, settle, window, covered = args
    grams = GRAMS
    bolus = 0.0
    if covered:
        # The subject's own titrated ratio, which is the analogue of "customary". The
        # physiological ratio in the population table is a quantity no real person has, and
        # `docs/METHODS.md` is explicit that a benchmark run on it measures the settings.
        from timsim.therapy import titrate
        prof = titrate.profile_for(name)
        bolus = grams / float(prof.cr_at(12 * 60))
    bw, (ra, egp, uii, uid, ren) = _run(name, grams, settle, window, bolus)
    _, (_, egp0, uii0, uid0, ren0) = _run(name, 0.0, settle, window)

    umol = lambda mg_per_kg: mg_per_kg * 1000.0 / MW_GLUCOSE      # mg/kg to micromol/kg
    # Rd is whole-body glucose disappearance, which in this model is the insulin-dependent and
    # insulin-independent routes. Renal excretion is not disappearance into tissue and is kept
    # separate, as the paper's Rd does not include it either.
    rd = uid + uii
    rd0 = uid0 + uii0
    base_rate = float(egp0.mean())
    return {"name": name, "BW": bw, "grams": grams, "bolus_u": bolus,
            "mra_auc": umol(float(ra.sum())),
            "egp_auc": umol(float(egp.sum())),
            "egp_baseline_rate": umol(base_rate),
            "egp_decrease_pct": 100.0 * (float(egp0.sum()) - float(egp.sum())) / float(egp0.sum()),
            "rd_auc": umol(float(rd.sum())),
            "rd_increase_pct": 100.0 * (float(rd.sum()) - float(rd0.sum())) / float(rd0.sum()),
            "renal_auc": umol(float(ren.sum()))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--window", type=int, default=WINDOW_MIN)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects)
    with mp.Pool(a.workers) as pool:
        arms = {label: pool.map(job, [(n, SETTLE_MIN, a.window, cov) for n in subs])
                for label, cov in (("basal only", False), ("meal bolus", True))}

    q = lambda v, p: float(np.percentile(np.asarray(v, float), p))
    band = lambda rows, k: [q([r[k] for r in rows], p) for p in (10, 50, 90)]
    rows = arms["meal bolus"]
    rec = {"provenance": provenance.stamp(), "n": len(rows), "window_min": a.window,
           "protocol": {"grams": GRAMS,
                        "insulin": "basal only, where Hinshaw's participants took their "
                                   "customary insulin to carbohydrate ratio"},
           "reference": {"citation": "Hinshaw et al., Diabetes 2013;62:2223-2229, n=19 T1D",
                         "ffm_over_bw": FFM_OVER_BW,
                         "per_ffm": {k: list(v) for k, v in HINSHAW.items()},
                         "per_bw": {k: list(v) for k, v in HINSHAW_BW.items()}},
           "arms": {k: v for k, v in arms.items()}}

    print(f"{len(rows)} subjects, {a.window} min window, {GRAMS:.0f} g carbohydrate, "
          f"reference converted to body weight at FFM/BW {FFM_OVER_BW:.3f}\n")
    print(f"{'':>42}{'basal only':>24}{'meal bolus':>24}{'Hinshaw B / L / D':>26}")
    show = [("meal appearance AUC, umol/kg/6h", "mra_auc", "mra_auc_umol_kg_6h", 0),
            ("production AUC, umol/kg/6h", "egp_auc", "egp_auc_umol_kg_6h", 0),
            ("production baseline, umol/kg/min", "egp_baseline_rate",
             "egp_baseline_umol_kg_min", 1),
            ("production decrease from baseline, %", "egp_decrease_pct",
             "egp_decrease_from_baseline_pct", 1),
            ("glucose disappearance AUC, umol/kg/6h", "rd_auc", "rd_auc_umol_kg_6h", 0),
            ("disappearance increase from baseline, %", "rd_increase_pct",
             "rd_increase_from_baseline_pct", 1)]
    for label, key, ref, dp in show:
        r = HINSHAW_BW[ref]
        cells = []
        for arm in ("basal only", "meal bolus"):
            v = band(arms[arm], key)
            rec.setdefault(arm, {})[key] = v
            cells.append(f"{v[0]:.{dp}f} / {v[1]:.{dp}f} / {v[2]:.{dp}f}")
        print(f"{label:>42}{cells[0]:>24}{cells[1]:>24}"
              f"{f'{r[0]:.{dp}f} / {r[1]:.{dp}f} / {r[2]:.{dp}f}':>26}")
    rec["grams"] = band(rows, "grams")
    rec["bolus_u"] = band(rows, "bolus_u")
    rec["renal_auc"] = band(rows, "renal_auc")
    print(f"\ncarbohydrate given: median {rec['grams'][1]:.0f} g "
          f"({rec['grams'][0]:.0f} to {rec['grams'][2]:.0f})")
    print(f"bolus given: median {rec['bolus_u'][1]:.1f} U from the titrated ratio")
    print(f"renal excretion, not in Rd: median {rec['renal_auc'][1]:.0f} umol/kg/6h")

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
