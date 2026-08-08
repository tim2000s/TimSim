"""Does the bench rank algorithms the way it should?

This is the mechanism that decides whether any safety verdict from TimSim is worth having,
and it is the one that is almost always missing. A simulator is usually validated by
showing that its output resembles real data. That says nothing about whether the ordering
it produces over algorithms is the true ordering, and the ordering is the whole product.

You cannot check an ordering against algorithms whose ranking you do not know. You can
check it against algorithms you have broken on purpose. `controller/reference.py` supplies
a plain automated insulin delivery algorithm and four named defects, each of which takes a
magnitude. The direction of the answer is fixed before the run by the mechanism rather
than by the measurement: an algorithm that believes insulin is weaker than it is will dose
harder and cause more hypoglycaemia, and one with no ceiling on insulin on board will
stack corrections.

Three things get checked.

Monotonicity. Dial one defect from none to severe and the safety score has to rise at
every step. A bench whose score is not monotone in the size of a known defect cannot rank
two algorithms that differ by less.

Separation. Each single defect has to be distinguishable from the reference by more than
the A/A noise floor measured on the same design. A defect that is real and invisible tells
you the bench is underpowered for that hazard, which is worth knowing before someone reads
a null as reassurance.

Direction. The reference has to come out safer than every defective variant, and a
deliberately timid variant has to come out safer still on hypoglycaemia and worse on
hyperglycaemia. A score that cannot see the trade-off is measuring one arm of it.

The score is the low blood glucose index, which is a published, asymmetric measure of
hypoglycaemia risk rather than something invented here. Inventing a composite would make
every result below a property of the weights.
"""
import numpy as np

from ..analysis import safety
from ..controller.reference import ReferenceAID
from ..simulation.run import simulate_cohort

# One defect, dialled from none to severe. The ordering is fixed by the mechanism: an
# algorithm that thinks a unit of insulin does less than it does will give more of it.
ISF_LADDER = (1.0, 0.85, 0.70, 0.55)

# One variant per named defect, at a magnitude a real misconfiguration reaches.
VARIANTS = {
    "reference": {},
    "isf_too_strong": {"isf_scale": 0.70},
    "no_iob_bound": {"use_iob_bound": False},
    "no_low_suspend": {"use_low_suspend": False},
    "acts_on_stale_readings": {"delay_min": 30.0},
    "timid": {"isf_scale": 2.0, "cr_scale": 2.0},
}


def run_variant(subjects, days=14, seed=0, layers=("physiology", "behaviour", "sensor"),
                **defects):
    """One arm of the ladder. The loop layer is off, since the algorithm is the loop."""
    return simulate_cohort(subjects, days=days, seed=seed, layers=layers, progress=False,
                           controller_factory=lambda n: ReferenceAID(n, **defects))


def score(results):
    """The safety score of an arm, plus the components a reader needs to interpret it."""
    records = safety.cohort(results)
    lbgi = np.array([r["lbgi"] for r in records], float)
    return {
        "lbgi_median": float(np.median(lbgi)),
        "lbgi_p90": float(np.percentile(lbgi, 90)),
        "lbgi_worst": float(lbgi.max()),
        "minutes_below_54_per_day": float(np.median(
            [r["minutes_below_54_per_day"] for r in records])),
        "rescue_grams_per_day": float(np.median(
            [r["rescue_grams_per_day"] for r in records])),
        "hbgi_median": float(np.median([r["hbgi"] for r in records])),
        "minutes_above_250_per_day": float(np.median(
            [r["minutes_above_250_per_day"] for r in records])),
        "mean_bg": float(np.median([r["mean_bg"] for r in records])),
        "time_in_range": float(np.median([r["time_in_range"] for r in records])),
        "did_not_complete": sum(1 for r in records if not r["completed"]),
        "per_subject_lbgi": lbgi.tolist(),
    }


def paired_delta(arm_a, arm_b, key="lbgi"):
    """Per-subject difference between two arms, which is how they should be compared."""
    a = {r["name"]: r[key] for r in safety.cohort(arm_a)}
    b = {r["name"]: r[key] for r in safety.cohort(arm_b)}
    shared = [n for n in a if n in b]
    return np.array([b[n] - a[n] for n in shared], float)


def check_score_is_monotone_in_a_graded_defect(subjects, days=14, seed=0,
                                               ladder=ISF_LADDER):
    """The safety score must rise at every step of a defect dialled from none to severe.

    This is the load-bearing check for any claim that the bench can rank. A score that is
    not monotone in the magnitude of a defect it can see cannot be trusted to order two
    algorithms whose difference is smaller.
    """
    scores = []
    for scale in ladder:
        arm = run_variant(subjects, days=days, seed=seed, isf_scale=scale)
        scores.append(score(arm)["lbgi_median"])
    rising = all(b > a for a, b in zip(scores, scores[1:]))
    return {"check": "the safety score rises with the size of a known defect",
            "level": 7, "value": float(scores[-1] - scores[0]),
            "target": "strictly increasing", "pass": bool(rising),
            "note": "median LBGI at insulin sensitivity scaled "
                    + "/".join(f"{s:g}" for s in ladder) + ": "
                    + ", ".join(f"{s:.2f}" for s in scores)}


def detectable_shift(null_deltas, n_subjects=None, power=0.8, alpha=0.05):
    """The smallest paired LBGI shift this design could resolve.

    The level 5 machinery, applied to the safety score instead of to time in range, and
    computed from the paired spread the A/A arm actually produced rather than assumed.

    An earlier version of the check below used the mean absolute paired difference of the
    A/A arm as its floor. That number is the typical size of the noise on one subject rather
    than the smallest shift detectable across a cohort, so it does not shrink as subjects
    are added. For a roughly normal paired difference it sits at 0.798 times the standard
    deviation whatever the cohort size, while this figure is 2.80 divided by the square root
    of it: the two coincide at about twelve subjects and diverge from there, so the old
    criterion is unintentionally strict on any cohort large enough to be worth running.

    Both are reported, because a borderline result should say which reading it rests on.
    """
    from scipy import stats as sps

    d = np.asarray(null_deltas, float)
    sd = float(d.std(ddof=1))
    n = int(n_subjects or len(d))
    return float((sps.norm.ppf(1 - alpha / 2) + sps.norm.ppf(power)) * sd / np.sqrt(n))


def check_each_defect_is_visible(subjects, days=14, seed=0, null_seed=1000,
                                 variants=None):
    """Every named defect has to separate from the reference by more than the noise.

    The noise floor is measured on the same design by running the reference twice with
    different seeds, so it is empirical. A defect that does not clear it is not being
    detected, whatever its effect on the trace looks like, and that says the bench is
    underpowered for that hazard at that cohort size rather than that the defect is benign.
    """
    variants = variants or {k: v for k, v in VARIANTS.items()
                            if k not in ("reference", "timid")}
    reference = run_variant(subjects, days=days, seed=seed)
    null = run_variant(subjects, days=days, seed=null_seed)
    null_deltas = paired_delta(reference, null)
    floor = detectable_shift(null_deltas, n_subjects=len(subjects))
    per_subject = float(np.abs(null_deltas).mean())

    seen, missed = {}, []
    for label, defect in variants.items():
        arm = run_variant(subjects, days=days, seed=seed, **defect)
        delta = float(np.median(paired_delta(reference, arm)))
        seen[label] = delta
        if abs(delta) <= floor:
            missed.append(label)
    return {"check": "every known defect separates from the reference",
            "level": 7,
            "value": float(min(abs(v) for v in seen.values())) if seen else float("nan"),
            "target": f"paired LBGI shift above the detectable {floor:.3f} "
                      f"at {len(subjects)} subjects",
            "pass": bool(not missed),
            "note": "paired median LBGI shift: "
                    + ", ".join(f"{k} {v:+.2f}" for k, v in seen.items())
                    + f"; smallest detectable shift {floor:.3f}, typical per-subject "
                      f"noise {per_subject:.3f}"
                    + (f"; not detected: {', '.join(missed)}" if missed else "")}


def check_the_trade_off_is_visible(subjects, days=14, seed=0):
    """A timid algorithm has to look safer on lows and worse on highs.

    An algorithm can always buy hypoglycaemia safety with hyperglycaemia, and a bench that
    reports only one of the two will rank the timid algorithm best every time. This checks
    that both arms of the trade-off move.

    Hyperglycaemia is read off mean glucose rather than off HBGI. HBGI is confounded here
    in a way worth knowing about: the reference algorithm causes more lows, the simulated
    person treats them with carbohydrate, and the rebound highs that follow load HBGI on
    the arm that is supposedly safer on highs. Mean glucose does not have that problem.
    """
    reference = score(run_variant(subjects, days=days, seed=seed))
    timid = score(run_variant(subjects, days=days, seed=seed, **VARIANTS["timid"]))
    safer_low = timid["lbgi_median"] < reference["lbgi_median"]
    worse_high = timid["mean_bg"] > reference["mean_bg"]
    return {"check": "a timid algorithm trades hypoglycaemia risk for hyperglycaemia",
            "level": 7, "value": float(timid["mean_bg"] - reference["mean_bg"]),
            "target": "LBGI falls and mean glucose rises",
            "pass": bool(safer_low and worse_high),
            "note": f"LBGI {reference['lbgi_median']:.2f} to {timid['lbgi_median']:.2f}, "
                    f"mean glucose {reference['mean_bg']:.0f} to {timid['mean_bg']:.0f} "
                    f"mg/dL, time in range {reference['time_in_range']:.1f} to "
                    f"{timid['time_in_range']:.1f}%"}


def table(subjects, days=14, seed=0, variants=None):
    """Every variant scored, for reading rather than for passing or failing."""
    variants = variants or VARIANTS
    return {label: score(run_variant(subjects, days=days, seed=seed, **defect))
            for label, defect in variants.items()}


__all__ = ["VARIANTS", "ISF_LADDER", "run_variant", "score", "paired_delta", "table",
           "check_score_is_monotone_in_a_graded_defect", "check_each_defect_is_visible",
           "check_the_trade_off_is_visible"]
