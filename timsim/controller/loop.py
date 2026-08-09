"""The baseline correction loops, neither of which is a shipped algorithm.

Something has to close the loop. Every real cohort these statistics are compared against
is running one, and a simulated person on open-loop basal-bolus is not comparable to them.
This is that something, and it is the baseline rather than the subject: for a comparison of
real algorithms, pass the algorithm under test as `controller` instead.

Two shapes are available, and which one is driving changes any hypoglycaemia figure
substantially.

`trend` is what this package started with: correct towards 120 mg/dL every five minutes on
the current reading, at half the calculated need, bounded by insulin on board, with basal
withdrawn when low or falling. Adding it returned both glucose autocorrelations and glucose
variability to the real range after the behaviour layer had pushed them out, which is what
it was built for.

`control-iq` is shaped like the published description of the algorithm the reference trial
actually ran. It was built to be the default, on the reasoning that a baseline twelve times
more eager to correct than the one in the reference data makes any hypoglycaemia comparison
unreadable. Measured, it is worse on every axis, and it is not the default:

    34 adults, 28 days          trend   control-iq   DCLP3
    time in range %             74.0        75.5      71.0
    time above 180 %            23.9        20.0     24.65
    insulin, U/day              64.9        74.2      47.0
    rescues a day               1.14        2.25      0.44
    severe lows a day           0.35        0.70      0.22

The reason is what Tandem does not publish. The cadence, the thresholds and the correction
fraction are theirs; the basal multiplier when glucose is predicted high, the ceiling on a
single automatic correction, and the prediction itself are not, and those are what drive the
result. Fitting them until the cohort matched DCLP3 would make DCLP3 useless for validating
the person, since the pair would have been tuned to it.

So the eager loop stays the baseline despite having the wrong cadence, and the shaped one
stays available and honest about what it is.

One thing the exercise did find. The first version predicted from a single five-minute
difference, and the sensor error here has a standard deviation near 12 mg/dL, so that
difference carries about 3.4 mg/dL per minute of noise and over 100 mg/dL once extrapolated
half an hour. It fired on noise, delivering 76 U a day. Fitting a least-squares slope over
thirty minutes takes the prediction noise from 101 mg/dL to 14, and any predictive
controller driven from this sensor needs to do something equivalent.

What `control-iq` copies is the published behaviour and nothing else. Tandem describe an
automatic correction bolus at most once an hour when glucose is predicted to exceed 180
mg/dL thirty minutes ahead, delivering 60% of a correction towards 110 mg/dL, and basal
modulated on the same prediction: suspended below 70, reduced below 112.5, usual through
160, increased to 180 and maximum above it. Those numbers are reproduced here. The
prediction is a linear extrapolation of the recent trend, which Tandem's is not, and none of
the rest of the algorithm is known. It is a stand-in with the right cadence and thresholds,
not a reimplementation, and a result that turns on the difference should not be believed.
"""
from dataclasses import dataclass

import numpy as np

from ..therapy.insulin import iob_fraction as _iob_fraction

DIA_MIN = 300.0           # insulin action duration
PEAK_MIN = 75.0           # bilinear activity peak
LOOP_FALL_SUSPEND = -1.5  # mg/dL/min, a fall fast enough to withdraw basal early


@dataclass(frozen=True)
class LoopSettings:
    """What a correction loop does, as numbers rather than as branches."""
    target: float             # what a correction aims at, mg/dL
    correct_above: float      # no correction below this
    correction_fraction: float
    max_correction_u: float
    min_interval_min: float   # between automatic corrections
    max_iob_u: float
    predict_min: float        # minutes ahead the decision is made on, 0 for reactive
    trend_window_min: float   # minutes of history the trend is fitted over
    suspend_below: float      # basal off
    reduce_below: float       # basal halved
    boost_above: float        # basal raised
    max_basal_above: float    # basal at its ceiling
    max_basal_scale: float


TREND = LoopSettings(
    target=120.0, correct_above=150.0, correction_fraction=0.5, max_correction_u=2.0,
    min_interval_min=5.0, max_iob_u=6.0, predict_min=0.0, trend_window_min=0.0,
    suspend_below=80.0, reduce_below=110.0,
    boost_above=float("inf"), max_basal_above=float("inf"), max_basal_scale=1.0)

# Tandem's published description: a correction at most hourly when glucose is predicted to
# exceed 180 thirty minutes out, at 60% of a correction towards 110, and basal suspended
# below 70, reduced below 112.5, raised from 160 and at its ceiling above 180.
CONTROL_IQ = LoopSettings(
    target=110.0, correct_above=180.0, correction_fraction=0.6, max_correction_u=6.0,
    min_interval_min=60.0, max_iob_u=6.0, predict_min=30.0, trend_window_min=30.0,
    suspend_below=70.0, reduce_below=112.5,
    boost_above=160.0, max_basal_above=180.0, max_basal_scale=3.0)

SHAPES = {"trend": TREND, "control-iq": CONTROL_IQ}

# Matches `simulation.run.DEFAULT_CONTROLLER`. Kept in one place because they drifted apart
# once, and a class defaulting to one shape while the simulator defaults to another is a
# difference nothing would report.
DEFAULT_SHAPE = "trend"


class CorrectionLoop:
    """Correction and basal modulation, in one of the shapes in `SHAPES`."""

    def __init__(self, shape=DEFAULT_SHAPE):
        if isinstance(shape, str):
            if shape not in SHAPES:
                raise ValueError(f"unknown loop shape {shape!r}; expected {sorted(SHAPES)}")
            shape = SHAPES[shape]
        self.s = shape
        self.boluses = []          # [(minute, units)]
        self.history = []          # [(minute, reading)] for the trend fit
        self.last_correction = -1e9

    def add(self, minute, units):
        if units > 0:
            self.boluses.append((minute, units))

    def iob(self, minute):
        return float(sum(u * _iob_fraction(minute - m) for m, u in self.boluses))

    def observe(self, minute, cgm):
        """Keep enough readings to fit a trend over, and no more."""
        self.history.append((float(minute), float(cgm)))
        cutoff = minute - max(self.s.trend_window_min, 0.0)
        self.history = [(m, v) for m, v in self.history if m >= cutoff]

    def trend(self, fall_rate):
        """Rate of change in mg/dL per minute, fitted rather than differenced.

        A single five-minute difference is not usable at a thirty-minute horizon. The
        sensor's error here has a standard deviation of about 12 mg/dL, so the difference
        between two consecutive readings carries roughly 17 mg/dL of noise, which is 3.4
        mg/dL per minute, which is over 100 mg/dL once extrapolated half an hour. A
        predictor built on that fires on noise, and the first version of this loop did:
        it delivered 76 U a day against the trial's 47 and produced three times the trial's
        severe hypoglycaemia.

        A least-squares slope over the window averages most of that away.
        """
        if self.s.trend_window_min <= 0 or len(self.history) < 3:
            return float(fall_rate)
        m = np.array([t for t, _ in self.history])
        v = np.array([x for _, x in self.history])
        m = m - m.mean()
        denom = float((m * m).sum())
        return float((m * (v - v.mean())).sum() / denom) if denom > 0 else float(fall_rate)

    def predicted(self, cgm, fall_rate):
        """Where glucose is heading, by extrapolating the fitted trend.

        Tandem's prediction is model-based and unpublished, and this is a stand-in with the
        right horizon rather than a reimplementation.
        """
        return float(cgm + self.trend(fall_rate) * self.s.predict_min)

    def correction(self, minute, cgm, cf, fall_rate=0.0):
        if minute - self.last_correction < self.s.min_interval_min:
            return 0.0
        seen = self.predicted(cgm, fall_rate)
        need = (seen - self.s.target) / cf - self.iob(minute)
        if need <= 0.05 or seen < self.s.correct_above or self.iob(minute) >= self.s.max_iob_u:
            return 0.0
        self.last_correction = minute
        headroom = max(self.s.max_iob_u - self.iob(minute), 0.0)
        dose = min(need * self.s.correction_fraction, self.s.max_correction_u, headroom)
        if dose <= 0.0:
            return 0.0
        self.add(minute, dose)
        return float(dose)

    def basal_scale(self, cgm, fall_rate):
        seen = self.predicted(cgm, fall_rate)
        if seen < self.s.suspend_below or (cgm < self.s.reduce_below
                                           and fall_rate < LOOP_FALL_SUSPEND):
            return 0.0
        if seen < self.s.reduce_below:
            return 0.5
        if seen >= self.s.max_basal_above:
            return self.s.max_basal_scale
        if seen >= self.s.boost_above:
            return 1.0 + (self.s.max_basal_scale - 1.0) * 0.5
        return 1.0
