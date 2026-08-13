"""A subject whose insulin sensitivity varies, in the way the S2017 model added.

The published 2008 personae hold every parameter fixed for the length of a run, so the
same person on the same day responds identically every time. Real sensitivity moves: it
dips before dawn and it drifts from one day to the next by a substantial fraction.

Which licensed version added what is worth stating precisely, because this module was
described as implementing S2013 for a long time and it does not.

    S2008   the base meal model. Time-invariant parameters, and no counterregulation
            of any kind. This is what simglucose implements and what sits underneath
            everything here.
    S2013   a nonlinear rise in insulin-dependent glucose utilisation once glucose falls
            below a threshold, driven by the Low Blood Glucose Risk Index, plus glucagon
            kinetics, secretion and action. Both exist to describe counterregulation.
    S2017   intraday insulin sensitivity variability, a dawn phenomenon model, and a
            diurnal basal and carbohydrate-ratio pattern per subject.

What is implemented below is the S2017 refinement, in mechanism rather than in detail: a
common time-varying factor scaling insulin-dependent glucose uptake (Vmx) and hepatic
insulin action on endogenous production (kp3), which are the two parameters S2017 varies,
with a dawn component and a day-to-day component at clinically reported magnitudes.

Nothing here implements S2013. There is no counterregulation in this package, and that
absence is load-bearing. Visentin et al. measured S2008 against clinical data by continuous
glucose error grid analysis and found 40.7% of hypoglycaemic readings accurate against
S2013's 85.9%, with 59.3% falling in the erroneous zone. On the outcome metrics S2008
under-reports the low blood glucose index at 0.23 against a measured 0.59, and time in
hypoglycaemia at 3.59% against 6.47%.

A subject here going low therefore has nothing to bring it back except carbohydrate the
behaviour layer supplies, and whatever insulin the loop withdraws.

That was thought to explain the hypoglycaemia rebound row, and on reading the source
material it does not. Two reasons, both worth keeping so the idea is not revisited.

S2013's counterregulation is a glucagon model built for bihormonal systems that infuse
glucagon as a drug. Hinshaw et al. (2015) publish its action parameters, but the input is a
glucagon concentration, not a falling glucose, so the secretion half is what would be
needed and that is unpublished.

More to the point, people with established type 1 diabetes largely lose the alpha-cell
glucagon response to hypoglycaemia. Visentin et al. flagged this themselves: including
glucagon secretion "could be not appropriate for all T1DM patients with a long duration".
Modelling it here would give these subjects a defence they do not have.

What T1D does retain is the catecholamine arm. Hinshaw et al. measure epinephrine roughly
tripling during a hypoglycaemia clamp, from about 20-30 to 60-120 pg/mL, and separate the
timescales: glucagon drives the endogenous glucose production rise over the first 60 to 90
minutes through glycogenolysis, and catecholamines drive it after that through
gluconeogenesis. A defence that acts beyond 90 minutes cannot explain either a rebound rate
or a 62-minute recovery time. Neither S2013 nor S2017 models the catecholamine arm.

So the rebound row stays where `docs/FIDELITY.md` leaves it: reported, with its direction
known, and not explained by anything in the licensed model lineage.
"""
import numpy as np
from simglucose.patient.t1dpatient import T1DPatient

# Dalla Man et al. (2014) calibrate intraday and interday sensitivity variation from
# clinical data. These magnitudes are in the range that literature reports; they are a
# modelling choice at the centre of it rather than a fit to anything here.
DIURNAL_AMPLITUDE = 0.20      # fractional dip in sensitivity, lowest around 06:00
INTERDAY_CV = 0.22            # day-to-day coefficient of variation
SENSITIVITY_BOUNDS = (0.3, 2.5)

# Runs of days that belong together.
#
# The day-to-day term above draws each day independently, and independent draws average out:
# a week's mean of seven draws at a coefficient of variation of 0.22 has one of 0.22/sqrt(7),
# about 0.08. Real life is not like that. Illness, a training block, a holiday and the
# menstrual cycle produce runs of days that move together, and a week inside one of them
# differs from a week outside it by much more than averaging predicts.
#
# The measurement that shows the gap is the week-to-week variation in total daily insulin,
# which is what a person's changing sensitivity must move whoever is dosing. Across 115 real
# users of the Nightscout cache over matched 28-day windows the median is 7.3% with an
# interquartile range of 4.5 to 11.1. TimSim reads 1.8% for the stock model and 4.0% with
# every layer on.
#
# `SLOW_TAU_DAYS` is the correlation time of the slow term and `SLOW_CV` its size. The slow
# term multiplies the independent daily one rather than replacing it, so Dalla Man's
# day-to-day figure is untouched: what is added is the thing it does not describe.
# Regressed 2026-08-12 against every signature, paired on the same subjects under the
# built-in loop, with each arm differing from the baseline by one thing:
#
#     signature      real        baseline   slow 0.15   slow 0.30
#     cv             29.5-34.3       30.7        33.6        34.1
#     acf30          0.78-0.87       0.87        0.86        0.86
#     acf60          0.50-0.68       0.64        0.61        0.62
#     outcome        26.5-33.5       24.0        26.4        26.4
#     hypo_rec       50-59           46.2        58.8        60.0
#     insulin_cv     4.5-11.1         5.3         3.8         4.4
#     in range /11                       8           9           9
#
# At 0.15 the outcome spread moves into range, +1.4 +/- 1.0, and the recovery time with it,
# +12.7 +/- 5.1, while both autocorrelations fall. That is the cluster saying the model is too
# predictable, and this is the only one of four mechanisms tried that moves it.
#
# It does so for the wrong reason. The term was added to raise the week-to-week variation in
# total daily insulin towards a real 7.3%, and it lowers it, from 5.3% to 3.8%, taking that
# statistic out of range. The rationale is refuted and the mechanism is kept on the evidence
# of what it actually does, which is a different claim and is recorded as one.
#
# 0.30 buys nothing more and costs hypoglycaemia, 4.09% below 70 against 2.36% at 0.15.
SLOW_TAU_DAYS = 9.0           # correlation time of the multi-day component
SLOW_CV = 0.15

# ------------------------------------------------------------------ the diurnal pattern
# Two shapes are available and they disagree about something structural.
#
# `sinusoid` is the one this package started with: a single cosine, lowest at 06:00 and
# highest at 18:00, applied identically to every subject. Its breakfast value is a good
# match for the measurement it was aimed at. Hinshaw et al. (2013) put postprandial
# sensitivity at 5.1, 7.5 and 7.2 (10^-4 dL/kg/min per uU/mL) at breakfast, lunch and
# dinner in 19 subjects with type 1 diabetes, so breakfast sits at 0.68 of the highest
# meal, and the cosine gives 0.68 at 07:00. It then keeps rising, which makes dinner the
# most insulin-sensitive meal of the day by 13% over lunch, where the measurement has the
# two within 4% of each other.
#
# `visentin` is the published model, and the reason to prefer it is not the numbers but
# the shape of the claim. Hinshaw could not establish a population pattern at all: the
# difference across meals was not significant (P = 0.34), the spread between subjects was
# nearly three times what was expected, and the paper's conclusion is that any diurnal
# pattern "is individual specific" and cannot be extrapolated to the type 1 population.
# Applying one common curve to every subject is the thing that finding rules out.
#
# Visentin et al. (2015) built the model that goes with it, for the S2013 simulator. Each
# subject's sensitivity is normalised to its own maximum, values above 60% called high and
# below called low, which gives seven distinguishable daily patterns. Each in silico
# subject is assigned one, with the probabilities their 20 subjects produced.
SI_CLASSES = {
    1: ("h", "h", "h"),       # equivalently l-l-l: no pattern at all
    2: ("h", "h", "l"),
    3: ("h", "l", "h"),
    4: ("h", "l", "l"),
    5: ("l", "h", "h"),
    6: ("l", "h", "l"),
    7: ("l", "l", "h"),
}
SI_CLASS_PROBABILITY = {1: 0.10, 2: 0.05, 3: 0.05, 4: 0.10, 5: 0.20, 6: 0.20, 7: 0.30}

# "In each class, low S_I values were (mean +/- SD) 40% +/- 23% of the high." The spread is
# most of the point: it is what makes two subjects of the same class behave differently.
SI_LOW_FRACTION = 0.40
SI_LOW_FRACTION_SD = 0.23
SI_LOW_FRACTION_BOUNDS = (0.15, 0.90)

# The nominal pattern is modulated by multiplicative noise N(1, 0.2^2), chosen so that a
# subject can drift into a neighbouring class but not across the whole set.
SI_CLASS_NOISE_SD = 0.20

# "An almost step-wise line signal that varies three times a day, at 4 a.m., 11 a.m. and
# 5 p.m." Each segment carries the level for the meal it contains, so 04:00 to 11:00 is
# breakfast, 11:00 to 17:00 lunch, and 17:00 round to 04:00 dinner. Almost step-wise
# rather than step-wise: their figure blends over about an hour, and a true step would put
# a discontinuity into a differential equation.
SI_EDGES = (4.0, 11.0, 17.0)
SI_SEGMENT_HOURS = (7.0, 6.0, 11.0)
SI_SMOOTH_HOURS = 1.0

# Measured, and the answer was no. Implemented faithfully with the published probabilities,
# ratio, transition times and noise, the seven-class model produces a diurnal glucose
# amplitude of 108 mg/dL on ten adults over 28 days, against 57 for the cosine and a real
# range of 34.7 to 56.3. It also kills four of the ten subjects, where the cosine loses
# none. Suspecting the day-to-day terms of compounding, since Visentin's noise describes
# something this package already models separately, the arm was rerun with this package's
# term switched off: survival recovered to eight of ten and the amplitude stayed at 108.
# So the amplitude comes from the structure rather than from double-counted noise, and the
# structure is the point of the model.
#
# The likely reason it does not transfer is that a sustained step held for six to eleven
# hours is a different thing from a smooth curve of similar range. Visentin validated
# against six-hour postprandial windows in a controlled inpatient protocol with the therapy
# settings adjusted to suit, not against 28 days of free living under a closed loop with
# settings titrated at nominal parameters.
#
# It stays available and off by default, the same treatment as the S2013 risk term, because
# a published model that does not transfer is worth being able to re-measure. Run it with
# `python examples/layer_ablation.py --arm visentin`.

# Whether to rescale each subject's pattern so its time-weighted mean is 1.0.
#
# Visentin does not. High means 100% of the subject's time-invariant value and low means
# 40% of it, so a class 7 subject averages 0.68 of nominal over the day and is materially
# more insulin resistant than the parameters say. They compensate on the therapy side,
# noting that varying S_I "perturbs the in silico subjects from their ideal condition, thus
# requiring modification of each subject's parameters, such as CR and correction factor",
# and their simulated boluses ran about 2 U below the optimal ratio.
#
# This package cannot follow them there without giving up something load-bearing. Every
# generated subject is closed at a basal steady state and its carbohydrate ratio and
# correction factor are measured from its own model at nominal parameters. Dropping mean
# sensitivity by a third would push the whole population off that steady state in one
# direction, and the resulting rise in glucose would be an artefact of the normalisation
# choice rather than evidence about diurnal patterns. Rescaling to unit mean keeps the
# ratio between segments, which is what the paper measured, and leaves the titration
# intact. Set it False for the literal model.
SI_NORMALISE_TO_UNIT_MEAN = True

# ------------------------------------------------------------------ S2013 hypoglycaemia
# S2013's first hypoglycaemia change, from equation A10 of the S2017 appendix:
#
#     U_id = [V_m0 + V_mx . X . (1 + r1 . risk)] . G_t / (K_m0 + G_t)
#
# Insulin-dependent glucose utilisation rises as glucose falls, so a low gets deeper. It is
# not counterregulation. It exists because S2008 under-reports hypoglycaemia: measured
# against clinical data, S2008 puts 3.59% of values in the hypoglycaemic range against a
# real 6.47%, and S2013 puts 7.98%.
#
# S2013's risk function is Kovatchev's Low Blood Glucose Risk Index, published in 1997 and
# already implemented in `analysis/safety.py`. That fixes the exponent at 1.084 and the
# threshold at 60 mg/dL, leaving r1 as the only free parameter.
#
# The other half of S2013's hypoglycaemia work is a glucagon compartment acting on
# endogenous glucose production, which is the actual counterregulation. It is not
# implemented, because its eight parameters were "randomly generated from an appropriate
# joint distribution" that the papers do not publish. So this brings in the half that makes
# lows worse without the half that rescues from them, and that asymmetry has to be watched
# rather than assumed away.
HYPO_RISK_THRESHOLD = 60.0    # mg/dL, the Gth of Dalla Man et al. (2014)
HYPO_RISK_EXPONENT = 1.084    # Kovatchev's LBGI exponent
HYPO_RISK_SCALE = 1.509       # Kovatchev's LBGI scale
# r1. Default zero, so the risk term is off and the body behaves as stock S2008.
#
# It was implemented, calibrated and measured on 2026-08-07, and then switched off. Both
# halves of that are worth recording.
#
# Calibrated at 0.05, time below 70 mg/dL moves from 2.79% to 4.18% against 4.07% measured
# across 30 real closed-loop users, so the risk term does exactly what the papers say: it
# corrects S2008's under-reporting of hypoglycaemia.
#
# It was switched off for two reasons. The first is measured. Holding the sensitivity layer
# constant and adding only this, the diurnal amplitude goes from 73.1 to 86.3 mg/dL against
# a real 34.7 to 56.3, and hypoglycaemia rebound does not move at all, 3.4 to 3.6. Across
# the full stack the fidelity table falls from eight of eleven to six, losing variability
# and diurnal amplitude, and one more subject in ten stops surviving. The rebound row this
# was aimed at improved by two points out of a gap of thirty-five.
#
# The second reason is methodological. r1 is a property of the body, and it was calibrated
# against time below 70, which is a property of the body and the algorithm together. Dalla
# Man et al. calibrated the same mechanism against hyperinsulinaemic clamps in 32 subjects,
# glucose driven down at 1 mg/dL/min to 50 mg/dL, which is a challenge with no controller
# in it. That is the right kind of target and this package does not have the data for it.
#
# The deeper point is that S2013 introduced this together with a glucagon compartment that
# raises endogenous glucose production during a low. The two oppose each other by design.
# Shipping the half that deepens lows without the half that recovers from them is not a
# partial implementation of S2013, it is a different model. The glucagon parameters are not
# published, so the pair cannot currently be implemented together.
HYPO_RISK_GAIN = 0.0


def hypo_risk(glucose_mgdl, basal_mgdl, threshold=HYPO_RISK_THRESHOLD):
    """The risk term of equation A12, which is the low half of Kovatchev's risk index."""
    g = max(float(glucose_mgdl), threshold)
    if g >= basal_mgdl:
        return 0.0
    f = HYPO_RISK_SCALE * (np.log(g) ** HYPO_RISK_EXPONENT
                           - np.log(basal_mgdl) ** HYPO_RISK_EXPONENT)
    return 10.0 * f ** 2


def draw_si_pattern(rng, n_days, normalise=SI_NORMALISE_TO_UNIT_MEAN):
    """Assign one subject a diurnal sensitivity class and its daily realisations.

    Returns the class number, the nominal level for each of the three segments, and a
    per-day, per-segment noise array. Separated from the patient so the population's
    class mix can be checked against the published probabilities without stepping a
    differential equation.
    """
    classes = sorted(SI_CLASSES)
    cls = int(rng.choice(classes, p=[SI_CLASS_PROBABILITY[c] for c in classes]))
    low = float(np.clip(rng.normal(SI_LOW_FRACTION, SI_LOW_FRACTION_SD),
                        *SI_LOW_FRACTION_BOUNDS))
    nominal = np.array([1.0 if s == "h" else low for s in SI_CLASSES[cls]], float)
    if normalise:
        nominal = nominal / (float(np.dot(nominal, SI_SEGMENT_HOURS)) / 24.0)
    noise = rng.normal(1.0, SI_CLASS_NOISE_SD, size=(int(n_days) + 2, 3))
    return cls, nominal, np.clip(noise, 0.3, 1.7)


def si_at(hour, levels, edges=SI_EDGES, smooth_hours=SI_SMOOTH_HOURS):
    """The segment level in force at an hour, blended across each transition.

    `levels[i]` takes effect at `edges[i]` and holds until `edges[i + 1]`, wrapping.
    """
    hour = float(hour) % 24.0
    n = len(edges)
    for i, edge in enumerate(edges):
        offset = (hour - edge + 12.0) % 24.0 - 12.0
        if abs(offset) < smooth_hours / 2.0:
            weight = 0.5 * (1.0 + np.sin(np.pi * offset / smooth_hours))
            return float(levels[(i - 1) % n] * (1.0 - weight) + levels[i] * weight)
    for i in range(n):
        lo, hi = edges[i], edges[(i + 1) % n]
        if (lo <= hour < hi) if lo < hi else (hour >= lo or hour < hi):
            return float(levels[i])
    return float(levels[-1])


# How much one meal's absorption differs from another's in the same person.
#
# simglucose's gastric emptying is deterministic given the meal, so the same 60 g absorbs
# identically every time. Real meals of the same size differ in fat, protein and form, and
# the spread is large. Across 6 users of the OpenAPS Data Commons export with at least fifteen
# isolated meals of 30 to 80 g eaten from a starting glucose of 80 to 160 mg/dL, the
# within-person coefficient of variation of the time to peak is 0.51, with quartiles at 0.47
# and 0.58, and of the rise per gram 0.68.
#
# This matters because three fidelity signatures fail together and all say the model is too
# predictable: the autocorrelation at thirty and sixty minutes sits above its range and the
# spread of outcomes from a stuck high below its own. Meal absorption acts on exactly that
# horizon and is the largest deterministic input the model has.
#
# The factor multiplies the gastric emptying rates and the intestinal absorption rate
# together, which shifts both when a meal peaks and how sharply. It is drawn once when a meal
# starts and held until the next one, so a meal still absorbing when the next begins takes the
# new factor for its tail. Meals here are three or more hours apart, so that is rare.
# Calibrated 2026-08-12 against the real spread above, ten subjects over 56 days:
#
#     setting   time to peak   CV time to peak   CV rise per gram   rise per gram
#      0.0           94 min          0.36               0.46             1.35
#      0.5           88 min          0.43               0.53             1.36
#      0.9           90 min          0.49               0.63             1.21
#     real          135 min          0.51               0.68             1.41
#
# 0.9 reproduces both spreads and leaves the mean rise per gram where it was, so the
# mechanism adds variance without biasing the level.
MEAL_ABSORPTION_CV = 0.9
# A systematic slowing, separate from the spread, and left at 1.0 because it does not do what
# it was added for. Real meals peak at 135 minutes and this model's at 90, which looks like
# absorption being too fast. It is not: slowing every rate threefold moves the peak from 90 to
# 100 minutes and saturates, while dragging the rise per gram from 1.21 down to 0.85 against a
# real 1.41.
#
#     scale   time to peak   rise per gram
#      1.00        90 min         1.21
#      0.70        98 min         1.22
#      0.50        99 min         1.02
#      0.35       100 min         0.85
#
# The gap turned out not to be a gap. Real time to peak was counted from the carbohydrate
# entry and the simulated from the meal, and pre-bolusing means those differ by fifteen or
# twenty minutes. Measured from the trough after the entry, which is the duration of the rise
# and is identical on both sides, real meals give 112 minutes against a simulated 100, with
# quartiles of 70 to 165 against 75 to 144.
#
# One consequence for the spread calibrated above. The 0.51 within-person coefficient of
# variation of time to peak was measured on the entry clock, so it carries whatever variation
# there is in how long before eating somebody boluses. It is therefore an upper bound on
# absorption variability, and the 0.9 setting fitted to it may be too high. On the trough
# clock the real quartile spread is 0.85 of the median against a simulated 0.69, so the
# direction holds and the size is smaller than the entry-clock figures suggest.
MEAL_ABSORPTION_SCALE = 1.0
MEAL_ABSORPTION_BOUNDS = (0.35, 2.6)


class VaryingPatient(T1DPatient):
    """T1DPatient with a time-varying insulin-sensitivity factor.

    Construct with `withName` as usual, then call `set_sensitivity` before stepping. A
    patient that has not had `set_sensitivity` called behaves exactly as the stock
    T1DPatient, so this class is a safe drop-in.
    """

    def set_meal_variability(self, rng, cv=MEAL_ABSORPTION_CV,
                             scale=MEAL_ABSORPTION_SCALE):
        """Switch on meal-to-meal variation in how fast carbohydrate arrives.

        `cv` is the coefficient of variation of the multiplicative factor. Zero leaves the
        stock deterministic absorption, so a patient that has not had this called behaves
        exactly as before.
        """
        self._kabs0 = float(self._params["kabs"])
        self._kmax0 = float(self._params["kmax"])
        self._kmin0 = float(self._params["kmin"])
        self._meal_rng = rng
        self._meal_cv = float(cv)
        self._meal_scale = float(scale)
        self._meal_factor = float(scale)
        self._last_cho = 0.0
        self._meal_varying = self._meal_cv > 0.0 or self._meal_scale != 1.0

    def _meal_absorption(self, action):
        """Draw a fresh factor when a meal starts, and apply the one in force."""
        if not getattr(self, "_meal_varying", False):
            return
        cho = float(getattr(action, "CHO", 0.0) or 0.0)
        if cho > 0.0 and self._last_cho <= 0.0:
            sigma = np.sqrt(np.log(1.0 + self._meal_cv ** 2))
            draw = (self._meal_rng.lognormal(-0.5 * sigma ** 2, sigma)
                    if self._meal_cv > 0.0 else 1.0)
            self._meal_factor = float(np.clip(self._meal_scale * draw,
                                              *MEAL_ABSORPTION_BOUNDS))
        self._last_cho = cho
        self._params["kabs"] = self._kabs0 * self._meal_factor
        self._params["kmax"] = self._kmax0 * self._meal_factor
        self._params["kmin"] = self._kmin0 * self._meal_factor

    def set_activity(self, activity, vmx_gain=None, vm0_gain=None):
        """Switch on physical activity.

        `activity` is a `person.activity.Activity`. Peripheral utilisation in the model is
        `Vm0 + Vmx * X`, insulin-independent plus insulin-dependent. A session raises both,
        which is why exercise lowers glucose even with little insulin about. What it leaves
        behind raises only `Vmx`, so a post-exercise low needs insulin on board and a low
        during a session does not.

        `Fsnc` is left alone: it is brain and nerve uptake and does not move with exercise.
        """
        from ..person.activity import VM0_GAIN, VMX_GAIN
        self._activity = activity
        self._act_vmx_gain = VMX_GAIN if vmx_gain is None else float(vmx_gain)
        self._act_vm0_gain = VM0_GAIN if vm0_gain is None else float(vm0_gain)
        self._vmx0 = float(self._params["Vmx"])
        self._vm00 = float(self._params["Vm0"])

    def _apply_activity(self, si):
        """Returns the sensitivity factor with activity folded in, and sets Fcns."""
        act = getattr(self, "_activity", None)
        if act is None:
            return si
        minute = float(self.t)
        during, after = act.during(minute), act.after(minute)
        self._params["Vm0"] = self._vm00 * (1.0 + self._act_vm0_gain * during)
        return si * (1.0 + self._act_vmx_gain * during
                     + act.after_gain * after)

    def set_hypo_risk(self, gain=HYPO_RISK_GAIN):
        """Switch on S2013's risk-modulated insulin action below basal glucose.

        `gain` is r1 of equation A10. Zero is the stock S2008 behaviour.
        """
        self._vmx0 = float(self._params["Vmx"])
        self._hypo_gain = float(gain)
        self._basal_glucose = float(self._params["Gb"])

    def set_sensitivity(self, rng, n_days, diurnal=DIURNAL_AMPLITUDE,
                        interday_cv=INTERDAY_CV, pattern="sinusoid",
                        slow_cv=None, slow_tau_days=SLOW_TAU_DAYS):
        """Switch on time-varying sensitivity.

        `pattern` selects the diurnal shape: "sinusoid" for the common cosine, "visentin"
        for the per-subject seven-class model. The day-to-day term applies to both, since
        it describes something neither shape does.
        """
        if pattern not in ("sinusoid", "visentin"):
            raise ValueError(f"unknown sensitivity pattern {pattern!r}")
        self._vmx0 = float(self._params["Vmx"])
        self._kp30 = float(self._params["kp3"])
        self._diurnal = float(diurnal)
        self._pattern = pattern
        if pattern == "visentin":
            self.si_class, self._si_levels, self._si_noise = draw_si_pattern(rng, n_days)
        sigma = np.sqrt(np.log(1.0 + interday_cv ** 2))
        self._interday = rng.lognormal(-0.5 * sigma ** 2, sigma, size=int(n_days) + 2)
        # A first-order autoregressive series on the log scale, so the slow term is
        # lognormal like the daily one and its runs have the stated correlation time.
        cv = SLOW_CV if slow_cv is None else float(slow_cv)
        if cv > 0.0:
            s2 = np.sqrt(np.log(1.0 + cv ** 2))
            phi = float(np.exp(-1.0 / max(float(slow_tau_days), 1e-6)))
            n = int(n_days) + 2
            eps = rng.normal(0.0, s2 * np.sqrt(1.0 - phi ** 2), size=n)
            x = np.empty(n)
            x[0] = rng.normal(0.0, s2)
            for i in range(1, n):
                x[i] = phi * x[i - 1] + eps[i]
            self._slow = np.exp(x - 0.5 * s2 ** 2)
        else:
            self._slow = np.ones(int(n_days) + 2)
        self._varying = True

    def _segment(self, hour):
        for i in range(len(SI_EDGES)):
            lo, hi = SI_EDGES[i], SI_EDGES[(i + 1) % len(SI_EDGES)]
            if (lo <= hour < hi) if lo < hi else (hour >= lo or hour < hi):
                return i
        return len(SI_EDGES) - 1

    def sensitivity(self):
        """The factor in force now. 1.0 means the published parameter value."""
        if not getattr(self, "_varying", False):
            return 1.0
        hour = (self.t / 60.0) % 24
        day = int(self.t // 1440)
        if getattr(self, "_pattern", "sinusoid") == "visentin":
            levels = self._si_levels * self._si_noise[day]
            shape = si_at(hour, levels)
        else:
            shape = 1.0 - self._diurnal * np.cos(2 * np.pi * (hour - 6) / 24)
        slow = getattr(self, "_slow", None)
        slow = 1.0 if slow is None else float(slow[min(day, len(slow) - 1)])
        return float(np.clip(shape * self._interday[day] * slow, *SENSITIVITY_BOUNDS))

    def step(self, action):
        self._meal_absorption(action)
        si = self.sensitivity() if getattr(self, "_varying", False) else 1.0
        if getattr(self, "_varying", False):
            self._params["kp3"] = self._kp30 * si
        # Activity multiplies the sensitivity factor and sets the insulin-independent term,
        # so it composes with the diurnal and day-to-day variation rather than replacing it.
        si_act = self._apply_activity(si)
        gain = getattr(self, "_hypo_gain", 0.0)
        if gain > 0.0:
            # Vmx carries both the sensitivity factor and the risk term, exactly as
            # equation A10 composes them.
            risk = hypo_risk(self.observation.Gsub, self._basal_glucose)
            self._params["Vmx"] = self._vmx0 * si_act * (1.0 + gain * risk)
        elif getattr(self, "_varying", False) or getattr(self, "_activity", None):
            self._params["Vmx"] = self._vmx0 * si_act
        return super().step(action)


def from_population(name, **kwargs):
    """Build a VaryingPatient from this package's generated population."""
    import pandas as pd
    from ..population import params_for
    return VaryingPatient(pd.Series(params_for(name)), **kwargs)
