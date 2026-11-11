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
paired standard deviations of 8.38, 2.85 and 0.68. Every driver lost 11.1 to 11.4 points of time in
range against its September S2008 figure, inside the registered 10 to 25, and terminations came to
1 of 200 where more than 3 of 160 were expected. The comparison with S2008 is made in the next
section, at the same code.

## The S2008 ranking at the same code: registration

Registered 9 November 2026, before the run. The S2008 ranking quoted beside the Hovorka one above
was produced on 6 September at a2d609c, inside the window ISSUES.md 54 marks as suspect on
hypoglycaemia for every oref0 figure. The oref0 adapter then handed oref about half the insulin
on board, and the fix measured on twelve S2008 adults lowered oref0 SMB's time below 70 mg/dL by
2.16 points [-2.69, -1.69] while moving time in range by +0.32 [-1.09, +1.71]. The Hovorka ranking
ran with the fix, so the two differ in the code as well as the body, and four hypoglycaemia
pairs that reverse between them cannot be assigned to the body until S2008 is run at the same code.

`examples/rank_drivers.py --out docs/measurements/driver_ranking_s2008_current.json` runs the
same design on S2008 at the current commit and settings store.

Expected from issue 54 alone: oref0 SMB minus the trend loop on time below 70 mg/dL near +0.4
(2.54 less 2.16), with an interval that may include zero, and on time in range near the 5.78 of
September. The trend loop and the Control-IQ stand-in keep the package insulin curve and are
expected within the A/A floor of their September figures. Boost changes by the curve alone and
has no expectation.

Reading. Where oref0 SMB minus the trend loop, or minus the stand-in, on time below 70 mg/dL or
the index still has an interval clear of zero with the sign opposite to Hovorka's, the reversal
belongs to the body. Where the S2008 interval spans zero or takes Hovorka's sign, the reversal
came from issue 54, and the two bodies do not disagree on that pair.

## The S2008 ranking at the same code: result

Run 9 November 2026 at 946c8f5, 200 runs in 106 minutes beside another seven-worker job, into
`docs/measurements/driver_ranking_s2008_current.json`. The stamp is marked dirty for one untracked
test file; no simulation or driver code differs from 07fd086, which
`tests/test_body_comparison.py` asserts. 198 runs completed, the two terminations hypoglycaemic,
one under the stand-in and one under oref0 SMB.

The trend loop and the stand-in reproduced their September medians to the decimal, as expected
for drivers whose code the fix did not touch. oref0 SMB moved as issue 54 predicts: time below
70 mg/dL from 3.92 to 1.86 per cent and time in range from 86.1 to 85.1. Boost moved from 1.35 to
1.66 below 70 mg/dL. The floor is that of September, resolving 2.78 points of time in range, 0.59
below 70 mg/dL and 0.14 on the index.

| pair | outcome | Hovorka | S2008 at the same code |
|---|---|---|---|
| oref - trend | TIR | 10.24 [9.13, 10.95] | 5.36 [4.63, 7.30] |
| oref - trend | TBR70 | -0.82 [-1.20, -0.30] | 0.29 [-0.05, 1.10] |
| oref - trend | LBGI | -0.14 [-0.23, -0.04] | 0.14 [0.05, 0.26] |
| oref - boost | TIR | 7.44 [5.47, 9.13] | 4.03 [3.34, 5.01] |
| oref - boost | TBR70 | 0.56 [0.21, 0.73] | 0.45 [0.11, 0.98] |
| oref - boost | LBGI | 0.15 [0.10, 0.21] | 0.21 [0.08, 0.31] |
| oref - control-iq | TIR | 4.90 [2.81, 6.58] | 3.63 [2.77, 4.30] |
| oref - control-iq | TBR70 | -3.49 [-4.42, -2.81] | -0.66 [-1.59, -0.03] |
| oref - control-iq | LBGI | -0.78 [-0.91, -0.62] | -0.13 [-0.27, 0.03] |
| control-iq - trend | TIR | 3.71 [1.90, 7.03] | 2.17 [1.30, 4.22] |
| control-iq - trend | TBR70 | 3.01 [1.77, 3.56] | 1.07 [0.86, 1.69] |
| control-iq - trend | LBGI | 0.65 [0.47, 0.82] | 0.27 [0.21, 0.36] |
| boost - control-iq | TIR | -2.52 [-4.07, 0.21] | -1.17 [-2.08, 0.32] |
| boost - control-iq | TBR70 | -4.04 [-5.00, -3.61] | -0.84 [-1.51, -0.60] |
| boost - control-iq | LBGI | -0.97 [-1.05, -0.87] | -0.24 [-0.33, -0.16] |
| boost - trend | TIR | 1.95 [0.86, 4.13] | 1.18 [0.47, 2.46] |
| boost - trend | TBR70 | -1.41 [-2.10, -0.91] | 0.04 [-0.13, 0.34] |
| boost - trend | LBGI | -0.34 [-0.44, -0.20] | -0.00 [-0.05, 0.08] |

At the same code one pair of eighteen reverses by the registered definition: oref0 SMB against the
trend loop on the index, +0.14 [0.05, 0.26] on S2008 and -0.14 [-0.23, -0.04] on Hovorka. The S2008
estimate clears that design's floor of 0.14 by less than 0.01 and the Hovorka one sits below its
floor of 0.30, so the reversal is at the edge of what either design resolves. On time below 70 mg/dL the same pair spans zero on S2008, and oref0 SMB against the
stand-in takes Hovorka's sign on both hypoglycaemia outcomes. The three other reversals counted
against the September column came from issue 54.

The two bodies therefore agree in sign on seventeen of the eighteen pairs. The order on time in
range is the same on both, oref0 SMB first and the stand-in second, and on both the stand-in has
the most time below 70 mg/dL and oref0 SMB has more than Boost. They differ in size: every
hypoglycaemia difference involving the stand-in is three to five times larger on Hovorka, and
Boost against the trend loop resolves on Hovorka (-1.41 [-2.10, -0.91] below 70 mg/dL) and not on
S2008 (0.04 [-0.13, 0.34]). Neither difference in size had been explained when this was
written; the section below locates both.

Agreement here is one change of body between two models that share the absence of
counterregulation and both overstate the uncovered meal, so it bounds a result to those shared
assumptions rather than establishing it as the algorithms'.

## Where the difference in size arises

Measured 10 and 11 November 2026 by `examples/hovorka_gap.py`, whose expectations were committed
before the probes and reruns (a879cfa, with the meal probe added in c59aff1 after the base reruns
had been read). Outputs are `hovorka_gap_existing.json`, `hovorka_gap_runs_*.json`,
`hovorka_gap_runs.json`, `hovorka_gap_probe.json` and `hovorka_gap_meal.json`. The reruns of
trend, the stand-in and Boost on both panels reproduced all 240 ranking runs' time in range and
time below 70 mg/dL to the bit, so the decomposition reads the ranking's own runs. Figures below
are means over the subjects completing both arms, with bootstrap intervals over subjects, where
the table above gives medians of paired differences.

Part of the factor is the statistic. Time below 70 mg/dL sits near zero for many subjects and
the median of a paired difference on it is unstable: the stand-in minus the trend loop is 3.01
against 1.07 on medians, a factor of 2.8, and +2.75 [2.26, 3.26] against +1.57 [1.16, 2.03] on
means, a factor of 1.75. Boost minus the stand-in goes from a factor of 4.8 on medians to 3.0 on
means (-4.35 [-4.97, -3.76] against -1.46 [-1.97, -0.98]). The rest of this section works on
means.

### The stand-in pairs: the same dose, a body that converts it into more time low

The stand-in delivers 6.8 [5.6, 8.3] U/day more than the trend loop on Hovorka and 6.2 [4.9, 7.6]
on S2008, and the composition is the same on both: about 13 U/day more basal and temporary basal,
less in boluses. Its algorithm is doing the same thing to both bodies. On the ratio scale its
excess is also the same, 1.63 [1.51, 1.77] times the trend loop's time below 70 mg/dL on Hovorka
and 1.88 [1.65, 2.15] on S2008, so the larger difference in points follows the trend loop's own
level, 4.37 per cent on Hovorka against 1.80 on S2008 on these runs. Each extra unit a day buys
0.41 [0.30, 0.53] points below 70 mg/dL on Hovorka and 0.25 [0.18, 0.35] on S2008. The same holds
on the true glucose (+2.85 against +1.58), so the sensor does not produce it.

The excess is spread across the panel rather than carried by a few people. The quarter of
Hovorka subjects with the largest excess carries 40 per cent of it, against 55 per cent on S2008,
and it does not follow insulin sensitivity on Hovorka (Spearman -0.16, p = 0.34) where it does on
S2008 (+0.50, p = 0.001). The Hovorka panel is narrower: the coefficient of variation of the
uptake sensitivity is 0.23 against 0.53 for S2008's `Vmx`, and with insulin held at a multiple
of each subject's own basal every Hovorka subject settles at the same glucose to within 1 mg/dL,
because its subjects differ only by a scaling of three sensitivities and body weight. Body weight
(median 77 against 82 kg) and basal per kilogram (1.48 against 1.42 pmol/kg/min) barely differ.

Split by where each low sits, the stand-in's excess falls 57 per cent within four hours of a meal
on Hovorka and 55 per cent on S2008, against the 67 per cent of time those windows cover, with
overnight lows a minor share on both (+0.32 and +0.23 points). The low type does not separate
the bodies.

The bodies alone, with no controller, separate them. Each starts at its basal steady state, and
the two are 28 mg/dL apart there: Hovorka subjects are closed at 115 mg/dL and the S2008 panel
has a median of 143. The first unit of a bolus lowers the Hovorka nadir by 25.8 [22.4, 29.6]
mg/dL and the S2008 nadir by 16.7 [13.0, 18.7], so 2.2 U reach 70 mg/dL from basal on Hovorka
against 5.6 U on S2008. Both bodies flatten by the same proportion as the nadir falls (the drop
per unit at 70 mg/dL is 0.41 and 0.44 of the first unit's), which refuted half of expectation 7.
Held at twice basal insulin, Hovorka reaches 39 mg/dL at twelve hours and falls through 70 at
17.3 mg/dL per hour; S2008 reaches 54 [46, 65] and falls through 70 at 9.2. At one and a half
times basal every Hovorka subject goes below 70 and settles at 60, while S2008 settles at 86 [73,
96] and 10 of 40 subjects reach 70. The difference is S2008's `-kp2*Gp`, which raises production
as glucose falls, and which Hovorka's production, `EGP0 (1 - x3)`, does not have. The shipped
hepatic defence on S2008 contributes almost nothing to it (54 against 53 mg/dL with it removed).

The swap tests put the production term in the loop. Giving Hovorka S2008's autoregulation below
basal, at the S2008 panel's median `kp2` of 0.0036 per minute, lowered the stand-in minus trend
difference by 1.15 [0.70, 1.64] points, from 2.81 to 1.66 on the 36 subjects completing all four runs, while lowering the trend
loop's own level only from 4.40 to 3.91. The gap between the bodies on that pair is 1.41 points
(2.81 against 1.40 on the 35 S2008 subjects completing all four of theirs), so the one term removes 0.5 to 1.2 of it.
Giving S2008 S2013's risk term at r1 = 0.05, which amplifies insulin-dependent uptake below
basal, raised the same difference by 0.72 [0.34, 1.10], from 1.40 to 2.13, and the stand-in
against Boost by 1.04 [0.63, 1.48]. In the held-insulin probe the risk term brings S2008 to 38
mg/dL at twice basal, beside Hovorka's 39. Both swaps used settings titrated on the unmodified
bodies, and four of the risk arm's forty stand-in runs terminated against one in the base arm, so its
change is measured on the survivors and is if anything an underestimate.

### Boost against the trend loop: a difference in what is dosed

Boost and the trend loop separate on Hovorka for a different reason, and neither swap moves it:
-0.11 [-0.52, 0.27] points with Hovorka's autoregulation and -0.30 [-0.67, 0.05] with S2008's
risk term. On the true glucose the risk arm moved it by -0.50 [-0.88, -0.13], towards Hovorka's
sign, which is the only sign of a body term reaching this pair. Boost gives 10.6 U/day less in
meal boluses than the trend loop on Hovorka and 8.1 less on S2008, and 12.5 and 15.0 U/day more in
boluses away from meals. Its time below 70 mg/dL in the four hours after meals is lower by 1.87
[1.56, 2.19] points on Hovorka and by 0.24 [0.07, 0.43] on S2008, against a trend-loop post-meal
level of 3.52 and 1.25 per cent, and it pays 0.62 and 0.52 points more after its own corrections
on the two bodies. On S2008 the two terms cancel. On Hovorka the post-meal term is larger because
the trend loop's post-meal lows are nearly three times as common there. The ratio of Boost to the
trend loop is 0.63 [0.55, 0.70] on Hovorka and 1.07 [0.95, 1.21] on S2008, so this pair does not
reduce to level.

A meal of 50 g bolused at the titrated ratio, with basal held and nothing else acting, falls 39
[36, 40] mg/dL below its starting glucose on Hovorka and 26 [14, 29] on S2008, and goes below 70
mg/dL in 6 of 40 Hovorka subjects and none of 40 S2008 ones. The nadir arrives at 334 and 416
minutes, after the four-hour window used above, so the probe shows that a fully bolused meal
overshoots further on Hovorka without showing that this is the post-meal low the runs record,
which also includes whatever the loop delivers after the meal.

### What this leaves

The stand-in pairs are larger on Hovorka mainly because Hovorka sits closer to 70 mg/dL, responds
more per unit and has nothing that raises production as glucose falls. Its algorithm doses both
bodies alike. Most of the inter-body difference on those pairs is carried by the one term S2008
has and Hovorka lacks, and `docs/MODEL.md` records that term as stronger in S2008 than in the
people it represents. The size of a hypoglycaemia penalty for added insulin is therefore set by
an unmeasured quantity, the slope of production against glucose at the insulin of a spontaneous
low, and the two bodies bracket it from opposite sides. The Boost against trend difference is a
difference in how much is bolused up front, which Hovorka's larger post-meal overshoot rewards
and which no low-glucose term moved. Signs agree on both bodies throughout; sizes in points of
time below 70 mg/dL are body-dependent by the factors above and are not to be quoted as the
algorithms'.

A counterregulation body is not indicated by this. What decides these sizes is how production
responds to falling glucose at loop insulin levels, and `docs/DESIGN_HYPOGLYCAEMIA.md` records
that the available human reference, the Rickels clamp, measures a different state; a third body
would add a third value of the same quantity without a target to choose between them. Nothing
here changes a sign in the ranking either, so it gives no reason to rerun the initial-settings
trial; it does say that any absolute hypoglycaemia figure from that trial carries the body's
choice of this slope.
