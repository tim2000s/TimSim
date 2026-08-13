"""Titrate every subject's settings, and record what the procedure found.

Run this before benchmarking anything. A controller scored on settings nobody titrated is
being judged partly on the settings: across this population the physiological correction
factor has a median of 15.1 mg/dL per unit against the 35 real DCLP3 participants ran, and
handing oref0 SMB the physiological value doubles its time below 70 mg/dL against handing it
the real one.

    python examples/titrate_cohort.py [--subjects 20] [--days 28] [--workers 6]

The result is written beside the population and is not committed, since it derives from the
published parameter tables in the same way the population does.
"""
import argparse
import numpy as np
from concurrent.futures import ProcessPoolExecutor

from timsim.therapy import titrate


def _one(job):
    name, days, seed = job
    return titrate.titrate_subject(name, days=days, seed=seed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--days", type=int, default=28)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    names = [f"adult#{i:03d}" for i in range(1, a.subjects + 1)]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        out = list(ex.map(_one, [(n, a.days, a.seed) for n in names]))

    found = [r for r in out if r["found"]]
    path = titrate.save(out, meta={"days": a.days, "seed": a.seed,
                                   "driver": titrate.REFERENCE_DRIVER,
                                   "scales": list(titrate.SCALES)})
    print(f"{len(found)}/{len(out)} subjects titrated, written to {path}\n")
    print(f"{'subject':>11}{'scale':>7}{'ISF':>7}{'TBR70':>8}{'TBR54':>8}{'TIR':>7}"
          f"{'CV':>7}  remaining misses")
    for r in out:
        if not r["found"]:
            print(f"{r['name']:>11}{'none':>7}   floors not met at any scale")
            continue
        last = r["trace"][-1]
        print(f"{r['name']:>11}{r['scale']:>7.2f}{last.get('isf', float('nan')):>7.1f}"
              f"{last['tbr70']:>8.2f}{last['tbr54']:>8.2f}{last['tir']:>7.1f}"
              f"{last['cv']:>7.1f}  {', '.join(last['fails']) or 'none'}")
    if found:
        sc = np.array([r["scale"] for r in found], float)
        isf = np.array([r["trace"][-1]["isf"] for r in found], float)
        print(f"\nscale: median {np.median(sc):.2f}, range {sc.min():.2f} to {sc.max():.2f}")
        print(f"correction factor: median {np.median(isf):.1f} mg/dL per unit, "
              f"range {isf.min():.1f} to {isf.max():.1f}   (DCLP3 ran 35)")


if __name__ == "__main__":
    main()
