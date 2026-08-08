"""Can you tell a simulated person from a real one?

Level 3 compares eleven cohort medians against an envelope of four cohort medians. That
is a weak test in a specific way: a simulator can match every median while getting the
spread across people wrong, and a population whose spread is wrong does not replicate
people, it replicates an average. Matching medians is also easy to reach by tuning, which
is why `docs/FIDELITY.md` insists on reporting the whole table whenever anything changes.

The stronger test is the one used for generative models everywhere else: train a
classifier to tell simulated traces from real ones. If a classifier given windows of both
cannot separate them, they are indistinguishable on everything the features encode, which
is a much larger claim than eleven medians landing in range. The interesting output is not
the number on its own but which features carry the weight, because those name what the
simulator is still getting wrong.

The classifier is deliberately small: a logistic regression on about a dozen interpretable
window statistics, cross-validated by subject, with a subject-level permutation null so
the figure has a scale to be read against. Something larger would separate the two on
artefacts of sample size and teach you nothing.

The scale matters more than it looks. A first version of this test read the null as 0.5,
which is what you get when window labels are permuted, and it duly reported an area under
the curve of 0.85 for one half of a simulated cohort against the other half. Nothing was
wrong with the simulator. People differ, so any classifier separates any two groups of
different people, and the comparison this test exists for is also between two groups of
different people. The null has to carry that structure, which means permuting at the
subject level and holding out whole subjects in cross-validation.

This has now been run against real data. `validation/dclp3.py` supplies 67 real closed-loop
participants and `AGAINST_DCLP3` below records the result: separable at 0.709 against a null
whose 95th percentile is 0.546, with the separation carried by hyperglycaemia. `demonstrate`
still runs both halves of the calibration on data this package can generate, which is what
establishes that the test has a null and has power before any of it is believed.
"""
import numpy as np

WINDOW_HOURS = 24.0
STRIDE_HOURS = 12.0


# ------------------------------------------------------------------------ features
def _acf(x, lag):
    if lag >= len(x) - 5:
        return 0.0
    a, b = x[:-lag], x[lag:]
    am, bm = a.mean(), b.mean()
    denom = np.sqrt(((a - am) ** 2).sum() * ((b - bm) ** 2).sum())
    return float(((a - am) * (b - bm)).sum() / denom) if denom else 0.0


def window_features(bg, sample_minutes):
    """Statistics of one window of glucose, chosen to be readable rather than exhaustive."""
    bg = np.asarray(bg, float)
    d = np.diff(bg)
    lag30 = max(int(round(30.0 / sample_minutes)), 1)
    lag60 = max(int(round(60.0 / sample_minutes)), 1)
    return np.array([
        bg.mean(),
        bg.std(),
        100.0 * bg.std() / bg.mean() if bg.mean() else 0.0,
        bg.min(),
        bg.max(),
        100.0 * np.mean(bg < 70),
        100.0 * np.mean(bg >= 180),
        np.mean(np.abs(d)) if len(d) else 0.0,
        100.0 * np.mean(d > 10) if len(d) else 0.0,
        _acf(bg, lag30),
        _acf(bg, lag60),
        np.std(np.diff(d)) if len(d) > 1 else 0.0,
    ], float)


FEATURE_NAMES = ["mean", "sd", "cv", "min", "max", "pct_below_70", "pct_above_180",
                 "mean_abs_delta", "pct_delta_over_10", "acf30", "acf60", "jitter"]


def trace_windows(bg, sample_minutes, window_hours=WINDOW_HOURS,
                  stride_hours=STRIDE_HOURS):
    """Overlapping windows of one trace, as feature rows."""
    n = int(round(window_hours * 60.0 / sample_minutes))
    step = max(int(round(stride_hours * 60.0 / sample_minutes)), 1)
    bg = np.asarray(bg, float)
    return np.array([window_features(bg[i:i + n], sample_minutes)
                     for i in range(0, max(len(bg) - n + 1, 0), step)]) \
        if len(bg) >= n else np.zeros((0, len(FEATURE_NAMES)))


def result_windows(results, use="cgm", **kwargs):
    """Feature rows for a cohort, with the subject each row came from.

    The subject index matters. Windows from one person are not independent of each other,
    and a classifier handed them as though they were will separate any two groups of
    different people, which is not the question.
    """
    rows, groups = [], []
    for i, r in enumerate(results):
        w = trace_windows(getattr(r, use), r.sample_time, **kwargs)
        if len(w):
            rows.append(w)
            groups.append(np.full(len(w), i))
    if not rows:
        return np.zeros((0, len(FEATURE_NAMES))), np.zeros(0, int)
    return np.vstack(rows), np.concatenate(groups)


# ------------------------------------------------------------------------ classifier
def _fit_logistic(x, y, l2=1.0, steps=400, lr=0.3):
    """Full-batch gradient descent. Small and legible beats fast for a dozen features."""
    w = np.zeros(x.shape[1] + 1)
    z = np.hstack([np.ones((len(x), 1)), x])
    for _ in range(steps):
        p = 1.0 / (1.0 + np.exp(-np.clip(z @ w, -30, 30)))
        grad = z.T @ (p - y) / len(y)
        grad[1:] += l2 * w[1:] / len(y)
        w -= lr * grad
    return w


def _score(x, w):
    return np.hstack([np.ones((len(x), 1)), x]) @ w


def auc(scores, labels):
    """Area under the ROC curve, by ranks, with ties averaged.

    `rankdata` rather than a loop over unique values: the permutation null calls this a few
    hundred times on a few thousand points, and the loop version was quadratic in ties.
    """
    from scipy.stats import rankdata

    scores, labels = np.asarray(scores, float), np.asarray(labels, int)
    n1, n0 = int(labels.sum()), int((1 - labels).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = rankdata(scores)
    return float((ranks[labels == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def _grouped_cv_auc(x, y, groups, folds, rng):
    """Cross-validate holding out whole subjects, so no subject is in both sides."""
    unique = np.unique(groups)
    if len(unique) < 2 * folds:
        folds = max(2, len(unique) // 2)
    order = rng.permutation(unique)
    chunks = np.array_split(order, folds)
    held = np.full(len(x), np.nan)
    for chunk in chunks:
        test = np.isin(groups, chunk)
        train = ~test
        if len(np.unique(y[train])) < 2 or not test.any():
            continue
        w = _fit_logistic(x[train], y[train])
        held[test] = _score(x[test], w)
    ok = np.isfinite(held)
    return auc(held[ok], y[ok]) if len(np.unique(y[ok])) == 2 else float("nan")


def discriminability(a, b, groups_a=None, groups_b=None, folds=4, seed=0,
                     permutations=100):
    """How separable two sets of windows are, cross-validated against a permuted null.

    Two design decisions carry the whole result, and an earlier version got both wrong.

    Cross-validation holds out whole subjects. Windows from one person share that person's
    mean, variability and daily rhythm, so a fold that puts some of a subject's windows in
    training and the rest in test is scoring the classifier on people it has already seen.

    The null permutes subject labels rather than window labels. This is the one that
    matters. Between-subject variation is large, so a classifier will separate any two
    groups of different people whether or not one of them is simulated. Permuting windows
    gives a null at 0.5 and makes that separation look like a finding: the first version of
    this test scored 0.85 splitting a cohort against itself, against a window-permuted null
    of 0.49. Permuting subjects reproduces the between-subject structure in the null, so
    the observed figure is read against what random groups of people score.

    The verdict is therefore not "is the AUC near 0.5" but "does the AUC exceed what a
    random split of the same people achieves".
    """
    a, b = np.atleast_2d(a), np.atleast_2d(b)
    if groups_a is None:
        groups_a = np.arange(len(a))
    if groups_b is None:
        groups_b = np.arange(len(b))
    groups_b = np.asarray(groups_b) + (np.max(groups_a) + 1 if len(groups_a) else 0)

    if len(a) < folds or len(b) < folds:
        return {"auc": float("nan"), "note": "too few windows to cross-validate"}

    x = np.vstack([a, b])
    y = np.concatenate([np.zeros(len(a)), np.ones(len(b))])
    groups = np.concatenate([np.asarray(groups_a), groups_b])
    mu, sd = x.mean(0), x.std(0)
    sd[sd == 0] = 1.0
    x = (x - mu) / sd

    rng = np.random.default_rng(seed)
    observed = _grouped_cv_auc(x, y, groups, folds, rng)

    unique = np.unique(groups)
    n_a = len(np.unique(groups_a))
    null = []
    for _ in range(permutations):
        shuffled = rng.permutation(unique)
        label_of = {g: (0.0 if i < n_a else 1.0) for i, g in enumerate(shuffled)}
        y_perm = np.array([label_of[g] for g in groups], float)
        v = _grouped_cv_auc(x, y_perm, groups, folds, rng)
        if np.isfinite(v):
            null.append(v)
    null = np.array(null)

    weights = _fit_logistic(x, y)[1:]
    return {"auc": float(observed),
            "null_auc_median": float(np.median(null)) if len(null) else float("nan"),
            "null_auc_p95": float(np.percentile(null, 95)) if len(null) else float("nan"),
            "p_value": float(np.mean(null >= observed)) if len(null) else float("nan"),
            "n_windows": (len(a), len(b)),
            "n_subjects": (n_a, len(np.unique(groups_b))),
            "weights": {n: float(w) for n, w in zip(FEATURE_NAMES, weights)},
            "top_features": [FEATURE_NAMES[i]
                             for i in np.argsort(-np.abs(weights))[:3]]}


# Measured 2026-08-07 against DCLP3's pump-received CGM, calibration half only: 3,752
# windows from 67 real closed-loop participants against 1,870 from 34 simulated subjects,
# whole subjects held out, subject labels permuted.
#
# TimSim is separable, at 0.709 against a null whose 95th percentile is 0.546. That is a
# long way from the 1.000 this test scores against a simulator with its layers switched off,
# and a long way from indistinguishable.
#
# What separates them is hyperglycaemia. TimSim's subjects spend a third less time above 180
# than real closed-loop users, run 8 mg/dL lower on average and peak 20 mg/dL lower, while
# spending slightly more time below 70. An algorithm tested here meets an easier
# hyperglycaemic world than the one it will be used in, which under-exercises the
# corrections it exists to make. That is consistent with the Boost work, where TimSim
# reached the committed meal state less often than the field.
#
# Two smaller readings. Sensor jitter is 5.53 against a real 4.39, so the sensor layer runs
# slightly hot even against the correct source. And the autocorrelations now match almost
# exactly, 0.84 and 0.58 on both sides, which retires the score-persistence gap recorded in
# `validation/boost.py` as an adapter artefact rather than a property of the simulator.
AGAINST_DCLP3 = {
    "auc": 0.709,
    "null_median": 0.453,
    "null_p95": 0.546,
    "p_value": 0.000,
    "windows": (3752, 1870),
    "subjects": (67, 34),
    "source": "DCLP3 pump-received CGM, calibration half",
    "marginals": {
        # feature: (DCLP3 median, TimSim median, standardised shift)
        "pct_above_180": (24.65, 16.49, -0.54),
        "mean": (150.64, 142.27, -0.42),
        "max": (259.00, 239.04, -0.38),
        "sd": (43.60, 38.53, -0.33),
        "jitter": (4.39, 5.53, +0.23),
        "pct_below_70": (0.00, 0.69, +0.22),
        "acf30": (0.84, 0.84, +0.03),
        "acf60": (0.58, 0.58, -0.03),
    },
    "reading": "separable, and the axis is hyperglycaemia: the simulated population is "
               "better controlled than real closed-loop users",
}


# ------------------------------------------------------------------------ checks
def check_the_test_is_calibrated(results, seed=0):
    """Split one cohort in two and the classifier must do no better than chance groups.

    Chance here is not 0.5. Two halves of a cohort are two groups of different people, and
    people differ, so a classifier separates them. What the test has to show is that it
    separates them no better than it separates a random regrouping of the same people,
    which is what the subject-level permutation null measures.

    Without this the test has no null and its verdict on real data would mean nothing.
    """
    half = len(results) // 2
    a, ga = result_windows(results[:half])
    b, gb = result_windows(results[half:])
    out = discriminability(a, b, ga, gb, seed=seed)
    ok = np.isfinite(out["auc"]) and out["auc"] <= out["null_auc_p95"]
    return {"check": "the discriminability test cannot separate a cohort from itself",
            "level": 3, "value": float(out["auc"]),
            "target": "at or below the 95th percentile of the subject-permuted null",
            "pass": bool(ok),
            "note": f"held-out AUC {out['auc']:.3f} against a subject-permuted null of "
                    f"{out['null_auc_median']:.3f} (95th percentile "
                    f"{out['null_auc_p95']:.3f}), p {out['p_value']:.3f}, "
                    f"{out['n_subjects'][0]} against {out['n_subjects'][1]} subjects"}


def check_the_test_detects_a_missing_mechanism(full, ablated, seed=0):
    """The classifier must separate the full simulator from one with layers removed.

    This is the power half of the calibration. A test that cannot see the difference
    between the full model and a model missing unannounced meals, rescue carbohydrate and
    sensor artefacts is not sensitive enough to be pointed at real data and believed when
    it returns a null.
    """
    a, ga = result_windows(full)
    b, gb = result_windows(ablated)
    out = discriminability(a, b, ga, gb, seed=seed)
    clears = np.isfinite(out["auc"]) and out["auc"] > max(out["null_auc_p95"], 0.70)
    return {"check": "the discriminability test detects a simulator missing mechanisms",
            "level": 3, "value": float(out["auc"]),
            "target": "above 0.70 and above the subject-permuted null",
            "pass": bool(clears),
            "note": f"held-out AUC {out['auc']:.3f} against a null 95th percentile of "
                    f"{out['null_auc_p95']:.3f}, p {out['p_value']:.3f}, "
                    f"carried by {', '.join(out['top_features'])}"}


def coverage(real_per_user, simulated_per_user):
    """How far each population reaches into the other, statistic by statistic.

    Takes per-user values rather than cohort medians, which is what this repository does
    not currently hold. Reported both ways round on purpose. A simulated population inside
    the real range on every statistic can still be far narrower than the real one, and a
    narrow population is what makes a bench look more decisive than it is.
    """
    out = {}
    for key, real in real_per_user.items():
        sim = np.asarray(simulated_per_user.get(key, []), float)
        real = np.asarray(real, float)
        if not len(sim) or not len(real):
            continue
        out[key] = {
            "real_inside_simulated": float(np.mean((real >= sim.min()) & (real <= sim.max()))),
            "simulated_inside_real": float(np.mean((sim >= real.min()) & (sim <= real.max()))),
            "spread_ratio": float(sim.std() / real.std()) if real.std() else float("nan"),
        }
    return out


def demonstrate(subjects, days=28, seed=0):
    """Run both halves of the calibration on data this package can generate."""
    from ..simulation.run import simulate_cohort

    full = simulate_cohort(subjects, days=days, seed=seed, progress=False)
    bare = simulate_cohort(subjects, days=days, seed=seed, layers=(), progress=False)
    return [check_the_test_is_calibrated(full, seed=seed),
            check_the_test_detects_a_missing_mechanism(full, bare, seed=seed)]


__all__ = ["window_features", "trace_windows", "result_windows", "discriminability",
           "auc", "coverage", "demonstrate", "FEATURE_NAMES",
           "check_the_test_is_calibrated", "check_the_test_detects_a_missing_mechanism"]
