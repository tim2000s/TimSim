# A second body: the Hovorka model

Every figure in this package was computed on one set of equations, S2008. An ordering of two
algorithms that reverses when the body is replaced by another published model is a property of the
model, and with one body there was no way to see it. `timsim/patient/hovorka.py` supplies a second
body behind the same interface, so that the person, sensor, site and controller layers are shared
and the equations are the only thing that changes.

## What the body is

The equations are those of Hovorka et al. (Physiol Meas 2004;25:905-920). The population follows
the single-hormone population of Resalat et al. (PLoS One 2019;14(7):e0217301), whose sampling
procedure was transcribed from their MATLAB source rather than from the paper where the two
disagree (`timsim/population/hovorka.py` gives both discrepancies). Only the three insulin
sensitivities and body weight vary between subjects.

Three choices were made that are modelling choices rather than measurements. Endogenous production
is floored at zero, as in Hovorka 2004. A first-order interstitial lag is added at the median `ksc`
of the ten published S2008 adults, 0.0915 per minute, so the sensor sees both bodies through the
same lag. And the physiology layer's time-varying sensitivity and meal-to-meal absorption variation
are drawn exactly as for S2008 and applied to the Hovorka parameters they correspond to. The S2008
hepatic mechanisms (`HYPO_EGP_DEFENCE` and the liver options of `simulate`) are not applied, and
`simulate` refuses them for a Hovorka subject rather than ignoring them. The activity layer is
refused for the same reason.

## Checks against the published population

Resalat's repository ships the 99 subjects their procedure produced. Solving each for its steady
state at 115 mg/dL with `steady_state` and converting to daily insulin as they do gives a median of
42.66 U/day, theirs 42.66, with the largest difference across the 99 at 0.0066 U/day. Across those
subjects `Sf3` has a standard deviation of 64.5 x 10^-4. The sampling standard deviation in their
source is 55 x 10^-4, the realised spread is wider because a shared uniform draw is added, and both
confirm that the 5.9 printed in their Table 2 is a typesetting error. These figures are in
`docs/measurements/hovorka_checks.json`, written by `examples/hovorka_checks.py` given their
`SingleHormone_VPP.mat`.

Generated here at seed 2026, 100 of 100 candidates passed Resalat's two physiological tests and the
plausibility ranges applied to S2008 subjects; Resalat report 99 of 100. Probed from each subject's
own body, the median correction factor is 28.9 mg/dL per unit (IQR 21.0 to 36.2) and the carbohydrate
ratio 7.75 g per unit (IQR 6.37 to 8.68), against 18.6 and 12.5 in the S2008 population and 40.0 and
8.0 in the DCLP3 pump settings. The median daily dose is 43.8 U.

## Where it departs from people

An uncovered meal on basal alone rises 33.0 mg/dL per 10 g at 50 g (IQR 30.3 to 38.1, n = 68) from
a median starting glucose of 151 mg/dL, and peaks at 165 minutes, measured by
`examples/meal_response.py --prefix 'hovorka#'` into `docs/measurements/meal_response_hovorka.json`.
The response is close to linear in size: 34.3, 33.0 and 32.8 at 30, 50 and 70 g. The same producer
gives 21.5 for S2008 across 306 titrated subjects from a median of 146 mg/dL
(`docs/measurements/meal_response.json`), and real uncovered meals rise 15.7 to 19.7 per logged
10 g across every filter in `docs/PADOVA_LIMITS.md`. So an unannounced meal costs this body about
1.7 to 2.1 times what it costs a person, against 1.1 to 1.4 times for S2008, and the cohort figures
below carry that.

Production has no glucose term, so nothing defends a falling glucose. Under the clamp protocol of
`examples/hypoglycaemic_clamp.py`, 1.0 mU/kg/min of insulin holds plasma insulin at 60.4 mU/L and
production falls to zero in 76 of 100 subjects, with a median of 0 and a ninetieth percentile of
0.45 mg/kg/min, at any glucose plateau. Rickels et al. measured 0.59 mg/kg/min (SE 0.12) in people
with no glucagon response. That is computed from the equations and the parameter table rather than
by simulating the clamp, in `examples/hovorka_checks.py`.

Titration under the trend loop (`examples/titrate_cohort.py --cohort hovorka --subjects 100`) found
settings clearing the consensus floors for 68 of 100 subjects, against 306 of 330 on S2008. Of the
68, 47 needed basal alone and 21 a weaker correction factor as well; the median adopted correction
factor is 29.1 mg/dL per unit. The 32 excluded subjects are the more sensitive ones, with a median
daily dose of 33.5 U against 49.9 for those titrated, and every one of them misses the floor below
54 mg/dL on at least one rung. At their adopted settings the titrated subjects reach a median time
in range of 63.2 per cent under the trend loop over the 28 titration days, against 77.3 for the
same loop on titrated S2008 adults in the September driver ranking.

## Driver ranking on the second body: registration

Registered 9 November 2026, before the run. `examples/rank_drivers.py --prefix 'hovorka#'` runs
the design of the S2008 ranking of 6 September 2026 unchanged: 40 titrated subjects, 28 days, the
four drivers on the bench seed and the trend loop again on `seeds.AA`, outcomes on the sensor trace
and pairs on the subjects completing both. Output goes to
`docs/measurements/driver_ranking_hovorka.json`.

The question is whether the ordering is the algorithms'. On S2008 oref0 SMB came first on time in
range and last on time below 70 mg/dL, the Control-IQ stand-in sat between oref0 SMB and the trend
loop on both, and Boost and the trend loop were not separated on the index or time below 70.

Expected if the ordering belongs to the algorithms: the same order on both outcomes. oref0 SMB
first on time in range and highest on time below 70 mg/dL and on the low blood glucose index, with
its intervals against the trend loop and against Boost clear of zero; the stand-in between oref0
SMB and the trend loop on time in range; and Boost against the trend loop inside the design's own
A/A floor on time below 70 and the index.

Expected regardless: every driver lower on time in range than on S2008, by 10 to 25 points, and
higher on time above 180, from the meal response above. More terminations than the 3 of 160 on
S2008, mostly hyperglycaemic.

A reversal is a pair whose interval excludes zero with the opposite sign to S2008 on time in range,
time below 70 mg/dL or the index. One reversal means the S2008 ordering on that pair cannot be
attributed to the algorithms. Agreement means the ordering survived one change of body, which is
weaker than showing it belongs to the algorithms, since both models share the absence of
counterregulation and both overstate the meal response.

## Driver ranking on the second body: result

Run 9 November 2026 at 07fd086, 200 runs in 27 minutes, into
`docs/measurements/driver_ranking_hovorka.json`. 199 runs completed; the one termination was
hyperglycaemic, under the trend loop on day 8.7. Medians over completers:

| driver | n | TIR | TBR70 | TBR54 | TAR180 | LBGI | U/day |
|---|---|---|---|---|---|---|---|
| trend | 39 | 66.2 | 3.66 | 1.13 | 29.6 | 0.90 | 49.1 |
| control-iq | 40 | 70.0 | 6.85 | 2.24 | 22.7 | 1.66 | 55.3 |
| boost | 40 | 68.4 | 2.18 | 0.71 | 28.2 | 0.61 | 48.2 |
| oref | 40 | 74.7 | 2.75 | 0.87 | 22.4 | 0.76 | 52.0 |

The A/A arm resolves 3.76 points of time in range, 1.28 below 70 mg/dL and 0.30 on the index, from
paired standard deviations of 8.38, 2.85 and 0.68. Pairs on the subjects completing both, as median
paired differences with bootstrap intervals, beside the S2008 figures of 6 September:

| pair | outcome | Hovorka | S2008 |
|---|---|---|---|
| oref - trend | TIR | 10.24 [9.13, 10.95] | 5.78 [4.38, 8.00] |
| oref - trend | TBR70 | -0.82 [-1.20, -0.30] | 2.54 [1.74, 3.14] |
| oref - trend | LBGI | -0.14 [-0.23, -0.04] | 0.70 [0.44, 0.83] |
| oref - boost | TIR | 7.44 [5.47, 9.13] | 4.58 [2.98, 7.22] |
| oref - boost | TBR70 | 0.56 [0.21, 0.73] | 2.58 [1.95, 3.05] |
| oref - boost | LBGI | 0.15 [0.10, 0.21] | 0.72 [0.57, 0.86] |
| oref - control-iq | TIR | 4.90 [2.81, 6.58] | 4.61 [0.93, 5.33] |
| oref - control-iq | TBR70 | -3.49 [-4.42, -2.81] | 1.05 [0.35, 1.72] |
| oref - control-iq | LBGI | -0.78 [-0.91, -0.62] | 0.35 [0.14, 0.50] |
| control-iq - trend | TIR | 3.71 [1.90, 7.03] | 2.17 [1.30, 4.22] |
| control-iq - trend | TBR70 | 3.01 [1.77, 3.56] | 1.07 [0.86, 1.69] |
| control-iq - trend | LBGI | 0.65 [0.47, 0.82] | 0.27 [0.21, 0.36] |
| boost - control-iq | TIR | -2.52 [-4.07, 0.21] | -1.18 [-3.37, -0.21] |
| boost - control-iq | TBR70 | -4.04 [-5.00, -3.61] | -1.08 [-1.51, -0.84] |
| boost - control-iq | LBGI | -0.97 [-1.05, -0.87] | -0.28 [-0.35, -0.26] |
| boost - trend | TIR | 1.95 [0.86, 4.13] | 1.23 [0.61, 2.03] |
| boost - trend | TBR70 | -1.41 [-2.10, -0.91] | -0.21 [-0.35, 0.06] |
| boost - trend | LBGI | -0.34 [-0.44, -0.20] | -0.06 [-0.09, 0.01] |

Against the registration, the ordering on time in range survived: oref0 SMB first, the stand-in
second, and every pair on that outcome with the S2008 sign or an interval spanning zero. The ordering
on hypoglycaemia did not. Four pairs reverse by the registered definition, all of them oref0 SMB
against the trend loop and against the stand-in, on time below 70 mg/dL and on the index. On S2008
oref0 SMB had the most hypoglycaemia of the four drivers; on this body it sits below the trend loop
and the stand-in has the most. The S2008 finding that oref0 SMB buys its time in range with
hypoglycaemia relative to those two drivers therefore cannot be attributed to the algorithms. Against
Boost it survives in sign at a quarter of the size, inside the floor on both outcomes.

Two registered expectations missed in other ways. Boost against the trend loop resolves on time below
70 mg/dL (-1.41) and on the index (-0.34) where it was expected inside the floor, so on this body
Boost is the safest of the four on hypoglycaemia. Terminations came to 1 of 200 where more than the
S2008 3 of 160 were expected. The absolute fall in time in range came in as expected, 11.1 to 11.4
points for every driver.

Agreement on time in range is one change of body. Both models lack counterregulation and both
overstate the uncovered meal, so it is weaker evidence that the time in range ordering belongs to the
algorithms than the reversals are that the hypoglycaemia ordering does not. No mechanism for the
reversal has been tested. One candidate is that oref0 SMB sizes its microboluses from the correction
factor, and the physiological factor from which titration starts is 28.9 mg/dL per unit here against
18.6 on S2008, so the same algorithm meets differently placed settings on the two bodies.
