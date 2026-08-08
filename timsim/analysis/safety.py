"""What to read off a run when the question is safety rather than fidelity.

Time in range is the wrong thing to lead on. Level 2 of the validation suite shows why:
the simulated person defends against lows with carbohydrate, so an algorithm that doses
too hard can hold its mean glucose steady while driving the person through repeated
rescues. Judged on time in range it looks fine. Judged on rescue carbohydrate and minutes
below 54 it does not.

Everything here is computed per subject. A cohort median is the wrong summary for a safety
question, because an algorithm that is excellent for 95 subjects and dangerous for five is
not an acceptable algorithm and a median conceals that completely. `worst_of` gives the
tail summaries that belong in a verdict.

Glucose figures come from `Result.bg`, the underlying blood glucose, rather than from the
sensor trace. A compression low is a false reading and should not count as hypoglycaemia,
and an algorithm that causes a real low which its own sensor understates should not get
credit for it.
"""
import numpy as np

SEVERE_MGDL = 54.0
LOW_MGDL = 70.0
HIGH_MGDL = 180.0
VERY_HIGH_MGDL = 250.0


def _risk(bg):
    """Kovatchev's symmetrising transform, the basis of LBGI and HBGI."""
    bg = np.clip(np.asarray(bg, float), 20.0, 600.0)
    f = 1.509 * (np.log(bg) ** 1.084 - 5.381)
    return 10.0 * f ** 2, f


def lbgi_hbgi(bg):
    """Low and high blood glucose indices. Asymmetric by design: LBGI weights lows."""
    r, f = _risk(bg)
    return float(np.mean(np.where(f < 0, r, 0.0))), float(np.mean(np.where(f > 0, r, 0.0)))


def _episodes(below, sample_minutes, min_minutes=15.0):
    """Runs of consecutive True lasting at least `min_minutes`, as durations."""
    out, run = [], 0
    for flag in np.append(np.asarray(below, bool), False):
        if flag:
            run += 1
        else:
            if run:
                out.append(run * sample_minutes)
            run = 0
    return [d for d in out if d >= min_minutes]


def summarise(result):
    """The safety record of one run."""
    bg = np.asarray(result.bg, float)
    dt = float(result.sample_time)
    days = max(len(bg) * dt / 1440.0, 1e-9)

    severe = _episodes(bg < SEVERE_MGDL, dt)
    low = _episodes(bg < LOW_MGDL, dt)
    lbgi, hbgi = lbgi_hbgi(bg)

    insulin = np.asarray(getattr(result, "insulin_series", []), float)
    per_hour = 0.0
    if len(insulin):
        width = max(int(round(60.0 / dt)), 1)
        if len(insulin) >= width:
            window = np.convolve(insulin, np.ones(width), mode="valid")
            per_hour = float(window.max())
        else:
            per_hour = float(insulin.sum())

    return {
        "name": result.name,
        "completed": bool(result.completed),
        "days_observed": float(len(bg) * dt / 1440.0),
        "minutes_below_54_per_day": float(np.sum(bg < SEVERE_MGDL) * dt / days),
        "minutes_below_70_per_day": float(np.sum(bg < LOW_MGDL) * dt / days),
        "severe_episodes_per_day": len(severe) / days,
        "longest_below_54_min": float(max(severe)) if severe else 0.0,
        "longest_below_70_min": float(max(low)) if low else 0.0,
        "minutes_above_250_per_day": float(np.sum(bg >= VERY_HIGH_MGDL) * dt / days),
        "lbgi": lbgi,
        "hbgi": hbgi,
        "rescue_grams_per_day": float(result.rescue_grams) / days,
        "rescue_events_per_day": float(result.rescue_events) / days,
        "insulin_per_day": float(np.nansum(insulin)) / days if len(insulin) else float("nan"),
        "peak_insulin_per_hour_u": per_hour,
        "peak_iob_u": float(result.meta.get("peak_iob_u", float("nan"))),
        "limit_bound": dict(result.meta.get("limit_bound", {})),
        "time_in_range": float(result.time_in_range),
        "mean_bg": float(bg.mean()) if len(bg) else float("nan"),
    }


def cohort(results):
    """Per-subject safety records for a cohort, including any that did not complete."""
    return [summarise(r) for r in results]


def worst_of(records, keys=None):
    """Tail summaries. The median is not the number a safety verdict turns on."""
    keys = keys or ["minutes_below_54_per_day", "minutes_below_70_per_day",
                    "longest_below_54_min", "lbgi", "rescue_grams_per_day",
                    "peak_insulin_per_hour_u", "peak_iob_u"]
    out = {"n_subjects": len(records),
           "n_did_not_complete": sum(1 for r in records if not r["completed"]),
           "subject_days": float(sum(r["days_observed"] for r in records))}
    for k in keys:
        usable = [r for r in records if np.isfinite(np.asarray(r.get(k, np.nan), float))]
        if not usable:
            continue
        vals = np.array([r[k] for r in usable], float)
        out[k] = {"median": float(np.median(vals)),
                  "p90": float(np.percentile(vals, 90)),
                  "worst": float(vals.max()),
                  "worst_subject": usable[int(np.argmax(vals))]["name"],
                  "n_reported": len(usable)}
    return out


def rate_upper_bound(n_events, subject_days, confidence=0.95):
    """A one-sided upper bound on an event rate, per subject-year.

    With zero events observed the bound is the rule of three: three over the exposure. It
    is the number to quote when a bench reports no severe events, because the absence of
    an event over a finite run does not bound the rate anywhere near zero.
    """
    from scipy import stats as sps

    if subject_days <= 0:
        return float("inf")
    upper = sps.chi2.ppf(confidence, 2 * (n_events + 1)) / 2.0
    return float(upper / subject_days * 365.25)


__all__ = ["summarise", "cohort", "worst_of", "lbgi_hbgi", "rate_upper_bound",
           "SEVERE_MGDL", "LOW_MGDL", "HIGH_MGDL"]
