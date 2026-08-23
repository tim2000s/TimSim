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

# How much of what the person eats the algorithm is told about. "some" is what real records
# show, at the two probabilities above. The other two are experimental conditions rather than
# descriptions of anybody: "always" is the lineage an algorithm's own configuration is derived
# from, since a user onboarding onto it has been announcing, and "never" is the condition these
# algorithms claim to handle, where meal detection has to do all of the work. A carbohydrate
# estimate is still wrong under "always", because announcing a meal and counting it correctly
# are different things.
ANNOUNCEMENT_MODES = ("always", "some", "never")
CARB_ESTIMATE_CV = 0.25

# Whether the error is centred.
#
# The draw above has mean one, so a meal is as likely to be over-counted as under-counted.
# The papers cited report mean absolute error, which is a spread and says nothing about
# direction, and the direction is separately well documented: people under-estimate, and more
# so as the meal grows.
#
# It matters here because of a gap nothing else explained. Real meals peak at 135 minutes and
# this model's at 90. It is not absorption: slowing every rate threefold moves the peak ten
# minutes and saturates. It is not when the insulin is given either, measured across 6,414
# real meals from ten users, where the median bolus lands on the meal, 65.4% within two
# minutes of it, only 11.7% more than a quarter of an hour late, and 2.2% of meals never
# bolused at all. A mean lateness of 2.2 minutes cannot produce a delay of forty-five.
#
# It is not the size of the dose either, which is what this parameter was added to test.
# Scaling the announced amount down leaves the peak where it was:
#
#     bias   time to peak   rise per gram
#     1.00        102 min        1.32
#     0.90         92 min        1.40
#     0.80         91 min        1.27
#     0.70         95 min        1.48
#     real        135 min        1.41
#
# Non-monotonic and inside the noise. Under-dosing raises the peak without delaying it,
# because when the peak arrives is set by the absorption profile and insulin scales its
# height. So absorption rate, bolus timing and dose size are all refused.
#
# It was the clock. Real time to peak was counted from the carbohydrate entry and the
# simulated from the meal, and those are not the same event, because pre-bolusing is standard
# practice and the entry can precede any food by fifteen or twenty minutes. Counting instead
# from the trough after the entry, which is the duration of the rise itself and is measurable
# identically on both sides:
#
#                      trough to peak            rise
#     real, 5,189 meals   112 min (70-165)     75 mg/dL
#     simulated, 442      100 min (75-144)     84 mg/dL
#
# Twelve minutes apart with quartiles that overlap almost entirely. The forty-five minute gap
# was mostly an artefact of clocking the two sides from different events, and the three
# mechanisms tested against it were tested against something that was not there.
#
# The parameter is left at 1.0. It would be defensible on the literature, which reports mean
# absolute error and separately documents that people under-count, but it was added to explain
# something that turned out not to need explaining, and adopting it now would be fitting.
CARB_ESTIMATE_BIAS = 1.0

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
# How much of a rescue helping reaches the gut, as a bioavailability. Meals are untouched.
#
# The simulated carbohydrate response is 21.1 to 21.6 mg/dL per 10 g against a real 15.9 to
# 19.7 across every defensible filter, so the same helping raises glucose about a fifth more
# here than in life. Rebound is what over-treating a low looks like, and it sat at 36 to 42 per
# cent against a real 23.2 to 28.4 in every configuration measured, which suggested the two were
# one defect seen twice.
#
# Measured on 450 paired runs across three cohort and controller pairings, against a control
# with no other mechanism changed:
#
#                       rebound      variability    time in range    recovery
#     commons/oref       -8.13 *        -3.79 *         +4.27 *        +0.18
#     dclp3/control-iq   -6.86 *        -3.41 *         +3.19 *        +3.90
#     dclp3/oref         -7.02 *        -3.87 *         +3.78 *        -0.79
#
#     * the bootstrap interval on the paired difference excludes zero
#
# Rebound moves from 36 to 42 per cent down to 29 to 33, towards the real 23.2 to 28.4.
# Variability falls from 34.3 to 35.6 down to 30.4 to 32.4, which is inside the real 29.5 to
# 34.3 rather than above it. Recovery time spans zero in all three, which matters because a
# mechanism that bought less overshoot at the price of a longer climb would have traded one
# failure for another, and `docs/DESIGN_HYPOGLYCAEMIA.md` fixed that as the refutation criterion
# before the run.
#
# It scales absorption rather than the helping, so `rescue_grams` still records what the person
# ate and only the gut sees less. `docs/PADOVA_LIMITS.md` declined to scale carbohydrate on two
# grounds, filter sensitivity and under-reported grams, and both are about logged meals rather
# than a rescue treatment, which is neither logged as a meal nor under-reported the same way.
RESCUE_BIOAVAILABILITY = 0.83

RESCUE_THRESHOLD = 70.0
RESCUE_PREEMPT_BG = 72.0          # treat early only when already close to the threshold
RESCUE_PREEMPT_FALL = -3.0        # mg/dL/min, a genuine fast fall
RESCUE_DELAY_MIN = (4.0, 16.0)    # uniform, minutes from decision to eating

# How long a meal takes to start moving glucose, over and above what the metabolic model's own
# gastric emptying supplies. The model empties at its maximum rate from the first minute, so a
# simulated meal starts raising glucose immediately, where a real one does not.
#
# Measured on meals nobody bolused for, matched on true grams and on baseline glucose: 363 real
# meals fall 5.0 mg/dL by fifteen minutes and have risen 2.0 by thirty, where 444 simulated ones
# are already up 3.8 and 14.9. From forty-five minutes onward the two agree closely, at 19.0
# against 30.2, 36.0 against 45.0, and 56.5 against 60.4 by ninety.
#
# The consequence is not the height of the excursion but its onset. A controller sees nothing
# for half an hour in life and sees a rise from the first cycle here, so an algorithm built to
# detect meals early is handed roughly thirty minutes it would not have. The announcement still
# reaches the algorithm when the person eats, since that is when somebody enters it.
# Swept against that profile at 0, 10, 20 and 30 minutes, scored on the root mean square
# difference across all six marks so it could not be fitted to the early ones alone. Ten minutes
# more than halves the error, from 9.4 to 4.1 mg/dL, and matches the real curve closely from
# forty-five minutes onward: 19.7 against 19.0, 32.0 against 36.0, and 54.5 against 56.5 at
# ninety. Twenty and thirty overshoot, at 7.9 and 13.9.
#
# The real curve falls 5.0 mg/dL by fifteen minutes, which no gastric delay produces. Those
# entries carry no insulin nearby and some were probably logged while glucose was already
# drifting down, so the earliest marks carry a selection effect and the calibration rests on the
# forty-five minute mark onward.
MEAL_ONSET_DELAY_MIN = 10.0
RESCUE_GRAMS = (20.0, 40.0)       # uniform, grams of fast carbohydrate
P_OVERTREAT = 0.25                # probability of a second helping
OVERTREAT_EXTRA = (10.0, 30.0)    # grams
RESCUE_REFRACTORY_MIN = 45.0      # one treatment episode, not one dosing cycle

# The size of one helping, drawn as the real entries are distributed.
#
# Remeasured 2026-08-13 on 4,544 entries from 30 users, after the first version globbed
# filenames in a way that missed any carrying a user-id prefix and so drew on 1,001 entries
# from 8. The medians came down and the spread went up:
#
#     reading      first pass          full sample        n
#      65-75    median 20.0 g       median 15.0 g      2405
#      55-65    median 24.0 g       median 18.0 g      1316
#      45-55    median 25.0 g       median 20.0 g       557
#      below 45 median 25.0 g       median 22.0 g       266
#
# The slope against the reading holds, -0.117 g per mg/dL against -0.129, and the ninetieth
# percentile holds at 45 g. What changed is the centre: the distribution is more skewed than
# the first sample suggested, with a mean of 21.0 g on a median of 15.0.
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
# Regressed on twenty subjects, paired, against the uniform draw this replaces and against the
# first sample's 22 g median:
#
#     signature      published    uniform 35 g   22 g fit   15 g fit
#     hypo rebound   23.2-28.4         64.6        54.7       47.0
#     hypo recovery  50-59             56.2        62.5       70.0
#     variability    29.5-34.3         34.7        36.8       35.5
#     grams a rescue                    35.2        26.1       21.5
#     inside the published band        10/11        8/11       8/11
#
# By that count the unfaithful uniform draw wins, and by the distribution of 101 real
# individuals it does not:
#
#     signature      real p10-p90   uniform   22 g fit   15 g fit
#     hypo rebound    16.7-52.9        64.6      54.7       47.0
#     hypo recovery   40.0-80.0        56.2      62.5       70.0
#     variability     29.9-41.4        34.7      36.8       35.5
#     inside that range                9/10      9/10      10/10
#
# The measured helping is the only arm with every signature inside the range of real people.
# The published band is the minimum and maximum of four cohort medians, so it describes where
# a cohort's centre sits rather than where people sit, and it is the wrong reference for a
# population meant to contain individuals. See `docs/CAPABILITY.md`.
#
# What the change exposes rather than causes: recovery to 100 mg/dL moves to 70 minutes, which
# is inside the real 40 to 80 but slow. The model's untreated lows already took 80 minutes
# against a real 59.4, and giving 35 g of carbohydrate was masking it.
#
# It costs nothing in survival, which was checked rather than assumed. Twelve subjects over 28
# days under each of two drivers:
#
#     helping     trend        control-iq
#     uniform     8/12 4.71%   5/12 4.92%
#     22 g        8/12 4.05%   6/12 7.28%
#     15 g        8/12 3.97%   5/12 5.90%
#
# Completion is flat and time below 70 falls slightly, so the smaller helping neither kills
# subjects nor deepens their lows. The attrition in that table belongs to the subjects and to
# Control-IQ rather than to anything here, and eight of twelve completing under the default
# driver is worth someone looking at on its own account.
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
RESCUE_DOSE_MEDIAN_G = 15.0       # at 65 mg/dL, the median entry in the real records
RESCUE_DOSE_PER_MGDL = -0.117     # g per mg/dL of reading, measured
RESCUE_DOSE_SIGMA = 0.857         # lognormal, giving a mean of 21.7 g and a p90 of 45
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


# How much subjects differ from each other in how closely they follow the therapy.
#
# Every subject here announces the same share of meals, misestimates carbohydrate by the same
# amount and runs settings of the same quality, so the population varies in what happens to it
# and not in what it does. Real people vary in both, and the three vary together: someone who
# misses boluses is also someone counting carbohydrate carelessly and running settings nobody
# has revisited. One latent draw per subject therefore drives all three rather than three
# independent draws, which would let a subject be careless about boluses and meticulous about
# carbohydrate and would not produce a group of people who do badly.
#
# It acts on the odds of missing a bolus rather than on the probability, so every subject stays
# inside zero and one without a clipping rule that would pile subjects up at the ends.
#
# The size comes from the literature on missed and mistimed doses rather than from either
# reference population, because both of those are what the mechanism is judged against and a
# parameter taken from them would stop the comparison being a test. Robinson et al. review the
# field (Diabetes Technology and Therapeutics 2021;23(8):845-857) and the pump-alarm study in it
# reports 4.9 missed meal boluses a week with a standard deviation of 3.7 across individuals, a
# between-person coefficient of variation of 0.76 on the rate at which a person misses a bolus.
#
# `ENGAGEMENT_SPREAD` is the standard deviation on the log-odds scale that reproduces that
# coefficient of variation at the population's own announcement rate, solved in
# `engagement_spread_for_cv` rather than asserted, so the number can be rederived if the
# announcement rate changes.
#
# Off by default until the measurement in docs/DESIGN_ALIGNMENT.md section D is made.
ENGAGEMENT_CV = 0.0
ENGAGEMENT_SPREAD = 1.047

# The quadrature the mean-preserving offset is solved against, and the offsets already solved.
# Fixed rather than redrawn so two runs of one subject agree and so the offset is a property of
# the parameter rather than of when it was first asked for.
_Z = np.random.default_rng(0).standard_normal(200000)
_OFFSETS = {}

# How far the carbohydrate estimate degrades across the same range, as the exponent applied to
# the latent draw. A modelling choice: nothing measures how strongly bolus omission and counting
# error travel together in one person, only that both are worse in the less engaged.
#
# Settings quality was drawn with them in the first version of this mechanism and is not, for two
# reasons. The correction-factor sweep in docs/DESIGN_ALIGNMENT.md section A found that lever
# moves time in range by nothing at all under a Control-IQ-shaped loop, because basal modulation
# replaces whatever the correction channel stops delivering, so coupling it here would add a free
# parameter that cannot act. And an external controller is constructed by the caller against the
# profile it was handed, so scaling the profile inside `simulate` would put the rig and the
# algorithm on different settings, which `_require_matching_profile` exists to prevent.
ENGAGEMENT_CARB_COUPLING = 0.30


def _mean_preserving_offset(base, s, z):
    """The log-odds shift holding the population miss rate at the rate `base` encodes.

    Spreading a probability on the log-odds scale moves its mean as well as its spread, because
    the inverse logit is not linear. Without this the mechanism would lower the announcement
    rate as well as vary it, and any change in outcome would be two effects rather than one.
    """
    target = 1.0 / (1.0 + np.exp(-base))
    lo, hi = -6.0, 6.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if float(np.mean(1.0 / (1.0 + np.exp(-(base + mid + s * z))))) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def engagement_spread_for_cv(cv, p_miss, n=200000, seed=0):
    """The log-odds spread and offset giving a between-person CV of `cv` on the miss rate.

    Returns `(spread, offset)`. Solved numerically because a logit-normal has no closed form
    for either quantity, and solved jointly because the offset holding the mean depends on the
    spread. Returns zeros for a non-positive target, which is the mechanism switched off.
    """
    if cv <= 0:
        return 0.0, 0.0
    z = np.random.default_rng(seed).standard_normal(n)
    base = np.log(p_miss / (1.0 - p_miss))

    def achieved(s):
        b = _mean_preserving_offset(base, s, z)
        p = 1.0 / (1.0 + np.exp(-(base + b + s * z)))
        return float(np.std(p) / np.mean(p)), b

    lo, hi = 0.0, 8.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if achieved(mid)[0] < cv:
            lo = mid
        else:
            hi = mid
    s = 0.5 * (lo + hi)
    return s, achieved(s)[1]


def engagement_for(name, cv=ENGAGEMENT_CV, seed=0, spread=None):
    """One subject's engagement, as its announcement rates and its counting error.

    Returns `(p_main, p_snack, carb_cv)`. At `cv <= 0` it returns the population values
    unchanged, which is the mechanism switched off and reproduces every arm run before it.

    Keyed on the subject name so a cohort is reproducible without regenerating the population,
    and so two runs of the same subject agree. The draw is a single standard normal, and a
    subject above the mean both misses more boluses and counts carbohydrate worse, because that
    is one person rather than two.
    """
    if cv <= 0:
        return P_ANNOUNCE_MAIN, P_ANNOUNCE_SNACK, CARB_ESTIMATE_CV
    import hashlib

    digest = hashlib.sha256(f"engagement:{name}:{seed}".encode()).digest()
    z = float(np.random.default_rng(int.from_bytes(digest[:8], "big")).standard_normal())
    s = ENGAGEMENT_SPREAD if spread is None else float(spread)

    def shifted(p):
        """Announcement probability after moving the odds of missing by `s * z`.

        The offset is solved per meal type, because holding the mean depends on where the rate
        starts and a main meal and a snack do not start in the same place.
        """
        miss = 1.0 - p
        base = np.log(miss / (1.0 - miss))
        b = _OFFSETS.get(round(p, 6))
        if b is None:
            b = _mean_preserving_offset(base, s, _Z)
            _OFFSETS[round(p, 6)] = b
        return float(1.0 - 1.0 / (1.0 + np.exp(-(base + b + s * z))))

    return (shifted(P_ANNOUNCE_MAIN), shifted(P_ANNOUNCE_SNACK),
            float(CARB_ESTIMATE_CV * np.exp(ENGAGEMENT_CARB_COUPLING * s * z)))


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
                 p_treat_low=None, announcement="some",
                 p_announce_main=P_ANNOUNCE_MAIN, p_announce_snack=P_ANNOUNCE_SNACK,
                 carb_estimate_cv=CARB_ESTIMATE_CV):
        self.rng = rng
        # Per-subject rather than module-level, so an engaged and a disengaged subject differ
        # in what they do and not only in what happens to them. They default to the population
        # values, which is what every arm before `engagement_cv` used.
        self.p_announce_main = float(p_announce_main)
        self.p_announce_snack = float(p_announce_snack)
        self.carb_estimate_cv = float(carb_estimate_cv)
        self.p_treat_low = float(P_TREAT_LOW if p_treat_low is None else p_treat_low)
        self.rescue_on = rescue
        self.announce_on = announce
        if announcement not in ANNOUNCEMENT_MODES:
            raise ValueError(f"announcement must be one of {ANNOUNCEMENT_MODES}")
        self.announcement = announcement
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
        # Both draws are taken in every mode and only then used, so the three announcement
        # conditions consume the generator identically and stay comparable. Drawing them
        # conditionally made each mode a different run rather than a different condition: under
        # one controller, announcing every meal then scored worse than announcing some, which is
        # backwards and was the streams diverging rather than an effect.
        u = self.rng.random()
        sigma = np.sqrt(np.log(1 + self.carb_estimate_cv ** 2))
        estimate = float(grams * CARB_ESTIMATE_BIAS
                         * self.rng.lognormal(-0.5 * sigma ** 2, sigma))
        if self.announcement == "never":
            self.unannounced_meals += 1
            return 0.0
        if self.announcement == "some":
            p = self.p_announce_snack if is_snack else self.p_announce_main
            if u > p:
                self.unannounced_meals += 1
                return 0.0
        self.announced_meals += 1
        return estimate

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


def delivery_schedule(meals):
    """Drawn meals as the minutes they are actually delivered on.

    Meals are drawn on a continuous clock and delivered on an integer minute, so two can round
    to the same one. Keying a plain dict on that minute dropped the earlier of the pair while
    the run's meal log went on reporting both, which happened in 3 of 200 subjects over 28 days
    and left a logged meal that was never announced and never reached the gut. They are merged
    instead: eating twice in the same minute is eating once, and the result counts as a snack
    only if both parts were snacks.

    Every arm goes through this, so the record of what a subject ate does not depend on which
    layers were switched on.

    `meals` is [(hours_from_start, grams, is_snack)]; the result is
    ((minute, grams, is_snack), ...) sorted by minute.
    """
    out = {}
    for h, g, snack in meals:
        m = int(round(float(h) * 60.0))
        if m in out:
            g0, s0 = out[m]
            out[m] = (g0 + float(g), bool(s0 and snack))
        else:
            out[m] = (float(g), bool(snack))
    return tuple((float(m), g, s) for m, (g, s) in sorted(out.items()))


class BehaviourScenario:
    """A mutable scenario: the scheduled meals plus whatever the person eats reactively.

    simglucose calls get_action(t) once per model minute, so rescue carbohydrate can be
    injected between calls. The scheduled meals carry an `is_snack` flag and their
    announced amount is resolved on delivery, so the announcement decision is recorded
    at the moment the meal is eaten rather than at construction.
    """

    def __init__(self, start_time, meals, person, meal_delay_min=MEAL_ONSET_DELAY_MIN,
                 rescue_bioavailability=RESCUE_BIOAVAILABILITY):
        self.start_time = start_time
        self.person = person
        self.meal_delay_min = float(meal_delay_min)
        # What fraction of a rescue helping reaches the gut. Meals are untouched.
        #
        # Hypoglycaemia rebound is 36 to 40 per cent against a real 23.2 to 28.4 in every
        # configuration measured, and the carbohydrate response is 21.1 to 21.6 mg/dL per 10 g
        # against a real 15.9 to 19.7. Rebound is what over-treating a low looks like, so those
        # may be the same defect twice: the same helping overshoots by about the ratio.
        #
        # It scales absorption rather than the helping, so `rescue_grams` still records what the
        # person ate and only the gut sees less. `docs/PADOVA_LIMITS.md` declined to scale
        # carbohydrate on two grounds, filter sensitivity and under-reported grams, and both are
        # about logged meals rather than a rescue treatment.
        self.rescue_bioavailability = float(rescue_bioavailability)
        # meals: [(hours_from_start, grams, is_snack)]
        self.effective = delivery_schedule(meals)
        self.sched = {int(m): (g, s) for m, g, s in self.effective}
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
            # The algorithm is told when the person eats; the gut receives it after the delay,
            # because announcing a meal and digesting it happen at different times.
            self._announced += self.person.announce(g, snack)
            if self.meal_delay_min > 0:
                self.person.pending.append((minute + self.meal_delay_min, g))
            else:
                grams += g
        rescue = self.person.due(minute, 1.0) * self.rescue_bioavailability
        grams += rescue
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


