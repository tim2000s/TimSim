"""Why simulated excursions above 180 mg/dL end sooner than the trial's, decomposed.

Two mechanisms have now changed what reaches the simulated person and left time above 180 mg/dL
where it was: weakening the correction factor by a factor of 2.7, and withholding a third of the
meal boluses. In both the loop absorbed the perturbation. What the excursion statistics already
said, and nobody had read this way, is that this model's excursions end too quickly rather than
starting too rarely, at a median duration of 40 minutes against the trial's 65 and a ninetieth
percentile of 190 against 265, while the peaks nearly match.

An excursion's duration is set by three things, and only one of them is the loop. How high it
climbs, since a peak nearer the threshold is above it for less time whatever happens next. How
fast glucose falls once it turns. And whether anything holds it up. This separates them.

The arms are the same subjects under three conditions:

    closed       the configuration as it ships, meals announced as the behaviour layer decides
    open         scheduled basal only, no modulation and no correction, meals unannounced
    no_fall      as `closed`, but the descent is measured from the peak rather than the crossing

`open` is the one that matters. It removes the loop entirely, so what remains is the model's own
disposal of a glucose load: insulin-independent utilisation, renal clearance above the threshold,
and whatever basal is running. If excursions still end quickly with nothing correcting them, the
loop is not the reason and the model clears glucose faster than a person does. If they persist,
the loop is the reason and its aggressiveness is the thing to compare against the real device.

    python examples/excursion_recovery.py --subjects 40 --workers 13
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
THRESHOLD = 180.0

# (label, controller, announcement)
ARMS = (("closed", "control-iq", "some"),
        ("open", "basal-bolus", "never"))


def excursions(g, step=STEP, threshold=THRESHOLD):
    """Every run above the threshold, with what it did on the way up and on the way down.

    Duration is the time at or above the threshold, which is what the trial comparison counts.
    The descent rate is measured from the peak to the crossing below, in mg/dL per hour, and is
    undefined for an excursion still running when the trace ends, which is dropped rather than
    counted as a fast recovery.
    """
    g = np.asarray(g, float)
    above = g >= threshold
    out, start = [], None
    for i, a in enumerate(np.append(above, False)):
        if a and start is None:
            start = i
        elif not a and start is not None:
            if i >= len(g):                      # still above when the trace ended
                start = None
                continue
            seg = g[start:i]
            k = int(np.argmax(seg))
            fall_min = (len(seg) - 1 - k) * step
            peak = float(seg.max())
            out.append({"duration_min": (i - start) * step, "peak": peak,
                        "rise_min": k * step,
                        "fall_min": fall_min,
                        "fall_rate": ((peak - g[i]) / (fall_min / 60.0)
                                      if fall_min > 0 else np.nan)})
            start = None
    return out


def one(job):
    name, arm, controller, announcement = job
    from timsim.simulation.run import simulate
    from timsim.therapy import titrate
    t0 = time.time()
    prof = titrate.profile_for(name)
    try:
        r = simulate(name, days=DAYS, seed=SEED, layers=LAYERS, controller=controller,
                     profile=prof, announcement=announcement)
    except Exception as exc:
        return {"name": name, "arm": arm, "completed": False, "error": str(exc)[:200],
                "seconds": time.time() - t0}
    cgm = np.asarray(r.cgm, float)
    days = max(len(cgm) * STEP / 1440.0, 1e-9)
    ex = excursions(cgm)
    return {"name": name, "arm": arm, "completed": bool(r.completed),
            "seconds": time.time() - t0, "days": float(days),
            "insulin_per_day": float(getattr(r, "insulin_units", float("nan")) / days),
            "tar180": float(100.0 * np.mean(cgm > THRESHOLD)),
            "excursions": ex}


def summarise(rows, label):
    """Pooled over subjects, since an excursion belongs to the cohort rather than to a person."""
    ex = [e for r in rows for e in r["excursions"]]
    if not ex:
        return None
    dur = np.asarray([e["duration_min"] for e in ex], float)
    peak = np.asarray([e["peak"] for e in ex], float)
    fall = np.asarray([e["fall_rate"] for e in ex], float)
    fall = fall[np.isfinite(fall)]
    days = sum(r["days"] for r in rows)
    return {"arm": label, "subjects": len(rows), "n_excursions": len(ex),
            "per_day": len(ex) / days,
            "median_dur": float(np.median(dur)), "p90_dur": float(np.percentile(dur, 90)),
            "median_peak": float(np.median(peak)), "p90_peak": float(np.percentile(peak, 90)),
            "median_rise_min": float(np.median([e["rise_min"] for e in ex])),
            "median_fall_min": float(np.median([e["fall_min"] for e in ex])),
            "median_fall_rate": float(np.median(fall)),
            "p10_fall_rate": float(np.percentile(fall, 10)),
            "tar180": float(np.median([r["tar180"] for r in rows])),
            "insulin_per_day": float(np.median([r["insulin_per_day"] for r in rows]))}


def real_reference():
    """The same statistics on the trial's closed-loop arm, or None when the data is absent."""
    try:
        from timsim.validation import dclp3
        sp = dclp3.split()
        cal = set(sp["calibration"])
        ex, days = [], 0.0
        for pid, segs in dclp3.traces(arm=dclp3.CLOSED_LOOP).items():
            if pid not in cal:
                continue
            for s in segs:
                g = np.asarray(s, float)[1]
                g = g[np.isfinite(g)]
                if len(g) < 288:
                    continue
                ex += excursions(g)
                days += len(g) * STEP / 1440.0
        if not ex:
            return None
        dur = np.asarray([e["duration_min"] for e in ex], float)
        peak = np.asarray([e["peak"] for e in ex], float)
        fall = np.asarray([e["fall_rate"] for e in ex], float)
        fall = fall[np.isfinite(fall)]
        return {"arm": "DCLP3", "subjects": None, "n_excursions": len(ex),
                "per_day": len(ex) / days,
                "median_dur": float(np.median(dur)), "p90_dur": float(np.percentile(dur, 90)),
                "median_peak": float(np.median(peak)),
                "p90_peak": float(np.percentile(peak, 90)),
                "median_rise_min": float(np.median([e["rise_min"] for e in ex])),
                "median_fall_min": float(np.median([e["fall_min"] for e in ex])),
                "median_fall_rate": float(np.median(fall)),
                "p10_fall_rate": float(np.percentile(fall, 10)),
                "tar180": None, "insulin_per_day": None}
    except Exception as exc:
        print(f"(DCLP3 reference unavailable: {exc})")
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subjects", type=int, default=40)
    ap.add_argument("--workers", type=int, default=int(os.environ.get("WORKERS", 8)))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "excursion_recovery.json"))
    a = ap.parse_args()

    from timsim.therapy import titrate
    rec = json.load(open(os.path.join(MEASUREMENTS, "cohorts.json")))
    titrated = set(titrate.titrated_subjects())
    subs = [s for s in rec["cohorts"]["dclp3"]["subjects"] if s in titrated][:a.subjects]
    jobs = [(n, lab, ctl, ann) for lab, ctl, ann in ARMS for n in subs]
    print(f"{len(subs)} subjects x {len(ARMS)} arms = {len(jobs)} runs on {a.workers} workers",
          flush=True)

    rows = []
    with futures.ProcessPoolExecutor(max_workers=a.workers) as pool:
        for i, r in enumerate(pool.map(one, jobs), 1):
            rows.append(r)
            if i % 20 == 0:
                print(f"  {i}/{len(jobs)}", flush=True)

    table = []
    for lab, _, _ in ARMS:
        done = [r for r in rows if r["arm"] == lab and r.get("completed")]
        s = summarise(done, lab)
        if s:
            table.append(s)
    real = real_reference()
    if real:
        table.append(real)

    json.dump({"provenance": provenance.stamp(), "days": DAYS, "layers": list(LAYERS),
               "threshold": THRESHOLD, "summary": table,
               "runs": [{k: v for k, v in r.items() if k != "excursions"} for r in rows]},
              open(a.out, "w"), indent=1)

    print(f"\n{'arm':10}{'n':>7}{'/day':>7}{'dur med':>9}{'dur p90':>9}{'peak med':>10}"
          f"{'peak p90':>10}{'rise min':>10}{'fall min':>10}{'fall/h':>9}{'U/day':>8}")
    for s in table:
        ins = f"{s['insulin_per_day']:.1f}" if s["insulin_per_day"] is not None else "-"
        print(f"{s['arm']:10}{s['n_excursions']:>7}{s['per_day']:>7.2f}{s['median_dur']:>9.0f}"
              f"{s['p90_dur']:>9.0f}{s['median_peak']:>10.0f}{s['p90_peak']:>10.0f}"
              f"{s['median_rise_min']:>10.0f}{s['median_fall_min']:>10.0f}"
              f"{s['median_fall_rate']:>9.1f}{ins:>8}")
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
