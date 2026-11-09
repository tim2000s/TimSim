"""What issue 54 did to the oref0 arm: the same subjects before and after the fix.

Issue 54 was two defects in the AndroidAPS adapters: `OrefController` pruned its insulin ledger
with a 240-minute margin added to the cutoff, dropping every dose more than an hour old, and
`LoopInputs` used the package's insulin curve where AndroidAPS uses oref0's exponential one.
Both were fixed in f0e5e45. This runs each subject twice on one seed under oref0 SMB: once with
both defects put back, which reproduces the code from 11c7ffb to 8d2907f, and once as shipped.
The person, the meals, the noise and the settings are identical, so the difference is the fix.

The settings come from a titration store passed on the command line. They are built the way
`titrate.profile_for` builds them, through `_profile`, without its code fingerprint check: the
fix added a function to `therapy/insulin.py` and touched only the adapters, so the reference
loop that did the titrating behaves as it did when the store was written.

    python examples/issue54_effect.py --store PATH --days 28 --workers 7
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "measurements", "issue54_effect.json")
OLD_MARGIN_MIN = 240.0        # CURVE_TICKS * sample, as the adapter passed it


def _controller(name, profile, arm):
    from timsim.controller import inputs as INP
    from timsim.controller import oref as O
    from timsim.therapy import insulin as INS

    if arm == "before":
        INP.iob_fraction = INS.iob_fraction                 # the package curve

        class Before(O.OrefController):
            def prune(self, minute):
                cutoff = minute - INS.DIA_MIN + OLD_MARGIN_MIN
                self.doses = [d for d in self.doses if d[0] > cutoff]
                self.basal_deviations = [d for d in self.basal_deviations if d[0] > cutoff]

        return Before(name, profile=profile)
    INP.iob_fraction = INS.oref_iob_fraction
    return O.OrefController(name, profile=profile)


def one(job):
    name, scale, basal_scale, arm, days, seed = job
    from timsim import simulate
    from timsim.therapy import titrate

    profile = titrate._profile(name, scale, basal_scale)
    c = _controller(name, profile, arm)
    iob_handed = []
    curve = c.iob_curve

    def watched(minute, *a, **k):
        out = curve(minute, *a, **k)
        iob_handed.append(out[0]["iob"])
        return out

    c.iob_curve = watched
    try:
        r = simulate(name, days=days, seed=seed, controller=c, profile=profile)
    finally:
        c.close()
    out = {"name": name, "arm": arm, "iob_handed_mean": float(np.mean(iob_handed)),
           "insulin_u_per_day": float(r.insulin_units) / days,
           "rescue_events": int(r.rescue_events), "completed": bool(r.completed)}
    for sig in ("cgm", "bg"):
        v = np.asarray(getattr(r, sig), float)
        out[sig] = {"tir": float(100 * np.mean((v >= 70) & (v <= 180))),
                    "tbr70": float(100 * np.mean(v < 70)), "tbr54": float(100 * np.mean(v < 54)),
                    "tar180": float(100 * np.mean(v > 180)), "mean": float(v.mean())}
    return out


def _spread(v):
    v = np.asarray(v, float)
    return {"median": float(np.median(v)), "mean": float(v.mean()),
            "min": float(v.min()), "max": float(v.max())}


def _paired(d, n_boot=10_000, seed=0):
    d = np.asarray(d, float)
    idx = np.random.default_rng(seed).integers(0, len(d), size=(n_boot, len(d)))
    med, mean = np.median(d[idx], axis=1), d[idx].mean(axis=1)
    return {"median": float(np.median(d)),
            "median_ci": [float(np.percentile(med, 2.5)), float(np.percentile(med, 97.5))],
            "mean": float(d.mean()),
            "mean_ci": [float(np.percentile(mean, 2.5)), float(np.percentile(mean, 97.5))]}


def main():
    from timsim import seeds

    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True, help="a titration store written by titrate.save")
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--seed", type=int, default=seeds.BENCH)
    ap.add_argument("--workers", type=int, default=7)
    a = ap.parse_args()

    store = json.load(open(a.store))
    subjects = {n: r for n, r in store["subjects"].items() if r.get("found")}
    jobs = [(n, r["scale"], 1.0 if r.get("basal_scale") is None else r["basal_scale"], arm,
             a.days, a.seed) for n, r in sorted(subjects.items()) for arm in ("before", "after")]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(one, jobs))
    by = {(r["name"], r["arm"]): r for r in rows}
    names = sorted(subjects)
    summary = {"arms": {}, "after_minus_before": {}}
    for arm in ("before", "after"):
        summary["arms"][arm] = {
            "iob_handed_mean": _spread([by[(n, arm)]["iob_handed_mean"] for n in names]),
            "insulin_u_per_day": _spread([by[(n, arm)]["insulin_u_per_day"] for n in names]),
            "rescue_events_total": int(sum(by[(n, arm)]["rescue_events"] for n in names)),
            **{sig: {k: _spread([by[(n, arm)][sig][k] for n in names])
                     for k in ("tir", "tbr70", "tbr54", "tar180", "mean")} for sig in ("cgm", "bg")}}
    for sig in ("cgm", "bg"):
        summary["after_minus_before"][sig] = {
            k: _paired([by[(n, "after")][sig][k] - by[(n, "before")][sig][k] for n in names])
            for k in ("tir", "tbr70", "tbr54", "tar180", "mean")}
    summary["after_minus_before"]["iob_handed_mean"] = _paired(
        [by[(n, "after")]["iob_handed_mean"] - by[(n, "before")]["iob_handed_mean"] for n in names])
    from timsim import provenance
    out = {"provenance": provenance.stamp(), "design": {"store": os.path.abspath(a.store), "store_meta": store.get("meta"),
                      "subjects": names, "days": a.days, "seed": a.seed,
                      "controller": "oref0 SMB, autosens on, TimSim defaults",
                      "before": "issue 54 defects restored: prune cutoff minute - 300 + 240, package curve",
                      "after": "as shipped from f0e5e45"},
           "summary": summary, "rows": rows, "seconds": round(time.time() - t0, 1)}
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {OUT} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
