"""Run the shipped oref0 SMB algorithm across a cohort and compare it with the field.

This is the second algorithm the package has been driven with, and it is the one that
matters for validation. Boost is a system this project has a hand in, so a simulator that
reproduces Boost's behaviour has demonstrated less than it appears to. oref0 was written
elsewhere, has the longest published record of any open-source loop, and knows nothing
about this simulator.

What the run can and cannot answer is worth stating before the numbers. It can say whether
a population that was matched to DCLP3 on age produces plausible outcomes under an algorithm
it was not tuned against. It cannot say that oref0 would produce these outcomes in a real
cohort, because the comparison groups differ in more than the algorithm: DCLP3 ran
Control-IQ, the trial cohort was screened differently, and this arm announces every meal.

Sensitivity detection runs by default, from `controller/autosens.py`. `--pin-autosens 1.0`
switches it off and reproduces the arm as it ran before the detection existed, which is the
comparison that says what the detection is worth.

Usage:
    python examples/oref_cohort.py --subjects 20 --days 28 --workers 8
    python examples/oref_cohort.py --subjects 20 --days 28 --workers 8 --pin-autosens 1.0
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timsim import simulate                                          # noqa: E402
from timsim import seeds
from timsim.controller import oref as O                              # noqa: E402
from timsim.population import cohort, names                          # noqa: E402
from timsim.validation import compare as C                           # noqa: E402


def one(job):
    """One subject, in its own process because each holds a node runtime of its own."""
    name, days, seed, target, autosens = job
    controller = O.OrefController(name, target_bg=target, autosens=autosens)
    try:
        result = simulate(name, days=days, seed=seed, controller=controller)
        # Both signals travel. DCLP3 reports real sensor readings, so a comparison with the
        # trial has to read `cgm`; the safety figures read `bg`, which carries no sensor
        # error. Confusing the two cost this package an investigation into counterregulation
        # that was chasing an artefact of the comparison.
        return {"name": name,
                "cgm": np.asarray(result.cgm, float).tolist(),
                "bg": np.asarray(result.bg, float).tolist(),
                "insulin_u_per_day": float(result.insulin_units) / days,
                "completed": bool(result.completed),
                "response": controller.response_profile()}
    finally:
        controller.close()


def summarise(runs, signal):
    bg = np.concatenate([np.asarray(r[signal], float) for r in runs])
    per_subject = [np.asarray(r[signal], float) for r in runs]
    band = lambda v, lo, hi: 100.0 * np.mean((v >= lo) & (v <= hi))
    return {
        "subjects": len(runs),
        "signal": "sensor reading" if signal == "cgm" else "glucose, no sensor error",
        "mean_mgdl": float(bg.mean()),
        "time_in_range": float(band(bg, 70, 180)),
        "below_70": float(100.0 * np.mean(bg < 70)),
        "below_54": float(100.0 * np.mean(bg < 54)),
        "above_180": float(100.0 * np.mean(bg > 180)),
        "above_250": float(100.0 * np.mean(bg > 250)),
        # Between-subject spread is the statistic the package has an open problem with, so
        # it is reported rather than folded into the pooled figure.
        "tir_sd_between_subjects": float(np.std([band(v, 70, 180) for v in per_subject])),
        "below_70_sd_between_subjects": float(
            np.std([100.0 * np.mean(v < 70) for v in per_subject])),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subjects", type=int, default=20)
    p.add_argument("--days", type=int, default=28)
    p.add_argument("--seed", type=int, default=seeds.BENCH)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--target", type=float, default=None,
                   help="glucose target in mg/dL; the real cohort runs near 90 where this "
                        "package defaults to 110, and the target is an input to the "
                        "algorithm rather than a property of the person")
    p.add_argument("--pin-autosens", type=float, default=None,
                   help="pin the sensitivity ratio instead of detecting it; 1.0 reproduces "
                        "the arm as it ran before detection existed")
    p.add_argument("--out", default=None, help="where to write the per-subject results")
    args = p.parse_args()

    if not O.available():
        raise SystemExit("no gathered oref; run bridge/oref/build.sh")

    # Match the trial's age distribution where the trial data is to hand, since age drives
    # insulin requirement and an unmatched cohort makes the comparison mean less than it
    # looks. Without it the run still stands on its own, and says so.
    try:
        from timsim.validation import dclp3
        picked, shortfall = cohort.matched(dclp3.ages(), args.subjects, seed=args.seed)
        if shortfall:
            print(f"note: {shortfall} short of the requested age composition")
        matched_to = "DCLP3 closed loop, age matched"
    except Exception as exc:
        picked = names()[:args.subjects]
        matched_to = f"unmatched ({type(exc).__name__}: no DCLP3 data to match against)"
    print(f"cohort: {len(picked)} subjects, {matched_to}\n")
    jobs = [(n, args.days, args.seed, args.target, args.pin_autosens) for n in picked]

    runs = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for r in pool.map(one, jobs):
            runs.append(r)
            print(f"  {r['name']}: done ({len(runs)}/{len(jobs)})", flush=True)

    print()
    print(f"oref0 SMB on TimSim, {sum(r['completed'] for r in runs)}/{len(runs)} completed, "
          f"{np.mean([r['insulin_u_per_day'] for r in runs]):.1f} U/day")
    stats = {sig: summarise(runs, sig) for sig in ("cgm", "bg")}
    keys = [k for k in stats["cgm"] if k not in ("subjects", "signal")]
    print(f"\n  {'':32s} {'as the sensor read it':>22s} {'truth':>12s}")
    for k in keys:
        print(f"  {k:32s} {stats['cgm'][k]:22.2f} {stats['bg'][k]:12.2f}")

    resp = [r["response"] for r in runs if r["response"]]
    if resp:
        print("\nwhat the algorithm did")
        for k in ("smb_pct", "smb_mean_u", "dose_mean_u", "zero_temp_pct",
                  "temp_issued_pct", "eventual_bg_median", "carbs_required_pct",
                  "autosens_median", "autosens_min", "autosens_max",
                  "autosens_below_1_pct"):
            vals = [x[k] for x in resp if x.get(k) is not None]
            if vals:
                print(f"  {k:24s} {np.mean(vals):.3f}")

    print("\nDCLP3 closed loop, middle 28 days, sensor readings: TIR 71.0%, above 180 24.65%")
    if args.pin_autosens is not None:
        print(f"Sensitivity is pinned at {args.pin_autosens}, so the hypoglycaemia figures "
              "are an upper bound.")

    if args.out:
        with open(args.out, "w") as fh:
            json.dump({"stats": stats, "runs": [
                {k: v for k, v in r.items() if k != "bg"} for r in runs]}, fh, indent=2)
        print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
