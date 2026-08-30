"""Whether the meal gate can decide the mechanism it is used to judge, paired per subject.

The two-timescale sweep (`liver_two_timescale.py`) reads a meal trough to peak of 115 min at
every fast fraction from 0.00 to 1.00 on one panel, with a single rung at 120, one sampling step
away. A fraction of 0.00 is the stock liver with the mechanism off, so the gate returns the same
verdict and the same median with the mechanism absent and with the whole of the gain moved onto
the fast delay.

A stable median has two explanations and they call for different conclusions. Either the
mechanism does nothing to the meal, in which case the audit's claim that the meal response is
lost above twice the published rate is wrong on this panel, or it does a great deal per subject
and the median cancels it, in which case the gate is the wrong summary and no verdict read off it
decides anything. This pairs the two ends on the same subjects to say which.

The comparison is the ablation the mechanism is entitled to: identical subject, identical
titrated settings, identical meal and bolus, with the fast pathway the only difference.

    python examples/liver_meal_gate_paired.py
"""
import argparse
import json
import multiprocessing as mp
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
MEASUREMENTS = os.path.join(REPO, "docs", "measurements")

from timsim import provenance

SWEEP = os.path.join(MEASUREMENTS, "liver_two_timescale.json")
OUT = os.path.join(MEASUREMENTS, "liver_meal_gate_paired.json")
KI_SCALE = 10.5
WORKERS = 7
BOOT = 10000
SEED = 20260830


def job(args):
    """One subject at one fast fraction. Module level, because macOS spawns rather than forks."""
    name, fraction, ki_scale = args
    from examples.liver_two_timescale import meal_shape
    r = meal_shape(name, fraction, ki_scale)
    return name, fraction, (r["trough_to_peak_min"] if r else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ki-scale", type=float, default=KI_SCALE)
    ap.add_argument("--workers", type=int, default=WORKERS)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()

    # The panel is read from the sweep rather than reselected, so this is the same 25 subjects the
    # sweep took its medians over and the two measurements cannot disagree about membership. That
    # disagreement is issue 44 and issue 45.
    sweep = json.load(open(SWEEP))
    panel = sweep["meal_panel"]

    jobs = [(n, f, a.ki_scale) for n in panel for f in (0.0, 1.0)]
    with mp.Pool(a.workers) as pool:
        got = {(n, f): v for n, f, v in pool.map(job, jobs)}

    paired = [(n, got[(n, 0.0)], got[(n, 1.0)]) for n in panel]
    unusable = [n for n, x, y in paired if x is None or y is None]
    paired = [(n, x, y) for n, x, y in paired if x is not None and y is not None]

    d = np.array([y - x for _, x, y in paired], dtype=float)
    rng = np.random.default_rng(SEED)
    boot = np.array([np.median(rng.choice(d, size=len(d), replace=True)) for _ in range(BOOT)])
    lo, hi = (float(v) for v in np.percentile(boot, [2.5, 97.5]))
    stock = np.array([x for _, x, _ in paired], dtype=float)
    fast = np.array([y for _, _, y in paired], dtype=float)

    print(f"{len(paired)} subjects paired at {a.ki_scale} times the published rate, "
          f"{len(unusable)} unusable {unusable}\n")
    print(f"{'subject':>12}{'stock':>9}{'fast 1.0':>10}{'diff':>8}")
    for n, x, y in paired:
        print(f"{n:>12}{x:>9.0f}{y:>10.0f}{y - x:>8.0f}")
    print(f"\nmedian trough to peak: stock {np.median(stock):.1f} min, "
          f"fast 1.0 {np.median(fast):.1f} min, against a real 112")
    print(f"paired difference: median {np.median(d):.1f} min, 95 per cent interval "
          f"{lo:.1f} to {hi:.1f}, mean {d.mean():.1f}, range {d.min():.0f} to {d.max():.0f}")
    print(f"{int(np.count_nonzero(d))} of {len(d)} subjects move at all, at a 5 min sampling step; "
          f"{int(np.count_nonzero(np.abs(d) >= 60))} move by an hour or more")
    print(f"between-subject spread of the statistic itself: stock {stock.min():.0f} to "
          f"{stock.max():.0f} min, fast 1.0 {fast.min():.0f} to {fast.max():.0f}")

    rec = {"provenance": provenance.stamp(), "ki_scale": a.ki_scale, "n": len(paired),
           "panel_from": os.path.basename(SWEEP), "unusable": unusable,
           "per_subject": [{"name": n, "stock_min": x, "fast_1.0_min": y, "diff_min": y - x}
                           for n, x, y in paired],
           "median_stock_min": float(np.median(stock)), "median_fast_min": float(np.median(fast)),
           "paired_median_min": float(np.median(d)), "paired_ci95_min": [lo, hi],
           "paired_mean_min": float(d.mean()),
           "subjects_moving": int(np.count_nonzero(d)),
           "subjects_moving_60min_or_more": int(np.count_nonzero(np.abs(d) >= 60)),
           "spread_stock_min": [float(stock.min()), float(stock.max())],
           "spread_fast_min": [float(fast.min()), float(fast.max())]}
    json.dump(rec, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
