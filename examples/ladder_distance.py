"""How far each layer moves the outcomes from the 2008 model towards the people in a trial.

`bench_matrix.py --benches ladder` runs five rungs, stock then physiology, behaviour, sensor and
site accumulating, with the algorithm held at whatever that trial's participants ran and the
cohort matched to them. This reads that into one table per pairing: what the rung produced, and
how far it sits from the real population, in units of the spread between real people.

Two things are reported beside every rung and neither is decoration.

Completion, because a run stops when glucose leaves the range the model is defined over, the runs
that stop are the ones that went furthest wrong, and every median is therefore conditioned on
survival. The physiology rung is the case that matters: it carries the physiological variation
with no behaviour layer, so nobody eats to treat a low, and it loses a third of the cohort. Its
median describes the subjects that avoided a severe low rather than the cohort.

And the reference each distance is against, because the three are not alike. DCLP3 supplies 67
participants with all six measures. The Commons supplies 77 users with four. CLOSE-IT publishes a
mean and a standard deviation for time in range and no participants at all, so it supports no
spread and no per-person comparison; its column says so rather than inventing one.

    python examples/ladder_distance.py
"""

import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import numpy as np

from examples.bench_tables import references
from timsim import provenance

RUNGS = ["stock", "phys", "behav", "sens", "site"]
LABELS = {"stock": "S2008 bare", "phys": "+physiology", "behav": "+behaviour",
          "sens": "+sensor", "site": "+site"}
# The simulated key, the printed name, and the field the real reference uses for it.
MEASURES = [("tir_cgm", "Time in range 70-180 %", "tir"),
            ("tbr70_cgm", "Time below 70 %", "tbr70"),
            ("tbr54_cgm", "Time below 54 %", "tbr54"),
            ("tar180_cgm", "Time above 180 %", "tar180"),
            ("mean_cgm", "Mean glucose mg/dL", "mean"),
            ("cv_cgm", "Variability CV %", "cv")]


def real_summary(ref):
    """Median and p10-p90 spread per measure, or None where the reference cannot supply it."""
    out = {}
    if isinstance(ref, dict):            # published summaries, no participants
        for key, (mean, sd) in ref.items():
            out[key] = {"median": float(mean), "spread": None, "n": None, "sd": float(sd)}
        return out
    for _, _, refkey in MEASURES:
        vals = [r[refkey] for r in ref if refkey in r and np.isfinite(r[refkey])]
        if not vals:
            continue
        v = np.asarray(vals, float)
        out[refkey] = {"median": float(np.median(v)),
                       "spread": float(np.percentile(v, 90) - np.percentile(v, 10)),
                       "n": len(v), "sd": float(np.std(v, ddof=1))}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default=os.path.join(MEASUREMENTS, "bench_ladder.json"))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "ladder_distance.json"))
    a = ap.parse_args()

    d = json.load(open(a.file))
    if d.get("bench_set") != "ladder":
        raise SystemExit(f"{a.file} records bench_set {d.get('bench_set')!r}, not 'ladder'.")

    idx = {}
    for r in d["runs"]:
        idx.setdefault((r["cohort"], r["controller"]), {}).setdefault(r["bench"], []).append(r)
    refs = references()

    report = {"file": os.path.basename(a.file), "provenance": provenance.stamp(), "pairings": {}}
    for (cohort, controller), arms in sorted(idx.items()):
        real = real_summary(refs.get(cohort, {}))
        print(f"\n{'=' * 92}\n{cohort} under {controller}")
        n_real = next((v["n"] for v in real.values() if v.get("n")), None)
        print(f"reference: {n_real} participants" if n_real else
              "reference: published summaries only, no participants, so no spread")

        print(f"\n  {'rung':13}{'completed':>11}" +
              "".join(f"{LABELS[r][:11]:>13}" for r in []) )
        print(f"  {'':13}{'':>11}" + "".join(f"{m[1][:22]:>24}" for m in MEASURES[:2]))
        rec = {"controller": controller, "reference_n": n_real, "rungs": {}}
        for rung in RUNGS:
            rows = arms.get(rung, [])
            done = [r for r in rows if r.get("completed")]
            entry = {"completed": len(done), "run": len(rows), "measures": {}}
            cells = []
            for key, _, refkey in MEASURES:
                v = [r[key] for r in done if key in r]
                if not v:
                    continue
                med = float(np.median(v))
                rr = real.get(refkey)
                gap = None
                if rr and rr.get("spread"):
                    gap = (med - rr["median"]) / rr["spread"]
                entry["measures"][key] = {"median": med, "gap_spreads": gap,
                                          "real_median": rr["median"] if rr else None}
                cells.append((med, gap))
            rec["rungs"][rung] = entry
            print(f"  {LABELS[rung]:13}{len(done):>6}/{len(rows):<4}" +
                  "".join(f"{m:>12.2f}{('' if g is None else f'{g:+.2f}'):>12}"
                          for m, g in cells[:2]))
        report["pairings"][f"{cohort}|{controller}"] = rec

        # The full table, one row per measure, so every rung is readable across.
        print(f"\n  {'measure':24}" + "".join(f"{LABELS[r]:>14}" for r in RUNGS) + f"{'real':>10}")
        for key, name, refkey in MEASURES:
            rr = real.get(refkey)
            line = f"  {name:24}"
            for rung in RUNGS:
                m = rec["rungs"][rung]["measures"].get(key)
                line += f"{m['median']:>14.2f}" if m else f"{'-':>14}"
            line += f"{rr['median']:>10.2f}" if rr else f"{'-':>10}"
            print(line)
            if rr and rr.get("spread"):
                gaps = "".join(
                    f"{rec['rungs'][r]['measures'][key]['gap_spreads']:>+14.2f}"
                    if rec["rungs"][r]["measures"].get(key) else f"{'-':>14}" for r in RUNGS)
                print(f"  {'  in spreads of real':24}{gaps}")

    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
