"""The figures `docs/HOVORKA.md` quotes about the second body, from a committed producer.

Three groups. The steady state against Resalat et al.'s own 99 subjects, read from
`SingleHormone_VPP.mat` in their repository (github.com/petejacobs/T1D_VPP, not redistributed
here), which is skipped when no path is given. Glucose production under the clamp protocol of
`examples/hypoglycaemic_clamp.py`, computed from the equations: production in this model has no
glucose term, so at a clamped insulin infusion it is the same at every glucose plateau. And the
titration outcome, read from the Hovorka store.

    python examples/hovorka_checks.py [--resalat-mat path/to/SingleHormone_VPP.mat]
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "docs", "measurements", "hovorka_checks.json")

from timsim import provenance
from timsim.patient.hovorka import steady_state
from timsim.population import hovorka as pop
from timsim.therapy import titrate

CLAMP_INSULIN = 1.0              # mU/kg/min, the Rickels protocol
MG_PER_MMOL_GLUCOSE = 180.16
KEYS = ("F01", "VG", "k12", "AG", "tmaxG", "EGP0", "tmaxI", "ke", "VI",
        "ka1", "ka2", "ka3", "Sf1", "Sf2", "Sf3")     # the row order of Resalat's ModPar


def resalat(path):
    import scipy.io as sio
    m = sio.loadmat(path)
    y, w, tdi = m["YmSbjt"], m["Weights"].ravel(), m["TDIRlist"].ravel()
    ours = []
    for j in range(y.shape[1]):
        _, u = steady_state(dict(zip(KEYS, y[:15, j])), pop.BASAL_GLUCOSE)
        ours.append(24.0 * pop.TDI_PER_BASAL * u * w[j] * 60.0 / 1000.0)
    ours = np.asarray(ours)
    return {"n": int(len(tdi)), "their_tdi_median": float(np.median(tdi)),
            "our_tdi_median": float(np.median(ours)),
            "max_abs_tdi_diff": float(np.abs(ours - tdi).max()),
            "their_sf3_sd": float(y[14].std())}


def clamp(params):
    plasma = CLAMP_INSULIN / (params.ke * params.VI)
    egp = np.maximum(0.0, params.EGP0 * (1.0 - params.Sf3 * plasma)) * MG_PER_MMOL_GLUCOSE
    return {"plasma_insulin_mu_per_l": float(plasma.iloc[0]),
            "subjects": int(len(egp)), "producing_nothing": int((egp == 0).sum()),
            "egp_median": float(np.median(egp)), "egp_p90": float(np.percentile(egp, 90))}


def titration():
    store = titrate.load(titrate.HOVORKA_STORE)
    if store is None:
        return None
    titrate.check_population(store, titrate.HOVORKA_PARAMS)
    q = pd.read_csv(pop.THERAPY_FILE).set_index("Name")
    subjects = store["subjects"]
    found = [n for n, r in subjects.items() if r["found"]]
    lost = [n for n, r in subjects.items() if not r["found"]]
    adopted = [r["trace"][-1] for r in subjects.values() if r["found"]]
    levers = {}
    for n in found:
        levers[subjects[n]["lever"]] = levers.get(subjects[n]["lever"], 0) + 1
    return {"titrated": len(subjects), "found": len(found), "levers": levers,
            "tdi_median_found": float(q.loc[found, "TDI"].median()),
            "tdi_median_excluded": float(q.loc[lost, "TDI"].median()) if lost else None,
            "cf_median_adopted": float(np.median([t["isf"] for t in adopted])),
            "tir_median_adopted": float(np.median([t["tir"] for t in adopted])),
            "excluded_missing_tbr54": sum(1 for n in lost if any(
                "tbr54" in t.get("fails", ()) for t in subjects[n]["trace"]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resalat-mat")
    a = ap.parse_args()
    params = pd.read_csv(pop.PATIENT_FILE)
    out = {"provenance": provenance.stamp(),
           "resalat": resalat(a.resalat_mat) if a.resalat_mat else None,
           "clamp": clamp(params), "titration": titration()}
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "provenance"}, indent=1))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
