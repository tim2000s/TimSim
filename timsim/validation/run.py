"""Run the validation suite and print a graded report.

    python -m timsim.validation.run --fast       # levels 1, 2 and 6, a few minutes
    python -m timsim.validation.run --ranking    # level 7, an hour or two
    python -m timsim.validation.run              # everything, several hours

The slow levels are 3, 4, 5 and 7, because each needs whole cohorts run for weeks. Level 5
runs the same controller twice to establish what a null looks like, which is the number
every later comparison has to be read against. Level 7 runs a ladder of deliberately
broken algorithms, which is a dozen cohorts rather than one, so it is worth running on its
own with `--ranking` and a `--subjects` count you have the time for.
"""
import argparse, json, os

import numpy as np

from ..population import names
from ..simulation.run import DEFAULT_LAYERS, simulate_cohort
from . import checks, ranking, replication

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(HERE, "docs", "validation.json")

LEVEL_NAMES = {
    1: "internal consistency",
    2: "face validity",
    3: "distributional fidelity",
    4: "known answer",
    5: "discriminating power",
    6: "robustness",
    7: "fault tolerance and ranking",
}


def fast_checks(subjects):
    out = [checks.check_steady_state_closure(),
           checks.check_published_cohort_obeys_clinical_rules()]
    for name in subjects[:3]:
        out.append(checks.check_quiet_subject_holds(name))
        out.append(checks.check_pump_quantisation_costs_what_it_should(name))
        out.append(checks.check_correction_moves_glucose_by_its_correction_factor(name))
        out.append(checks.check_unbolused_carbohydrate_raises_glucose(name))
        out.append(checks.check_meal_peaks_at_a_plausible_time(name))
    out.append(checks.check_the_sensor_layer_is_a_reading_and_not_a_glucose(subjects[0]))
    out.append(checks.check_the_algorithm_sees_the_sensor_artefacts(subjects[0]))
    out.append(checks.check_delivery_limits_bind(subjects[0]))
    out.append(checks.check_glucose_is_monotone_in_insulin(subjects[0]))
    out.append(checks.check_more_insulin_is_defended_with_carbohydrate(subjects[0]))
    out.append(checks.check_population_is_stable_across_seeds())
    out.append(checks.check_conclusion_survives_behaviour_parameters(subjects[0]))
    return out


def slow_checks(subjects, days):
    full = DEFAULT_LAYERS
    no_loop = tuple(l for l in DEFAULT_LAYERS if l != "loop")

    print("  cohort with every layer ...", flush=True)
    loop_a = simulate_cohort(subjects, days=days, seed=0, layers=full, progress=False)
    print("  the same cohort again, different seed, same controller ...", flush=True)
    loop_b = simulate_cohort(subjects, days=days, seed=1000, layers=full, progress=False)
    print("  the same cohort with the loop switched off ...", flush=True)
    open_arm = simulate_cohort(subjects, days=days, seed=0, layers=no_loop, progress=False)

    print("  the same cohort with nothing switched on ...", flush=True)
    bare = simulate_cohort(subjects, days=days, seed=0, layers=(), progress=False)

    return [
        checks.check_signatures_against_real_data(loop_a),
        replication.check_the_test_is_calibrated(loop_a),
        replication.check_the_test_detects_a_missing_mechanism(loop_a, bare),
        checks.check_closing_the_loop_improves_time_in_range(open_arm, loop_a),
        checks.check_null_contrast_is_null(loop_a, loop_b),
        checks.minimum_detectable_difference(loop_a, loop_b),
        checks.minimum_detectable_difference(loop_a, loop_b, n_subjects=100),
    ]


def ranking_checks(subjects, days):
    """Level 7. Whether the bench orders algorithms the way a known defect says it should."""
    print("  dialling one defect from none to severe ...", flush=True)
    out = [ranking.check_score_is_monotone_in_a_graded_defect(subjects, days=days)]
    print("  each named defect against the reference ...", flush=True)
    out.append(ranking.check_each_defect_is_visible(subjects, days=days))
    print("  the hypoglycaemia against hyperglycaemia trade-off ...", flush=True)
    out.append(ranking.check_the_trade_off_is_visible(subjects, days=days))
    return out


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
    ap.add_argument("--ranking", action="store_true",
                    help="level 7 only: does the bench order known defects correctly")
    ap.add_argument("--subjects", type=int, default=20)
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()

    subjects = names("adult")[:a.subjects]
    if a.ranking:
        results = ranking_checks(subjects, a.days)
    else:
        results = fast_checks(subjects)
        if not a.fast:
            results += slow_checks(subjects, a.days) + ranking_checks(subjects, a.days)

    text = report(results)
    print(text)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"results": results, "subjects": len(subjects), "days": a.days,
               "fast_only": a.fast}, open(OUT, "w"), indent=1)
    print(f"\nwritten to {OUT}")


if __name__ == "__main__":
    main()
