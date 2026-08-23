"""Where in the day the missing hyperglycaemia lives: fasting, postprandial, or everywhere.

The gap against DCLP3 decomposes into peaks 11 mg/dL too low and 29 per cent too few excursions,
and both are what a trace displaced downward produces: a meal rise starting from 141 mg/dL peaks
lower and crosses 180 less often than the same rise starting from 155. Whether the displacement
is in fact uniform decides which mechanism is worth building next. A deficit that is flat across
the day, present at 04:00 when nothing has been eaten for hours, is a baseline problem that no
meal machinery can touch. A deficit concentrated in the hours after meals is the opposite.

So this compares mean glucose and time above 180 mg/dL hour by hour, the configured simulator
against the trial's calibration participants, and then collapses the hours into two windows:

    fasting        02:00 to 06:00, five hours after the last scheduled snack and before
                   breakfast, when the only inputs are basal and whatever the night is doing
    postprandial   the three hours following each of the template's main meals, 07:00 to
                   10:00, 12:30 to 15:30 and 18:30 to 21:30

The trial's hours come from its own timestamps the same way `hyperglycaemia_gap.py` derives
them, so the two profiles are computed identically. The trial does not record meal times, which
is why the windows are clock windows rather than meal-relative ones: the simulated template puts
its meals where people conventionally eat, and the trial's participants ate on clocks of their
own that the windows can only approximate. A deficit that moves between the windows survives
that approximation; a few minutes of misalignment does not move a four-hour average.

    python examples/day_profile.py --subjects 84 --workers 13
"""
import argparse
import concurrent.futures as futures
import json
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance, seeds

DAYS = 28
SEED = seeds.BENCH
LAYERS = ("physiology", "behaviour", "sensor", "site")
STEP = 5.0

FASTING = (2.0, 6.0)
POSTPRANDIAL = ((7.0, 10.0), (12.5, 15.5), (18.5, 21.5))


def window_masks(hours):
    """Boolean masks for the fasting and postprandial windows over an hour-of-day array."""
    fasting = (hours >= FASTING[0]) & (hours < FASTING[1])
    post = np.zeros_like(fasting)
    for lo, hi in POSTPRANDIAL:
        post |= (hours >= lo) & (hours < hi)
    return fasting, post


def profile(g, hours):
    """Mean glucose and share above 180 by hour bin, plus the two windows."""
    g = np.asarray(g, float)
    ok = np.isfinite(g)
    g, hours = g[ok], hours[ok]
    by_mean = np.full(24, np.nan)
    by_tar = np.full(24, np.nan)
    hb = hours.astype(int) % 24
    for h in range(24):
        m = hb == h
        if m.sum():
            by_mean[h] = g[m].mean()
            by_tar[h] = 100.0 * np.mean(g[m] > 180)
    fasting, post = window_masks(hours)
    out = {"by_hour_mean": by_mean.tolist(), "by_hour_tar180": by_tar.tolist()}
    for label, m in (("fasting", fasting), ("postprandial", post)):
        out[label] = ({"mean": float(g[m].mean()), "tar180": float(100.0 * np.mean(g[m] > 180)),
                       "n": int(m.sum())} if m.sum() else None)
    return out


def one(name):
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    t0 = time.time()
    prof = titrate.profile_for(name)
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller="control-iq",
                     profile=prof, announcement="some")
    except Exception as exc:
        return {"name": name, "completed": False, "error": str(exc)[:200]}
    g = np.asarray(r.cgm, float)
    # The run starts at midnight and is primed with one step before its loop, so sample i sits
    # at minute (i + 1) * step. `hyperglycaemia_gap.py` records the same convention.
    minutes = (np.arange(len(g)) + 1) * STEP
    hours = (minutes / 60.0) % 24.0
    return {"name": name, "completed": bool(r.completed), "seconds": time.time() - t0,
            **profile(g, hours)}


def trial():
    """The same profile on the trial's calibration participants, pooled."""
    from timsim.validation import dclp3
    sp = dclp3.split()
    cal = set(sp["calibration"])
    gs, hs = [], []
    for pid, segs in dclp3.traces(arm=dclp3.CLOSED_LOOP).items():
        if pid not in cal:
            continue
        for t, g in segs:
            g = np.asarray(g, float)
            hs.append(((np.asarray(t, np.int64) // 3600) % 24)
                      + (np.asarray(t, np.int64) % 3600) / 3600.0)
            gs.append(g)
    return profile(np.concatenate(gs), np.concatenate(hs))


def pool(rows, key):
    """The cohort's pooled window statistics, weighting each subject's window by its samples."""
    vals = [r[key] for r in rows if r.get(key)]
    n = sum(v["n"] for v in vals)
    return {"mean": sum(v["mean"] * v["n"] for v in vals) / n,
            "tar180": sum(v["tar180"] * v["n"] for v in vals) / n, "n": n}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=84)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 8)))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "day_profile.json"))
    a = ap.parse_args()

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    titrated = set(titrate.titrated_subjects())
    subs = [s for s in rec["cohorts"]["dclp3"]["subjects"] if s in titrated][:a.subjects]
    print(f"{len(subs)} subjects on {a.workers} workers", flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as poolx:
        for i, r in enumerate(poolx.map(one, subs), 1):
            rows.append(r)
            if i % 20 == 0:
                print(f"  {i}/{len(subs)}", flush=True)
    done = [r for r in rows if r.get("completed")]
    print(f"completed {len(done)}/{len(rows)}")

    real = trial()
    sim = {"fasting": pool(done, "fasting"), "postprandial": pool(done, "postprandial")}
    sim_mean = np.nanmean([r["by_hour_mean"] for r in done], axis=0)
    sim_tar = np.nanmean([r["by_hour_tar180"] for r in done], axis=0)

    report = {"provenance": provenance.stamp(), "days": DAYS, "layers": list(LAYERS),
              "subjects": len(done), "windows": {"fasting": FASTING,
                                                 "postprandial": list(POSTPRANDIAL)},
              "simulated": {**sim, "by_hour_mean": sim_mean.tolist(),
                            "by_hour_tar180": sim_tar.tolist()},
              "real": real, "runs": rows}
    json.dump(report, open(a.out, "w"), indent=1)

    print(f"\n{'window':14}{'sim mean':>10}{'real mean':>11}{'gap':>7}"
          f"{'sim TAR':>9}{'real TAR':>10}{'gap':>7}")
    for w in ("fasting", "postprandial"):
        s, r = sim[w], real[w]
        print(f"{w:14}{s['mean']:>10.1f}{r['mean']:>11.1f}{s['mean'] - r['mean']:>+7.1f}"
              f"{s['tar180']:>9.1f}{r['tar180']:>10.1f}{s['tar180'] - r['tar180']:>+7.1f}")

    print(f"\nmean glucose by hour, gap (simulated minus real)")
    print("  hour " + "".join(f"{h:>6}" for h in range(0, 24, 2)))
    gaps = sim_mean - np.asarray(real["by_hour_mean"])
    print("  gap  " + "".join(f"{gaps[h]:>+6.1f}" for h in range(0, 24, 2)))
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
