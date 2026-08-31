"""Carbohydrate appearance read from the model rather than inferred from the glucose it causes.

The simulated meal rise is 0.64 of the real one unbolused and 0.52 bolused, measured per person
against 767 Loop participants in `sim_meal_shape.json`. A rise is appearance divided by how fast
the glucose is cleared and how large a space it is diluted into, so a rise being short says
nothing about which of the three is responsible.

Appearance is the one that can be read directly. simglucose computes it as

    Ra = f * kabs * Qgut / BW        mg/kg/min

from the gut compartment, so it is a state of the model and needs no reference to be checked
against itself. Two things are asked of it here.

Whether the gut delivers what it was given. Integrating Ra over a long enough window and
multiplying by body weight should return the bioavailable fraction of the dose. A shortfall means
carbohydrate is being lost rather than absorbed slowly, which would be a defect in the meal model
as implemented rather than in its parameters.

What the glucose does per unit that arrives. Dividing the peak rise by the appearance that caused
it separates the gut from everything downstream. If appearance is conserved and its shape is the
published one, a short rise belongs to clearance or to the distribution volume, and `Vg` is the
first thing to look at because a rise is a mass divided by it.

The meal is uncovered and the layers are off, so the run is deterministic and the appearance is
the meal model alone. Insulin does not enter the appearance expression at all, so a bolus arm
would measure the same gut.

    python examples/meal_appearance.py --subjects 40
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

OUT = os.path.join(MEASUREMENTS, "meal_appearance.json")
SETTLE_MIN = 600
WATCH_MIN = 480
GRAMS = 60.0
WORKERS = 7
MARKS = (60, 120, 180, 240)


def job(args):
    """One subject, one uncovered meal, with appearance read from the gut each minute."""
    name, grams, settle, watch = args
    p = V.from_population(name)
    q = p._params
    bw, f, kabs = float(q.BW), float(q["f"]), float(q["kabs"])
    basal = q.u2ss * bw / 6000.0

    for _ in range(settle):
        p.step(PAction(CHO=0.0, insulin=basal))
    g0 = float(p.observation.Gsub)

    ra, gsub = [], []
    for m in range(watch):
        # The dose is delivered in the first minute, as `CustomScenario` delivers it.
        p.step(PAction(CHO=(grams if m == 0 else 0.0), insulin=basal))
        ra.append(f * kabs * float(p.state[2]) / bw)
        gsub.append(float(p.observation.Gsub))

    ra = np.asarray(ra, float)
    gsub = np.asarray(gsub, float)
    # Integrated at one minute steps, so the sum is the integral in mg/kg.
    total = float(ra.sum())
    expected = f * grams * 1000.0 / bw
    peak_i = int(np.argmax(ra))
    rise = float(gsub.max() - g0)
    return {"name": name, "BW": bw, "f": f, "kabs": kabs, "Vg": float(q["Vg"]),
            "appeared_mg_per_kg": total, "expected_mg_per_kg": expected,
            "recovered_fraction": total / expected if expected else float("nan"),
            "peak_ra": float(ra[peak_i]), "peak_ra_min": float(peak_i + 1),
            "fraction_by": {str(m): float(ra[:m].sum() / total) if total else float("nan")
                            for m in MARKS},
            "rise_mgdl": rise, "rise_per_10g": rise / (grams / 10.0),
            "rise_per_mg_per_kg": rise / total if total else float("nan")}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--grams", type=float, default=GRAMS)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    from examples.panel import dosable
    subs = dosable(a.subjects)
    with mp.Pool(a.workers) as pool:
        rows = pool.map(job, [(n, a.grams, SETTLE_MIN, WATCH_MIN) for n in subs])

    q = lambda v, p: float(np.percentile(np.asarray(v, float), p))
    def band(key, scale=1.0):
        v = [r[key] * scale for r in rows]
        return [q(v, 10), q(v, 50), q(v, 90)]

    rec = {"provenance": provenance.stamp(), "grams": a.grams, "n": len(rows),
           "settle_min": SETTLE_MIN, "watch_min": WATCH_MIN, "rows": rows,
           "recovered_fraction": band("recovered_fraction"),
           "peak_ra": band("peak_ra"), "peak_ra_min": band("peak_ra_min"),
           "rise_per_10g": band("rise_per_10g"),
           "rise_per_mg_per_kg": band("rise_per_mg_per_kg"),
           "Vg": band("Vg"), "kabs": band("kabs"),
           "fraction_by": {str(m): [q([r["fraction_by"][str(m)] for r in rows], p)
                                    for p in (10, 50, 90)] for m in MARKS}}

    print(f"{len(rows)} subjects, one uncovered {a.grams:.0f} g meal, layers off\n")
    show = [("carbohydrate recovered, fraction of bioavailable dose", "recovered_fraction", 3),
            ("peak appearance, mg/kg/min", "peak_ra", 2),
            ("time to peak appearance, min", "peak_ra_min", 0),
            ("glucose rise, mg/dL per 10 g", "rise_per_10g", 1),
            ("glucose rise per mg/kg appeared", "rise_per_mg_per_kg", 3),
            ("Vg, dL/kg", "Vg", 2)]
    for label, key, dp in show:
        v = rec[key]
        print(f"{label:>48}   {v[0]:.{dp}f} / {v[1]:.{dp}f} / {v[2]:.{dp}f}")
    print(f"\n{'fraction appeared by':>48}   " + "  ".join(f"{m} min" for m in MARKS))
    print(f"{'':>48}   " + "  ".join(f"{rec['fraction_by'][str(m)][1]:.2f}   " for m in MARKS))

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
