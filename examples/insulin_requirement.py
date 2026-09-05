"""Daily insulin per kilogram and the basal fraction: the generated adults against DCLP3's.

Written 5 September 2026, after a daily dose of 69.1 U under oref0 SMB against 41.1 for adult
Loop participants was put forward as a lead and rightly questioned: a daily dose scales with
body weight, insulin sensitivity and diet, so two sets of people are not compared by it. What
is a property of the person, and so of the population this package generates, is the insulin
a body needs per kilogram and how that need divides between basal and meals. The generator
constrains the first only by accepting any requirement between 8 and 160 U a day
(`timsim/population/generate.py`, `TDI_RANGE`) and the second not at all.

DCLP3 carries both for its participants: weight at screening (`DiabPhysExam_a.txt`), and at
each visit the current total daily insulin and the mean daily basal over the preceding seven
days (`InsulinPumpSettings_a.txt`, `CurrTotInsDaily` and `TotBasalPreced7Days`). The
randomisation visit reports the therapy the participant arrived on, and the 26-week visit the
therapy of the arm, Control-IQ or sensor-augmented pump. Both are read, on the adults of the
calibration half only; the sealed 40 per cent is not opened.

The generated adults are read three ways, in order of how much of the package each involves.
The closure gives each subject's basal rate (`derive.basal_rate`), and the screening day gives
its requirement on three meals with matched boluses (`TDI` in the therapy table). Those two are
the physiology alone. The delivered dose is then measured by running forty titrated adults for
28 days under the built-in correction loop and under oref0 SMB, with every layer on, and
splitting the delivered units into bolus and the rest. Weight is the same `BW` on every row.

    quantity                       real                          simulated
    weight, kg                     screening                     BW
    basal, U/kg/day                seven-day mean, per visit     closure rate; delivered non-bolus
    total, U/kg/day                current total, per visit      screening-day requirement; delivered
    basal fraction                 basal / total                 the same, on the delivered units

Registered before the run. The generated adults are expected to sit above the real
distribution on total insulin per kilogram (a delivered 0.8 U/kg/day under the loops, against
a real figure expected near 0.6) and above it on basal per kilogram (0.37 at closure), and
below it on basal fraction (0.30 under oref0 SMB against a real figure expected near 0.5). The
rule: a simulated median outside the real 10th to 90th percentile on a quantity makes that
quantity a screening target for the generator, and one inside closes the lead on that
quantity. The comparison on age is reported beside it, since the generated adults are older
(median 49 against 29 for the trial's closed-loop half) and need per kilogram falls with age.

    python examples/insulin_requirement.py
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds
from timsim.validation import dclp3

OUT = os.path.join(MEASUREMENTS, "insulin_requirement.json")
WORKERS = 7
ADULT_AGE = 18.0
LB_TO_KG = 0.45359237
VISITS = ("Randomization", "26-Week")
DRIVERS = ("trend", "oref")


def real_side():
    """Per adult of the calibration half: weight, age, arm, and per visit the basal and total."""
    ro = dclp3.roster()
    keep = set(ro.PtID) & set(dclp3.split()["calibration"])
    arm = dict(zip(ro.PtID, ro.trtGroup))
    sc = pd.read_csv(dclp3._path("DiabScreening_a.txt"), sep="|", encoding="utf-16")
    age = {int(p): float(a) for p, a in
           zip(sc.PtID, pd.to_numeric(sc.AgeAtEnrollment, errors="coerce")) if a == a}
    pe = pd.read_csv(dclp3._path("DiabPhysExam_a.txt"), sep="|", encoding="utf-16")
    w = pd.to_numeric(pe.Weight, errors="coerce")
    w = np.where(pe.WeightUnits.astype(str).str.lower().str.startswith("lb"), w * LB_TO_KG, w)
    weight = {int(p): float(x) for p, x in zip(pe.PtID, w) if x == x}
    ps = pd.read_csv(dclp3._path("InsulinPumpSettings_a.txt"), sep="|", encoding="utf-16")
    vi = pd.read_csv(dclp3._path("VisitInfo_a.txt"), sep="|", encoding="utf-16")
    ps = ps.merge(vi[["ParentLoginVisitID", "Visit"]], on="ParentLoginVisitID", how="left")
    ps["total"] = pd.to_numeric(ps.CurrTotInsDaily, errors="coerce")
    ps["basal"] = pd.to_numeric(ps.TotBasalPreced7Days, errors="coerce")
    out = {}
    for p in sorted(keep):
        if p not in weight or age.get(p, 0.0) < ADULT_AGE:
            continue
        rec = {"arm": arm[p], "age": age[p], "weight_kg": weight[p]}
        for v in VISITS:
            g = ps[(ps.PtID == p) & (ps.Visit == v)].dropna(subset=["total", "basal"])
            if g.empty:
                continue
            g = g.sort_values("RecID").iloc[0]
            rec[v] = {"total_u_day": float(g.total), "basal_u_day": float(g.basal)}
        out[int(p)] = rec
    return out


def population_side():
    """Every generated adult: weight, age, closure basal and the screening-day requirement."""
    from timsim.population import names, params_for, therapy_for
    from timsim.population import derive
    out = {}
    for n in names("adult"):
        p, t = params_for(n), therapy_for(n)
        out[n] = {"weight_kg": float(p["BW"]), "age": float(t["Age"]),
                  "basal_u_day": derive.basal_rate(p) * 1440.0,
                  "requirement_u_day": float(t["TDI"])}
    return out


def job(args):
    name, driver, days = args
    from timsim.simulation.run import simulate, DEFAULT_LAYERS
    from timsim.therapy import titrate
    from examples.capability_table import driver_for
    prof = titrate.profile_for(name)
    ctrl = driver_for(name, driver, prof)
    try:
        r = simulate(name, days=days, seed=seeds.BENCH, layers=DEFAULT_LAYERS,
                     controller=ctrl, profile=prof)
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()
    if r.termination:
        return name, driver, None
    bolus = float(np.sum(r.bolus_series))
    return name, driver, {"total_u_day": r.insulin_units / r.days_requested,
                          "bolus_u_day": bolus / r.days_requested}


def pct(v):
    v = np.asarray(v, float)
    return [float(np.percentile(v, q)) for q in (10, 50, 90)] if v.size else [np.nan] * 3


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    if not dclp3.available():
        raise SystemExit("DCLP3 is not available; see docs/VALIDATION.md")

    real = real_side()
    pop = population_side()
    from examples.panel import dosable
    subs = dosable(a.subjects)
    jobs = [(n, d, a.days) for d in DRIVERS for n in subs]
    print(f"{len(real)} real adults in the calibration half, {len(pop)} generated adults, "
          f"{len(jobs)} runs on {a.workers} workers", flush=True)
    with mp.Pool(a.workers) as pool:
        runs = pool.map(job, jobs, chunksize=1)
    delivered, dropped = {}, []
    for n, d, o in runs:
        if o is None:
            dropped.append({"subject": n, "driver": d})
        else:
            delivered[(n, d)] = {**o, "weight_kg": pop[n]["weight_kg"]}
    if dropped:
        print(f"  terminated: {', '.join(x['subject'] + ' ' + x['driver'] for x in dropped)}")

    rng = np.random.default_rng(20260905)

    def ci(v):
        v = np.asarray(v, float)
        b = np.array([np.median(rng.choice(v, size=v.size, replace=True)) for _ in range(10000)])
        return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]

    # Each row is one side of one quantity: a label, the values, and the people behind them.
    rows = []

    def add(quantity, side, label, values):
        values = [float(v) for v in values if v == v]
        if not values:
            return
        rows.append({"quantity": quantity, "side": side, "label": label, "n": len(values),
                     "p10_50_90": pct(values), "ci95_median": ci(values)})

    R = list(real.values())
    add("age_years", "real", "DCLP3 adults", [r["age"] for r in R])
    add("age_years", "sim", "generated adults", [p["age"] for p in pop.values()])
    add("weight_kg", "real", "DCLP3 adults", [r["weight_kg"] for r in R])
    add("weight_kg", "sim", "generated adults", [p["weight_kg"] for p in pop.values()])
    for v in VISITS:
        have = [r for r in R if v in r]
        for arm_label, sel in (("both arms", have),
                               ("Control-IQ", [r for r in have if r["arm"] == dclp3.CLOSED_LOOP]),
                               ("pump", [r for r in have if r["arm"] == dclp3.PUMP])):
            if v == "Randomization" and arm_label != "both arms":
                continue
            lab = f"DCLP3 {v.lower()}, {arm_label}"
            add("basal_u_kg_day", "real", lab, [r[v]["basal_u_day"] / r["weight_kg"] for r in sel])
            add("total_u_kg_day", "real", lab, [r[v]["total_u_day"] / r["weight_kg"] for r in sel])
            add("basal_fraction", "real", lab,
                [r[v]["basal_u_day"] / r[v]["total_u_day"] for r in sel if r[v]["total_u_day"] > 0])
    add("basal_u_kg_day", "sim", "closure, 300 generated adults",
        [p["basal_u_day"] / p["weight_kg"] for p in pop.values()])
    add("total_u_kg_day", "sim", "screening day, 300 generated adults",
        [p["requirement_u_day"] / p["weight_kg"] for p in pop.values()])
    add("basal_fraction", "sim", "screening day, 300 generated adults",
        [p["basal_u_day"] / p["requirement_u_day"] for p in pop.values()])
    for d in DRIVERS:
        D = [o for (n, dd), o in delivered.items() if dd == d]
        lab = f"delivered under {'the built-in loop' if d == 'trend' else 'oref0 SMB'}"
        add("basal_u_kg_day", "sim", lab,
            [(o["total_u_day"] - o["bolus_u_day"]) / o["weight_kg"] for o in D])
        add("total_u_kg_day", "sim", lab, [o["total_u_day"] / o["weight_kg"] for o in D])
        add("basal_fraction", "sim", lab,
            [(o["total_u_day"] - o["bolus_u_day"]) / o["total_u_day"] for o in D])

    verdicts = {}
    print(f"\n{'quantity':>16}  {'side':>4}  {'n':>4}  {'p10':>7}{'p50':>8}{'p90':>8}"
          f"  {'95 per cent on p50':>20}  label")
    for q in ("age_years", "weight_kg", "basal_u_kg_day", "total_u_kg_day", "basal_fraction"):
        here = [r for r in rows if r["quantity"] == q]
        ref = next((r for r in here if r["side"] == "real" and "both arms" in r["label"]
                    and "randomization" in r["label"]), None) or \
              next((r for r in here if r["side"] == "real"), None)
        for r in here:
            lo, hi = r["ci95_median"]
            p = r["p10_50_90"]
            flag = ""
            if r["side"] == "sim" and ref is not None:
                inside = ref["p10_50_90"][0] <= p[1] <= ref["p10_50_90"][2]
                flag = "inside" if inside else "outside"
                verdicts[f"{q}: {r['label']}"] = flag
            print(f"{q:>16}  {r['side']:>4}  {r['n']:>4}  {p[0]:>7.2f}{p[1]:>8.2f}{p[2]:>8.2f}"
                  f"  {f'[{lo:.2f}, {hi:.2f}]':>20}  {r['label']}  {flag}")
        print()

    json.dump({"provenance": provenance.stamp(), "split_fingerprint": dclp3.split()["fingerprint"],
               "adult_age": ADULT_AGE, "visits": list(VISITS), "days": a.days,
               "seed": seeds.BENCH, "subjects": subs, "drivers": list(DRIVERS),
               "dropped": dropped, "rows": rows, "verdicts": verdicts,
               # Per person, only the delivered ratios: neither the trial's per-participant
               # records nor the generated parameters are redistributed.
               "delivered": [{"subject": n, "driver": d,
                              "total_u_kg_day": o["total_u_day"] / o["weight_kg"],
                              "basal_u_kg_day": (o["total_u_day"] - o["bolus_u_day"]) / o["weight_kg"],
                              "basal_fraction": (o["total_u_day"] - o["bolus_u_day"]) / o["total_u_day"]}
                             for (n, d), o in sorted(delivered.items())]},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
