"""What the person does: announcing meals, treating lows, and adjusting settings.

This is the layer that separates this package from a physiological simulator. The model
underneath describes a body. It does not describe someone eating a sandwich without
telling the algorithm, drinking juice when their sensor alarms, or nudging a ratio after
a bad fortnight. Those behaviours dominate several of the statistics a real glucose trace
shows, and no refinement of the differential equations produces them.

Measured against 192 real closed-loop users, adding this layer to the 2008 personae moved
the unannounced-meal rise tail, hypoglycaemia recovery and the drift of the sensitivity
setting from far outside the real range to inside or near it. See `docs/FIDELITY.md`.

Every parameter below is a published clinical figure or an explicit modelling choice, and
none is fitted to a fidelity statistic, so the resulting statistics are a test of the
layer rather than a restatement of its inputs.
"""
import numpy as np
from simglucose.simulation.scenario import Action as ScenarioAction

# --------------------------------------------------------------------------- parameters
# Announcement. Carbohydrate counting error is well characterised: Brazeau et al. (2013)
# and Meade & Rushton (2016) both put mean absolute error around 15-25% of the meal, and
# Roversi et al. (2020) reports a similar spread from CGM-based inference. Announcement
# rate for main meals in AID users is high but not total; snacks are routinely missed,
# which is the standard clinical account of the unannounced-carbohydrate problem.
P_ANNOUNCE_MAIN = 0.80
P_ANNOUNCE_SNACK = 0.35
CARB_ESTIMATE_CV = 0.25

# Rescue. The 15-15 rule (15 g, recheck at 15 min) is the standard advice, and the observed
# practice is to exceed it: Savard et al. (2016) and the ADA's own guidance note routine
# over-treatment.
#
# Recalibrated 2026-08-07 against measured behaviour rather than against the rule. Carb
# entries following a low were counted across 30 real closed-loop users over 5008 days:
#
#     rescues per day     median 0.44   (p25 0.09, p75 1.30)
#     grams per rescue    median 28.5   mean 33.8
#     rescue g per day    median 16.6
#
# The earlier settings treated far too often with far too little: 1.50 rescues a day at 25 g
# against a real 0.44 at 34 g. Frequency was the larger error and it came from two places.
# A refractory window of 20 minutes splits one treatment episode into three, where a person
# treats, waits, rechecks and is done. And treating pre-emptively at 80 mg/dL on any fall
# fires constantly on a closed loop, where the algorithm is already withdrawing insulin;
# real users at 80 and falling mostly let it work.
#
# This matters beyond the rescue statistics because every rescue produces a sharp rise that
# looks like a meal. At the old settings TimSim generated sustained 50 mg/dL climbs 1.9 to
# 2.3 times as often as real users, and drove a real algorithm's meal detector into its
# observing state about twice as much as the field does.
#
# Calibrated against the rescue statistics above and nothing else. Neither the fidelity
# table nor any algorithm's behaviour was consulted in choosing these, which is what makes
# the movement in those a test rather than a restatement.
#
# One caveat on the target: the real figures count carbohydrate that was logged. People
# treat lows without recording them, so 0.44 a day is a lower bound and the true rate sits
# somewhere above it. That is why the calibration lands at 0.93 rather than being pushed
# down to 0.44.
RESCUE_THRESHOLD = 70.0
RESCUE_PREEMPT_BG = 72.0          # treat early only when already close to the threshold
RESCUE_PREEMPT_FALL = -3.0        # mg/dL/min, a genuine fast fall
RESCUE_DELAY_MIN = (4.0, 16.0)    # uniform, minutes from decision to eating
RESCUE_GRAMS = (20.0, 40.0)       # uniform, grams of fast carbohydrate
P_OVERTREAT = 0.25                # probability of a second helping
OVERTREAT_EXTRA = (10.0, 30.0)    # grams
RESCUE_REFRACTORY_MIN = 45.0      # one treatment episode, not one dosing cycle

# The size of one helping, drawn as the real entries are distributed.
#
# The totals above are per episode and are close to real: 34.4 g a rescue against a logged
# median of 28.5. What is not real is that the whole of it arrives in one dose. Across 1,001
# carbohydrate entries made below 75 mg/dL by 8 users of the OpenAPS Data Commons export, the
# median entry is 20 g at a reading of 65 to 75 and 25 g below 55, with a ninetieth percentile
# of 45. People eat about 22 g, wait, and eat again if they are still low, which is the
# fifteen-and-fifteen rule the same records show being followed.
#
# The difference is most of the rebound. Giving 34.4 g at a median reading of 61 mg/dL peaks
# at 208 within three hours and above 180 on 71.2% of rescues, against a real rebound rate of
# 23.2 to 28.4%. Drawing the measured 22 g instead peaks at 172 and rebounds on 44.5%.
#
# Splitting the same total into repeated helpings on a twenty-minute recheck, which is what
# the real records show people doing, was tried first and made it worse: 72.9% above 180 and
# 33.5% above 250, against 71.2% and 24.0% for the single large dose. Carbohydrate takes about
# twenty minutes to act, so the simulated person is still below the threshold at the recheck
# and almost always eats again, 1.6 helpings an episode, and the second lands while the first
# is still absorbing. It is not adopted, and the timing here is unchanged from the refractory
# window already calibrated against the real rescue rate. Only the size of a helping changes.
#
# Dose size against the reading the person can see: -0.129 g per mg/dL, from 23.5 g at 68 to
# 26.5 g at 45, with a spread about that line of 15.8 g. The dependence is weak, r = -0.074,
# and is included because it is measured rather than because it is large. The lognormal spread
# reproduces the observed ninetieth percentile of 45 g on a median of 22.
#
# An earlier version of this measurement summed every entry in a window around each excursion
# and found a much stronger dependence on depth, -0.406 g per mg/dL. That was re-treatment
# being counted as one large dose: deeper lows get more entries, not bigger ones.
#
# What it costs and what it buys, twenty adults over 28 days under the built-in loop, paired,
# with nothing but the size of a helping changed:
#
#     hypoglycaemia rebound >180   63.9 -> 54.5   -12.0 +/- 4.4   real 23.2-28.4
#     outcome SD at a stuck high   25.9 -> 23.8    -0.9 +/- 0.8   real 26.5-33.5
#     rise tail                     4.4 ->  4.3    -0.2 +/- 0.1   real 3.7-6.6, still inside
#     insulin week-to-week %CV      4.2 ->  4.6    +0.5 +/- 0.9   real 4.5-11.1
#     hypoglycaemia recovery, min  50.0 -> 50.0    +2.2 +/- 4.2   real 50-59, still inside
#     rescues a day                0.99 -> 0.91                   real 0.44 logged
#     grams a rescue               36.1 -> 25.6                   real 20-25 an entry
#
# Signatures inside the real range go from eight of eleven to seven. What is lost is the
# outcome spread, moving 0.9 further below a range it was sitting on the edge of. What is
# bought is twelve points off the worst-fitting statistic in the package. The rebound is still
# about twice the real rate, so this closes roughly a third of that gap and the remainder is
# somewhere else: a rescue here raises glucose by about 4.9 mg/dL per gram, which is at the
# upper end of what is clinically expected and has not been validated.
# Whether a low is treated at all.
#
# Across 3,012 excursions below 70 in the OpenAPS Data Commons export, 23.4% have a
# carbohydrate entry within fifteen minutes before to thirty minutes after the crossing, and
# that share is flat with depth: 23.1% for excursions bottoming between 54 and 70, 24.6%
# between 45 and 54, 24.1% between 35 and 45. People mostly do not eat for a low, whatever
# depth it reaches, and let the loop bring them back.
#
# TimSim treats nearly every low, and the consequence shows up in the one statistic it cannot
# otherwise explain. Its response to a rescue now matches real people closely: 25.6 g eaten at
# 62 mg/dL peaking at 172 within three hours, against 25.0 g at 64 peaking at 170 across 309
# isolated real rescues, and 4.91 mg/dL per gram against a real 4.23 with an interquartile
# range of 3.02 to 6.90. What differs is how many recoveries are driven by eating rather than
# by the algorithm withdrawing insulin, and the rebound signature counts every recovery.
#
# The share is a probability drawn once per episode rather than per sample, because a draw
# every five minutes would treat almost surely within the episode. An episode ends when
# glucose clears the threshold by 10 mg/dL.
#
# Setting it to the measured share does not fix what it was built to fix, and the measurement
# that shows why is worth more than the knob. Splitting lows into treated and untreated on
# both sides, by the same rule, over 13 real users and 20 subjects:
#
#                      recovery to 100      rebound above 180
#     real, untreated       62.4 min              25.3%      n=4660
#     TimSim, untreated     80.0 min              38.5%      n= 366
#     real, treated         50.0 min              33.2%      n= 912
#     TimSim, treated       65.0 min              55.5%      n= 128
#
# The model is worse in both strata by about the same factor, 1.5 times the rebound and some
# sixteen minutes slower, so the share of lows treated is not what makes it rebound twice as
# often as real people. A simulated low lasts longer and overshoots harder however it ends,
# which is a property of how the person recovers rather than of what they eat, and nothing in
# this layer can reach it.
#
# Treating a low does make rebound more likely, in the real records as well: 33.2% against
# 25.3%. Weighting those by the real 16.4% treated share gives a pooled 26.6%, which lands
# inside the 23.2 to 28.4 that `signatures.REAL_RANGE` carries from a separate 192 users, so
# the two measurements agree where they overlap.
#
# Sweeping the share over 1.0, 0.6, 0.4 and 0.25 on twenty subjects moves the rebound from
# 53.3 to 40.5 and does so without order, 50.0 at 0.6 and 55.1 at 0.4, which is mostly noise
# at that sample size. Recovery leaves its range at every reduced level. Signatures inside the
# range fall from seven of eleven to six.
#
# So the knob stays and the default does not move. The real share counts logged carbohydrate
# and people treat without recording it, so 23.4% is a lower bound in any case.
P_TREAT_LOW = 1.0                 # measured at 0.16-0.23 in real records; see above

RESCUE_MEASURED_DOSE = True       # False restores the uniform 20-40 g draw
RESCUE_DOSE_MEDIAN_G = 22.0       # at 65 mg/dL, the median entry in the real records
RESCUE_DOSE_PER_MGDL = -0.129     # g per mg/dL of reading, measured
RESCUE_DOSE_SIGMA = 0.557         # lognormal, giving a ninetieth percentile near 45 g
RESCUE_DOSE_BOUNDS = (4.0, 90.0)  # g, the range the real entries occupy

# How much people differ from each other in when they treat a low, as a coefficient of
# variation applied per subject and held for the run.
#
# The rescue parameters above are one set shared by every subject, and the consequence is
# measurable. Across the 30 real closed-loop users the rescue rate has a median of 0.44 a
# day with quartiles at 0.09 and 1.30, a factor of fourteen between them. The simulated
# cohort spans a factor of 2.6. Every subject treats at the same glucose and waits the same
# time before treating again, so the largest behavioural difference between real people is
# absent from the population.
#
# Two knobs carry it, and both are things people genuinely differ on: the glucose at which
# somebody treats, and how long they wait before treating again. Sweeping them one at a time
# over four subjects gives 0.62 to 2.57 rescues a day for thresholds from 58 to 85 mg/dL,
# and 2.18 down to 0.71 for refractory periods from 20 to 180 minutes.
#
# Drawn to reproduce the observed quartiles rather than any fidelity statistic, on the same
# principle as the rest of this module.
#
# Measured at a coefficient of variation of 0.30 across all 100 subjects over 28 days. It is
# the best lever found for the population's narrowness and the only one that has improved
# per-subject coverage, from 91.0% of the trial's participants to 94.0%, and it moves the
# between-subject spread of mean glucose from 8.44 to 10.21 mg/dL against a trial figure of
# 14.24. The rescue rate spans a factor of 4.2 between quartiles against the 2.6 it had and
# the 14.4 real users have.
#
# It is off by default because of what it does to the other direction. The share of virtual
# subjects resembling a real participant falls from 73.5% to 64.9%, the spread of time below
# 54 widens from 2.75 to 3.10 where it was already the worst-fitting statistic, and
# variability widens from 1.63 to 1.90.
#
# That is the structural problem rather than a property of this knob. The population needs
# its spread of mean glucose widened and its spread of hypoglycaemia narrowed, and every
# source of between-subject variation tried so far widens both. Something that narrows
# hypoglycaemia is what is missing, and adding variation is not it.
BEHAVIOUR_SPREAD_CV = 0.0
RESCUE_THRESHOLD_BOUNDS = (55.0, 88.0)
RESCUE_REFRACTORY_BOUNDS = (15.0, 240.0)


def rescue_style(name, cv=BEHAVIOUR_SPREAD_CV, seed=0):
    """One subject's treating style: the glucose they act on and how long they then wait.

    Keyed on the subject name so a cohort is reproducible without regenerating the
    population, and so two runs of the same subject agree.
    """
    if cv <= 0:
        return RESCUE_THRESHOLD, RESCUE_REFRACTORY_MIN
    import hashlib

    digest = hashlib.sha256(f"rescue:{name}:{seed}".encode()).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    sigma = np.sqrt(np.log(1.0 + float(cv) ** 2))
    threshold = float(np.clip(RESCUE_THRESHOLD * rng.lognormal(-0.5 * sigma ** 2, sigma),
                              *RESCUE_THRESHOLD_BOUNDS))
    # Waiting longer and treating later go together in the same person, so the refractory
    # is drawn against the threshold rather than independently: someone who lets a low run
    # is also someone who does not recheck in a hurry.
    refractory = float(np.clip(
        RESCUE_REFRACTORY_MIN * rng.lognormal(-0.5 * (2 * sigma) ** 2, 2 * sigma),
        *RESCUE_REFRACTORY_BOUNDS))
    return threshold, refractory

# Adaptation. Real weekly ISF drift is 8-22% CV, measured on the cohort. A weekly
# adjustment bounded to +/-30% is the shape autosens/autotune already use.
ADAPT_PERIOD_MIN = 7 * 24 * 60
ADAPT_GAIN = 0.5
ADAPT_CLIP = (0.70, 1.30)


class Person:
    """Announcement behaviour, rescue-carbohydrate behaviour, and the record of both.

    Holds no glucose model. It is handed the CGM each cycle and returns what the person
    does: how much carbohydrate reaches the gut, and how much of it the algorithm is
    told about.
    """

    def __init__(self, rng, rescue=True, announce=True,
                 rescue_threshold=RESCUE_THRESHOLD,
                 rescue_refractory_min=RESCUE_REFRACTORY_MIN,
                 p_treat_low=None):
        self.rng = rng
        self.p_treat_low = float(P_TREAT_LOW if p_treat_low is None else p_treat_low)
        self.rescue_on = rescue
        self.announce_on = announce
        self.rescue_threshold = float(rescue_threshold)
        # The pre-emptive trigger sits just above the threshold, so it follows it.
        self.rescue_preempt_bg = float(rescue_threshold) + (
            RESCUE_PREEMPT_BG - RESCUE_THRESHOLD)
        self.rescue_refractory_min = float(rescue_refractory_min)
        self.pending = []          # [(minute_due, grams)]
        self.last_rescue_min = -1e9
        self.treating = None
        self.rescue_events = 0
        self.rescue_grams = 0.0
        # When each treatment was decided and how large it was. Counts alone cannot answer
        # whether a person treated a particular low, which is the question that matters
        # when a run leaves someone below 54 mg/dL for hours.
        self.rescue_log = []
        self.unannounced_meals = 0
        self.announced_meals = 0

    # ---------------------------------------------------------------- announcement
    def announce(self, grams, is_snack):
        """What the algorithm is told about a meal of `grams`. Zero means unannounced."""
        if not self.announce_on:
            return grams
        p = P_ANNOUNCE_SNACK if is_snack else P_ANNOUNCE_MAIN
        if self.rng.random() > p:
            self.unannounced_meals += 1
            return 0.0
        self.announced_meals += 1
        sigma = np.sqrt(np.log(1 + CARB_ESTIMATE_CV ** 2))
        return float(grams * self.rng.lognormal(-0.5 * sigma ** 2, sigma))

    # ---------------------------------------------------------------- rescue
    def _dose(self, cgm):
        """One helping, drawn as the real entries are distributed.

        Lognormal about a median that shifts slightly with the reading, so a person low
        enough to be worried takes a little more. The dependence is weak because the measured
        one is weak, and the spread is wide because the measured spread is wide.
        """
        median = RESCUE_DOSE_MEDIAN_G + RESCUE_DOSE_PER_MGDL * (float(cgm) - 65.0)
        median = max(median, RESCUE_DOSE_BOUNDS[0])
        g = float(self.rng.lognormal(np.log(median), RESCUE_DOSE_SIGMA))
        return float(np.clip(g, *RESCUE_DOSE_BOUNDS))

    def observe(self, minute, cgm, fall_rate):
        """Called once per CGM sample. May schedule a rescue for a few minutes later."""
        if not self.rescue_on:
            return
        low = cgm < self.rescue_threshold
        falling_fast = cgm < self.rescue_preempt_bg and fall_rate < RESCUE_PREEMPT_FALL

        # An episode ends once glucose is clear of the threshold, and the decision whether to
        # treat this one is taken once rather than at every sample.
        if cgm > self.rescue_threshold + 10.0:
            self.treating = None
        if minute - self.last_rescue_min < self.rescue_refractory_min:
            return
        if not (low or falling_fast):
            return
        if self.treating is None:
            self.treating = bool(self.rng.random() < self.p_treat_low)
        if not self.treating:
            return
        if RESCUE_MEASURED_DOSE:
            grams = self._dose(cgm)
        else:
            grams = float(self.rng.uniform(*RESCUE_GRAMS))
            if self.rng.random() < P_OVERTREAT:
                grams += float(self.rng.uniform(*OVERTREAT_EXTRA))

        self.last_rescue_min = minute
        delay = float(self.rng.uniform(*RESCUE_DELAY_MIN))
        self.pending.append((minute + delay, grams))
        self.rescue_events += 1
        self.rescue_grams += grams
        self.rescue_log.append((float(minute), float(minute + delay), grams, float(cgm)))

    def due(self, minute, window):
        """Rescue carbohydrate reaching the gut in [minute, minute+window). Never
        announced: people treating a low do not enter it as a meal bolus."""
        if not self.pending:
            return 0.0
        take = [g for m, g in self.pending if minute <= m < minute + window]
        self.pending = [(m, g) for m, g in self.pending if not (minute <= m < minute + window)]
        return float(sum(take))


class BehaviourScenario:
    """A mutable scenario: the scheduled meals plus whatever the person eats reactively.

    simglucose calls get_action(t) once per model minute, so rescue carbohydrate can be
    injected between calls. The scheduled meals carry an `is_snack` flag and their
    announced amount is resolved on delivery, so the announcement decision is recorded
    at the moment the meal is eaten rather than at construction.
    """

    def __init__(self, start_time, meals, person):
        self.start_time = start_time
        self.person = person
        # meals: [(hours_from_start, grams, is_snack)]
        self.sched = {int(round(h * 60.0)): (g, snack) for h, g, snack in meals}
        # get_action is called once per model minute; the runner steps the environment
        # three minutes at a time, so announcements accumulate and are drained per step.
        self._announced = 0.0
        self._true = 0.0

    def reset(self):
        self._announced = 0.0
        self._true = 0.0

    def drain(self):
        """(announced grams, true grams) since the last call."""
        a, t = self._announced, self._true
        self._announced, self._true = 0.0, 0.0
        return a, t

    def get_action(self, t):
        minute = int(round((t - self.start_time).total_seconds() / 60.0))
        grams = 0.0
        if minute in self.sched:
            g, snack = self.sched.pop(minute)
            grams += g
            self._announced += self.person.announce(g, snack)
        grams += self.person.due(minute, 1.0)
        self._true += grams
        return ScenarioAction(meal=grams)


class AdaptiveRatios:
    """A weekly-adapting insulin-sensitivity setting, so ISF drift has something to read.

    The physiology layer already varies true sensitivity week to week. Nothing in the
    stock basal-bolus controller responds to it, which is why the drift signature reads a
    structural zero: it reads the algorithm's setting, not the person's physiology. A
    bounded weekly adjustment towards target is the same shape autosens and autotune use.
    """

    def __init__(self, cf0, cr0):
        self.cf0, self.cr0 = cf0, cr0
        self.factor = 1.0
        self.history = []           # [(minute, effective CF)]
        self._acc, self._n, self._last = 0.0, 0, 0.0

    def observe(self, minute, cgm, target=140.0):
        self._acc += cgm - target
        self._n += 1
        if minute - self._last >= ADAPT_PERIOD_MIN and self._n:
            bias = self._acc / self._n
            # running high means more insulin is needed: a SMALLER correction factor
            adj = 1.0 - ADAPT_GAIN * np.clip(bias / 60.0, -1.0, 1.0)
            self.factor = float(np.clip(self.factor * adj, *ADAPT_CLIP))
            self._acc, self._n, self._last = 0.0, 0, minute
        self.history.append((minute, self.cf0 * self.factor))

    @property
    def cf(self):
        return self.cf0 * self.factor

    @property
    def cr(self):
        return self.cr0 * self.factor

    def weekly_cv(self):
        """The signature the suite reads: weekly %CV of the effective sensitivity."""
        if len(self.history) < 2:
            return np.nan
        m = np.array([h[0] for h in self.history], float)
        v = np.array([h[1] for h in self.history], float)
        weeks = (m // ADAPT_PERIOD_MIN).astype(int)
        per = np.array([v[weeks == w].mean() for w in np.unique(weeks)])
        return float(100 * per.std() / per.mean()) if len(per) > 1 and per.mean() else np.nan


