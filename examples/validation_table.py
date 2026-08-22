"""What stock S2008 does, what each layer changes, and how far each sits from real people.

One table per pairing, where a pairing is a real population and the algorithm those people
actually ran. Arms are stock S2008 on the settings its own physiology implies, the same body on
titrated settings, then each layer alone, then all four together, then the announced and
unannounced variants of the two arms that carry meal announcement.

Every cell carries a median, a mean with its standard deviation, and the range across subjects.
All three, because the trials report a mean and this package reports a median, and quoting one
against the other is a comparison computed differently on the two sides. The range is neither: it
says how varied the simulated population is, and a population can sit on the real median while
being far narrower than the cohort it stands for.

Completion is reported for every arm with the terminations grouped by direction, because a run
stops when glucose leaves the range the model is defined over, the runs that stop are the ones
that went furthest wrong, and every median above is therefore conditioned on survival.

A difference from the real population is called only when the real median falls outside the
simulated cohort's 95 per cent interval, which is issue 16. A gap in units of the real spread
says how large it is, not whether it survives the cohort having been drawn differently.

    python examples/validation_table.py
"""

import argparse
import collections
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import numpy as np

from examples.bench_tables import BOOTSTRAP, _ci, references
from timsim import provenance, seeds

ARMS = [("stock", "stock S2008"), ("base", "titrated settings"),
        ("physiology", "+physiology only"), ("behaviour", "+behaviour only"),
        ("sensor", "+sensor only"), ("site", "+site only"),
        ("all_layers", "all four layers"),
        ("behaviour_announced", "behaviour, announced"),
        ("behaviour_unannounced", "behaviour, unannounced"),
        ("all_layers_announced", "all four, announced"),
        ("all_layers_unannounced", "all four, unannounced")]

MEASURES = [("tir_cgm", "Time in range 70-180 %", "tir"),
            ("tbr70_cgm", "Time below 70 %", "tbr70"),
            ("tbr54_cgm", "Time below 54 %", "tbr54"),
            ("tar180_cgm", "Time above 180 %", "tar180"),
            ("mean_cgm", "Mean glucose mg/dL", "mean"),
            ("cv_cgm", "Variability CV %", "cv")]


def real_stats(ref):
    """Median, mean and spread per measure, or the published summary where that is all there is."""
    out = {}
    if isinstance(ref, dict):
        for key, (mean, sd) in ref.items():
            out[key] = {"median": None, "mean": float(mean), "sd": float(sd),
                        "p10": None, "p90": None, "n": None, "summary_only": True}
        return out
    for _, _, refkey in MEASURES:
        v = np.asarray([r[refkey] for r in ref
                        if refkey in r and np.isfinite(r[refkey])], float)
        if not len(v):
            continue
        out[refkey] = {"median": float(np.median(v)), "mean": float(np.mean(v)),
                       "sd": float(np.std(v, ddof=1)),
                       "p10": float(np.percentile(v, 10)), "p90": float(np.percentile(v, 90)),
                       "n": len(v), "summary_only": False}
    return out


def terminations(rows):
    """Why the runs that did not finish stopped, grouped."""
    out = collections.Counter()
    for r in rows:
        if r.get("completed"):
            continue
        t = r.get("termination") or {}
        out[t.get("direction") or ("error" if r.get("error") else "unknown")] += 1
    return dict(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", default=os.path.join(MEASUREMENTS, "validation.json"))
    ap.add_argument("--out", default=os.path.join(MEASUREMENTS, "validation_table.json"))
    a = ap.parse_args()

    d = json.load(open(a.file))
    # `combined` is the four arms `docs/BASELINE.md` reports and is a subset of `validation`.
    # Arms absent from the file are skipped below rather than reported empty, so a combined file
    # yields a four-arm table and a validation file the full eleven. Any other set is refused,
    # because reading the baseline or matrix sets here would silently drop most of their rows.
    if d.get("bench_set") not in ("validation", "combined"):
        raise SystemExit(f"{a.file} records bench_set {d.get('bench_set')!r}, "
                         "which is neither 'validation' nor 'combined'.")

    idx = {}
    for r in d["runs"]:
        idx.setdefault((r["cohort"], r["controller"]), {}).setdefault(r["bench"], []).append(r)
    refs = references()
    rng = np.random.default_rng(seeds.BENCH)

    report = {"file": os.path.basename(a.file), "provenance": provenance.stamp(),
              "verdict": "the real median falls outside the simulated 95% interval",
              "pairings": {}}

    for (cohort, controller), arms in sorted(idx.items()):
        real = real_stats(refs.get(cohort, {}))
        print(f"\n{'=' * 100}\n{cohort} under {controller}")
        n_real = next((v["n"] for v in real.values() if v.get("n")), None)
        print("real reference: " + (f"{n_real} participants" if n_real else
              "published summary only, no participants"))
        rec = {"controller": controller, "reference_n": n_real, "arms": {}}

        for key, name, refkey in MEASURES:
            rr = real.get(refkey)
            print(f"\n  {name}")
            print(f"    {'arm':26}{'median':>9}{'mean':>9}{'sd':>7}{'range':>16}"
                  f"{'completed':>11}{'vs real':>10}")
            for arm, label in ARMS:
                rows = arms.get(arm, [])
                done = [r for r in rows if r.get("completed")]
                v = np.asarray([r[key] for r in done if key in r and np.isfinite(r[key])], float)
                if not len(v):
                    continue
                lo, hi = _ci(v, rng)
                verdict = "-"
                if rr and rr.get("median") is not None:
                    verdict = "differs" if not (lo <= rr["median"] <= hi) else "same"
                cell = {"median": float(np.median(v)), "mean": float(np.mean(v)),
                        "sd": float(np.std(v, ddof=1)), "min": float(v.min()),
                        "max": float(v.max()), "interval": [lo, hi],
                        "completed": len(done), "run": len(rows),
                        "terminations": terminations(rows), "verdict": verdict}
                rec["arms"].setdefault(arm, {})[key] = cell
                print(f"    {label:26}{cell['median']:>9.2f}{cell['mean']:>9.2f}"
                      f"{cell['sd']:>7.2f}{f'{v.min():.1f}-{v.max():.1f}':>16}"
                      f"{len(done):>7}/{len(rows):<3}{verdict:>10}")
            if rr:
                rm = f"{rr['median']:.2f}" if rr["median"] is not None else "-"
                span = ("n/a" if rr["p10"] is None
                        else f"{rr['p10']:.1f}-{rr['p90']:.1f}")
                print(f"    {'REAL':26}{rm:>9}{rr['mean']:>9.2f}{rr['sd']:>7.2f}"
                      f"{span:>16}{str(rr['n'] or '-'):>11}")

        print(f"\n  terminations, by arm")
        print(f"    {'arm':26}{'completed':>11}   reasons")
        for arm, label in ARMS:
            rows = arms.get(arm, [])
            if not rows:
                continue
            done = sum(1 for r in rows if r.get("completed"))
            t = terminations(rows)
            rec["arms"].setdefault(arm, {})["completion"] = {
                "completed": done, "run": len(rows), "terminations": t}
            reasons = ", ".join(f"{k} {v}" for k, v in sorted(t.items())) or "none"
            print(f"    {label:26}{done:>7}/{len(rows):<3}   {reasons}")
        report["pairings"][f"{cohort}|{controller}"] = rec

    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
