"""Build the shipped population. Run once after install, or to regenerate with a new seed.

    python -m simperson.population.build --n 100 --seed 2026

The generated tables are written into the package so that every later run uses the same
subjects. Regenerating with a different seed is the check that a result does not depend
on one draw.
"""
import argparse, json, os
from . import PARAMS_DIR, PATIENT_FILE, THERAPY_FILE, REPORT_FILE
from .generate import generate


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--shrinkage", type=float, default=0.5)
    ap.add_argument("--truncate", type=float, default=2.5)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    os.makedirs(PARAMS_DIR, exist_ok=True)
    patients, therapy, report = generate(n=a.n, seed=a.seed, shrinkage=a.shrinkage,
                                         truncate=a.truncate, verbose=not a.quiet)
    patients.to_csv(PATIENT_FILE, index=False)
    therapy.to_csv(THERAPY_FILE, index=False)
    json.dump(report, open(REPORT_FILE, "w"), indent=1)

    print(f"\n{report['accepted']} subjects from {report['candidates']} candidates "
          f"({100*report['acceptance_rate']:.0f}% accepted)")
    for why, n in sorted(report["rejections"].items(), key=lambda kv: -kv[1]):
        print(f"  {n:5d}  {why}")
    print(f"\nwritten to {PARAMS_DIR}")


if __name__ == "__main__":
    main()
