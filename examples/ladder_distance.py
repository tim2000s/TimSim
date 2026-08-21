"""How far each layer moves the outcomes from the 2008 model towards the people in a trial.

`bench_matrix.py --benches ladder` runs five rungs, stock then physiology, behaviour, sensor and
site accumulating, with the algorithm held at whatever that trial's participants ran and the
cohort matched to them. This reads that into one table per pairing: what the rung produced, and
how far it sits from the real population, in units of the spread between real people.

A gap is reported as distinguishable only when the real median falls outside the simulated
cohort's 95 per cent interval, which is issue 16 in `docs/ISSUES.md`. Expressing a difference in
units of the real between-person spread says how large it is and not whether it survives the
cohort having been drawn differently, and on these runs several differences quoted that way are
inside the interval. The spread column is kept beside the verdict as a magnitude, never as the
evidence.

Two more things are reported beside every rung and neither is decoration.

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

from examples.bench_tables import BOOTSTRAP, _ci, references
from timsim import provenance, seeds

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
                       "p10": float(np.percentile(v, 10)),
                       "p90": float(np.percentile(v, 90)),
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
    rng = np.random.default_rng(seeds.BENCH)

    report = {"file": os.path.basename(a.file), "provenance": provenance.stamp(),
              "test": "the real median falls outside the simulated cohort's 95% interval",
              "bootstrap": BOOTSTRAP, "pairings": {}}

    for (cohort, controller), arms in sorted(idx.items()):
        real = real_summary(refs.get(cohort, {}))
        n_real = next((v["n"] for v in real.values() if v.get("n")), None)
        print(f"\n{'=' * 96}\n{cohort} under {controller}")
        print(f"reference: {n_real} participants" if n_real else
              "reference: published summaries only, no participants")

        rec = {"controller": controller, "reference_n": n_real, "rungs": {}}
        for rung in RUNGS:
            rows = arms.get(rung, [])
            done = [r for r in rows if r.get("completed")]
            entry = {"completed": len(done), "run": len(rows), "measures": {}}
            for key, _, refkey in MEASURES:
                v = [r[key] for r in done if key in r and np.isfinite(r[key])]
                if not v:
                    continue
                med = float(np.median(v))
                lo, hi = _ci(v, rng)
                # Two different things, and reporting only the first is what the note of
                # 9 August 2026 warns against. The interval is uncertainty in the centre and
                # decides the verdict. p10 to p90 is the spread across subjects, and a
                # population can sit on the real median while being far narrower than the real
                # cohort, which makes a bench look more decisive than it is.
                p10, p90 = float(np.percentile(v, 10)), float(np.percentile(v, 90))
                rr = real.get(refkey)
                cell = {"median": med, "interval": [lo, hi], "n": len(v),
                        "p10": p10, "p90": p90, "spread": p90 - p10}
                if rr:
                    cell["real_median"] = rr["median"]
                    cell["differs"] = not (lo <= rr["median"] <= hi)
                    if rr.get("spread"):
                        cell["gap_spreads"] = (med - rr["median"]) / rr["spread"]
                        cell["real_spread"] = rr["spread"]
                        cell["spread_ratio"] = (p90 - p10) / rr["spread"] if rr["spread"] else None
                entry["measures"][key] = cell
            rec["rungs"][rung] = entry

        print(f"\n  {'':26}" + "".join(f"{LABELS[r]:>14}" for r in RUNGS) + f"{'real':>10}")
        print(f"  {'completed':26}" +
              "".join(f"{rec['rungs'][r]['completed']:>9}/{rec['rungs'][r]['run']:<4}"
                      for r in RUNGS))

        for key, name, refkey in MEASURES:
            rr = real.get(refkey)
            meds, verds, gaps, spans, ratios = [], [], [], [], []
            for rung in RUNGS:
                c = rec["rungs"][rung]["measures"].get(key)
                if not c:
                    for lst in (meds, verds, gaps, spans, ratios):
                        lst.append(f"{'-':>14}")
                    continue
                meds.append(f"{c['median']:>14.2f}")
                spans.append(f"{c['p10']:>7.1f}-{c['p90']:<6.1f}")
                ratios.append(f"{c['spread_ratio']:>14.2f}" if c.get("spread_ratio")
                              else f"{'-':>14}")
                if "differs" in c:
                    verds.append(f"{('differs' if c['differs'] else 'same'):>14}")
                else:
                    verds.append(f"{'no test':>14}")
                gaps.append(f"{c['gap_spreads']:>+14.2f}" if "gap_spreads" in c else f"{'-':>14}")
            print(f"\n  {name:26}" + "".join(meds) +
                  (f"{rr['median']:>10.2f}" if rr else f"{'-':>10}"))
            print(f"  {'  p10 to p90 of subjects':26}" + "".join(spans) +
                  (f"{rr['p10']:>5.1f}-{rr['p90']:<5.1f}" if rr and rr.get("p10") is not None
                   else ""))
            print(f"  {'  median against real':26}" + "".join(verds))
            if rr and rr.get("spread"):
                print(f"  {'  spread against real':26}" + "".join(ratios))
                print(f"  {'  magnitude, spreads':26}" + "".join(gaps))

        # The headline: how many measures a rung cannot be told apart from the trial on.
        print(f"\n  {'indistinguishable from real':26}", end="")
        for rung in RUNGS:
            ms = [c for c in rec["rungs"][rung]["measures"].values() if "differs" in c]
            same = sum(1 for c in ms if not c["differs"])
            rec["rungs"][rung]["indistinguishable"] = same
            rec["rungs"][rung]["tested"] = len(ms)
            print(f"{(f'{same} of {len(ms)}' if ms else '-'):>14}", end="")
        print()
        report["pairings"][f"{cohort}|{controller}"] = rec

    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\n\nwrote {a.out}")


if __name__ == "__main__":
    main()
