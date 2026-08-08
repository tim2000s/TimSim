"""The infusion site: a cannula that mostly works, and sometimes quietly does not.

Everything else in this package assumes that insulin leaving the pump reaches the
subcutaneous depot. Real infusion sets do not honour that assumption. A cannula kinks, the
tissue around it scars or inflames, the adhesive lifts, and absorption drops away without
any alarm. The pump log looks perfectly normal throughout, which is what makes it hard.

This matters here because it turned out to be the largest single fidelity gap in the
package. Measured against the closed-loop arm of DCLP3, TimSim reproduced the number of
excursions above 180 mg/dL (3.19 a day against 3.56) and their height (median peak 201
against 210) and still spent only 18.2% of the time above 180 where the trial spent 27.1%.
The whole of that shortfall sat in long episodes: 61% of it in excursions lasting more
than six hours and a further 38% in three to six hours, with everything shorter already
matching. Real participants had 0.73 excursions a day over three hours against TimSim's
0.41, and the longest real one ran for 54 hours.

The shape of those long real excursions says what causes them. Glucose enters them at
about 0.68 mg/dL per minute, which is far too slow for a meal and about right for basal
insulin going missing, plateaus around 242 and peaks around 306, and leaves at about
-0.62 mg/dL per minute. Every one of the 67 participants examined had them, at a median
of 3.8 per 30 days. A functioning closed loop cannot hold someone at 242 for seven hours
while delivering correction, so the insulin was not arriving.

So the model here is absorption failure, not a glucose disturbance. A set that has failed
passes only a fraction of what the pump sends it, and the loop responds by driving basal
up against a ceiling and achieving very little, which is the behaviour the traces show.

Two details are worth stating because they change the numbers.

The insulin still leaves the pump. A failed site loses it between the reservoir and the
plasma, so total daily dose is unaffected and any figure reconstructed from a pump log
looks normal. `Result.insulin_units` therefore continues to report what was delivered,
not what was absorbed, and the difference is recorded separately.

Detection is not instant, and it stalls overnight. People notice a failed site by being
high and not coming down, which takes hours, and they cannot notice it while asleep. That
is not a refinement: the hour-by-hour comparison against DCLP3 showed the deepest part of
the gap between midnight and 04:00, where the trial sat at 35% and 25% above 180 and
TimSim sat at 13% and 11%, while the daytime hours were close. An overnight failure runs
until morning.

What it buys, and what it costs. On 34 adults over 28 days against the same trial half,
time above 180 goes from 18.2% to 23.2% against the trial's 27.1%, the median excursion
lengthens from 55 to 60 minutes against 65 and the 90th percentile from 195 to 250 against
265, and peaks stay where they were (median 202 against 210, p90 282 against 293). Every
hour of the day moves toward the trial. Against that, autocorrelation rises past the
trial's own range, 0.90 at thirty minutes against an interquartile range of 0.85 to 0.89
and 0.73 at sixty against 0.62 to 0.71. That is a real remaining difference and it points
somewhere specific: TimSim's long highs are smoother than real ones, which sit on top of
people correcting, eating and changing sets rather than simply waiting.

Roughly two fifths of the original difference is still unaccounted for, and it is not
spread evenly. The hours after midnight remain well short, 18% against 35% at hour zero,
while breakfast now runs over, 30% against 19% at hour eight. That is a different problem
from this one and probably a physiological rather than a mechanical one.

`examples/hyperglycaemia_gap.py` is the measurement, kept runnable so these figures can be
rechecked instead of trusted. The rates are population figures, and `InfusionSite` takes
different ones.
"""
import numpy as np

# How often a set fails, per subject per 30 days. The DCLP3 calibration participants had a
# median of 3.82 excursions over six hours per 30 days and a 90th percentile of 12.03, so
# the rate has to vary a lot between people as well as having the right average. Site
# trouble does cluster in individuals: scar tissue and body habitus persist, and a subject
# who gets on badly with sets keeps getting on badly with them. The gamma draw below gives
# each subject its own rate for the whole run rather than redrawing it daily.
#
# The figure here is higher than 3.82 because not every failure produces an excursion over
# six hours: a mild one caught in the afternoon shows up in the trial's three-to-six hour
# band instead, and some never cross 180 at all. Calibrated against the whole duration
# distribution rather than the tail, it lands at 7.3 failures per 30 days as run.
FAILURES_PER_30_DAYS = 8.0
SUBJECT_RATE_SHAPE = 1.6

# What still gets through a failed set. Total occlusion is the rare case; the common one is
# a partial loss that leaves the loop apparently working and quietly under-dosing.
#
# This is the parameter the calibration was most sensitive to, and the first pass had it
# too low. A range of 0.05 to 0.45 reproduced the total time above 180 and overshot the
# excursion peaks by 17 mg/dL at the 90th percentile, pushing variability and
# autocorrelation past the trial's own ranges. Milder and more frequent failures match the
# duration distribution as well and the peaks much better.
RESIDUAL_ABSORPTION = (0.25, 0.70)

# Noticing. The person suspects a site once the reading has been above NOTICE_BG for
# NOTICE_MIN continuous minutes, and acts SUSPECT_TO_CHANGE_MIN later, which covers
# fetching a set, changing it and waiting for the new one to prime. NOTICE_BG has to sit
# below the plateau a mild failure produces, or the mild ones are never noticed at all and
# run until the set is due, which puts all of their time into the tail past six hours.
NOTICE_BG = 230.0
NOTICE_MIN = 90.0
SUSPECT_TO_CHANGE_MIN = 45.0

# Asleep. No site gets changed at 03:00 because the pump is quietly failing, so detection
# is suspended overnight and resumes on waking. This is what produces the overnight
# hyperglycaemia the trial shows and the simulator was missing.
ASLEEP_FROM_HOUR = 23.0
ASLEEP_UNTIL_HOUR = 7.0

# Routine changes. A set that has not failed still gets replaced every few days, and a set
# that fails late in its life may be replaced on schedule before anyone notices anything.
SET_LIFE_DAYS = (2.5, 3.5)


def _asleep(minute):
    hour = (minute / 60.0) % 24.0
    return hour >= ASLEEP_FROM_HOUR or hour < ASLEEP_UNTIL_HOUR


class InfusionSite:
    """Absorption at the cannula, as a multiplier on insulin reaching the body.

    Call `absorbed_fraction(minute)` for the multiplier and `observe(minute, reading)` with
    what the person or their system can see. The site does its own detection because a set
    gets changed whether or not the behaviour layer is modelling meals, which keeps the
    layer independently switchable and the ablation clean.
    """

    def __init__(self, rng, failures_per_30_days=FAILURES_PER_30_DAYS,
                 residual=RESIDUAL_ABSORPTION, set_life_days=SET_LIFE_DAYS):
        self.rng = rng
        self.residual_range = residual
        self.set_life_days = set_life_days
        # This subject's own susceptibility, held for the whole run.
        self.rate_per_30d = float(rng.gamma(SUBJECT_RATE_SHAPE,
                                            failures_per_30_days / SUBJECT_RATE_SHAPE))
        self.failures = 0
        self.units_lost = 0.0
        self.failed_minutes = 0.0
        self._fraction = 1.0
        self._suspect_since = None
        self._change_at = None
        self._high_since = None
        self._new_set(0.0)

    def _new_set(self, minute):
        """Fit a set, and decide now whether and when it will fail."""
        life = float(self.rng.uniform(*self.set_life_days)) * 1440.0
        self._expires_at = minute + life
        self._fraction = 1.0
        self._suspect_since = self._change_at = self._high_since = None
        # Probability this particular set fails at some point in its life, from the
        # subject's own rate and how long a set lasts.
        p = min(1.0, self.rate_per_30d * life / (30.0 * 1440.0))
        if self.rng.random() < p:
            self._fails_at = minute + float(self.rng.uniform(0.0, life))
            self._residual = float(self.rng.uniform(*self.residual_range))
        else:
            self._fails_at = None

    def absorbed_fraction(self, minute):
        """The fraction of pumped insulin that reaches the depot at this instant."""
        if self._change_at is not None and minute >= self._change_at:
            self._new_set(minute)
        elif minute >= self._expires_at:
            # Replaced on schedule, which also silently fixes a failure nobody spotted.
            self._new_set(minute)
        elif self._fails_at is not None and minute >= self._fails_at and self._fraction == 1.0:
            self._fraction = self._residual
            self.failures += 1
        return self._fraction

    def observe(self, minute, reading, step_minutes=5.0):
        """Feed the site what is visible, so the person can notice it has gone wrong."""
        if self._fraction < 1.0:
            self.failed_minutes += step_minutes
        if self._change_at is not None:
            return
        if reading is None or reading < NOTICE_BG:
            self._high_since = None
            return
        if self._high_since is None:
            self._high_since = minute
        # Being high for long enough is the signal, but it only registers while awake.
        if not _asleep(minute) and minute - self._high_since >= NOTICE_MIN:
            self._change_at = minute + SUSPECT_TO_CHANGE_MIN

    def apply(self, minute, basal_u_per_min, bolus_u, step_minutes):
        """Attenuate a delivery, returning what the body gets and what the site swallowed.

        The units lost are counted over the step, basal included, because a failing site
        loses most of its insulin through the basal rate rather than through boluses.
        """
        f = self.absorbed_fraction(minute)
        if f >= 1.0:
            return basal_u_per_min, bolus_u, 0.0
        lost = (basal_u_per_min * step_minutes + bolus_u) * (1.0 - f)
        self.units_lost += lost
        return basal_u_per_min * f, bolus_u * f, lost

    def report(self):
        return {"site_failures": self.failures,
                "site_failed_minutes": self.failed_minutes,
                "site_units_lost": self.units_lost,
                "site_rate_per_30d": self.rate_per_30d}


__all__ = ["InfusionSite", "FAILURES_PER_30_DAYS", "RESIDUAL_ABSORPTION", "SET_LIFE_DAYS"]
