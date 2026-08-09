"""Comparing a simulated cohort against a real one, without the usual mistake.

Nearly every wrong conclusion this package has produced came from comparing two things that
were not measured the same way. Not from bad arithmetic, and not from the simulator: from a
real figure and a simulated figure that looked comparable and were not. Four in a single
week, each of which produced a confident, specific, wrong finding that then drove real work.

    A peak taken as the maximum within each excursion on one side, and as every sample
    above the threshold pooled on the other. Two different statistics with one name.

    The first 28 days of each trial participant against a simulated month. The opening
    month is the run-in, while people settle onto a device they have just been given, and
    it reads 2.8 mg/dL low. Taking the middle 28 days reproduces the full record.

    `Result.bg` against a real continuous monitor. `bg` carries no sensor error, and a
    sensor's error does not merely blur a threshold, it fragments crossings of it: the same
    runs give 100 excursions below 54 mg/dL on the truth and 380 on the reading. This one
    cost an investigation into missing counterregulation and a gate criterion.

    Roughly 18,000 real windows against 1,870 simulated ones, because the trial followed
    people for a median of 164 days and the simulator ran for 28.

So the point of this module is not convenience. It is that a comparison should be hard to
express wrongly. `Cohort` carries what its numbers are and how much of them there is,
`compare` refuses to put two cohorts side by side unless they agree on that, and both sides
go through one statistic function rather than two implementations of the same idea.

None of it helps with the fifth mistake, which was asserting what the model does without
measuring it. Nothing here can catch that.
"""
from dataclasses import dataclass

import numpy as np

# What a series of numbers actually is. A sensor reading and a glucose without sensor error
# are different quantities, and no threshold statistic transfers between them.
READING = "reading"      # a continuous monitor, with its noise, its floor and its lag
TRUTH = "truth"          # glucose as the model knows it, which no field study observes
SIGNALS = (READING, TRUTH)

# Where to take a fixed-length sample of a longer record from. The middle, because the start
# of a trial is the run-in and the end is where people drop out.
MIDDLE, START = "middle", "start"


@dataclass(frozen=True)
class Cohort:
    """Contiguous glucose segments from one population, and what they are.

    `segments` is a sequence of (subject, values). A subject may appear more than once, once
    per uninterrupted stretch of wear, and `compare` groups by it so that a subject with six
    months of data does not count as many people.
    """
    name: str
    signal: str
    sample_minutes: float
    segments: tuple

    def __post_init__(self):
        if self.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, not {self.signal!r}")
        if not self.segments:
            raise ValueError(f"cohort {self.name!r} has no segments")

    @property
    def subjects(self):
        return len({s for s, _ in self.segments})

    @property
    def days(self):
        return sum(len(v) for _, v in self.segments) * self.sample_minutes / 1440.0

    def sample(self, max_days, take=MIDDLE):
        """A fixed number of days per subject, so exposure can be matched between cohorts.

        Taking it from the middle is the default and the reason is empirical: the opening
        month of DCLP3 reads 2.8 mg/dL below the same participants' full records, because
        it is people adapting to a device they have just been given.
        """
        if take not in (MIDDLE, START):
            raise ValueError(f"take must be {MIDDLE!r} or {START!r}")
        budget = int(round(max_days * 1440.0 / self.sample_minutes))
        by_subject = {}
        for subject, values in self.segments:
            by_subject.setdefault(subject, []).append(np.asarray(values, float))

        out = []
        for subject, chunks in by_subject.items():
            total = sum(len(c) for c in chunks)
            skip = max((total - budget) // 2, 0) if take == MIDDLE else 0
            left = budget
            for chunk in chunks:
                if skip >= len(chunk):
                    skip -= len(chunk)
                    continue
                chunk = chunk[skip:]
                skip = 0
                if left <= 0:
                    break
                out.append((subject, chunk[:left]))
                left -= len(out[-1][1])
        return Cohort(self.name, self.signal, self.sample_minutes, tuple(out))


# ------------------------------------------------------------------- building cohorts
def from_results(results, signal=READING, name="simulated"):
    """A cohort from `simulate_cohort` output.

    `signal` chooses which series, and it is the argument to get right: READING takes
    `Result.cgm`, what the algorithm and the person acted on, and TRUTH takes `Result.bg`,
    which is interstitial glucose without sensor error and which nothing in the field
    measures. Compare against a trial on READING.
    """
    if signal not in SIGNALS:
        raise ValueError(f"signal must be one of {SIGNALS}, not {signal!r}")
    attr = "cgm" if signal == READING else "bg"
    steps = {float(r.sample_time) for r in results}
    if len(steps) != 1:
        raise ValueError(f"cohort mixes sample intervals {sorted(steps)}")
    segments = tuple((r.name, np.asarray(getattr(r, attr), float)) for r in results
                     if len(getattr(r, attr)))
    return Cohort(name, signal, steps.pop(), segments)


def from_dclp3(arm=None, calibration_only=True, source=None, name=None,
               min_days=7.0, max_gap_minutes=8.0, min_segment=288):
    """A cohort from the DCLP3 trial, split into uninterrupted stretches of wear.

    Always READING: the trial records a continuous monitor and there is no ground truth in
    it. A gap longer than `max_gap_minutes` ends a segment, so a break in wear is never read
    as an excursion.
    """
    from . import dclp3

    arm = dclp3.CLOSED_LOOP if arm is None else arm
    ids = set(dclp3.roster().query(f"trtGroup == '{arm}'").PtID)
    if calibration_only:
        ids &= set(dclp3.split()["calibration"])
    traces = dclp3.traces(participants=ids, source=source or dclp3.DEFAULT_SOURCE,
                          min_days=min_days, max_gap_minutes=max_gap_minutes,
                          min_segment=min_segment)
    segments = tuple((participant, np.asarray(values, float))
                     for participant, segs in sorted(traces.items())
                     for _, values in segs)
    label = name or f"DCLP3 {arm}" + (" calibration half" if calibration_only else "")
    return Cohort(label, READING, 5.0, segments)


# ------------------------------------------------------------------------ statistics
def episodes(values, sample_minutes, threshold, below=True):
    """Every uninterrupted run past a threshold, as (minutes, peak).

    One function, used on both sides of every comparison. The peak is the extreme within
    the episode, not every sample past the threshold pooled: pooling lets one long
    excursion contribute hundreds of samples and drown out the short ones, which is a
    different statistic that has been reported under the same name.
    """
    v = np.asarray(values, float)
    past = v < threshold if below else v >= threshold
    out, start = [], None
    for i, flag in enumerate(np.append(past, False)):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            window = v[start:i]
            out.append(((i - start) * sample_minutes,
                        float(window.min() if below else window.max())))
            start = None
    return out


def episode_stats(threshold=54.0, below=True):
    """A statistic over a cohort: how often excursions happen and how long they last."""
    def statistic(cohort):
        found, minutes = [], 0.0
        for _, values in cohort.segments:
            found += episodes(values, cohort.sample_minutes, threshold, below)
            minutes += len(values) * cohort.sample_minutes
        days = minutes / 1440.0
        if not found:
            return {"episodes": 0, "per_day": 0.0, "days": days}
        durations = np.array([d for d, _ in found])
        peaks = np.array([p for _, p in found])
        return {"episodes": len(found), "per_day": len(found) / days, "days": days,
                "median_minutes": float(np.median(durations)),
                "p90_minutes": float(np.percentile(durations, 90)),
                "p99_minutes": float(np.percentile(durations, 99)),
                "max_minutes": float(durations.max()),
                "total_minutes_per_day": float(durations.sum() / days),
                "median_peak": float(np.median(peaks))}
    statistic.__name__ = f"episodes_{'below' if below else 'above'}_{threshold:.0f}"
    return statistic


def time_in_band(lo=70.0, hi=180.0):
    """Percentage of samples in, below and above a band, pooled across the cohort."""
    def statistic(cohort):
        v = np.concatenate([values for _, values in cohort.segments])
        return {"in_range": float(np.mean((v >= lo) & (v < hi)) * 100),
                "below": float(np.mean(v < lo) * 100),
                "above": float(np.mean(v >= hi) * 100),
                "mean": float(v.mean()), "days": cohort.days}
    statistic.__name__ = f"time_in_{lo:.0f}_{hi:.0f}"
    return statistic


# --------------------------------------------------------------------------- comparing
def compare(real, simulated, statistic, match_exposure=True, take=MIDDLE,
            allow_signal_mismatch=False):
    """Put two cohorts side by side, having checked they can be.

    Refuses a comparison across signals, because a reading and a glucose without sensor
    error are different quantities and a threshold statistic does not transfer between
    them. `allow_signal_mismatch` exists so that the difference can be measured
    deliberately, and it is recorded in the result when used.

    `match_exposure` caps the longer record to the shorter one, per subject, so a trial
    that followed people for half a year is not compared with a simulated month.
    """
    for cohort in (real, simulated):
        if not isinstance(cohort, Cohort):
            raise TypeError("compare takes Cohort objects; build them with from_results "
                            "or from_dclp3 so the signal travels with the numbers")
    if real.sample_minutes != simulated.sample_minutes:
        raise ValueError(f"sample intervals differ: {real.sample_minutes} against "
                         f"{simulated.sample_minutes} minutes")
    if real.signal != simulated.signal and not allow_signal_mismatch:
        raise ValueError(
            f"{real.name} is {real.signal} and {simulated.name} is {simulated.signal}. "
            "These are different quantities: a sensor's error fragments threshold "
            "crossings, so episode counts and durations do not transfer between them. "
            "Use from_results(..., signal=compare.READING) to compare against a trial, "
            "or pass allow_signal_mismatch=True to measure the difference on purpose.")

    if match_exposure:
        days_each = min(real.days / max(real.subjects, 1),
                        simulated.days / max(simulated.subjects, 1))
        real, simulated = real.sample(days_each, take), simulated.sample(days_each, take)

    out = {"statistic": getattr(statistic, "__name__", "statistic"),
           "real": {"name": real.name, "subjects": real.subjects, "days": real.days,
                    **statistic(real)},
           "simulated": {"name": simulated.name, "subjects": simulated.subjects,
                         "days": simulated.days, **statistic(simulated)},
           "signal": real.signal if real.signal == simulated.signal else
                     f"{real.signal} against {simulated.signal}",
           "exposure_matched": bool(match_exposure)}
    if real.signal != simulated.signal:
        out["warning"] = ("signals differ, so these figures are not like for like and the "
                          "difference between them is partly the measurement")
    return out


def report(result):
    """The comparison as text, with the exposure and the signal it must be quoted with."""
    keys = [k for k in result["real"]
            if k not in ("name", "subjects", "days") and isinstance(result["real"][k],
                                                                    (int, float))]
    width = max(len(k) for k in keys) if keys else 10
    lines = [f"{result['statistic']}, measured on {result['signal']}",
             f"  {result['real']['name']}: {result['real']['subjects']} subjects, "
             f"{result['real']['days']:.0f} days",
             f"  {result['simulated']['name']}: {result['simulated']['subjects']} subjects, "
             f"{result['simulated']['days']:.0f} days",
             "",
             f"  {'':<{width}} {'real':>12} {'simulated':>12}"]
    for key in keys:
        lines.append(f"  {key:<{width}} {result['real'][key]:12.2f} "
                     f"{result['simulated'][key]:12.2f}")
    if "warning" in result:
        lines += ["", f"  warning: {result['warning']}"]
    return "\n".join(lines)





# ------------------------------------------------------------- per-subject coverage
# The clinical zones, from the consensus continuous-glucose targets. Visentin et al. state
# the criterion in terms of zones rather than of a single summary, and the reason is that a
# virtual subject can match a real one on time in range while spending its time out of range
# at the opposite end.
ZONES = ((0.0, 54.0, "below_54"), (54.0, 70.0, "below_70"), (70.0, 180.0, "in_range"),
         (180.0, 250.0, "above_180"), (250.0, 1e9, "above_250"))


def subject_profile(values):
    """One subject's outcome vector: time in each clinical zone, plus level and spread."""
    v = np.asarray(values, float)
    out = {name: float(np.mean((v >= lo) & (v < hi)) * 100) for lo, hi, name in ZONES}
    out["mean"] = float(v.mean())
    out["cv"] = float(100.0 * v.std() / v.mean()) if v.mean() else 0.0
    return out


def profiles(cohort):
    """Outcome vectors per subject, pooling a subject's separate stretches of wear."""
    joined = {}
    for subject, values in cohort.segments:
        joined.setdefault(subject, []).append(np.asarray(values, float))
    return {s: subject_profile(np.concatenate(v)) for s, v in joined.items()}


def coverage(real, simulated, tolerance=1.0, keys=None):
    """Does a virtual subject exist for each real one, and is the spread right?

    This is the criterion the simulator's own authors used. Visentin et al. validated
    against a clinical trial by asking, for each real subject, whether a virtual subject
    exists behaving similarly in the same clinical zones, rather than by asking whether the
    cohort medians agree. The two are different claims and only the first is about
    replicating people.

    A real subject is covered when some virtual subject matches it on every statistic to
    within `tolerance` standard deviations of the real population's own spread. Distance is
    the largest standardised difference rather than the average, because a virtual subject
    that matches on four zones and is wildly out on the fifth has not matched.

    Reported both ways round on purpose. A population that covers every real subject can
    still contain subjects no real person resembles, and one that is entirely plausible can
    still be far narrower than reality. A narrow population is what makes a bench look more
    decisive than it is.
    """
    if real.signal != simulated.signal:
        raise ValueError(f"{real.name} is {real.signal} and {simulated.name} is "
                         f"{simulated.signal}; coverage compares outcomes, and a sensor "
                         "reading and a glucose without sensor error are not the same "
                         "outcome")
    rp, sp = profiles(real), profiles(simulated)
    keys = list(keys or [name for _, _, name in ZONES] + ["mean", "cv"])

    r = np.array([[rp[s][k] for k in keys] for s in sorted(rp)], float)
    m = np.array([[sp[s][k] for k in keys] for s in sorted(sp)], float)
    scale = r.std(0)
    scale[scale == 0] = 1.0

    # largest standardised difference between every real subject and every virtual one
    d = np.abs((r[:, None, :] - m[None, :, :]) / scale).max(axis=2)
    nearest_sim = d.min(axis=1)
    nearest_real = d.min(axis=0)

    return {
        "statistic": "per-subject coverage",
        "tolerance_sd": float(tolerance),
        "real": {"name": real.name, "subjects": len(rp)},
        "simulated": {"name": simulated.name, "subjects": len(sp)},
        "real_covered": float(np.mean(nearest_sim <= tolerance)),
        "simulated_plausible": float(np.mean(nearest_real <= tolerance)),
        "median_distance_to_nearest": float(np.median(nearest_sim)),
        "spread_ratio": {k: float(m[:, i].std() / scale[i]) for i, k in enumerate(keys)},
        "uncovered": [s for s, dist in zip(sorted(rp), nearest_sim) if dist > tolerance],
        "worst": {s: {**rp[s], "distance": float(dist)}
                  for s, dist in sorted(zip(sorted(rp), nearest_sim),
                                        key=lambda x: -x[1])[:3]},
    }


# Measured 2026-08-09 against the 67 closed-loop calibration participants, 28 days each,
# at a tolerance of one standard deviation of the real population's own spread.
#
# The two directions behave completely differently and that is the finding. Coverage grows
# with how many subjects are run, because every extra subject is another chance to resemble
# someone. Plausibility does not move at all: about 72% of virtual subjects resemble a real
# participant whether ten or a hundred are drawn, because it is a property of what the
# population is made of rather than of how much of it is used.
#
# So the two questions are separable. "Can this population represent real people" is
# answered by running more of it, and at a hundred subjects the answer is 91%. "Is this
# population made of real people" is not, and the answer is that between a quarter and a
# third of it resembles nobody in the trial, which no amount of running fixes.
AGAINST_DCLP3 = {
    "real_participants": 67, "days": 28, "tolerance_sd": 1.0,
    # subjects run: (real covered, virtual plausible)
    "by_cohort_size": {10: (0.472, 0.730), 20: (0.669, 0.740), 34: (0.725, 0.715),
                       50: (0.830, 0.712), 75: (0.875, 0.713), 100: (0.910, 0.720)},
    "median_distance_sd": 0.57,
    "uncovered_participants": 6,
    "completed": (98, 100),
    "spread_ratio": {"below_54": 2.74, "below_70": 1.38, "in_range": 0.81,
                     "above_180": 0.76, "above_250": 0.78, "mean": 0.59, "cv": 1.67},
    # The spread ratios above are inflated by run-to-run noise and the mean-glucose one
    # substantially. Running eight subjects at four seeds each separates the two: the
    # spread between subjects is 7.43 mg/dL of mean glucose and the spread within one
    # subject across seeds is 5.89, a ratio of 1.26. Changing which random meals and
    # sensor noise a subject gets moves its mean glucose nearly as far as changing which
    # subject it is.
    #
    # Removing that component leaves a true between-subject spread near 6 to 7 mg/dL
    # against an implied 14.2 in the trial, so the population carries about 45% of the
    # real between-subject variation rather than the 59% measured on a single seed. A
    # comparison averaged over this population is averaging over less person-to-person
    # difference than it appears to.
    "seed_versus_subject": {"between_subject_sd": 7.43, "within_subject_sd": 5.89,
                            "ratio": 1.26, "subjects": 8, "seeds": 4,
                            "true_between_sd": (5.99, 6.82),
                            "real_sd_implied": 14.24,
                            "spread_ratio_physiology_only": (0.42, 0.48)},
    "reading": "the population can stand in for 91% of the trial's participants when all "
               "of it is run, and about 28% of it resembles nobody in the trial at any "
               "size; mean glucose varies about half as much between subjects as it should "
               "and time below 54 nearly three times as much",
}


def coverage_report(result):
    lines = [f"per-subject coverage at {result['tolerance_sd']:.1f} standard deviations",
             f"  {result['real']['name']}: {result['real']['subjects']} subjects",
             f"  {result['simulated']['name']}: {result['simulated']['subjects']} subjects",
             "",
             f"  real subjects with a virtual counterpart   "
             f"{result['real_covered'] * 100:5.1f}%",
             f"  virtual subjects resembling a real one     "
             f"{result['simulated_plausible'] * 100:5.1f}%",
             f"  median distance to the nearest, in sd      "
             f"{result['median_distance_to_nearest']:5.2f}",
             "",
             "  spread against the real population, 1.0 is equal:"]
    for k, v in result["spread_ratio"].items():
        lines.append(f"    {k:<12} {v:5.2f}")
    if result["uncovered"]:
        lines += ["", f"  {len(result['uncovered'])} real subjects nothing resembles"]
    return "\n".join(lines)


__all__ = ["Cohort", "compare", "report", "from_results", "from_dclp3", "episodes",
           "episode_stats", "time_in_band", "coverage", "coverage_report", "profiles",
           "subject_profile", "ZONES", "READING", "TRUTH", "MIDDLE", "START"]
