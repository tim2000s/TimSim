"""How much of the variation between real people does the population carry?

A benchmark run on a virtual population answers a question about the average of that
population, and how far that answer transfers depends on whether its members differ from one
another as much as real people do. A population narrower than the reference makes competing
algorithms look more alike than they are.

The quantity is the standard deviation across subjects of each outcome, against the standard
deviation across participants of the same outcome in the real population, both computed on the
sensor trace because comparisons against trial data go on `cgm`. A ratio below one is a
population that under-represents human variation and above one is the reverse, and this package
does both at once: it is too narrow on where glucose sits and too wide on hypoglycaemia.

These figures were quoted in `docs/FIDELITY.md` before this script existed, having been computed
by hand, which is why they are recomputed here rather than read from anywhere.

Two things the ratio does not separate. Run-to-run variation is inside the simulated standard
deviation, because each subject contributes one month and a different month would move it, so
the simulated side is inflated by an amount only seed replication can measure. And subjects that
stopped early are excluded by default, which matters most on hypoglycaemia, so the comparison is
also reported without that restriction.

Reads the bench matrix already on disk and simulates nothing.

    python examples/spread_ratio.py
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

import json
import numpy as np

from timsim import provenance, seeds

OUT = os.path.join(MEASUREMENTS, "spread_ratio.json")
ARM = "layered_some"
BOOTSTRAP = 5000

MEASURES = [("tir_cgm", "Time in range 70-180, %", "tir"),
            ("tbr70_cgm", "Time below 70, %", "tbr70"),
            ("tbr54_cgm", "Time below 54, %", "tbr54"),
            ("tar180_cgm", "Time above 180, %", "tar180"),
            ("mean_cgm", "Mean sensor glucose, mg/dL", "mean"),
            ("cv_cgm", "Variability, CV %", "cv")]


def _ratio_interval(sim, real, rng, reps=BOOTSTRAP):
    """Percentile interval on the ratio of standard deviations, resampling both sides."""
    si = rng.integers(0, len(sim), size=(reps, len(sim)))
    ri = rng.integers(0, len(real), size=(reps, len(real)))
    draws = sim[si].std(axis=1, ddof=1) / real[ri].std(axis=1, ddof=1)
    return float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def main():
    from examples.bench_tables import references, load

    d, idx = load()
    ref = references()
    rng = np.random.default_rng(seeds.BENCH)

    out = {"population": d["population"], "arm": ARM, "days": d["days"],
           "provenance": provenance.stamp(), "pairings": {}}

    for (cohort, controller), arms in sorted(idx.items()):
        real_rows = ref.get(cohort)
        if not isinstance(real_rows, list) or not real_rows:
            continue
        by_name = arms.get(ARM, {})
        block = {}
        for require_complete in (True, False):
            rows = [r for r in by_name.values()
                    if r.get("completed") or not require_complete]
            if len(rows) < 20:
                continue
            key = "completers" if require_complete else "as_observed"
            block[key] = {"n": len(rows), "measures": {}}
            for field, name, refkey in MEASURES:
                sim = np.array([r[field] for r in rows if np.isfinite(r[field])], float)
                real = np.array([r[refkey] for r in real_rows], float)
                lo, hi = _ratio_interval(sim, real, rng)
                block[key]["measures"][refkey] = {
                    "label": name,
                    "simulated_sd": float(sim.std(ddof=1)),
                    "real_sd": float(real.std(ddof=1)),
                    "ratio": float(sim.std(ddof=1) / real.std(ddof=1)),
                    "ratio_interval": [lo, hi],
                    "real_n": int(len(real)),
                }
        if block:
            out["pairings"][f"{cohort}|{controller}"] = block

    json.dump(out, open(OUT, "w"), indent=1)
    print(f"wrote {OUT}\n")

    for pairing, block in out["pairings"].items():
        print(f"=== {pairing}")
        for key, side in block.items():
            print(f"  {key}, {side['n']} subjects")
            for refkey, row in side["measures"].items():
                lo, hi = row["ratio_interval"]
                print(f"    {row['label']:28} simulated {row['simulated_sd']:7.2f}  "
                      f"real {row['real_sd']:7.2f}  ratio {row['ratio']:5.2f} "
                      f"[{lo:.2f},{hi:.2f}]")
        print()


if __name__ == "__main__":
    main()
