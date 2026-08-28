# Can the UVA/Padova S2008 Simulator Be Made to Resemble a Real Closed-Loop Cohort? A Person-in-the-Loop Layer, Measured Against Two Real Populations

Candidate for publication. Every figure below is traceable to a file in `docs/measurements/`
and was measured against the population and settings store recorded under Provenance.

## Abstract

Background. In-silico testing of automated insulin delivery uses virtual patients
reproducing metabolism without the person around it. The UVA/Padova S2008 release, the one
available without licence, has a noiseless sensor and a patient who announces every meal
accurately and never treats a low. Whether that gap closes from outside the differential
equations is unestablished.

Methods. Four layers were added: sensitivity that moves, a person who eats and treats their own
hypoglycaemia, sensor error inside the loop, and infusion sets that fail. Settings were
titrated to consensus hypoglycaemia floors under a fixed regimen. Cohorts of 70 to 90, matched
to each reference on what it publishes, ran 28 days under a Control-IQ stand-in and under oref0
SMB, with distance to the real population computed before and after on the same people.

Results. On the four measures describing where glucose sits, the layers cut that distance by
55, 39 and 76 per cent across three pairings; on hypoglycaemia they increased it in all three.
They cost 5.4 to 12.3 points of time in range from a bare 93.1 to 95.6, against real cohorts at
71.3 and 80.1. Withdrawing announcement cost the controller without meal detection
4.84 points (3.58 to 7.22) and oref0 SMB 0.08 to 0.84, every interval spanning zero, against
CLOSE-IT's 2.2.

Conclusions. S2008 moves a long way towards a real closed-loop cohort without touching its
equations. Hypoglycaemia moves the wrong way in every pairing and is the measure this bench
places worst. A distinguishability verdict depends on cohort size.

Keywords. simulation, automated insulin delivery, closed-loop, validation, type 1 diabetes,
in-silico testing

## Introduction

The UVA/Padova simulator was accepted in 2008 as a substitute for animal testing ahead of
clinical trials of closed-loop control, and it remains the standard bench for that purpose.
What it models is metabolism. What it does not model is the person: their meals, their
estimates of those meals, their treatment of their own hypoglycaemia, the sensor they wear and
the infusion set that fails without telling them.

Those omissions have grown more consequential since 2008. Contemporary systems detect
unannounced meals and adapt to sensitivity that moves, and they are judged on hypoglycaemia
exposure accumulated over months rather than over hours. An algorithm evaluated against a
patient who announces every meal accurately and never treats a low is being asked an easier
question than the one it will face in use.

Two later releases address part of this. S2013 added a risk term and a glucagon compartment,
and S2017 added time-varying parameters. Both are licensed and not redistributable, so work
outside that licensing arrangement proceeds from S2008. This paper describes what can be added
to S2008 from published sources and from real records, and reports how far the result resembles
people running the same algorithms.

The question is narrower than whether the model is good, and more useful. The ways S2008 departs
from real records are already documented. What has not been established is whether they can be
closed from outside the differential equations, by adding the person the model omits rather than
by altering the physiology it inherits. So: if the bare model sits where no real cohort sits, can
it be moved, how far, and on which measures?

Answering that requires three things a single comparison does not supply. A distance from the
real population that can be computed before and after, in units that make measures with
different scales comparable. A reference population running the same algorithm, so that a
difference is attributable to the bench rather than to the controller. And a floor below which a
difference cannot be established at all, because a cohort places a median far less precisely than
the spread between people suggests.

The question is not whether the simulator predicts an individual's glucose under a dosing change,
which it does not attempt.

## Methods

### The model and the population

The metabolic model is the UVA/Padova S2008 virtual patient reached through simglucose 0.2.11.
Six hundred subjects were generated from the published parameter tables and screened for
steady-state consistency, under a closure test requiring the steady-state relations to reproduce
all thirty published subjects. The population is generated locally and is not redistributed.

The generator is reproducible from its seed, each class drawing from a stream keyed by a stable
digest rather than by a salted hash, so the same seed returns the same subjects in any process.
Subject names are positional, so a regenerated population reuses every name for a different body:
the titration store records a digest of the population its settings were fitted to and refuses to
be applied to any other.

### The layers

Physiology varies insulin sensitivity with a diurnal shape and an independent day-to-day term at
a published coefficient of variation, with a third component correlated across several days on
the reasoning that independent daily draws average out across a week where real runs of days do
not.

Behaviour draws a meal schedule from 292,140 carbohydrate entries logged by 147 real users, scales
it to body weight, announces a main meal with probability 0.80 and a snack with probability 0.35,
and applies a lognormal error to the announced quantity, so the algorithm receives an estimate
rather than the truth. Hypoglycaemia is treated with a helping drawn from a distribution measured
across 4,544 real carbohydrate entries recorded below 75 mg/dL, at a median of 15 g for a reading
of 65 to 75 mg/dL.

The sensor carries error and compression artefacts, quantised to the reporting increment, applied
inside the control loop rather than to the output so that the algorithm and the simulated person
both see them. Comparisons against real records are made on the sensor reading, since that is
what real records contain.

The infusion site fails at a subject-specific rate calibrated against the duration distribution
of prolonged hyperglycaemic excursions in the trial, passing a residual fraction of delivered
insulin. Detection requires the reading to remain above 230 mg/dL for 90 waking minutes.

### Counterregulation, and why nothing was added

S2008 contains no counterregulatory response, and none is added here. Establishing what the model
does during hypoglycaemia requires reproducing the protocol the human
reference figures come from, because glucose production here is a linear function of glucose and
of insulin in a remote compartment, and a figure for it is uninterpretable without the insulin it
was measured at.

A stepped hyperinsulinaemic clamp was reproduced in silico across 20 adults, with insulin infused
at 1.0 mU/kg/min and glucose held at successive plateaus of 90, 80, 65, 55 and 45 mg/dL by a
variable glucose infusion. With no defence term the model produces 0.49 mg/kg/min at the 55 mg/dL
plateau and 0.46 at 45, both inside the 0.42 to 0.84 measured by Rickels et al. in twelve people
with long-standing type 1 diabetes and no discernible glucagon response.

The model is therefore inside the human range at this without a defence term, and the gain ships
at zero. A figure of 0.14 mg/kg/min circulates for the same quantity and is not comparable to it:
it reads production during a spontaneous low under a closed loop and sets it against a clamp
measurement, which are opposite conditions. One happens because the algorithm withdrew insulin,
the other while insulin is deliberately held high, and remote insulin is 219 in the first against
441 in the second.

What the clamp does show is a spread the median hides. Six of 20 subjects produce nothing at all
at the 55 mg/dL plateau and nine of 20 at 45, where no real person produces nothing, and raising
the gain far enough to lift them drives the subjects already producing over 2 mg/kg/min further
out. That width belongs to the published `kp1`, `kp2` and `kp3` values and no gain removes it.

### The algorithms

A stand-in for Control-IQ reproduces Tandem's published description: an automatic correction at
most hourly when glucose is predicted above 180 mg/dL half an hour ahead, at 60 per cent of a
correction towards 110, with basal suspended below 70, reduced below 112.5, raised from 160 and at
its ceiling above 180. What Tandem do not publish is how far basal may be raised, how large a
single automatic correction may be, and how much insulin on board the loop tolerates. Both a
variant using guessed values and a variant fitted to one half of the trial are reported.

oref0 SMB, the OpenAPS reference algorithm, is driven unmodified from its own source across a
node process boundary with one decision marshalled per cycle.

A reactive correction loop supplied with this package is the fixed regimen under which settings
are titrated. It is not a shipped product, is not a model of one, and is not reported as an arm.

### Settings

A virtual subject's correction factor can be computed from its own model, which produces a value
no real person has access to. The corresponding real quantity, taken from the recorded pump
settings of the 112 DCLP3 closed-loop participants and summarised per participant, has a median
of 40.0 mg/dL per unit with an interquartile range of 30.0 to 50.7. Across the 306 subjects that
titrate here the physiological value has a median of 18.6.

Each subject's basal was reduced in five per cent steps to a floor of a fifth until its own record
cleared the consensus hypoglycaemia floors of below 54 mg/dL under 1 per cent and below 70 under
4, with the correction factor weakened only where no basal reduction inside that bound sufficed.
Titration ran under the reactive correction loop for every subject, since tuning a bench with the
system under test in the loop would let a system that provokes hypoglycaemia be answered by
weakening its subjects' settings.

The procedure moves the population very little and should not be read as closing the settings gap.
It leaves 229 of 330 subjects with exactly what they started with, weakens 77, and refuses to dose
24. The population median correction factor moves from 18.6 to 18.9 mg/dL per unit, so the
distance to the trial participants' 40.0 is essentially unchanged. What titration does is exclude
the subjects whose physiological settings put them below the floors, and those 24 exclusions fall
unevenly, at 7 of 21 children against 8 of 199 adults.

### The reference populations, and what each one licenses

The DCLP3 trial supplies the closed-loop arm of a six-month randomised trial of Control-IQ.
Outcomes are computed from the trial's own traces, per participant, over the calibration half of a
stratified split, with the held-out half reserved for the fitted controller. It contributes the traits the cohort is matched on and the outcome figures the Control-IQ arms
are set beside, and does not supply the algorithm.

The OpenAPS Data Commons supplies people running the algorithm under test. The April 2026 export
holds 240 user directories. For each, the exported files were merged, deduplicated to the minute
and sorted, and a single 28-day window taken from the middle of that user's record; a window was
kept when it held at least 70 per cent of the 8,064 readings a five-minute sensor would produce,
which 103 users met. Of those, 77 also hold pump records across that window, which a reconstructed
daily requirement needs. That set of 77 is the one a cohort is matched to.

The CLOSE-IT trial supplies the only randomised evidence of what withdrawing meal announcement
does to an oref-derived system in life. Seventy-five adults ran the Android Artificial Pancreas
System through a 12-week run-in with meal announcement and were then randomised to continue or
discontinue for a further 12 weeks. Participant-level data is not published, so the cohort
standing in for it is drawn from published summaries rather than matched to people, and no
distinguishability verdict is computed against it.

### Matching a cohort to a reference

Each real person is matched to the nearest unused virtual subject in standardised age and
log-insulin space, sampling without replacement, so the cohort follows the reference's joint
distribution rather than each margin separately. Insulin is matched on a log scale because its
spread is multiplicative. The distance achieved is recorded with each cohort, so that a cohort
matched to a reference the population cannot reach says so rather than looking matched.

| Cohort | n | Matched on | Median age | Median daily insulin, U | Median match distance |
|---|---|---|---|---|---|
| DCLP3 | 90 | age and daily insulin | 30.0 | 45.9 | 0.23 |
| Commons | 77 | daily insulin only | 17.2 | 38.1 | 0.003 |
| CLOSE-IT | 75 | age and daily insulin | 43.9 | 44.8 | 0.20 |

The Commons is matched on requirement alone because the export publishes no demographics, and the
consequence is visible in its age column: matching on insulin draws in adolescents, and 53 per
cent of that cohort is under 18 against 24 per cent of the DCLP3 cohort.

### How far an answer moves when only the participants change

A simulated median reported beside a real one is only meaningful once it is known how far either
moves when nothing changes but which people were drawn, so both are measured. On the real side,
each population is split at random in two and the difference between the half medians recorded,
repeated 5,000 times. On the simulated side, the same algorithm and bench are run on three
disjoint cohorts of 90 subjects sharing no member.

A difference against the real population is called distinguishable only when the real median falls
outside the simulated cohort's 95 per cent interval. That verdict is a function of cohort size and
is reported with the size that produced it.

### Comparisons and statistics

Every outcome is the share of one person's own readings meeting a condition, computed with the
same function on both sides and summarised across people only afterwards. Simulated runs are 28
days at five-minute resolution, which matches the window taken from each real record. Arms are
paired over the subjects completing both arms of the comparison in question, and intervals come
from 2,000 bootstrap resamples of the paired differences. Completion counts and the direction of
every early termination are reported alongside outcomes, because a run ends when glucose leaves
the range the model is defined over and a completion count averages a hypoglycaemia failure with a
hyperglycaemia one.

## Results

### How far the bare model is from a real cohort, and how far the layers move it

Distance is the absolute difference between the simulated and real medians, in units of the real
tenth-to-ninetieth percentile spread, averaged over the measures in each group, so a distance of
one is the width of the real population. Computed on the same subjects before and after.

| Pairing | n | Where glucose sits, bare | Layered | Change | Hypoglycaemia, bare | Layered | Change |
|---|---|---|---|---|---|---|---|
| DCLP3, Control-IQ stand-in | 79 | 0.89 | 0.40 | −55% | 0.29 | 0.62 | +118% |
| DCLP3, oref0 SMB | 77 | 0.83 | 0.51 | −39% | 0.35 | 1.48 | +321% |
| Commons, oref0 SMB | 64 | 0.52 | 0.13 | −76% | 0.19 | 0.29 | +53% |

The first group is time in range, time above 180 mg/dL, mean glucose and variability. The second
is time below 70 and below 54 mg/dL.

On the four measures describing where glucose sits, the layers move the population towards the
real one in every pairing, by between two fifths and three quarters. On hypoglycaemia they move it
further away in every pairing. That split runs through everything below.

### The bare model sits where no real population sits

Holding one controller fixed and varying only the bench beneath it, at the meal scenario where
some meals are announced. Medians over the subjects completing both arms, with the paired
difference over those same subjects and its 95 per cent interval.

| Measure | Bare | Layered | Paired difference | DCLP3 |
|---|---|---|---|---|
| Control-IQ stand-in, DCLP3 cohort, 79 paired | | | | |
| Time in range 70-180, % | 95.59 | 83.26 | −12.33 [−13.55, −10.04] | 71.29 |
| Time below 70, % | 0.84 | 2.29 | +1.45 [+1.00, +1.98] | 1.36 |
| Time below 54, % | 0.06 | 0.55 | +0.48 [+0.35, +0.79] | 0.20 |
| Time above 180, % | 3.37 | 13.70 | +10.33 [+8.64, +12.09] | 26.87 |
| Mean sensor glucose, mg/dL | 126.71 | 140.14 | +13.43 [+11.12, +15.63] | 155.45 |
| Variability, CV % | 20.93 | 30.02 | +9.09 [+7.19, +9.90] | 33.37 |
| Insulin, U/day | 44.31 | 48.77 | +4.46 [+1.95, +7.85] | |
| Rescue helpings per 30 d | 0.00 | 39.64 | +39.64 [+34.29, +47.14] | |
| oref0 SMB, DCLP3 cohort, 77 paired | | | | |
| Time in range 70-180, % | 93.49 | 85.90 | −7.59 [−9.56, −5.72] | 71.29 |
| Time below 70, % | 2.44 | 3.66 | +1.22 [+0.30, +1.95] | 1.36 |
| Time above 180, % | 3.09 | 10.07 | +6.98 [+5.27, +8.00] | 26.87 |
| Mean sensor glucose, mg/dL | 120.16 | 128.76 | +8.60 [+6.39, +12.40] | 155.45 |
| oref0 SMB, Commons cohort, 64 paired | | | | |
| Time in range 70-180, % | 93.05 | 85.08 | −7.97 [−10.53, −6.26] | 80.05 |
| Time below 70, % | 1.43 | 3.58 | +2.15 [+1.17, +2.83] | 2.72 |
| Time above 180, % | 4.35 | 10.44 | +6.09 [+4.71, +9.51] | 15.06 |
| Mean sensor glucose, mg/dL | 123.29 | 132.26 | +8.97 [+5.82, +12.37] | 134.90 |

On the bare patient the Control-IQ stand-in holds 95.6 per cent of readings in range at a mean of
126.7 mg/dL and spends 3.4 per cent above 180. No published closed-loop cohort achieves that, and
the trial it is set beside sits 24.3 percentage points and 28.7 mg/dL away.

Five movements appear in every pairing and none of their intervals spans zero. Mean glucose rises
by 6.6 to 13.4 mg/dL. Time above 180 mg/dL rises by 6.0 to 10.3 points. Variability rises by 6.3
to 9.1 points. Delivered insulin rises. And rescue carbohydrate appears at 40 to 60 helpings per
30 days where the bare patient has none, because the bare patient has no mechanism to treat a low.

Time in range falls in every pairing, by 5.4 to 12.3 points, which is the least informative of the
five: it is the measure the two benches differ on least in the CLOSE-IT pairing and the one most
often quoted.

Every one of those movements is towards the real population. The bare model is too flat, too low
and too predictable, it delivers too little insulin, and it never eats anything nobody told it
about. The layers supply each of those and the distance closes accordingly.

### Fitting the unpublished half of Control-IQ, and testing it on data it never saw

Tandem publish the cadence, the thresholds and the correction fraction. How far basal may be
raised, how large a single automatic correction may be and how much insulin on board the loop
tolerates are not published, and they are what drives the result. Across twelve configurations of
those three the distance to the calibration half ranges from 0.177 to 1.347, a factor of 7.6 on
numbers nobody outside Tandem knows.

The best configuration raises basal at most twofold rather than the threefold guessed, and
tolerates 4 U of insulin on board rather than 8. It scores 0.177 against the calibration
participants and 0.251 against the held-out half, so it transfers: a fit that had found the
calibration half rather than the algorithm would have degraded considerably more. Nineteen
subjects, 18 completing.

| Measure | Fitted arm | Gap to calibration half, spreads | Gap to held-out half, spreads |
|---|---|---|---|
| Time in range, % | 80.07 | +0.32 | +0.21 |
| Time below 70, % | 2.20 | +0.37 | +0.43 |
| Time below 54, % | 0.51 | +0.75 | +1.06 |
| Time above 180, % | 17.29 | −0.34 | −0.27 |
| Mean glucose, mg/dL | 143.31 | −0.31 | −0.25 |
| Variability, CV % | 30.79 | −0.23 | −0.14 |

The one gap that grows on transfer is time below 54 mg/dL, which is the measure this bench places
least reliably and the one the layers move the wrong way.

### How far an answer moves when only the participants change

Three disjoint cohorts of 90 subjects, sharing no member, under the same controller and bench.
Beside them, the same quantity measured on people by splitting each real population at random in
two. All in units of the real between-person spread.

| Measure | Control-IQ, bare | Control-IQ, layered | oref0, bare | oref0, layered | DCLP3 split-half |
|---|---|---|---|---|---|
| Time in range | 0.11 | 0.07 | 0.14 | 0.06 | 0.21 |
| Mean glucose | 0.01 | 0.03 | 0.03 | 0.08 | 0.21 |
| Time above 180 | 0.04 | 0.03 | 0.07 | 0.09 | 0.21 |
| Variability | 0.30 | 0.15 | 0.29 | 0.19 | 0.20 |
| Time below 70 | 0.37 | 0.40 | 0.81 | 0.41 | 0.32 |
| Time below 54 | 0.30 | 0.70 | 1.08 | 0.41 | 0.33 |

On time in range, mean glucose and time above 180 mg/dL the bench is more reproducible across
groups of subjects than the trial is across groups of participants, by a factor of two to seven.
On variability it is comparable. On hypoglycaemia it is worse, by up to a factor of three, and
worst in the bare oref0 SMB arm.

### What survives that

A difference is called distinguishable where the real median falls outside the simulated cohort's
95 per cent interval, on cohorts of 64 to 86.

| Pairing and arm | Same as real | Differs from real |
|---|---|---|
| Commons, oref0 SMB, bare | below 70, below 54 | in range, above 180, mean, CV |
| Commons, oref0 SMB, layered | CV | the other five |
| Commons, oref0 SMB, layered unannounced | mean, CV, below 70 | in range, above 180, below 54 |
| DCLP3, Control-IQ stand-in, bare | below 70 | the other five |
| DCLP3, Control-IQ stand-in, layered | none | all six |

These verdicts depend on the cohort size that produced them. A simulated cohort of fifteen has a
95 per cent interval wide enough to contain most real medians, and the same arm would be called
indistinguishable on four of six measures at that size; at 64 to 86 the interval narrows and the
test fails more often. Reporting a bench as indistinguishable from real people is therefore a
statement about how few subjects were run as much as about the simulator, which is why the verdict
is given here with its cohort size attached rather than on its own.

The direction the layers move the verdict is informative even where the verdict is negative. On
the Commons pairing the bare arm agrees with real people on hypoglycaemia and disagrees on all
four measures of where glucose sits; the layered arm reverses part of that, agreeing on variability
and moving hypoglycaemia out of agreement. The layers buy the centre of the distribution at the
cost of its lower tail.

### Meal behaviour

The model's response to an uncovered meal is larger than the real one and arrives at the same
time. A meal on basal alone raises glucose by 21.53 mg/dL per 10 g across 306 subjects, linear in
size at 21.28, 21.47 and 21.83 for 30, 50 and 70 g, peaking at 215 to 225 minutes.

The real figure depends on what counts as uncovered, and the dependence is reported rather than
resolved by choosing one definition.

| Definition | Meals | Median g | Rise per 10 g | Peak, min |
|---|---|---|---|---|
| No insulin within 30 min | 7,996 | 38 | 19.71 | 179 |
| No insulin within 30 min, baseline 80 to 180 | 5,343 | 35 | 18.53 | 189 |
| Bolus-free 30 min before to 120 after | 2,501 | 33 | 15.69 | 248 |
| Bolus-free a full action duration before and 4 h after | 388 | 43 | 17.38 | 177 |
| The same, loop within 0.5 U of schedule | 317 | 43 | 15.89 | 189 |

Across 101,882 candidate meals from 128 users the rise runs 15.7 to 19.7 mg/dL per logged 10 g and
the peak 177 to 248 minutes. Logged grams under-state intake, so the real rise per gram eaten is
lower still, which widens the gap rather than narrowing it. The simulated peak sits inside the
real range on every definition.

### Withdrawing meal announcement

Each controller met three conditions differing only in what the person said about their meals,
drawn from the same random stream. The contrast below is every meal announced against none
announced, within the layered arm, paired per subject.

| Arm | Announced | Unannounced | Difference |
|---|---|---|---|
| Control-IQ stand-in, DCLP3 cohort, n=71 | 85.81 | 80.98 | −4.84 [−7.22, −3.58] |
| oref0 SMB, DCLP3 cohort, n=74 | 86.43 | 85.59 | −0.84 [−2.61, +0.08] |
| oref0 SMB, Commons cohort, n=58 | 85.71 | 85.63 | −0.08 [−2.22, +1.06] |
| oref0 SMB, CLOSE-IT cohort, n=58 | 86.43 | 85.76 | −0.66 [−1.97, +0.47] |
| CLOSE-IT, 75 adults | 69 ± 13 | 66 ± 8 | −2.2, 95% CI −6.2 to 1.7 |

The two controllers separate in the direction their designs predict. The Control-IQ stand-in has
no meal detection and loses 4.84 points of time in range with an interval excluding zero. oref0
SMB, which microboluses on deviation from prediction, loses between 0.08 and 0.84 points in three
different cohorts with every interval spanning zero. CLOSE-IT randomised that question in 75
adults on an oref-derived system and reported 2.2 points with an interval that also spans zero.

Where the announcement goes instead is visible in the other measures. For the stand-in, time above
180 mg/dL rises 4.87 points and mean glucose 8.76 mg/dL when announcement is withdrawn, while time
below 70 does not move. The cost of an unannounced meal on this bench is hyperglycaemia rather
than hypoglycaemia.

The simulated arms sit about 17 points of time in range above the CLOSE-IT trial in absolute
terms, so the bench supports the relative question and not the absolute one.

### Completion

Across the 1,260 runs of the baseline set, 103 did not complete 28 days. Ninety-three of those
ended low and 10 ended high. Completion is worse on the layered bench in every cohort, at 76 to 79
of 86 against 85 or 86 of 86 bare for the DCLP3 cohort, so every median above is conditioned on a
survival criterion the two benches do not share.

## Discussion

A model whose limitations are well documented can be brought closer to real cohorts from outside
its equations, on most of what is usually measured, and the improvement divides along a line worth
setting out.

The measures describing where glucose sits close substantially. Time in range, time above 180
mg/dL, mean glucose and variability all move towards the real population in all three pairings, by
between two fifths and three quarters of the distance they started at, without altering a
published parameter. What supplies the movement is the meals nobody announced, the carbohydrate
people eat when they go low, a sensor carrying error and an infusion set that fails. The bare
model is flatter, lower and more predictable than a real cohort because it contains none of those
rather than because its physiology is wrong.

Hypoglycaemia does not close, and it moves the wrong way in all three pairings rather than in
some. The mechanisms that correct the centre of the distribution overshoot its lower tail: a
person who eats when they go low and misses meals produces more excursions than either reference
population records. This is also where the bench is least reproducible, at 0.40 to 0.70 spreads
between disjoint groups against a trial split-half of 0.32, so it is the worst-measured statistic
here as much as the worst-fitting one. Separating those would need larger cohorts than a
600-subject population supports.

A hepatic defence term is not warranted on this evidence. Reproduced properly, the clamp puts the
model inside the human range with no such term, so the case for adding one rests on a comparison
between a spontaneous low and a clamp measurement that does not hold. What the clamp does show is
a spread no gain repairs: a third of subjects produce nothing at the 55 mg/dL plateau, where no
real person produces nothing, and lifting them drives the subjects already above 2 mg/kg/min
further out.

The distinguishability result should be read with care, because it is the part of this work most
sensitive to a choice that is not about the simulator. At cohorts of fifteen the layered arm is
indistinguishable from real people on four of six measures; at cohorts of 64 to 86 it is
distinguishable on five or six of six, with the same runs behind both. A test that compares a real
median against a simulated interval gets stricter as the
simulated cohort grows, so any claim of the form "this simulator is indistinguishable from real
people" is quoting its own sample size, and a bench that wanted to pass such a test could do so by
running fewer subjects.

What does not depend on that choice is the direction the layers move things, which is measured on
the same subjects before and after and reported as a paired difference with an interval. That is
the result this paper rests on.

The announcement experiment shows the bench separating two controllers in the direction their
designs predict, and agreeing with the only randomised trial of that question on the same
algorithm family. The stand-in without meal detection loses 4.84 points of time in range; oref0
SMB loses nothing distinguishable from zero in three cohorts, and CLOSE-IT reported the same
non-result in people. The absolute level is about 17 points optimistic against CLOSE-IT, so the
bench supports the relative comparison and not the absolute one.

Two results bear on how in-silico work of this kind should be reported. A difference quoted in
units of the between-person spread does not establish that a difference exists, and the
interpretability floor has to be measured on both sides and quoted with the result. And the
direction of an incomplete run matters as much as the count: 93 of the 103 incomplete runs here
ended low, so a completion count alone averages two opposite failures.

## Limitations

Every cohort figure is conditioned on survival, and the layered and bare benches do not lose the
same subjects.

The population carries less between-subject spread than a real one, and the reason is in the
model's own provenance: when the simulator was released, the joint parameter distributions that
were reliably available described adults without diabetes, and the type 1 subjects were made from
those with adjustments to the mean. The adjustments moved the centre; the spread and the
correlations between parameters were inherited from people whose glucose regulates itself. Every
claim here about how variable simulated people are carries that caveat.

The Commons users are self-selected do-it-yourself loopers whose records span 2015 to 2022, are
not demographically characterised, and are not fully independent of this work, since other
quantities here are calibrated against the same export. Matching on daily insulin alone makes that
cohort 53 per cent under 18.

The CLOSE-IT comparison is against published summary statistics, with a cohort drawn from them
rather than matched to participants, and no distinguishability verdict is computed against it.

Titration does not bring these subjects to real settings and is not intended to. It moves the
population median correction factor by 0.3 mg/dL per unit, so the subjects are dosed from
settings roughly twice as strong as the trial participants ran. Twenty-four subjects clear the
floors at no combination and are excluded, which selects towards subjects that can be made safe
and removes a third of the children.

The distinguishability test compares a real median against a simulated interval and is not a
formal test of equality. It answers whether a difference is establishable at the cohort size used,
which is a weaker question than whether the two populations agree.

Two controllers are reported and one of them is a stand-in built from a published description
rather than the product itself, so a difference attributed to the bench under that arm could
belong to the reconstruction.

## Provenance

Every figure above is reproducible from the repository against population `704cfac086df54ba` and
settings `0df43fd250fadd47`. The settings digest was rewritten on 26 August 2026 to hash the
adopted settings rather than the file holding them; measurements stamped `046e0da5bc380688` were
taken against a byte-identical store and are the same experiment.

| Section | Produced by | Output |
|---|---|---|
| Layer and announcement effects, completion | `examples/bench_matrix.py --benches baseline`, `examples/baseline_effects.py` | `baseline_trend.json`, `baseline_effects.json` |
| Distance before and after | `examples/distance_to_real.py` | `distance_to_real.json` |
| Distinguishability | `examples/validation_table.py` | `validation_table.json` |
| Fitted Control-IQ | `examples/fit_control_iq.py` | `control_iq_fit.json` |
| Group effect | `examples/cohort_replicates.py` | `cohort_replicates*.json` |
| Split-half baseline | `examples/cohort_variation.py` | `cohort_variation.json` |
| Meal behaviour | `examples/meal_response.py`, `examples/real_meals.py` | `meal_response.json`, `real_meals_dia.json` |
| Clamp | `examples/hypoglycaemic_clamp.py` | `clamp.json` |
| Cohorts | `examples/build_cohorts.py` | `cohorts.json` |
| Commons reference | `examples/commons_cohort.py`, `examples/commons_requirement.py` | `commons_cohort.json`, `commons_requirement.json` |
| Titration | `examples/titrate_cohort.py`, `examples/titration_reference.py` | `titrated_settings.json`, `titration_reference.json` |

Each script writes its output with a stamp of the population fingerprint, the titrated settings
digest and the code revision, and any analysis combining results refuses inputs whose stamps
disagree.
