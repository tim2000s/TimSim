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
