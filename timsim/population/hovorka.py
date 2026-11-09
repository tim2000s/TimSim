"""Generate the Hovorka population, following Resalat et al. (PLoS One 2019;14(7):e0217301).

Only the three insulin sensitivities and body weight vary between subjects; every other
parameter is the Hovorka 2004 nominal value in Resalat's Table 2. The sensitivities are the
nominal values for people without diabetes multiplied by 0.4, the factor Resalat chose so that
the population's mean daily insulin matched 42.3 U across their twenty clinical participants.

The sampling is transcribed from `SampleVirtualPopulationFromDistribution.m` in their source
rather than from the paper, because the two disagree and the source is what produced their
population. One standard normal draw drives all three sensitivities, and a uniform draw shared
between `Sf1` and `Sf3` decorrelates them by the amount the source calls a 75 per cent and a 25
per cent correlation with `Sf2`. The paper's Table 2 gives `Sf3` as 214 ± 5.9 (x 10^-4), where
the source's spread is 55 x 10^-4; the paper's figure repeats `Sf1`'s and is taken to be a
typesetting error. Body weight is drawn with a standard deviation of 15.9 kg in the source
against 14.6 kg in the paper's Table 1.

Each candidate then passes Resalat's two physiological tests, and the plausibility ranges this
package applies to its S2008 subjects:

  1. with no insulin, glucose reaches 300 mg/dL
  2. at 15 U/h, glucose falls to 100 mg/dL or below
  3. the probed correction factor, carbohydrate ratio and daily dose fall inside the ranges in
     `population/generate.py`

Daily dose is Resalat's estimate, the steady-state basal over 24 h times 1.78, since nothing
else here gives a Hovorka subject a daily dose. Settings are measured from each subject's own
body by the same probe as for S2008, so the two bodies are given settings in the same way.

    python -m timsim.population.hovorka --n 100
"""
import argparse
import hashlib
import json
import os

import numpy as np
import pandas as pd

from . import PARAMS_DIR

PATIENT_FILE = os.path.join(PARAMS_DIR, "hovorka_params.csv")
THERAPY_FILE = os.path.join(PARAMS_DIR, "hovorka_quest.csv")
REPORT_FILE = os.path.join(PARAMS_DIR, "hovorka_report.json")
PREFIX = "hovorka#"

# Resalat Table 2. Units: mmol/kg/min, L/kg, per minute, minutes, per mU/L.
NOMINAL = {"F01": 0.0097, "VG": 0.16, "k12": 0.066, "AG": 0.8, "tmaxG": 40.0,
           "EGP0": 0.0161, "tmaxI": 55.0, "ke": 0.138, "VI": 0.12,
           "ka1": 0.006, "ka2": 0.06, "ka3": 0.03}
SENSITIVITY_REDUCTION = 0.4
# (mean, standard deviation, share of the decorrelating uniform), before the reduction.
SF = {"Sf1": (51.2e-4, 14.4e-4, 0.25), "Sf2": (8.2e-4, 3.2e-4, 0.0),
      "Sf3": (520e-4, 137.5e-4, 0.75)}
WEIGHT = (76.3, 15.9)
BASAL_GLUCOSE = 115.0          # mg/dL, Resalat's steady state
TDI_PER_BASAL = 1.78           # Resalat's ratio of daily dose to daily basal
SCREEN_MINUTES = 5000          # Resalat's 1000 steps of 5 minutes


def draw(n, rng):
    z = rng.standard_normal(n)
    r = rng.uniform(size=n)
    out = {"BW": WEIGHT[0] + WEIGHT[1] * rng.standard_normal(n)}
    for k, (mean, sd, w) in SF.items():
        out[k] = SENSITIVITY_REDUCTION * (sd * (z + (-w + 2.0 * w * r)) + mean)
    return pd.DataFrame(out)


def _hold(p, start_mgdl, insulin_u_per_min, minutes):
    from simglucose.patient.t1dpatient import Action
    from ..patient.hovorka import HovorkaPatient
    q = dict(p, Gb=start_mgdl)
    patient = HovorkaPatient(q)
    for _ in range(minutes):
        patient.step(Action(insulin=insulin_u_per_min, CHO=0.0))
    return patient.observation.Gsub


def screen(p):
    """None if the candidate passes, otherwise the reason it does not."""
    from ..patient.hovorka import steady_state
    from .generate import CF_RANGE, CR_RANGE, TDI_RANGE, measure_settings
    from ..patient.hovorka import HovorkaPatient

    if min(p["Sf1"], p["Sf2"], p["Sf3"]) <= 0.0:
        return "non-positive sensitivity", None
    if p["BW"] <= 0.0:
        return "non-positive body weight", None
    try:
        _, u = steady_state(p, BASAL_GLUCOSE)
    except ValueError:
        return "no steady state", None
    if _hold(p, BASAL_GLUCOSE, 0.0, SCREEN_MINUTES) < 300.0:
        return "does not reach 300 mg/dL without insulin", None
    if _hold(p, 160.0, 15.0 / 60.0, SCREEN_MINUTES) > 100.0:
        return "does not fall to 100 mg/dL at 15 U/h", None

    basal = u * p["BW"] / 1000.0          # U/min
    cf, cr = measure_settings(p, make=lambda: HovorkaPatient(p), basal=basal)
    tdi = basal * 60.0 * 24.0 * TDI_PER_BASAL
    if cf is None or not (CF_RANGE[0] <= cf <= CF_RANGE[1]):
        return "correction factor outside the plausible range", None
    if not (CR_RANGE[0] <= cr <= CR_RANGE[1]):
        return "carbohydrate ratio outside the plausible range", None
    if not (TDI_RANGE[0] <= tdi <= TDI_RANGE[1]):
        return "daily dose outside the plausible range", None
    # u2ss in pmol/kg/min, the unit `therapy/profile.py` reads basal from for every subject.
    return None, {"u2ss": u * 6.0, "CF": cf, "CR": cr, "TDI": tdi}


def generate(n=100, seed=2026):
    rng = np.random.default_rng(seed)
    rows, quest, rejected, tried = [], [], {}, 0
    while len(rows) < n:
        for _, c in draw(n, rng).iterrows():
            tried += 1
            p = {"Name": f"{PREFIX}{len(rows) + 1:03d}", **NOMINAL, **c.to_dict(),
                 "Gb": BASAL_GLUCOSE}
            why, s = screen(p)
            if why:
                rejected[why] = rejected.get(why, 0) + 1
                continue
            rows.append({**p, "u2ss": s["u2ss"]})
            quest.append({"Name": p["Name"], "CR": s["CR"], "CF": s["CF"],
                          "Age": np.nan, "TDI": s["TDI"]})
            if len(rows) == n:
                break
    return pd.DataFrame(rows), pd.DataFrame(quest), {
        "seed": seed, "candidates": tried, "accepted": n, "rejected": rejected}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    params, quest, report = generate(a.n, a.seed)
    params.to_csv(PATIENT_FILE, index=False)
    quest.to_csv(THERAPY_FILE, index=False)
    with open(PATIENT_FILE, "rb") as fh:
        report["fingerprint"] = hashlib.sha256(fh.read()).hexdigest()[:16]
    with open(REPORT_FILE, "w") as fh:
        json.dump(report, fh, indent=1)
    print(json.dumps(report, indent=1))
    print(quest[["CF", "CR", "TDI"]].describe().round(2))


if __name__ == "__main__":
    main()
