"""Choosing which virtual subjects to run, so that they are the right people.

A virtual population is not a cohort. The hundred subjects here span ages 7 to 75, and any
particular comparison is against a particular group of real people who do not. Running the
34 adults against the closed-loop arm of DCLP3 compares a median age of 49 against a median
of 29, with no adolescents at all where the trial is 28% under 18. That is not a subtle
mismatch and it moves the things you would expect it to move: adolescents need more insulin
per kilogram and run higher, older adults weigh more and need more insulin in total.

So the cohort is a choice, and it should be made against the reference rather than by taking
whichever class is convenient. `matched` does that by age, which is the only demographic the
public DCLP3 release keeps: weight, height and HbA1c are all stripped from it.

Age is a proxy and a weak one. It stands in here for the things that actually differ between
a fourteen year old and a fifty year old and that the model does carry, which are body
weight, insulin sensitivity and total daily requirement. A cohort matched on age is closer
to the reference than one matched on nothing, and it is not the same as a cohort matched on
physiology.
"""
import numpy as np

# Wide enough that each bin holds several subjects of the hundred, narrow enough to separate
# children from adolescents from adults, which is how the published population is built.
AGE_BINS = (0.0, 13.0, 18.0, 26.0, 40.0, 200.0)


def ages(subjects=None):
    """Each subject's age, from the generated therapy table."""
    from . import names as all_names, therapy_for

    subjects = list(subjects) if subjects is not None else all_names()
    return {name: float(therapy_for(name)["Age"]) for name in subjects}


def matched(reference_ages, n=None, seed=0, bins=AGE_BINS, subjects=None):
    """Subjects whose age distribution follows a reference population's.

    Samples without replacement inside each age bin, in the reference's own proportions, so
    a trial that is a quarter adolescent gets a cohort that is a quarter adolescent.

    When a bin cannot supply its share, every bin is scaled down to the one that binds
    rather than that bin alone being short. Filling from a bin the reference does not have
    would misrepresent the population, and taking fewer from only the short bin quietly
    changes the composition into something nobody chose: asking for 30 subjects at 28%
    adolescent from a population thin on 26 to 40 year olds gave 50% adolescent before this
    was fixed. The shortfall is returned either way.
    """
    available = ages(subjects)
    reference = np.asarray([a for a in reference_ages if np.isfinite(a)], float)
    if not len(reference):
        raise ValueError("no reference ages given")
    n = int(n or len(reference))

    rng = np.random.default_rng(seed)
    wanted = np.histogram(reference, bins=bins)[0] / len(reference)
    pool = {i: sorted(name for name, age in available.items()
                      if bins[i] <= age < bins[i + 1])
            for i in range(len(bins) - 1)}

    # How far every bin has to shrink for the tightest one to be satisfiable.
    scale = 1.0
    shortfall = {}
    for i, share in enumerate(wanted):
        want = share * n
        if want <= 0:
            continue
        if want > len(pool[i]):
            shortfall[f"{bins[i]:.0f}-{bins[i + 1]:.0f}"] = int(round(want)) - len(pool[i])
            scale = min(scale, len(pool[i]) / want)

    chosen = []
    for i, share in enumerate(wanted):
        take = int(round(share * n * scale))
        if take > 0:
            chosen += list(rng.choice(pool[i], size=min(take, len(pool[i])),
                                      replace=False))
    return sorted(chosen), shortfall


def describe(subjects):
    """Median and range of a cohort's age, for quoting beside a result."""
    a = np.array(list(ages(subjects).values()), float)
    return {"n": len(a), "age_median": float(np.median(a)),
            "age_min": float(a.min()), "age_max": float(a.max()),
            "fraction_under_18": float(np.mean(a < 18))}


__all__ = ["matched", "ages", "describe", "AGE_BINS"]
