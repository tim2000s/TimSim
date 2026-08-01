"""Eleven statistics that distinguish a real glucose trace from a simulated one.

Each is computed identically on real data and on simulator output, so the two are
directly comparable. They were chosen because each is sensitive to a different mechanism,
and between them they cover what a simulator has to get right before a controller
comparison run on it means anything:

    cv          how wide the glucose distribution is
    tail        how often glucose jumps, which unannounced meals drive
    acf30/60    how fast the curve decorrelates, which says how predictable it is
    outcome     the spread of where you end up 30 minutes after a stuck high, which is
                where varying insulin efficacy shows up
    diurnal     the peak-to-trough of the hour-of-day mean
    hypo_rec    how fast a low recovers, which carbohydrate treatment drives
    hypo_reb    how often that recovery overshoots
    compress    sharp reversing dips from lying on the sensor
    noise       high-frequency measurement jitter
    drift       how much the sensitivity setting moves week to week

Every function takes a dict with keys `t` (seconds), `bg` (mg/dL) and `hour`, on a
five-minute grid, and returns a scalar. `evaluate` runs the set over a list of subjects
and returns each statistic with a bootstrap interval.

The real-world reference ranges in `REAL_RANGE` were measured across 192 users of four
different closed-loop systems. A simulator statistic outside its range is a gap; whether
that gap matters depends on which question is being asked of the simulator.
"""
import numpy as np

# Measured across four real cohorts, 192 users. Min and max of the per-cohort medians.
REAL_RANGE = {
    "cv": (29.5, 34.3),
    "tail": (3.7, 6.6),
    "acf30": (0.78, 0.87),
    "acf60": (0.50, 0.68),
    "outcome": (26.5, 33.5),
    "diurnal": (34.7, 56.3),
    "hypo_rec": (50.0, 59.0),
    "hypo_reb": (23.2, 28.4),
    "compress": (1.9, 5.3),
    "noise": (4.5, 6.7),
    "drift": (8.2, 21.7),
}

UNITS = {"cv": "%", "tail": "%", "acf30": "", "acf60": "", "outcome": "mg/dL",
         "diurnal": "mg/dL", "hypo_rec": "min", "hypo_reb": "%", "compress": "/30d",
         "noise": "mg/dL", "drift": "%CV"}


# ------------------------------------------------------------- per-user signatures
def _deltas(d, lo=240, hi=360):
    dt, dbg = np.diff(d["t"]), np.diff(d["bg"])
    return dbg[(dt >= lo) & (dt <= hi)]


def _lag_corr(t, bg, lag_s, tol=90):
    """Autocorrelation at a time lag, gap-robust: match each sample to one lag_s later."""
    j = np.searchsorted(t, t + lag_s)
    j = np.clip(j, 0, len(t) - 1)
    ok = np.abs(t[j] - (t + lag_s)) <= tol
    if ok.sum() < 50:
        return np.nan
    x, y = bg[ok], bg[j][ok]
    xm, ym = x.mean(), y.mean()
    denom = np.sqrt(((x - xm) ** 2).sum() * ((y - ym) ** 2).sum())
    return float(((x - xm) * (y - ym)).sum() / denom) if denom else np.nan


def _within_band_outcome_sd(d, lo=180, hi=240, horizon=1800, tol=240, minn=200):
    t, bg = d["t"], d["bg"]
    j = np.clip(np.searchsorted(t, t + horizon), 0, len(t) - 1)
    good = np.abs(t[j] - (t + horizon)) <= tol
    inband = (bg >= lo) & (bg < hi) & good
    if inband.sum() < minn:
        return np.nan
    return float((bg[j][inband] - bg[inband]).std())


def _diurnal_amp(d):
    h, bg = d["hour"], d["bg"]
    prof = np.array([bg[(h >= k) & (h < k + 1)].mean() if np.any((h >= k) & (h < k + 1))
                     else np.nan for k in range(24)])
    prof = prof[np.isfinite(prof)]
    return float(prof.max() - prof.min()) if len(prof) else np.nan


def _hypo(d, dt_hint=300):
    t, bg = d["t"], d["bg"]
    below = bg < 70
    onset = np.where(below[1:] & ~below[:-1])[0] + 1
    rec, reb = [], []
    for i in onset:
        end = min(i + 40, len(bg) - 1)
        st, sb = t[i:end + 1], bg[i:end + 1]
        r = np.where(sb >= 100)[0]
        if not len(r):
            continue
        rec.append((st[r[0]] - st[0]) / 60.0)
        r2 = min(r[0] + 25, len(sb) - 1)
        reb.append(bool(np.any(sb[r[0]:r2 + 1] > 180)))
    if not rec:
        return np.nan, np.nan
    return float(np.median(rec)), float(np.mean(reb))


def _compression_rate(d):
    t, bg = d["t"], d["bg"]
    below = bg < 70
    onset = np.where(below[1:] & ~below[:-1])[0] + 1
    n = 0
    for i in onset:
        pre = bg[max(0, i - 4):i].mean() if i >= 1 else bg[i]
        w = min(i + 6, len(bg) - 1)
        seg = bg[i:w + 1]
        nadir = seg.min()
        if seg[-1] >= pre - 15 and pre >= 85 and (pre - nadir) > 25:
            n += 1
    span = (t[-1] - t[0]) / 86400.0 if len(t) > 1 else 1
    return 30.0 * n / max(span, 1)


def _noise_jitter(d, lo=240, hi=360):
    t, bg = d["t"], d["bg"]
    d2 = np.diff(np.diff(bg))
    g = np.diff(t)
    ok = (g[:-1] >= lo) & (g[:-1] <= hi) & (g[1:] >= lo) & (g[1:] <= hi)
    return float(np.std(d2[ok])) if np.any(ok) else np.nan


# Each signature: (key, label, per-user fn(d)->scalar, higher_is_lower_freq?) ; drift/exercise special
SIGS = [
    ("cv",          "Glucose variability (CV%)",              lambda d: 100 * d["bg"].std() / d["bg"].mean()),
    ("tail",        "Rise tail P(Δ>10 mg/dL / 5min) %",       lambda d: 100 * np.mean(_deltas(d) > 10) if len(_deltas(d)) else np.nan),
    ("acf30",       "Autocorrelation @30 min",                lambda d: _lag_corr(d["t"], d["bg"], 1800)),
    ("acf60",       "Autocorrelation @60 min",                lambda d: _lag_corr(d["t"], d["bg"], 3600)),
    ("outcome",     "Outcome SD @stuck-high +30min (mg/dL)",  _within_band_outcome_sd),
    ("diurnal",     "Diurnal amplitude (mg/dL)",              _diurnal_amp),
    ("hypo_rec",    "Hypo recovery to 100 (min)",             lambda d: _hypo(d)[0]),
    ("hypo_reb",    "Hypo rebound >180 %",                    lambda d: 100 * _hypo(d)[1] if np.isfinite(_hypo(d)[1]) else np.nan),
    ("compress",    "Compression lows / 30d",                 _compression_rate),
    ("noise",       "Sensor jitter (2nd-diff SD)",            _noise_jitter),
]


def boot_ci(vals, stat=np.median, n=2000, seed=0):
    vals = np.asarray([v for v in vals if np.isfinite(v)], float)
    if len(vals) == 0:
        return (np.nan, np.nan, np.nan)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(vals), size=(n, len(vals)))
    bs = np.array([stat(vals[i]) for i in idx])
    return float(stat(vals)), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))




def from_result(result):
    """Pack a simulation Result onto the five-minute grid the signatures assume."""
    cgm = np.asarray(result.cgm, float)
    t_native = np.arange(len(cgm)) * result.sample_time * 60.0
    grid = np.arange(0, t_native[-1] + 1, 300.0)
    bg = np.interp(grid, t_native, cgm)
    return dict(t=grid, bg=bg, hour=(grid / 3600.0) % 24)


def evaluate(results, drift=None, seed=0):
    """Every signature over a cohort, as {key: (median, lo, hi)}.

    `drift` is the per-subject weekly sensitivity CV, which is a property of the
    algorithm rather than of the trace and so cannot be read off the glucose.
    """
    packed = [from_result(r) if hasattr(r, "cgm") else r for r in results]
    out = {key: boot_ci([fn(d) for d in packed], seed=seed + i)
           for i, (key, _, fn) in enumerate(SIGS)}
    if drift is None:
        drift = [getattr(r, "isf_weekly_cv", np.nan) for r in results]
    finite = [v for v in drift if np.isfinite(v)]
    out["drift"] = boot_ci(finite, seed=seed + 99) if finite else (0.0, 0.0, 0.0)
    return out


def in_real_range(key, value, pad=0.10):
    """Whether a value sits inside the real range, with a small tolerance.

    The real range is the spread of four cohort medians, which is narrow enough that an
    exact test is harsher than the measurement supports. The tolerance is stated rather
    than silently applied.
    """
    lo, hi = REAL_RANGE[key]
    span = hi - lo
    return bool(lo - pad * span - 1e-9 <= value <= hi + pad * span + 1e-9)


def report(stats, pad=0.10):
    """A plain table of every signature against its real range."""
    lines = [f"{'signature':<12} {'real range':>14} {'measured':>22}  verdict"]
    for key, label, _ in SIGS + [("drift", "ISF drift", None)]:
        if key not in stats:
            continue
        lo, hi = REAL_RANGE[key]
        v, l, h = stats[key]
        ok = "in range" if in_real_range(key, v, pad) else "OUT"
        lines.append(f"{key:<12} {lo:6.1f}-{hi:<7.1f} "
                     f"{v:8.2f} [{l:6.2f}-{h:6.2f}]  {ok}")
    return "\n".join(lines)


__all__ = ["SIGS", "REAL_RANGE", "UNITS", "evaluate", "report", "in_real_range",
           "from_result", "boot_ci"]
