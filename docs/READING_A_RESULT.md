# Reading a result from this bench

This page is for someone holding a figure produced by this package and deciding what it can be
taken to mean. It states which comparisons the bench supports, at what resolution, and which it
does not, with the size of the residual where one has been measured. Every figure below traces
to a file in `docs/measurements/` and to the script in `examples/` that wrote it. Where a claim
rests on a modelling choice rather than a measurement, the sentence says so. The longer form,
organised by the real cohort each simulated one is matched to and ending in a question-by-question
table of what a run against them supports, is study 19 of the paper series
(`Research-Papers/TimSim/19_reading_against_real_cohorts.md`).

The short form. The bench compares closed-loop algorithms of similar aggressiveness against each
other on the same simulated people, and resolves differences of about three points of time in
range on forty subjects over 28 days. It does not place any of them against a real cohort in
absolute terms and it does not settle open loop against closed loop. The hypoglycaemia tail is
not described well enough for a figure below 54 mg/dL to be quoted without the caveat in the
second table.

## What a figure was measured on

A number from this bench, unless its provenance block says otherwise, was measured on the sensor
trace (`cgm`) rather than on interstitial glucose without sensor error (`bg`), on subjects
whose settings were titrated under the built-in correction loop until their own record cleared
the consensus hypoglycaemia floors, over 28 days on the bench month (`seeds.BENCH`), with the
shipped four layers on and meals announced as the shipped default announces them. The two
signals differ by the sensor model alone and the difference is not small: the same runs give
100 excursions below 54 mg/dL on `bg` and 380 on `cgm`. `docs/METHODS.md` sets out each of
these choices and what moving one does.

A quoted result carries its settings digest, its population fingerprint, its target, its
reference population, its completion count and why its runs ended, because across four
configurations of one unmodified algorithm time below 70 mg/dL spans 2.75 to 7.61 per cent
where the two algorithms compared on a fixed configuration differ by 3.37 points
(`docs/METHODS.md`, "What a result has to carry"). A figure without those is a figure about
the harness.

## Comparisons the bench supports

| Comparison | Resolution | Condition | Where measured |
|---|---|---|---|
| Two closed loops against each other, paired per subject | 2.78 points of time in range on 40 subjects over 28 days, measured on the design; 2.43 on 20 over 14 days | the difference clears the A/A floor and its interval clears zero | `driver_ranking.json`, `docs/VALIDATION.md` level 5 |
| The same on the low blood glucose index | 0.23 on 40 subjects, 0.32 on 20, 0.40 on 12 | as above | `ranking_power.json` |
| A stress test for a named pathological behaviour | four named defects each shift the index past the 0.23 floor at 40 subjects, two of them by less than the floor's own uncertainty | the defect's shift exceeds the floor at the size run | `ranking_power.json`, `timsim/validation/ranking.py` |
| Attributing an effect to a mechanism by switching it off | the statistic the mechanism is meant to move, with the layer on and off | the statistic has been shown to see the mechanism | `mechanism_regression.json`, `examples/layer_ablation.py` |
| A pre-clinical gate with fixed criteria | bounded by exposure: 2800 subject-days with no severe event bounds the rate no lower than about one per 2.6 subject-years | the verdict is quoted with the exposure that produced it | `timsim/validation/gate.py` |

The first row is the one the bench was built for, and its dependence on the largest known
residual was measured. Raising the meal rise of the published model until oref0 SMB's covered
rise reads the real 15.1 mg/dL per 10 g leaves the order of the three closed-loop drivers where
it was and moves no difference among them by more than 2.0 points at the estimate, or 3.7 at
the edge of the interval, on twenty subjects (`meal_yield_ranking.json`).

## The ranking, on the shipped configuration

Measured on 6 September 2026 by `examples/rank_drivers.py` (`driver_ranking.json`, 200 runs in
51 minutes): the forty-adult panel, 28 days on the bench month, the four closed-loop drivers
under the shipped configuration, and the built-in trend loop a second time on a second month
(`seeds.AA`) as the A/A arm. The fifty-eight runs this shares with `meal_yield_ranking.json`
reproduced it to the decimal. Each column is over that driver's completers, as median, mean and
range, the way the trials report; the terminations are listed beneath.

| Driver | n | TIR % | TBR70 % | TBR54 % | TAR180 % | LBGI | U/day |
|---|---|---|---|---|---|---|---|
| trend loop | 40 | 77.3, 78.5 (66.2–88.5) | 1.30, 1.80 (0.55–4.75) | 0.24, 0.49 (0.02–1.84) | 20.7, 19.7 (6.7–31.0) | 0.46, 0.55 (0.18–1.25) | 55.9 |
| Control-IQ stand-in | 39 | 81.4, 80.6 (60.9–90.5) | 2.49, 3.36 (1.10–7.78) | 0.63, 1.06 (0.15–2.96) | 15.5, 16.0 (6.1–33.5) | 0.68, 0.91 (0.33–1.97) | 59.6 |
| Boost | 40 | 79.5, 79.4 (64.6–91.8) | 1.35, 1.65 (0.26–5.87) | 0.21, 0.43 (0.02–1.98) | 19.5, 18.9 (6.0–33.4) | 0.44, 0.50 (0.11–1.57) | 55.1 |
| oref0 SMB | 38 | 86.1, 84.4 (69.5–92.8) | 3.92, 4.17 (1.12–9.61) | 0.99, 1.25 (0.22–3.79) | 9.8, 11.5 (3.4–26.6) | 1.10, 1.20 (0.52–2.46) | 65.9 |

Three of 160 runs ended early: one hypoglycaemic under the stand-in (adult#033, day 14) and,
under oref0 SMB, one hypoglycaemic (adult#020, day 15) and one hyperglycaemic with the infusion
site not absorbing (adult#014, day 24). Every figure in the table is conditioned on the rest.

The floor was measured on the design itself. The trend loop against itself across two months
gives a paired median of +0.86 points of time in range [-2.49, 1.90], so the null comes out
null, with a paired standard deviation of 6.28 points; at 80 per cent power and a two-sided 5
per cent level that resolves 2.78 points on forty subjects, and 0.59 points below 70 mg/dL,
0.25 below 54, 2.92 above 180 and 0.14 on the low blood glucose index. The spread is wider
than the 3.88 points measured on twenty subjects over 14 days (level 5), and it is not two
outliers: the standard deviation from the median absolute deviation is 6.13. Forty subjects
over 28 days resolve less than a projection from the smaller design says, which is what
`ranking_power.json` found for the index, and a floor is read at the size it was measured at.

Every pair, on the subjects that completed both arms, as the median paired difference with a
bootstrap interval. A difference is called resolved when the estimate exceeds the floor for
that outcome and the interval clears zero.

| Pair (second minus first) | n | TIR, points | TBR70, points | TBR54, points | LBGI |
|---|---|---|---|---|---|
| trend, oref0 SMB | 38 | +5.78 [4.38, 8.00] | +2.54 [1.74, 3.14] | +0.74 [0.51, 0.93] | +0.70 [0.44, 0.83] |
| Boost, oref0 SMB | 38 | +4.58 [2.98, 7.22] | +2.58 [1.95, 3.05] | +0.76 [0.60, 1.00] | +0.72 [0.57, 0.86] |
| Control-IQ stand-in, oref0 SMB | 37 | +4.61 [0.93, 5.33] | +1.05 [0.35, 1.72] | +0.22 [-0.02, 0.51] | +0.35 [0.14, 0.50] |
| trend, Control-IQ stand-in | 39 | +2.17 [1.30, 4.22] | +1.07 [0.86, 1.69] | +0.36 [0.24, 0.64] | +0.27 [0.21, 0.36] |
| Control-IQ stand-in, Boost | 39 | -1.18 [-3.37, -0.21] | -1.08 [-1.51, -0.84] | -0.30 [-0.58, -0.24] | -0.28 [-0.35, -0.26] |
| trend, Boost | 40 | +1.23 [0.61, 2.03] | -0.21 [-0.35, 0.06] | +0.01 [-0.06, 0.04] | -0.06 [-0.09, 0.01] |

What the bench resolves. oref0 SMB sits first on time in range and last on every hypoglycaemia
measure: 4.6 to 5.8 points of time in range above each of the other three, clear of the 2.78
floor, bought with 2.5 points more time below 70 mg/dL than the trend loop or Boost and 1.05
more than the stand-in, and a low blood glucose index 0.35 to 0.72 higher against a floor of
0.14. The stand-in sits between: below oref0 SMB on every measure, and above the trend loop and
Boost on time below 70 and 54 mg/dL and on the index by amounts that clear their floors. The
trend loop and Boost are not separated on any outcome; their 1.23 points of time in range has
an interval clear of zero and sits under the floor, and the same holds for the stand-in's 2.17
over the trend loop. An interval that clears zero on a median and a floor set from the paired
standard deviation of the mean answer different questions, and where they disagree the
difference is reported as unresolved at this size.

Against the registration (docstring of `examples/rank_drivers.py`). The order on time in range
and on time below 70 mg/dL came out as registered. The oref0 SMB margins on time in range sit
inside the twenty-subject intervals, and its hypoglycaemia excess over the trend loop and Boost
sits inside the registered 2.0 to 2.9 points; the excess over the stand-in, 1.05, is what was
registered for that pair. The stand-in's shortfall to oref0 SMB on time in range, 4.6 points,
is above the 1 to 3 registered from the DCLP3-matched cohort under always-announced meals, and
the difference is reported rather than explained. Completion, 157 of 160, is one above the
registered band. The floor missed the registration: a paired standard deviation of 6.28 where
3 to 5 was expected, so the design resolves 2.8 points rather than the 2 that had been carried
from level 5, and the first table of this page reads accordingly.

The residuals to carry beside this table are the ones in the next section. The order among the
three closed loops has been shown not to depend on the meal rise bound at the size a panel of
twenty resolves; the absolute figures in the first table do depend on the reference, by 5 to
16 points of time in range, and the hypoglycaemia columns are spread four to five times wider
across subjects than a trial's across people.

## Comparisons the bench does not support

Each row is a measured residual rather than a suspicion, and the size is the size to carry
beside any figure that depends on it.

| Comparison | What the bench does instead | Size | Where measured |
|---|---|---|---|
| An algorithm's absolute time in range against a real cohort | scores every closed loop above the people it is prescribed to, by an amount set by which cohort is asked | 4.8 points above the OpenAPS Data Commons users, 12.0 above the DCLP3 closed-loop arm, 16.3 above the CLOSE-IT participants; 2.6 of that range is the controller and 1.2 the cohort | `docs/BASELINE.md`, `bench_matrix.json` |
| Open loop against closed loop | judges the open-loop arm on meals that rise about a third less per gram than a real adult's | the open-loop shortfall on time in range widens by 4.4 to 7.3 points when the rise is brought to the real figure, and its time below 70 mg/dL moves from third of four to first | `meal_yield_ranking.json` |
| Time below 54 mg/dL, or any figure from the hypoglycaemia tail | spreads the tail four to five times wider across subjects than the trial did across people | ratio of the between-subject spread to the real one 4.38 [3.26, 5.96] against DCLP3 under the Control-IQ stand-in and 4.73 [3.61, 6.38] under oref0 SMB; 1.09 [0.77, 1.76] against the Commons | `spread_ratio.json` |
| How a person recovers from a low nobody treats | recovers slowly, and about a third of subjects produce no glucose at all under a 55 mg/dL clamp | 105 minutes to 100 mg/dL under the built-in loop and 114 under oref0 SMB against 65 (41 to 119) for Commons users; 86 of 230 adults produce no glucose at 55 mg/dL with the defence off and 79 of 232 at the shipped gain | `low_recovery.json`, `hypo_defence_gain.json` |
| Whether a fast-acting loop is safe on a person who does not treat lows | eight of 40 adults under oref0 SMB leave the range from below inside 28 days when nothing is eaten, against one when the person treats | the shipped person treats every low it notices, which hides the slow recovery from any figure measured on it | `low_recovery.json` |
| What a dosing change does to a particular person | reproduces the spread of glucose thirty minutes after a stuck high on ten subjects only | 27.0 mg/dL [22.0, 30.7] against 26.5 to 33.5 real, inside the range for the first time and at its confident end | `docs/VALIDATION.md`, "What none of this establishes" |
| Calling an algorithm safe | bounds the severe event rate from exposure, and cannot see a rate below the bound | one per 2.6 subject-years from 2800 subject-days with no events | `timsim/validation/gate.py` |
| Anything measured on untitrated settings | measures the settings as much as the algorithm | oref0 SMB on the physiological correction factor spends 3.66 per cent of time below 70 mg/dL against 1.40 at the titrated one; the Control-IQ stand-in moves from 2.29 to 1.91 | `docs/METHODS.md`, `examples/titration_reference.py` |

Two residuals sit inside the real spread and are recorded here so a reader does not carry them
as caveats. Insulin delivered per kilogram is 0.657 U/kg/day under the built-in loop and 0.758
under oref0 SMB against 0.527 (0.356 to 0.838) for the DCLP3 adults, inside the range on both
(`insulin_requirement.json`). Rebound after a treated low, the share followed by a reading
above 180 mg/dL within two hours, is 34 per cent per person (17 to 65 across 40 adults)
against the Commons users' 26 (10 to 49), also inside (`low_recovery.json`).

## Where the residuals come from, as far as is known

The meal rise is placed. Per 10 entered grams on covered meals, the simulated adult rises 9.9
to 11.5 mg/dL depending on the driver where 470 adult Loop participants rise 15.1 (10.1 to
22.3 across people, `insulin_by_peak.json`). The controller, the grams denominator, the
carbohydrate estimate bias and the insulin delivered by the peak were each excluded in turn,
the last by driving the simulated person with the real insulin profile and finding the rise
unchanged, -0.07 mg/dL per 10 g [-0.75, 0.50] (`insulin_profile_rise.json`). What remains is
the published model's glucose appearance and disposal, which this package does not refit;
`docs/PADOVA_AUDIT.md` sets out why. All thirteen pre-registered candidates for the gap between
the bench and real cohorts have been refuted by measurement, the last of them, a delay in the
liver's response to insulin, on 6 September 2026: at the clamp-fitted scale it moves time in
range +0.27 points (-1.54 to 1.09) paired on the DCLP3 cohort and +2.00 (0.06 to 4.28) on the
Commons, the wrong sign on both, with time above 180 mg/dL unmoved
(`docs/measurements/liver_delay_cohort.json`, `docs/DESIGN_ALIGNMENT.md`).

The slow untreated recovery is the person's. Swapping the controller moves the recovery by 9
minutes paired, so about 40 of the 40 to 50 minutes of excess belong to the simulated person's
counterregulation, and the hepatic defence that was added to supply it produces nothing in a
third of subjects at the shipped gain of 0.05. Raising the gain to 0.25 stops the fall-throughs
and carries the median production to 1.03 mg/kg/min, outside the human band of 0.42 to 0.84,
and on the outcome table moves time below 54 mg/dL by less than the variation between real
groups, so the gain stays where the clamp put it (`hypo_defence_gain.json`,
`docs/DESIGN_HYPOGLYCAEMIA.md`).

The optimism against real cohorts is not one number and has no single cause. Six candidate
explanations were tested and none survived (`docs/BASELINE.md`); the range across references is
larger than the difference between the algorithms being compared, which is why the reference
belongs in any statement of the residual.

## What to do with a figure

Quote a paired difference with its interval and the floor it was read against, on the subjects
that completed both arms, with the terminations listed by direction. State which of the rows
above the comparison depends on. A difference among closed loops that clears the floor is a
finding of this bench. The same difference against an open loop, or an absolute figure against
a trial, is quoted with the residual from the table beside it, since the residual is of the
same size as the difference or larger. Deciding what a change does to a person still needs a
trial.
