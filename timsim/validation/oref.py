"""What the shipped oref0 SMB algorithm did on this population, measured.

The record exists for the same reason `validation/boost.py` does: a number quoted in prose
drifts from the run that produced it, and a number in a module can be asserted against.

The reason for running oref0 at all is that it was written elsewhere. Boost is a system this
project has a hand in, so a simulator that reproduces Boost's behaviour has demonstrated
less than it appears to. oref0 has the longest published record of any open-source loop and
knows nothing about this simulator.
"""

# Measured 2026-08-11. Twenty-one subjects drawn to match the DCLP3 closed-loop arm's age
# distribution, 28 days each at seed 0, the default four layers, and the package's default
# target of 110 mg/dL rather than the 90 the real cohort runs.
#
#                                   as the sensor read it        truth
#   mean, mg/dL                                  137.68       137.38
#   time in range 70-180, %                       74.61        76.06
#   below 70, %                                    6.54         5.70
#   below 54, %                                    2.12         1.56
#   above 180, %                                  18.85        18.24
#   above 250, %                                   4.55         4.17
#   between-subject SD of time in range           12.15        12.27
#   between-subject SD of below 70                 4.38         4.44
#
# Both signals are reported because they answer different questions and have been confused
# here before. DCLP3 publishes sensor readings, so a comparison with the trial reads the
# sensor column; the safety figures read the truth column, which carries no sensor error.
COHORT = {
    "measured": "2026-08-11", "subjects": 21, "completed": 20, "days": 28, "seed": 0,
    "matched_on": "DCLP3 closed-loop arm age distribution",
    "target_mgdl": 110.0,
    "reading": {"mean_mgdl": 137.68, "time_in_range": 74.61, "below_70": 6.54,
                "below_54": 2.12, "above_180": 18.85, "above_250": 4.55,
                "tir_sd_between_subjects": 12.15, "below_70_sd_between_subjects": 4.38},
    "truth": {"mean_mgdl": 137.38, "time_in_range": 76.06, "below_70": 5.70,
              "below_54": 1.56, "above_180": 18.24, "above_250": 4.17,
              "tir_sd_between_subjects": 12.27, "below_70_sd_between_subjects": 4.44},
    "insulin_u_per_day": 63.4,
}

# What the algorithm did with the run, rather than what happened to the person. These are the
# figures that separate a closed loop from an open one, and a bench that reports outcomes
# without them cannot tell a working adapter from a broken one that happened to land near the
# right glucose.
BEHAVIOUR = {
    "smb_pct": 36.88,                 # cycles carrying a microbolus
    "smb_mean_u": 0.541,              # size of one, when it fires
    "dose_mean_u": 0.203,             # across all cycles
    "zero_temp_pct": 38.26,           # cycles where basal was withheld entirely
    "temp_issued_pct": 78.02,         # cycles where a temporary basal was set or replaced
    "eventual_bg_median": 119.0,      # oref's own projection, mg/dL
    "carbs_required_pct": 1.86,       # cycles where oref asked for rescue carbohydrate
}

# The subjects' own programmed requirement, which is the figure the delivered total has to be
# read against. At 63.4 U/day against a programmed 61.3 the algorithm is delivering close to
# what the population needs, so the hypoglycaemia below is a matter of distribution in time
# rather than of total dose.
REQUIREMENT = {"programmed_tdi_mean": 61.3, "median": 62.5, "range": (26.0, 141.0)}

# The same twenty-one subjects at the same seed under the package's own controllers, which
# is what makes the oref figures readable. Sensor readings throughout.
#
#   arm                    insulin U/day     TIR    <70    <54   >180   rescues/day  done
#   open loop, no loop              46.9    64.4   2.11   0.57   33.5          1.09  18/21
#   Boost V5, shipped               49.9    72.2   1.31   0.27   26.5          0.82  21/21
#   built-in correction loop        54.5    75.1   2.43   0.62   22.5          1.31  21/21
#   oref0 SMB, shipped              63.4    74.6   6.54   2.12   18.9             -  20/21
#
# The oref0 row pins the sensitivity ratio at 1.0. Running the detection instead changes none
# of these figures measurably; see AUTOSENS below.
#   DCLP3 closed loop, real            -    71.0      -      -  24.65             -      -
#
# Programmed requirement across these subjects is 61.3 U/day.
#
# Three things follow.
#
# Insulin and hyperglycaemia move together across four independent controllers spanning
# 46.9 to 63.4 U/day: time above 180 falls 33.5, 26.5, 22.5, 18.9 in the same order. Nothing
# in the package arranges that, since two of the four arms are other people's code driven
# through a pipe, so it is evidence that the simulator responds to insulin in a graded way
# rather than saturating or running away.
#
# Boost lands closest to the trial it was never fitted to, 72.2% in range against DCLP3's
# 71.0% and 26.5% above 180 against 24.65%, while delivering 19% under the programmed
# requirement. It also carries the lowest hypoglycaemia of any arm including the open loop,
# which is what withholding basal on a fall is supposed to achieve.
#
# oref0 reaches the same time in range as the built-in correction loop, 74.6% against 75.1%,
# and buys the better hyperglycaemia figure with 2.7 times the time below 70 and 3.4 times
# the time below 54. That excess is not a property of the person layer: the same virtual
# subjects sit at 2.43% below 70 under the built-in loop and 1.31% under Boost, so the
# simulator produces ordinary hypoglycaemia rates under two other controllers and the oref
# figure belongs to the oref arm. Sensitivity detection has since been built and does not
# account for it.
LIKE_FOR_LIKE = {
    "measured": "2026-08-11", "subjects": 21, "days": 28, "seed": 0, "signal": "reading",
    "open_loop": {"insulin_u_per_day": 46.9, "time_in_range": 64.4, "below_70": 2.11,
                  "below_54": 0.57, "above_180": 33.5, "rescues_per_day": 1.09,
                  "completed": (18, 21)},
    "boost_v5": {"insulin_u_per_day": 49.9, "time_in_range": 72.2, "below_70": 1.31,
                 "below_54": 0.27, "above_180": 26.5, "rescues_per_day": 0.82,
                 "completed": (21, 21)},
    "built_in_loop": {"insulin_u_per_day": 54.5, "time_in_range": 75.1, "below_70": 2.43,
                      "below_54": 0.62, "above_180": 22.5, "rescues_per_day": 1.31,
                      "completed": (21, 21)},
    "oref0_smb": {"insulin_u_per_day": 63.4, "time_in_range": 74.61, "below_70": 6.54,
                  "below_54": 2.12, "above_180": 18.85, "completed": (20, 21)},
}

# DCLP3's closed-loop arm over its middle 28 days, sensor readings, which is the held-out
# reference this package measures itself against.
AGAINST_DCLP3 = {"time_in_range": 71.0, "above_180": 24.65}

# Sensitivity detection was built on the hypothesis that it explained the excess
# hypoglycaemia, and the measurement refutes it. Twenty-one subjects, paired, sensor readings,
# detection against the ratio pinned at 1.0, with 95% intervals on the paired difference:
#
#   insulin, U/day    63.39 -> 67.44    +4.05 +/- 9.53
#   time in range     74.38 -> 74.16    -0.22 +/- 1.11
#   below 70           6.95 ->  6.47    -0.47 +/- 0.65
#   below 54           2.40 ->  2.13    -0.27 +/- 0.37
#   above 180         18.68 -> 19.37    +0.70 +/- 1.21
#
# Every interval spans zero. The detector is not idle: per-subject median ratios run from 0.70
# to 1.00 and six of the twenty-one sit at the 0.70 clamp, so for those subjects it is asking
# for a larger reduction than oref permits and the hypoglycaemia is unmoved regardless. The
# figures below 70 and 54 therefore stand as they are rather than as upper bounds, and the
# cause of the excess is unidentified.
AUTOSENS = {
    "measured": "2026-08-11", "subjects": 21, "paired": True, "signal": "reading",
    "pinned": {"insulin_u_per_day": 63.39, "time_in_range": 74.38, "below_70": 6.95,
               "below_54": 2.40, "above_180": 18.68, "mean_mgdl": 137.19},
    "detected": {"insulin_u_per_day": 67.44, "time_in_range": 74.16, "below_70": 6.47,
                 "below_54": 2.13, "above_180": 19.37, "mean_mgdl": 138.77},
    "difference_ci95": {"insulin_u_per_day": (4.05, 9.53), "time_in_range": (-0.22, 1.11),
                        "below_70": (-0.47, 0.65), "below_54": (-0.27, 0.37),
                        "above_180": (0.70, 1.21), "mean_mgdl": (1.59, 1.82)},
    "ratio": {"median_of_subject_medians": 0.99, "lowest": 0.70, "highest": 1.20,
              "subjects_at_the_floor": 6},
    "verdict": "no measurable effect on any outcome; the hypothesis that autosens explained "
               "the excess hypoglycaemia is refuted",
}

# What this arm cannot yet be read for.
#
# Carbohydrate reaches the algorithm as a rate integrated into a plain decay rather than as a
# timestamped entry, so oref's own absorption model is seeded rather than driven by the
# deviations it observes.
#
# Insulin on board is built on this package's bilinear action curve rather than the
# exponential one AndroidAPS uses. Both peak at 75 minutes over a five-hour duration, so they
# differ in shape rather than in scale. The alternative has not been tested.
OPEN = (
    "the excess hypoglycaemia is unexplained; autosens was the hypothesis and is refuted",
    "carbohydrate arrives as a rate rather than a timestamped entry",
    "insulin on board uses this package's bilinear curve, not AndroidAPS's exponential one",
)

__all__ = ["COHORT", "BEHAVIOUR", "REQUIREMENT", "LIKE_FOR_LIKE", "AUTOSENS",
           "AGAINST_DCLP3", "OPEN"]
