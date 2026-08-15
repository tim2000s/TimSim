"""Every simulated number in the validation paper, produced in one run.

Four bench arms and two extra announcement conditions, on the titrated cohort at one seed.
The algorithm is held fixed inside each pair and only the bench varies, so a difference
between the two columns of a table belongs to the bench.

Outcomes are reported on the sensor reading, because that is what the real records this is
compared against contain. The underlying glucose is carried alongside for the safety figures,
and the two are never mixed in one comparison.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")
import json
import time
import numpy as np
from concurrent.futures import ProcessPoolExecutor


DAYS, SEED = 28, 11
LAYERS = ("physiology", "behaviour", "sensor", "site")
OUT = os.path.join(MEASUREMENTS, "paper_tables.json")

# (arm key, controller, layers, announcement). The bare arm has no behaviour layer, so its
# announcement setting is inert and is recorded only to keep the job description uniform.
ARMS = [
    ("trend_bare",    "trend", (),     "some"),
    ("trend_layered", "trend", LAYERS, "some"),
    ("oref_bare",     "oref",  (),     "some"),
    ("oref_layered",  "oref",  LAYERS, "some"),
    ("oref_always",   "oref",  LAYERS, "always"),
    ("oref_never",    "oref",  LAYERS, "never"),
]


def one(job):
    arm, name, controller, layers, announcement = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    prof = titrate.profile_for(name)
    ctrl, t0 = controller, time.time()
    try:
        if controller == "oref":
            from timsim.controller import oref
            ctrl = oref.OrefController(name, profile=prof)
        r = simulate(name, days=DAYS, seed=SEED, layers=layers, controller=ctrl,
                     profile=prof, announcement=announcement)
    except Exception as exc:
        return {"arm": arm, "name": name, "completed": False, "error": str(exc)[:200],
                "seconds": time.time() - t0}
    finally:
        if hasattr(ctrl, "close"):
            ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    bg = np.asarray(r.bg, dtype=float)
    days = max(len(bg) * 5.0 / 1440.0, 1e-9)
    out = {"arm": arm, "name": name, "completed": bool(r.completed), "days": float(days),
           "seconds": time.time() - t0,
           "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days),
           "rescue_per_30d": float(30.0 * getattr(r, "rescue_events", 0) / days),
           "final_bg": float(bg[-1]), "lowest_bg": float(np.min(bg)),
           "highest_bg": float(np.max(bg))}
    for sig, lab in ((cgm, "cgm"), (bg, "bg")):
        out[f"tir_{lab}"] = float(100.0 * np.mean((sig >= 70) & (sig <= 180)))
        out[f"tbr70_{lab}"] = float(100.0 * np.mean(sig < 70))
        out[f"tbr54_{lab}"] = float(100.0 * np.mean(sig < 54))
        out[f"tar180_{lab}"] = float(100.0 * np.mean(sig > 180))
        out[f"mean_{lab}"] = float(np.mean(sig))
        out[f"cv_{lab}"] = float(100.0 * np.std(sig, ddof=1) / np.mean(sig))
    return out


def main():
    from timsim.therapy import titrate
    subjects = sorted(titrate.titrated_subjects())
    jobs = [(arm, n, c, l, a) for arm, c, l, a in ARMS for n in subjects]
    print(f"{len(subjects)} titrated subjects, {len(ARMS)} arms, {len(jobs)} runs", flush=True)

    rows, t0 = [], time.time()
    with ProcessPoolExecutor(max_workers=10) as ex:
        for i, row in enumerate(ex.map(one, jobs), 1):
            rows.append(row)
            if i % 10 == 0 or i == len(jobs):
                print(f"  {i}/{len(jobs)} done, {(time.time()-t0)/60:.1f} min elapsed",
                      flush=True)
            if row.get("error"):
                print(f"  ! {row['arm']} {row['name']}: {row['error'][:110]}", flush=True)
    json.dump(rows, open(OUT, "w"), indent=1)
    print(f"\nwrote {OUT} after {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
