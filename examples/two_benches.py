"""oref0 SMB against the stock UVA/Padova S2008 patient and against the full TimSim stack.

The algorithm is identical in both arms, compiled from its own source and driven across a node
pipe, so every difference belongs to the bench. Subjects and seed are held, and results are
paired over the subjects completing both arms.

Outcomes are reported on the sensor reading and on the underlying glucose separately. The two
benches do not present the same signal: the stock patient has no sensor layer, so the algorithm
sees the underlying glucose there and a noisy one here, which is part of what is being compared
rather than a confound to remove.
"""
import json
import os
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from timsim.simulation.run import simulate
from timsim.analysis import signatures
from timsim.therapy import titrate

# Only subjects whose settings have been through `examples/titrate_cohort.py`. An algorithm
# scored on settings nobody titrated is being judged partly on the settings, and the effect is
# not small: the physiological correction factor doubles oref0's time below 70 mg/dL against
# the one real users run.
SUBJECTS = list(titrate.titrated_subjects()) or [f"adult#{i:03d}" for i in range(1, 21)]
DAYS, SEED = 28, 11
ARMS = {"padova": (), "timsim": ("physiology", "behaviour", "sensor", "site")}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "measurements", "two_benches.json")


def one(job):
    name, arm = job
    from timsim.controller import oref
    prof = titrate.profile_for(name)          # raises if this subject was never titrated
    ctrl = oref.OrefController(name, profile=prof)
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=ARMS[arm], controller=ctrl,
                     profile=prof)
    except Exception as e:
        return {"name": name, "arm": arm, "completed": False, "error": str(e)[:140]}
    finally:
        ctrl.close()

    cgm = np.asarray(r.cgm, dtype=float)
    bg = np.asarray(r.bg, dtype=float)
    below = cgm < 70
    v = {k: float(fn(signatures.from_result(r))) for k, _, fn in signatures.SIGS}
    v["insulin_cv"] = float(signatures.insulin_weekly_cv(
        getattr(r, "insulin_series", []), getattr(r, "sample_time", 5.0)))
    days = max(len(bg) * 5.0 / 1440.0, 1e-9)
    out = {"name": name, "arm": arm, "completed": bool(r.completed), "days": days,
           "values": v, "episodes_per_30d": float(30.0 * np.sum(below[1:] & ~below[:-1]) / days),
           "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days),
           "rescue_per_30d": float(30.0 * getattr(r, "rescue_events", 0) / days),
           "lowest_bg": float(np.min(bg))}
    for sig, label in ((cgm, "cgm"), (bg, "bg")):
        out[f"tir_{label}"] = float(100.0 * np.mean((sig >= 70) & (sig <= 180)))
        out[f"tbr70_{label}"] = float(100.0 * np.mean(sig < 70))
        out[f"tbr54_{label}"] = float(100.0 * np.mean(sig < 54))
        out[f"tar180_{label}"] = float(100.0 * np.mean(sig > 180))
        out[f"mean_{label}"] = float(np.mean(sig))
    return out


if __name__ == "__main__":
    jobs = [(n, a) for a in ARMS for n in SUBJECTS]
    with ProcessPoolExecutor(max_workers=6) as ex:
        rows = list(ex.map(one, jobs))
    json.dump(rows, open(OUT, "w"), indent=1)
    idx = {(r["arm"], r["name"]): r for r in rows}
    keep = sorted({n for _, n in idx if idx.get(("padova", n), {}).get("completed")
                   and idx.get(("timsim", n), {}).get("completed")})
    for a in ARMS:
        sub = [r for r in rows if r["arm"] == a]
        print(f"{a:>8} {sum(r.get('completed', False) for r in sub)}/{len(sub)} completed")
    print(f"paired over {len(keep)} subjects completing both arms\n")

    def paired(get, label):
        d = np.asarray([get(idx[("timsim", n)]) - get(idx[("padova", n)]) for n in keep], float)
        d = d[np.isfinite(d)]
        m = d.mean() if len(d) > 1 else float("nan")
        h = 1.96 * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
        pv = np.median([get(idx[("padova", n)]) for n in keep])
        tv = np.median([get(idx[("timsim", n)]) for n in keep])
        print(f"| {label} | {pv:.2f} | {tv:.2f} | {m:+.2f} +/- {h:.2f} |")

    print("| Measure | Padova S2008 | Person in the loop | Paired difference, 95% |")
    print("|---|---|---|---|")
    for k, lab in (("tir_cgm", "Time in range, %"), ("tar180_cgm", "Time above 180, %"),
                   ("tbr70_cgm", "Time below 70, %"), ("tbr54_cgm", "Time below 54, %"),
                   ("mean_cgm", "Mean sensor glucose, mg/dL"),
                   ("lowest_bg", "Lowest true glucose, mg/dL"),
                   ("insulin_per_day", "Insulin, U/day"),
                   ("episodes_per_30d", "Hypo episodes per 30 days"),
                   ("rescue_per_30d", "Rescue helpings per 30 days")):
        paired(lambda r, k=k: r[k], lab)

    print("\n| Signature | Reference | Padova S2008 | Person in the loop | Paired difference |")
    print("|---|---|---|---|---|")
    for k, lab, _ in signatures.SIGS:
        b = signatures.REAL_RANGE.get(k)
        ref = f"{b[0]:g} to {b[1]:g}" if b else ""
        d = np.asarray([idx[("timsim", n)]["values"][k] - idx[("padova", n)]["values"][k]
                        for n in keep], float)
        d = d[np.isfinite(d)]
        pv = np.nanmedian([idx[("padova", n)]["values"][k] for n in keep])
        tv = np.nanmedian([idx[("timsim", n)]["values"][k] for n in keep])
        m = d.mean() if len(d) > 1 else float("nan")
        h = 1.96 * d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else float("nan")
        mark = lambda v: " inside" if b and b[0] <= v <= b[1] else ""
        print(f"| {lab} | {ref} | {pv:.2f}{mark(pv)} | {tv:.2f}{mark(tv)} | {m:+.3g} +/- {h:.2g} |")
