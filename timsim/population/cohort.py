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


def traits(subjects=None):
    """Each subject's age and total daily insulin, from the generated therapy table."""
    from . import names as all_names, therapy_for

    subjects = list(subjects) if subjects is not None else all_names()
    out = {}
    for name in subjects:
        q = therapy_for(name)
        out[name] = (float(q["Age"]), float(q["TDI"]))
    return out


def matched_on_traits(reference, n=None, seed=0, subjects=None, weights=(1.0, 1.0)):
    """Subjects matched to a reference population on age and daily insulin together.

    `reference` is an iterable of (age, total daily insulin) pairs from real people.

    Matching on age alone was what the public DCLP3 release allowed and it leaves the thing
    age is a proxy for unmatched. The trial also publishes each participant's recorded total
    daily insulin, and the OpenAPS Data Commons publishes no demographics at all but allows a
    requirement to be reconstructed from delivery, so daily insulin is the one trait both
    references share and it is closer to what the model actually carries.

    Each real person is matched to the nearest unused subject in standardised space, sampling
    without replacement, so the cohort follows the reference's joint distribution rather than
    each margin separately. Insulin is matched on a log scale because its spread is
    multiplicative: the gap between 20 and 30 U/day is the gap between 60 and 90, not the gap
    between 60 and 70.

    Returns the chosen names and the distance actually achieved, since a cohort matched to a
    reference the population cannot reach should say so rather than look matched.
    """
    have = traits(subjects)
    ref = np.asarray([(a, t) for a, t in reference
                      if np.isfinite(a) and np.isfinite(t) and t > 0], float)
    if not len(ref):
        raise ValueError("no reference traits given")
    n = int(n or len(ref))

    names = sorted(have)
    pool = np.asarray([have[k] for k in names], float)
    ref_z = np.column_stack([ref[:, 0], np.log(ref[:, 1])])
    pool_z = np.column_stack([pool[:, 0], np.log(pool[:, 1])])
    centre, scale = ref_z.mean(0), ref_z.std(0)
    scale[scale == 0] = 1.0
    w = np.asarray(weights, float)
    ref_z = (ref_z - centre) / scale * w
    pool_z = (pool_z - centre) / scale * w

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(ref_z))[:n]
    chosen, used, distances = [], set(), []
    for i in order:
        d = np.linalg.norm(pool_z - ref_z[i], axis=1)
        for j in np.argsort(d):
            if names[j] not in used:
                used.add(names[j])
                chosen.append(names[j])
                distances.append(float(d[j]))
                break
        if len(used) == len(names):
            break
    return sorted(chosen), {"n": len(chosen), "requested": n,
                            "median_distance": float(np.median(distances)),
                            "p90_distance": float(np.percentile(distances, 90))}


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


__all__ = ["matched", "matched_on_traits", "ages", "traits", "describe", "AGE_BINS"]
