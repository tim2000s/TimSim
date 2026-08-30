"""Trough to peak for a meal, defined once so both sides of the comparison read the same thing.

The real side runs in SQL against 132 million CGM readings, because pulling them into Python to
measure a hundred thousand meals would be absurd. The simulated side runs here. Two
implementations of one definition is the arrangement that produced most of the entries in
`docs/ISSUES.md`, so `tests/test_meal_shape.py` pulls a sample of real subjects through both and
requires them to agree exactly. That test is the only thing making the comparison auditable, and
a change to either implementation is finished when it passes.

The definition. A carbohydrate event is an index meal if its size is inside the band and no other
carbohydrate event falls between `clear_before_min` before it and `window_min` after it. The peak
is the highest glucose in the window that follows it, and the trough is the lowest glucose at or
before that peak, both resolved to the earliest time on a tie. Trough to peak is the interval
between them, which is the duration of the rise.

The peak is taken from the absolute trace. `examples/meal_with_bolus.py` took it from the
difference against a counterfactual run of the same subject eating nothing, which no real trace
has, so the two sides were locating the same landmark by different methods. Its docstring already
said the absolute trace was the right choice.

Rescue carbohydrate counts as a carbohydrate event for the isolation test and never as an index
meal. A real person logging 15 g for a low puts it in the same field as a meal, so the simulated
side has to treat it the same way or it admits meals the real side would have rejected.
"""
import numpy as np

# The band the simulated 60 g meal sits inside, and the same band the real side selects on.
GRAMS = (30.0, 90.0)
CLEAR_BEFORE_MIN = 120.0
WINDOWS = (180, 240, 300, 360, 480, 720)
COVERAGE = 0.8
STEP_MIN = 5.0


def shapes(index_events, carb_minutes, minutes, glucose, window_min,
           clear_before_min=CLEAR_BEFORE_MIN, grams=GRAMS, coverage=COVERAGE,
           step_min=STEP_MIN):
    """Trough to peak for every isolated index meal in one trace.

    `index_events` is (minute, grams) for the meals that may be indexed. `carb_minutes` is every
    carbohydrate event including snacks and rescues, which is what isolation is tested against.
    Returns one record per admitted meal, and records why nothing was admitted rather than
    returning an empty list silently.
    """
    minutes = np.asarray(minutes, float)
    glucose = np.asarray(glucose, float)
    carbs = np.sort(np.asarray(carb_minutes, float))
    need = int((window_min / step_min) * coverage)

    out, rejected = [], {"size": 0, "isolation": 0, "coverage": 0}
    for t, g in index_events:
        t = float(t)
        if not (grams[0] <= float(g) <= grams[1]):
            rejected["size"] += 1
            continue
        # Strict inequalities on both sides, and events sharing a minute with the index do not
        # break it, which is how the SQL reads. Two entries logged at the same instant are one
        # event split in two rather than two meals.
        near = carbs[(carbs > t - clear_before_min) & (carbs < t + window_min) & (carbs != t)]
        if near.size:
            rejected["isolation"] += 1
            continue
        sel = (minutes >= t) & (minutes <= t + window_min)
        if int(np.count_nonzero(sel)) < need:
            rejected["coverage"] += 1
            continue
        wm, wg = minutes[sel], glucose[sel]
        peak_i = int(np.argmax(wg))               # argmax takes the earliest on a tie
        trough_i = int(np.argmin(wg[:peak_i + 1]))
        out.append({"minute": t, "grams": float(g),
                    "trough_to_peak_min": float(wm[peak_i] - wm[trough_i]),
                    "trough_at_index": bool(trough_i == 0),
                    "peak_mgdl": float(wg[peak_i]), "trough_mgdl": float(wg[trough_i]),
                    "hour": float((t / 60.0) % 24.0)})
    return out, rejected


def per_person(values, min_meals=20):
    """The two components, kept apart. Returns None when the person has too few meals.

    Within-person spread is the interquartile range of one person's own meals. Between-person
    spread is what the distribution of these medians carries. The real data says the first is
    the larger of the two, and a simulated subject eating one meal has none of it.
    """
    v = np.asarray(values, float)
    if v.size < min_meals:
        return None
    return {"meals": int(v.size), "median": float(np.median(v)),
            "iqr": float(np.percentile(v, 75) - np.percentile(v, 25))}


def summarise(per_subject):
    """Between-person and within-person components as tenth, fiftieth and ninetieth percentiles."""
    med = [p["median"] for p in per_subject]
    iqr = [p["iqr"] for p in per_subject]
    q = lambda v, p: float(np.percentile(np.asarray(v, float), p)) if v else float("nan")
    return {"subjects": len(per_subject), "meals": int(sum(p["meals"] for p in per_subject)),
            "between_person_median": [q(med, 10), q(med, 50), q(med, 90)],
            "within_person_iqr": [q(iqr, 10), q(iqr, 50), q(iqr, 90)]}
