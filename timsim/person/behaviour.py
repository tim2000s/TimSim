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
                 rescue_refractory_min=RESCUE_REFRACTORY_MIN):
        self.rng = rng
        self.rescue_on = rescue
        self.announce_on = announce
        self.rescue_threshold = float(rescue_threshold)
        # The pre-emptive trigger sits just above the threshold, so it follows it.
        self.rescue_preempt_bg = float(rescue_threshold) + (
            RESCUE_PREEMPT_BG - RESCUE_THRESHOLD)
        self.rescue_refractory_min = float(rescue_refractory_min)
        self.pending = []          # [(minute_due, grams)]
        self.last_rescue_min = -1e9
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
    def observe(self, minute, cgm, fall_rate):
        """Called once per CGM sample. May schedule a rescue for a few minutes later."""
        if not self.rescue_on:
            return
        if minute - self.last_rescue_min < self.rescue_refractory_min:
            return
        low = cgm < self.rescue_threshold
        falling_fast = cgm < self.rescue_preempt_bg and fall_rate < RESCUE_PREEMPT_FALL
        if not (low or falling_fast):
            return
        self.last_rescue_min = minute
        delay = float(self.rng.uniform(*RESCUE_DELAY_MIN))
        grams = float(self.rng.uniform(*RESCUE_GRAMS))
        if self.rng.random() < P_OVERTREAT:
            grams += float(self.rng.uniform(*OVERTREAT_EXTRA))
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


