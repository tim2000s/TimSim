"""Run the validation suite and print a graded report.

    python -m timsim.validation.run              # everything, about 90 minutes
    python -m timsim.validation.run --fast       # levels 1, 2 and 6 only, a few minutes

The slow levels are 3, 4 and 5, because each needs whole cohorts run for weeks. Level 5
in particular runs the same controller twice to establish what a null looks like, which
is the number every later comparison has to be read against.
"""
import argparse, json, os

import numpy as np

from ..population import names
from ..simulation.run import simulate_cohort
from . import checks

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(HERE, "docs", "validation.json")

LEVEL_NAMES = {
    1: "internal consistency",
    2: "face validity",
    3: "distributional fidelity",
    4: "known answer",
    5: "discriminating power",
    6: "robustness",
}


def fast_checks(subjects):
    out = [checks.check_steady_state_closure(),
           checks.check_published_cohort_obeys_clinical_rules()]
    for name in subjects[:3]:
        out.append(checks.check_quiet_subject_holds(name))
        out.append(checks.check_correction_moves_glucose_by_its_correction_factor(name))
        out.append(checks.check_unbolused_carbohydrate_raises_glucose(name))
        out.append(checks.check_meal_peaks_at_a_plausible_time(name))
    out.append(checks.check_layers_are_isolated(subjects[0]))
    out.append(checks.check_glucose_is_monotone_in_insulin(subjects[0]))
    out.append(checks.check_more_insulin_is_defended_with_carbohydrate(subjects[0]))
    out.append(checks.check_population_is_stable_across_seeds())
    out.append(checks.check_conclusion_survives_behaviour_parameters(subjects[0]))
    return out


def slow_checks(subjects, days):
    full = ("physiology", "behaviour", "loop", "sensor")
    no_loop = ("physiology", "behaviour", "sensor")

    print("  cohort with every layer ...", flush=True)
    loop_a = simulate_cohort(subjects, days=days, seed=0, layers=full, progress=False)
    print("  the same cohort again, different seed, same controller ...", flush=True)
    loop_b = simulate_cohort(subjects, days=days, seed=1000, layers=full, progress=False)
    print("  the same cohort with the loop switched off ...", flush=True)
    open_arm = simulate_cohort(subjects, days=days, seed=0, layers=no_loop, progress=False)

    return [
        checks.check_signatures_against_real_data(loop_a),
        checks.check_closing_the_loop_improves_time_in_range(open_arm, loop_a),
        checks.check_null_contrast_is_null(loop_a, loop_b),
        checks.minimum_detectable_difference(loop_a, loop_b),
        checks.minimum_detectable_difference(loop_a, loop_b, n_subjects=100),
    ]


def report(results):
    lines = []
    for level in sorted(LEVEL_NAMES):
        rows = [r for r in results if r["level"] == level]
        if not rows:
            continue
        lines.append(f"\nLevel {level}: {LEVEL_NAMES[level]}")
        for r in rows:
            mark = "  --  " if r["pass"] is None else ("  ok  " if r["pass"] else " FAIL ")
            lines.append(f"{mark}{r['check']}")
            lines.append(f"        {r['note']}  (target: {r['target']})")
    judged = [r for r in results if r["pass"] is not None]
    failed = [r for r in judged if not r["pass"]]
    lines.append(f"\n{len(judged) - len(failed)} of {len(judged)} checks passed")
    if failed:
        lines.append("failed: " + "; ".join(r["check"] for r in failed))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fast", action="store_true", help="skip the cohort-scale levels")
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()

    subjects = names("adult")[:a.subjects]
    results = fast_checks(subjects)
    if not a.fast:
        results += slow_checks(subjects, a.days)

    text = report(results)
    print(text)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"results": results, "subjects": len(subjects), "days": a.days,
               "fast_only": a.fast}, open(OUT, "w"), indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
