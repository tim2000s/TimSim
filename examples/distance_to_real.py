"""How much of the distance between the bare model and a real cohort the layers close.

The bare UVA/Padova S2008 patient sits a long way from any real closed-loop population on most
outcomes, and the question this package exists to answer is whether a person-in-the-loop layer
moves it towards one. That is a question about distance, so it needs a unit, and the raw gap in
percentage points is not one: a simulated median two points from a reference whose people span
forty points is close, and the same two points against a reference spanning four is not.

The unit used here is the spread between real people, taken as the tenth to ninetieth
percentile of the reference population's own per-person outcomes. A gap of one spread means the
simulated median sits as far from the real median as a real tenth-percentile person sits from a
real ninetieth-percentile one.

Three quantities are reported per measure. The bare gap and the layered gap are signed, so the
direction of the error is visible and a layer that overshoots is not scored as an improvement.
The fraction closed is `1 - |layered gap| / |bare gap|`, which is 1.0 when the layers land on
the real median, 0.0 when they leave the distance unchanged, and negative when they make it
worse. It is reported only where the bare model started at least `MIN_GAP` spreads from the
reference. Below that there is almost no distance to close, and dividing by it produces large
numbers that describe the size of the denominator rather than the effect of the layers: time
below 54 mg/dL under Control-IQ starts 0.08 spreads away and returns a fraction of -20.7, where
the movement it is scoring is six tenths of a percentage point.

Subjects are paired: only those completing both the bare and the layered arm contribute, so the
two medians describe the same bodies. This derives from `bench_matrix.json` and runs no
simulation, so it is cheap to recompute whenever the matrix changes.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np

from examples.bench_tables import MEASURES, load, references, paired
from timsim import provenance

# The layered arm to score. `layered_some` is the bench the package ships: the person announces
# some meals and misses others, which is what the real populations were doing.
LAYERED = "layered_some"

# Below this the bare model is already on the reference and the fraction closed is a ratio of
# two small numbers. The threshold is a tenth of the spread between a real tenth-percentile and
# ninetieth-percentile person, which is well inside the noise on any of these measures.
MIN_GAP = 0.10

# Below this the comparison is a statement about which subjects survived rather than about the
# layers. Runs end when glucose leaves the range the model is defined over, and the runs that
# fail are the ones that went lowest, so every figure here is conditioned on survival.
MIN_PAIRED = 10
OUT = os.path.join(MEASUREMENTS, "distance_to_real.json")


def distances(arms, subjects, ref):
    """Per measure: the bare and layered medians, the real median, and the gaps between."""
    keep = paired(arms, "bare", LAYERED, subjects)
    # `analysis/cohort.py::paired_subjects` refuses a comparison built from partial overlap,
    # and `bench_tables.paired` does not, so the refusal is repeated here rather than assumed.
    # A median over a handful of survivors is a statement about which subjects survived.
    if len(keep) < MIN_PAIRED:
        raise ValueError(
            f"only {len(keep)} subjects completed both the bare and the {LAYERED} arm, "
            f"which is below the {MIN_PAIRED} this comparison needs. Every figure here is "
            f"conditioned on survival, and at this count it is mostly conditioned on it.")
    out = {"paired": len(keep)}
    for key, name, refkey in MEASURES:
        if not refkey:
            continue
        bare = np.array([arms["bare"][n][key] for n in keep], float)
        lay = np.array([arms[LAYERED][n][key] for n in keep], float)
        real = np.array([r[refkey] for r in ref], float)
        spread = np.percentile(real, 90) - np.percentile(real, 10)
        if not spread:
            continue
        mb, ml, mr = float(np.median(bare)), float(np.median(lay)), float(np.median(real))
        spread = float(spread)
        gap_bare, gap_lay = (mb - mr) / spread, (ml - mr) / spread
        out[refkey] = {
            "bare": mb, "layered": ml, "real": mr,
            "real_spread_p10_p90": spread,
            "gap_bare_spreads": gap_bare,
            "gap_layered_spreads": gap_lay,
            # Withheld when the bare model is already on the real median: there is no
            # distance to close, so a fraction of it describes the denominator.
            "closed": (1 - abs(gap_lay) / abs(gap_bare)) if abs(gap_bare) >= MIN_GAP else None,
            "bare_already_within": bool(abs(gap_bare) < MIN_GAP),
        }
    return out


def main():
    d, idx = load()
    ref = references()
    out = {"population": d.get("population"), "days": d.get("days"), "seed": d.get("seed"),
           "layered_arm": LAYERED, "provenance": provenance.stamp(), "pairings": {}}

    for (cohort, controller), arms in idx.items():
        r = ref.get(cohort)
        if not isinstance(r, list) or not r:
            print(f"{cohort}/{controller}: no per-person reference, skipped")
            continue
        res = distances(arms, sorted({n for by in arms.values() for n in by}), r)
        out["pairings"][f"{cohort}|{controller}"] = res

        print(f"\n{'=' * 92}\n{cohort} under {controller}, "
              f"paired over {res['paired']} subjects, {len(r)} real people")
        print(f"  {'Measure':28}{'bare':>9}{'layered':>9}{'real':>9}"
              f"{'gap bare':>11}{'gap lay':>10}{'closed':>9}")
        for key, name, refkey in MEASURES:
            v = res.get(refkey)
            if not v:
                continue
            c = v["closed"]
            print(f"  {name:28}{v['bare']:>9.2f}{v['layered']:>9.2f}{v['real']:>9.2f}"
                  f"{v['gap_bare_spreads']:>+11.2f}{v['gap_layered_spreads']:>+10.2f}"
                  f"{(f'{c:>+9.2f}' if c is not None else '     near')}")
        print("  'near' means the bare model started within "
              f"{MIN_GAP} spreads, so no fraction is reported")

    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
