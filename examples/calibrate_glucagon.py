"""Can a glucagon gate reproduce the measured concentration and the measured production at once?

Two clamp studies, two targets, one mechanism. The secretion parameters are fitted so that a
subject with the Hypo-RESOLVE responsivity reaches 9.4 pmol/L at a 2.8 mmol/L clamp, and the
result is then scored on whether the production that glucagon drives is a meaningful share of
the 0.42 to 0.84 mg/kg/min Rickels measured at the same depth. Nothing about the second target
is used to fit the first, so hitting both would be a real constraint.

`docs/DESIGN_COUNTERREGULATION_AND_EXERCISE.md` fixes what would refute this before it was run.
The mechanism fails if the glucagon contribution to production is under a tenth of the total
with the gluconeogenesis sensitivity at the top of its published range, because then it does not
carry the production it exists to explain and the empirical defence stays.

    python examples/calibrate_glucagon.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np

from timsim.patient import glucagon as G

OUT = os.path.join(MEASUREMENTS, "glucagon_calibration.json")

# The Hypo-RESOLVE clamp: 2.8 mmol/L held for 60 minutes, reached from euglycaemia.
CLAMP_MGDL = G.CLAMP_TARGET_MMOL_L * 18.0182
DESCENT_MIN = 60.0
PLATEAU_MIN = 60.0
RICKELS_EGP = (0.42, 0.84)


def clamp_profile(minutes=DESCENT_MIN + PLATEAU_MIN, start=100.0, target=CLAMP_MGDL):
    """Glucose falling linearly to the clamp target, then held, one value per minute."""
    out = []
    for t in range(int(minutes)):
        if t < DESCENT_MIN:
            out.append(start + (target - start) * t / DESCENT_MIN)
        else:
            out.append(target)
    return out


def run_clamp(responsivity, sigma=G.SIGMA, delta=G.DELTA, b=None, d=None):
    """Glucagon and the production it drives, at the end of the plateau."""
    model = G.Glucagon(responsivity, sigma=sigma, delta=delta, b=b, d=d)
    profile = clamp_profile()
    conc, egp = [], []
    for i, g in enumerate(profile):
        model.step(g, minutes=1.0)
        if i >= DESCENT_MIN + PLATEAU_MIN - 20:      # the last twenty minutes of the plateau
            conc.append(model.concentration)
            egp.append(model.egp_mg_kg_min())
    return float(np.mean(conc)), float(np.mean(egp))


def fit_sigma(target_pmol_l, responsivity, delta=G.DELTA):
    """The static responsivity that puts a subject at the measured concentration.

    One free parameter against one target, solved by bisection rather than a sweep, since the
    response is monotone in sigma.
    """
    lo, hi = 0.0, 200.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        conc, _ = run_clamp(responsivity, sigma=mid, delta=delta)
        if conc - G.BASAL_PMOL_L < target_pmol_l:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def main():
    healthy = float(np.mean(G.RESPONSIVITY_RANGE)) or 0.225
    top = G.RESPONSIVITY_RANGE[1]

    print(f"Hypo-RESOLVE: type 1 diabetes {G.T1D_RESPONSE_PMOL_L} pmol/L above basal, "
          f"controls {G.CONTROL_RESPONSE_PMOL_L}, at {G.CLAMP_TARGET_MMOL_L} mmol/L "
          f"({CLAMP_MGDL:.1f} mg/dL)\n")

    # Fit the static arm so a subject at the top of the retained range reaches the measured
    # type 1 response. That is the most favourable reading of the evidence for this mechanism.
    sigma = fit_sigma(G.T1D_RESPONSE_PMOL_L, top)
    conc, _ = run_clamp(top, sigma=sigma)
    print(f"fitted static responsivity {sigma:.3f} at retained fraction {top:.2f}: "
          f"{conc - G.BASAL_PMOL_L:.2f} pmol/L above basal\n")

    print(f"  {'gluconeogenesis d':>19}{'glycogenolysis b':>19}{'glucagon EGP':>15}"
          f"{'share of 0.59':>15}")
    rows = []
    for d in (G.D_GLUCONEOGENESIS[0], 1.0, 4.0, 8.0, G.D_GLUCONEOGENESIS[1]):
        for b in (G.B_GLYCOGENOLYSIS[0], G.B_GLYCOGENOLYSIS[1]):
            _, egp = run_clamp(top, sigma=sigma, b=b, d=d)
            share = egp / 0.59
            rows.append({"d": d, "b": b, "egp": egp, "share": share})
            print(f"  {d:>19.3f}{b:>19.3f}{egp:>15.4f}{share:>14.1%}")

    best = max(rows, key=lambda r: r["egp"])

    # What the concentration target costs: how far outside the published range the
    # gluconeogenesis sensitivity would have to sit to reach the Rickels band.
    _, egp_at_top = run_clamp(top, sigma=sigma, b=G.B_GLYCOGENOLYSIS[1],
                              d=G.D_GLUCONEOGENESIS[1])
    needed = (G.D_GLUCONEOGENESIS[1] * (RICKELS_EGP[0] / egp_at_top)
              if egp_at_top > 0 else float("inf"))

    # The two criteria the design fixed in advance, joined by `or` as it states them. Both are
    # evaluated because a mechanism can fail one and pass the other, and the earlier version of
    # this script tested only the second and reported success while the first was failing.
    needs_unpublished_d = needed > G.D_GLUCONEOGENESIS[1]
    under_a_tenth = best["share"] < 0.10
    refuted = needs_unpublished_d or under_a_tenth

    print(f"\n  the most favourable parameterisation inside the published ranges gives "
          f"{best['egp']:.4f} mg/kg/min,")
    print(f"  which is {best['share']:.1%} of the 0.59 Rickels measured at this depth")
    print(f"\n  to reach {RICKELS_EGP[0]} mg/kg/min the gluconeogenesis sensitivity would need "
          f"to be {needed:.1f}, against a published upper bound of {G.D_GLUCONEOGENESIS[1]}")
    print(f"\n  criterion 1, reaching the Rickels band needs an unpublished sensitivity: "
          f"{needs_unpublished_d}")
    print(f"  criterion 2, contributes under a tenth of the production:               "
          f"{under_a_tenth}")
    print(f"\n  VERDICT: {'REFUTED, per the design' if refuted else 'the mechanism carries the production'}")
    if refuted and not under_a_tenth:
        print(f"  It contributes a real minority, {best['share']:.1%}, and cannot carry the rest.")

    json.dump({"fitted_sigma": sigma, "responsivity": top,
               "concentration_pmol_l": conc - G.BASAL_PMOL_L,
               "target_pmol_l": G.T1D_RESPONSE_PMOL_L,
               "rows": rows, "best": best,
               "criterion_needs_unpublished_d": bool(needs_unpublished_d),
               "criterion_under_a_tenth": bool(under_a_tenth),
               "refuted": bool(refuted),
               "gluconeogenesis_needed_for_rickels": needed},
              open(OUT, "w"), indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
