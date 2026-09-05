"""Does a hypoglycaemia mechanism move the outcome, not just the clamp?

The clamp is where the defect was found and the matrix is where it matters. A subject producing
0.3 mg/kg/min instead of nothing at a clamp may still fall just as far during a spontaneous low,
because the insulin driving one is about half the clamp's.

Two arms, paired on the subject, on the cohorts the bench matrix uses:

    base        the shipped configuration
    bio         plus the rescue absorption scale

It was designed for three. `docs/DESIGN_HYPOGLYCAEMIA.md` put a production floor first, on the
reasoning that the floor changes how deep lows get and so changes how much rescue carbohydrate
is eaten, which is what the second mechanism acts on. The floor was refuted against the criteria
fixed before it was built and was removed, so that ordering no longer applies and the floor is
held at zero in both arms.

Extended 5 September 2026 for the EGP defence at 0.25. `examples/low_recovery.py` found that
with the person not eating for a low, 8 of 40 subjects under oref0 SMB fall to about 10 mg/dL
within 28 days and none do with the defence at 0.25, at a clamp cost already recorded in
`patient/varying.py` (median production 1.06 mg/kg/min against a human 0.42 to 0.84). This
puts that arm on the outcome table under the shipped person, against the shipped configuration
stated explicitly, on the same pairings. Registered: the arm is worth adopting on the outcome
if time below 54 mg/dL falls, paired, by more than the group variation `group_floor.json`
measures for the cell (95th percentile of the difference between disjoint halves, layered
cells: 0.41 points under Control-IQ on DCLP3, 0.34 under oref0 SMB on DCLP3, 0.56 on the
Commons cohort) with the interval clear of zero; a fall inside that variation says the
fall-throughs and the outcome are separate, as the floor's were, and the defence stays at 0.05.
Completion, rebound and recovery are reported beside it. The registration as first written gave
0.34 for the Control-IQ cell, a transcription error against `group_floor.json`, corrected after
the DCLP3 half had been read; the result is inside both figures.

Result, 5 September 2026 (`egp_defence_outcome.json`, pooled from `_mac.json` and
`_desktop.json`, 484 runs of 28 days, identical population and settings fingerprints). Time
below 54 mg/dL fell in every cell and in every cell by less than the group variation:

    cell                      shipped   defence   paired difference       group variation
    DCLP3, Control-IQ          0.55      0.47     -0.14 [-0.24, -0.05]    0.41
    DCLP3, oref0 SMB           1.00      0.77     -0.30 [-0.42, -0.18]    0.34
    Commons, oref0 SMB         1.13      0.81     -0.31 [-0.43, -0.19]    0.56

So on the criterion above the defence at 0.25 is refuted on the outcome table and the setting
stays at 0.05. Rebound, the statistic furthest from real, did not move (-1.4 [-3.4, +0.7], -0.3
[-2.4, +1.8] and +1.8 [-0.7, +4.3] points) and recovery moved by under three minutes.

What the paired table cannot show is completion, since a subject enters it only when both of
its runs reached 28 days, and this is where the two arms differ. `_terminations.json` and
`_terminations_commons.json` rerun every subject that left the table under either arm, with the
direction recorded; both reproduce the main runs to every decimal. Of the 242 subject-runs
under the shipped configuration, 18 ended by glucose falling through 40 mg/dL to about 10, each
with one to four rescues eaten in the six hours before the end, so the person was eating and
still falling; 3 ended above 500. With the defence at 0.25, 4 end from below and 5 from above:
three subjects that completed at 0.05 leave through 500 mg/dL at 0.25 (adolescent#031 and
adult#004 on DCLP3 under oref0 SMB, child#037 on Commons), none with a site failure in
progress, and adult#084 on Commons falls through at 0.25 having completed at 0.05. Completion
runs 221 of 242 against 233.

This is the floor's result in a different form. The mechanism that keeps a subject from reaching
10 mg/dL moves time below 54 by a tenth to a third of a point, inside what a change of
participants does, so the fall-throughs and the outcome are separate quantities and fixing one
says little about the other. The decision left is whether a bench that excludes 9 subjects in
242 rather than 21 is worth a clamp production of 1.06 mg/kg/min against a human 0.42 to 0.84,
and two more subjects leaving through the top. It is a modelling choice and is not taken here.

The pairings can run on different machines (`--pairings`, `--out`) and be reported together
(`--from file ...`), which checks that every file carries the same arms and provenance
fingerprints before pooling the runs.

    python examples/hypoglycaemia_arms.py
    python examples/hypoglycaemia_arms.py --arms shipped defence --pairings dclp3:control-iq dclp3:oref \
        --out docs/measurements/egp_defence_outcome_mac.json
    python examples/hypoglycaemia_arms.py --arms shipped defence --pairings commons:oref \
        --out docs/measurements/egp_defence_outcome_desktop.json
    python examples/hypoglycaemia_arms.py --arms shipped defence \
        --from docs/measurements/egp_defence_outcome_mac.json docs/measurements/egp_defence_outcome_desktop.json \
        --out docs/measurements/egp_defence_outcome.json
"""
import argparse

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import time
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "rescue_bio_alone.json")
DAYS, SEED = 28, seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")

# The rescue scale is the ratio of the real carbohydrate response to the simulated one: real
# 15.9 to 19.7 mg/dL per logged 10 g against a simulated 21.1 to 21.6, so the midpoints give
# about 0.83. It is a bioavailability, so the person still eats what the record says.
RESCUE_BIO = 0.83

# Every arm states every mechanism explicitly, including the control. Leaving the control to
# inherit module defaults is what made an earlier run compare a configuration with itself.
ARMS = {
    "base":      {"hypo_egp_floor": 0.0, "rescue_bioavailability": 1.0, "hypo_egp_defence": 0.05},
    "bio":       {"hypo_egp_floor": 0.0, "rescue_bioavailability": RESCUE_BIO,
                  "hypo_egp_defence": 0.05},
    # The shipped configuration since the bio arm was adopted, and the defence raised on it.
    "shipped":   {"hypo_egp_floor": 0.0, "rescue_bioavailability": RESCUE_BIO,
                  "hypo_egp_defence": 0.05},
    "defence":   {"hypo_egp_floor": 0.0, "rescue_bioavailability": RESCUE_BIO,
                  "hypo_egp_defence": 0.25},
}


def one(job):
    cohort, controller, name, arm = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    ctrl, t0 = controller, time.time()
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=ctrl,
                     profile=prof, announcement="some", **ARMS[arm])
    except Exception as exc:
        return {"cohort": cohort, "controller": controller, "arm": arm, "name": name,
                "completed": False, "error": str(exc)[:200]}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, float)
    days = max(len(cgm) * 5.0 / 1440.0, 1e-9)
    from timsim.analysis import signatures as S
    packed = S.from_result(r)
    return {"cohort": cohort, "controller": controller, "arm": arm, "name": name,
            "completed": bool(r.completed),
            "termination": None if r.completed else r.termination,
            "tir": float(100 * np.mean((cgm >= 70) & (cgm <= 180))),
            "tbr70": float(100 * np.mean(cgm < 70)),
            "tbr54": float(100 * np.mean(cgm < 54)),
            "mean": float(np.mean(cgm)),
            "cv": float(100 * np.std(cgm, ddof=1) / np.mean(cgm)),
            "rescue_per_30d": float(30.0 * r.rescue_events / days),
            "rescue_g_per_day": float(r.rescue_grams / days),
            "hypo_rec": float(S._hypo(packed)[0]),
            "hypo_reb": float(100 * S._hypo(packed)[1])}


def boot(d, n=5000, seed=0):
    d = np.asarray([x for x in d if np.isfinite(x)], float)
    if len(d) < 3:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    m = d[rng.integers(0, len(d), size=(n, len(d)))].mean(axis=1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", nargs="+", default=["base", "bio"], choices=list(ARMS))
    ap.add_argument("--pairings", nargs="+",
                    default=["dclp3:control-iq", "dclp3:oref", "commons:oref"])
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", "7")))
    ap.add_argument("--subjects", nargs="+", default=None,
                    help="restrict to these subjects, for looking at particular runs")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--from", dest="pool", nargs="+", default=None,
                    help="report from these files' runs instead of running")
    a = ap.parse_args()
    arms = a.arms
    base_arm = arms[0]

    if a.pool:
        rows, stamp = [], None
        for path in a.pool:
            j = json.load(open(path))
            key = {k: j["provenance"][k] for k in ("population", "settings")}
            if stamp is None:
                stamp, arms = key, list(j["arms"])
            elif key != stamp or list(j["arms"]) != arms:
                raise SystemExit(f"{path}: arms or fingerprints differ from {a.pool[0]}")
            rows += j["runs"]
        base_arm = arms[0]
        print(f"{len(rows)} runs pooled from {len(a.pool)} files", flush=True)
    else:
        rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
        from timsim.therapy import titrate
        tit = set(titrate.titrated_subjects())
        pairings = [tuple(p.split(":")) for p in a.pairings]
        jobs = []
        for cohort, controller in pairings:
            subs = [s for s in rec["cohorts"][cohort]["subjects"] if s in tit]
            if a.subjects:
                subs = [s for s in subs if s in a.subjects]
            for arm in arms:
                jobs += [(cohort, controller, s, arm) for s in subs]
        print(f"{len(jobs)} runs, {len(arms)} arms across {len(pairings)} pairings "
              f"on {a.workers} workers", flush=True)

        rows, t0 = [], time.time()
        with ProcessPoolExecutor(max_workers=a.workers) as ex:
            for i, row in enumerate(ex.map(one, jobs), 1):
                rows.append(row)
                if i % 40 == 0 or i == len(jobs):
                    print(f"  {i}/{len(jobs)} done, {(time.time()-t0)/60:.1f} min", flush=True)

    a.arms = arms
    idx = {}
    for r in rows:
        idx.setdefault((r["cohort"], r["controller"]), {}).setdefault(r["arm"], {})[r["name"]] = r

    MEAS = [("tbr54","Time below 54 %"),("tbr70","Time below 70 %"),("hypo_reb","Rebound %"),
            ("hypo_rec","Recovery min"),("tir","Time in range %"),("cv","Variability %"),
            ("rescue_g_per_day","Rescue g/day")]
    report = {}
    for key, arms in sorted(idx.items()):
        base = arms.get(base_arm, {})
        for arm in [x for x in a.arms if x != base_arm]:
            other = arms.get(arm, {})
            keep = [n for n in base
                    if base[n].get("completed") and other.get(n, {}).get("completed")]
            if len(keep) < 10:
                continue
            print(f"\n=== {key[0]} / {key[1]} : {arm} against base, paired over {len(keep)} ===")
            print(f"  {'measure':18}{'base':>9}{arm:>11}{'paired difference':>26}")
            for k, lab in MEAS:
                x = np.array([base[n][k] for n in keep], float)
                y = np.array([other[n][k] for n in keep], float)
                m, lo, hi = boot(y - x)
                flag = "" if lo <= 0 <= hi else "  *"
                report[f"{key[0]}|{key[1]}|{arm}|{k}"] = {"base": float(np.nanmedian(x)),
                                                          "arm": float(np.nanmedian(y)),
                                                          "diff": m, "lo": lo, "hi": hi}
                print(f"  {lab:18}{np.nanmedian(x):>9.2f}{np.nanmedian(y):>11.2f}"
                      f"{f'{m:+.2f} [{lo:+.2f},{hi:+.2f}]':>26}{flag}")

    for key, arms in sorted(idx.items()):
        line = "  ".join(f"{x} {sum(1 for v in arms.get(x, {}).values() if v.get('completed'))}"
                         f"/{len(arms.get(x, {}))}" for x in a.arms)
        print(f"\n  completion {key[0]}/{key[1]}: {line}")

    json.dump({"arms": {x: ARMS[x] for x in a.arms}, "rescue_bio": RESCUE_BIO, "runs": rows,
               "report": report, "provenance": provenance.stamp()}, open(a.out, "w"), indent=1)
    print(f"\n  * marks a difference whose interval excludes zero")
    print(f"written to {a.out}")


if __name__ == "__main__":
    main()
