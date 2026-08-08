"""Take an algorithm through the whole safety workflow and print a verdict.

The order matters and is the order in `docs/OSAID.md`. Register the criteria first, then
establish the noise floor, then look for failures, and only then run the cohort that
produces the verdict. Doing it the other way round means choosing a threshold after seeing
the result, which is not a threshold.

    python examples/safety_gate.py                       # the reference algorithm
    python examples/safety_gate.py --defect no_iob_bound # one that should fail
    python examples/safety_gate.py --subjects 34 --days 28

The default is small so that it runs in a few minutes. A verdict worth quoting needs the
whole population, and the exposure line in the output says what the run you actually did
supports.
"""
import argparse
import json
import os

import numpy as np

from timsim import simulate, therapy
from timsim.controller.reference import ReferenceAID
from timsim.population import names
from timsim.simulation.run import simulate_cohort
from timsim.validation import faults, gate, ranking
from timsim.validation.checks import minimum_detectable_difference

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The algorithm supplies the loop, so that layer is left out. The site layer is in: a set
# that stops absorbing is a property of the person and their hardware rather than of the
# system under test, and how an algorithm behaves when it is high and dosing into a failed
# site is one of the things this gate exists to see.
LAYERS = ("physiology", "behaviour", "sensor", "site")


def _window(run, start_min, hours=6.0):
    """The stretch from the fault onset to `hours` later, which is where to look.

    Summarising the whole run instead is how a fault comes to look like nothing happened:
    a three-hour sensor dropout on day two leaves the minimum glucose of a three-day run
    exactly where it was, somewhere else entirely.
    """
    lo = int(start_min / run.sample_time)
    hi = lo + int(hours * 60.0 / run.sample_time)
    return run.bg[lo:hi], run.insulin_series[lo:hi]


def fault_scenarios(subject, defect, days=3):
    """Level 7. One subject, one seed, one fault at a time, against a clean control.

    Run on a dawn-shaped basal profile rather than a flat one. A clock shift against a flat
    schedule changes nothing at all, so testing it there is testing nothing, and a real
    system is always reading a schedule.
    """
    profile = therapy.for_subject(subject, diurnal=True)
    control = simulate(subject, days=days, seed=11, layers=LAYERS, profile=profile,
                       controller=ReferenceAID(subject, profile=profile, **defect))
    rows = []
    for label, build in faults.SCENARIOS.items():
        fault = build()
        run = simulate(subject, days=days, seed=11, layers=LAYERS, profile=profile,
                       faults=faults.Faults(fault),
                       controller=ReferenceAID(subject, profile=profile, **defect))
        bg, insulin = _window(run, fault.start_min)
        ref_bg, ref_insulin = _window(control, fault.start_min)
        rows.append({
            "scenario": label,
            "expected": fault.expected,
            "completed": run.completed,
            "min_bg": float(bg.min()) if len(bg) else float("nan"),
            "control_min_bg": float(ref_bg.min()) if len(ref_bg) else float("nan"),
            "max_bg": float(bg.max()) if len(bg) else float("nan"),
            "control_max_bg": float(ref_bg.max()) if len(ref_bg) else float("nan"),
            "insulin_u": float(insulin.sum()),
            "control_insulin_u": float(ref_insulin.sum()),
        })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--defect", choices=sorted(ranking.VARIANTS), default="reference")
    ap.add_argument("--subjects", type=int, default=12)
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()

    defect = ranking.VARIANTS[a.defect]
    subjects = names("adult")[:a.subjects]
    design = {"subjects": len(subjects), "days": a.days, "layers": list(LAYERS),
              "algorithm": a.defect}

    print(f"1. registering criteria for {a.defect}")
    print(f"   fingerprint {gate.fingerprint(design=design)}")
    print("   record this before the run; a verdict whose fingerprint does not match "
          "had its thresholds moved\n")

    print("2. establishing the noise floor")
    null_a = ranking.run_variant(subjects, days=a.days, seed=0, layers=LAYERS, **defect)
    null_b = ranking.run_variant(subjects, days=a.days, seed=1000, layers=LAYERS, **defect)
    mdd = minimum_detectable_difference(null_a, null_b)
    print(f"   {mdd['note']}\n")

    print("3. fault scenarios on one subject, over the six hours from onset")
    print(f"   {'scenario':<18} {'BG range':>17}  {'control':>17}  {'insulin U':>18}")
    for row in fault_scenarios(subjects[0], defect):
        flag = "  DID NOT COMPLETE" if not row["completed"] else ""
        print(f"   {row['scenario']:<18} "
              f"{row['min_bg']:7.1f}-{row['max_bg']:<9.1f} "
              f"{row['control_min_bg']:7.1f}-{row['control_max_bg']:<9.1f} "
              f"{row['insulin_u']:8.2f} vs {row['control_insulin_u']:6.2f}{flag}")
    print("   read the traces rather than the summary; what you are looking for is a "
          "fallback and a recovery\n")

    print("4. the cohort that produces the verdict")
    results = simulate_cohort(subjects, days=a.days, seed=0, layers=LAYERS,
                              progress=False,
                              controller_factory=lambda n: ReferenceAID(n, **defect))
    verdict = gate.evaluate(results, design=design, label=a.defect)
    print()
    print(gate.report(verdict))

    out = os.path.join(HERE, "docs", f"gate_{a.defect}.json")
    json.dump(verdict, open(out, "w"), indent=1, default=float)
    print(f"\nwritten to {out}")


if __name__ == "__main__":
    main()
