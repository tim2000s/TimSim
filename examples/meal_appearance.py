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
it separates the gut from everything downstream, and the channels it leaves by are states of the
model too. Appearance turned out to be conserved and `Vg` reproduces the published distribution,
so this now also integrates where the glucose goes:

    EGP     endogenous production, `kp1 - kp2*Gp - kp3*Id`, floored at zero
    Uii     insulin-independent utilisation, the constant `Fsnc`
    Uid     insulin-dependent utilisation, `(Vm0 + Vmx*X) * Gt / (Km0 + Gt)`
    E       renal excretion, `ke1 * (Gp - ke2)` above the threshold and zero below

Renal excretion is the one to look at first. Its threshold sits near 180 mg/dL in plasma terms and
the simulated meal peaks reach about 200, so it removes glucose from the top of an excursion and
from nowhere else, which is the shape of a defect that lowers a peak while leaving the rest of the
curve alone. The rise here is 0.79 of the real one with no loop acting at all, and the excursion
shape below the peak already matches real people.

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


def _trace(name, grams, settle, watch):
    """One subject over one window, with every flux read from the state each minute."""
    p = V.from_population(name)
    q = p._params
    bw, f, kabs = float(q.BW), float(q["f"]), float(q["kabs"])
    basal = q.u2ss * bw / 6000.0

    for _ in range(settle):
        p.step(PAction(CHO=0.0, insulin=basal))
    g0 = float(p.observation.Gsub)

    ra, gsub, egp, uii, uid, ren = [], [], [], [], [], []
    for m in range(watch):
        # The dose is delivered in the first minute, as `CustomScenario` delivers it.
        p.step(PAction(CHO=(grams if m == 0 else 0.0), insulin=basal))
        x = p.state
        ra.append(f * kabs * float(x[2]) / bw)
        gsub.append(float(p.observation.Gsub))
        # Read after the step, so every flux is taken at the same instant as the appearance it is
        # being compared with. Reading some before and some after mixes two states, which is the
        # defect that cost three wrong versions of the two-timescale liver.
        egp.append(max(float(q.kp1 - q.kp2 * x[3] - q.kp3 * x[8]), 0.0))
        uii.append(float(q.Fsnc))
        uid.append(float((q.Vm0 + q.Vmx * x[6]) * x[4] / (q.Km0 + x[4])))
        ren.append(float(q.ke1 * (x[3] - q.ke2)) if float(x[3]) > float(q.ke2) else 0.0)

    ra = np.asarray(ra, float)
    gsub = np.asarray(gsub, float)
    egp, uii, uid, ren = (np.asarray(v, float) for v in (egp, uii, uid, ren))
    # One minute steps, so a sum is an integral in mg/kg.
    fluxes = {"EGP": float(egp.sum()), "Uii": float(uii.sum()),
              "Uid": float(uid.sum()), "renal": float(ren.sum()), "Ra": float(ra.sum())}
    return {"bw": bw, "f": f, "kabs": kabs, "Vg": float(q["Vg"]), "g0": g0,
            "ra": ra, "gsub": gsub, "fluxes": fluxes}
    # Integrated at one minute steps, so the sum is the integral in mg/kg.
def job(args):
    """One subject with the meal and the same subject eating nothing, differenced.

    Integrated over eight hours the fluxes are dominated by what the subject does anyway: about
    1.9 mg/kg/min of production and the same again of disposal, against 700 mg/kg from a 60 g
    meal. The absolute integrals therefore say almost nothing about where the meal went, and the
    counterfactual is what separates the meal from the metabolism it lands on. Identical subject,
    identical basal, no meal, so the difference is the meal and the model is deterministic with
    the layers off.
    """
    name, grams, settle, watch = args
    m = _trace(name, grams, settle, watch)
    c = _trace(name, 0.0, settle, watch)

    bw, f, kabs = m["bw"], m["f"], m["kabs"]
    ra, gsub, g0 = m["ra"], m["gsub"], m["g0"]
    total = float(ra.sum())
    expected = f * grams * 1000.0 / bw
    peak_i = int(np.argmax(ra))
    rise = float(gsub.max() - g0)
    # Attributable to the meal: what each channel did with it, over what it would have done.
    delta = {k: m["fluxes"][k] - c["fluxes"][k] for k in m["fluxes"]}
    disposed = delta["Uid"] + delta["Uii"] + delta["renal"]
    fluxes = m["fluxes"]
    return {"name": name, "BW": bw, "f": f, "kabs": kabs, "Vg": m["Vg"],
            "delta_mg_per_kg": delta,
            "meal_disposal_mg_per_kg": disposed,
            "egp_suppressed_mg_per_kg": -delta["EGP"],
            "share_uid": delta["Uid"] / total if total else float("nan"),
            "share_renal": delta["renal"] / total if total else float("nan"),
            "share_egp_suppression": -delta["EGP"] / total if total else float("nan"),
            "appeared_mg_per_kg": total, "expected_mg_per_kg": expected,
            "recovered_fraction": total / expected if expected else float("nan"),
            "peak_ra": float(ra[peak_i]), "peak_ra_min": float(peak_i + 1),
            "fraction_by": {str(k): float(ra[:k].sum() / total) if total else float("nan")
                            for k in MARKS},
            "rise_mgdl": rise, "rise_per_10g": rise / (grams / 10.0),
            "rise_per_mg_per_kg": rise / total if total else float("nan"),
            "renal_share_of_appearance": fluxes["renal"] / total if total else float("nan"),
            "fluxes_mg_per_kg": fluxes}


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
           "renal_share_of_appearance": band("renal_share_of_appearance"),
           "share_uid": band("share_uid"), "share_renal": band("share_renal"),
           "share_egp_suppression": band("share_egp_suppression"),
           "fraction_by": {str(m): [q([r["fraction_by"][str(m)] for r in rows], p)
                                    for p in (10, 50, 90)] for m in MARKS}}

    print(f"{len(rows)} subjects, one uncovered {a.grams:.0f} g meal, layers off\n")
    show = [("carbohydrate recovered, fraction of bioavailable dose", "recovered_fraction", 3),
            ("peak appearance, mg/kg/min", "peak_ra", 2),
            ("time to peak appearance, min", "peak_ra_min", 0),
            ("glucose rise, mg/dL per 10 g", "rise_per_10g", 1),
            ("glucose rise per mg/kg appeared", "rise_per_mg_per_kg", 3),
            ("Vg, dL/kg", "Vg", 2),
            ("insulin-dependent uptake, share of what appeared", "share_uid", 3),
            ("renal excretion, share of what appeared", "share_renal", 3),
            ("production suppressed, share of what appeared", "share_egp_suppression", 3)]
    for label, key, dp in show:
        v = rec[key]
        print(f"{label:>48}   {v[0]:.{dp}f} / {v[1]:.{dp}f} / {v[2]:.{dp}f}")
    print(f"\n{'attributable to the meal, mg/kg':>48}   p10 / p50 / p90")
    for k in ("Ra", "Uid", "renal", "EGP"):
        v = [q([r["delta_mg_per_kg"][k] for r in rows], p) for p in (10, 50, 90)]
        rec.setdefault("delta_mg_per_kg", {})[k] = v
        print(f"{k:>48}   {v[0]:.1f} / {v[1]:.1f} / {v[2]:.1f}")
    print(f"\n{'fraction appeared by':>48}   " + "  ".join(f"{m} min" for m in MARKS))
    print(f"{'':>48}   " + "  ".join(f"{rec['fraction_by'][str(m)][1]:.2f}   " for m in MARKS))

    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
