# Can the UVA/Padova S2008 Simulator Be Made to Resemble a Real Closed-Loop Cohort? A Person-in-the-Loop Layer, Measured Against Two Real Populations

Candidate for publication. Every figure below is traceable to a file in `docs/measurements/`
and was measured against the population recorded under Provenance.

## Abstract

**Background.** In-silico testing of automated insulin delivery rests on virtual patients that
reproduce metabolism without reproducing the person around it. The S2008 release of the
UVA/Padova model, the version available without licence, has no counterregulatory response,
fixed parameters, a noiseless sensor and a patient who announces every meal accurately. Its
departures from real records are documented. Whether they can be closed from outside the
differential equations, by adding the person the model omits, has not been established. This
paper measures it.

**Methods.** Four layers were added: insulin sensitivity that moves, a person who eats and
treats their own hypoglycaemia, sensor error inside the control loop, and infusion sets that
fail and are noticed late. A defence of hepatic glucose production was calibrated against a
stepped hyperinsulinaemic clamp reproduced in silico. Settings were titrated per subject to
consensus hypoglycaemia limits under a fixed regimen. Cohorts were matched to each reference on
what that reference publishes, which for the DCLP3 trial is age and recorded daily insulin and
for the OpenAPS Data Commons is a daily requirement reconstructed from delivery. Three
algorithms were run, each held fixed while the bench varied. A stand-in for Control-IQ was
additionally fitted on one half of the trial and reported on the other. How far each answer
moves when only the participants change was measured on both sides, by splitting each real
population in two and by running the same algorithm on disjoint groups of subjects.

**Results.** Distance from the real population was computed on the same subjects before and
after, in units of the real between-person spread. On the four measures describing where glucose
sits, the layers reduced it by 60, 22 and 47 per cent across the three pairings, from 0.75, 0.53
and 0.32 to 0.30, 0.41 and 0.17. On hypoglycaemia they increased it against the trial cohort,
from 0.95 and 1.06 to 1.49 and 1.36, and left it unchanged against the do-it-yourself users at
0.22 and 0.21. On the bare patient three algorithms held 85.8 to 93.1 per cent of readings in
range at 121.9 to 126.5 mg/dL, against real cohorts at 71.3 and 79.6 per cent; adding the layers
raised mean glucose by 12.3 to 16.2 mg/dL, roughly doubled time above 180, raised variability and
delivered insulin, and introduced 50 to 69 rescue helpings per thirty days, with no interval
spanning zero. Where the simulated and real sides ran the same algorithm the layered cohort was
statistically indistinguishable from real people on time in range, time above 180, mean glucose
and variability, and its answer moved no more when the participants changed than the trial's did.
The model's uncovered meal response is larger than the real one, 22.2 mg/dL per 10 g against 15.7
to 19.7 per logged 10 g, and peaks inside the real range. Withdrawing meal announcement cost a
controller without meal detection 6.34 percentage points of time in range and cost oref0 SMB
between 0.9 and 1.8 points across three cohorts with every interval spanning zero, against 2.2
points with an interval spanning zero in the CLOSE-IT trial.

**Conclusions.** S2008 can be moved a long way towards a real closed-loop cohort without
touching its differential equations, and the movement is measurable rather than asserted: on the
pairing built to answer the question properly it becomes statistically indistinguishable from
real people on four of six measures. What does not close is hypoglycaemia, which moves further
from a commercial system's trial while staying where it was against a do-it-yourself population,
and which this bench also measures least reliably. A difference expressed in units of
between-person spread does not establish that a difference exists; the interpretability floor has
to be measured and quoted with the result.

**Keywords.** simulation, automated insulin delivery, closed-loop, validation, type 1 diabetes,
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

The question this paper answers is narrower than whether the model is good, and more useful. The
ways S2008 departs from real records are already documented, here and elsewhere. What has not
been established is whether they can be closed from outside the differential equations, by
adding the person the model omits rather than by altering the physiology it inherits. So: if the
bare model sits where no real cohort sits, can it be moved, how far, and on which measures?

Answering that requires three things a single comparison does not supply. A distance from the
real population that can be computed before and after, in units that make measures with
different scales comparable. A reference population running the same algorithm, so that a
difference is attributable to the bench rather than to the controller. And a floor below which a
difference cannot be established at all, because a cohort of fifteen or twenty places a median
far less precisely than the spread between people suggests.

The question is not whether the simulator predicts an individual's glucose under a dosing
change, which it does not attempt.

Three design decisions follow from measurements reported here rather than from convention, and
they are stated in the introduction because each of them changes what a reader should take from
a result of this kind.

A comparison of this sort is uninterpretable without knowing how far its answer moves when only
the participants change. That quantity is measured on both sides: by splitting each real
population in two, and by running the same algorithm on disjoint groups of simulated subjects.

A cohort has to be matched to the reference on something the reference publishes. The DCLP3
release retains age and each participant's recorded daily insulin. The OpenAPS Data Commons
publishes no demographics at all, so a daily requirement is reconstructed from delivery, which
is the only physiological trait available.

An algorithm that is a stand-in for a commercial product is fitted, if at all, on one half of
the trial and reported on the other. Fitting it to the whole trial would make the trial useless
for validating the person.

## Methods

### The model and the population

The metabolic model is the UVA/Padova S2008 virtual patient reached through simglucose. One
hundred subjects were generated from the published parameter tables and screened for
steady-state consistency, under a closure test requiring the steady-state relations to
reproduce all thirty published subjects. The population is generated locally and is not
redistributed.

The generator is reproducible from its seed, each class drawing from a stream keyed by a stable
digest rather than by a salted hash, so the same seed returns the same subjects in any process.
Subject names are positional, so a regenerated population reuses every name for a different
body: the titration store therefore records a digest of the population its settings were fitted
to and refuses to be applied to any other. Growing the population is append-only, and the
subjects reported here were confirmed unchanged by rerunning the signature measurement on the
larger population and obtaining identical values.

### The layers

Physiology varies insulin sensitivity with a diurnal shape and an independent day-to-day term
at a published coefficient of variation, with a third component correlated across several days
on the reasoning that independent daily draws average out across a week where real runs of days
do not.

Behaviour draws a meal schedule scaled to body weight, announces a main meal with probability
0.80 and a snack with probability 0.35, and applies a lognormal error to the announced quantity,
so the algorithm receives an estimate rather than the truth. Hypoglycaemia is treated with a
helping drawn from a distribution measured across 4,544 real carbohydrate entries recorded below
75 mg/dL, at a median of 15 g for a reading of 65 to 75 mg/dL.

The sensor carries error and compression artefacts, quantised to the reporting increment, applied
inside the control loop rather than to the output so that the algorithm and the simulated person
both see them. Comparisons against real records are made on the sensor reading, since that is
what real records contain.

The infusion site fails at a subject-specific rate calibrated against the duration distribution
of prolonged hyperglycaemic excursions in the trial, passing a residual fraction of delivered
insulin. Detection requires the reading to remain above 230 mg/dL for 90 waking minutes.

### Counterregulation

S2008 contains no counterregulatory response. Establishing what it does during hypoglycaemia
requires reproducing the protocol the human reference figures come from, because glucose
production in this model is a linear function of glucose and of insulin in a remote compartment,
and a figure for it is uninterpretable without the insulin it was measured at. The same subjects
report 1.16 mg/kg/min during spontaneous lows under a closed loop, at a remote insulin of 219,
and far less at a clamped plateau, where the clamp holds remote insulin at 441.

A stepped hyperinsulinaemic clamp was therefore reproduced in silico, with insulin infused at
1.0 mU/kg/min and glucose held at successive plateaus of 90, 80, 65, 55 and 45 mg/dL by a
variable glucose infusion. A term opposing insulin's suppression of production, rising as
glucose falls on a logistic centred at 58 mg/dL, was calibrated on that clamp against Rickels et
al., who measured 0.42 to 0.84 mg/kg/min with a mean of 0.59 in twelve people with long-standing
type 1 diabetes and no discernible glucagon response.

The gain is 0.20, which places the median at 0.65 mg/kg/min at the 55 mg/dL plateau and 0.57 at
45, both inside the human interval. Two properties of this calibration have to be quoted with
it. The median is a weak statistic on this population, because the distribution is zero-inflated:
fourteen of thirty-four adults produce nothing at all at the 55 mg/dL plateau with the defence
off, so the median moves by a factor of three depending on which subset of adults is used. And no
gain removes the zeros; seven of thirty-four still produce nothing where no real person produces
nothing, because lifting them requires a gain that drives the subjects already producing over
2 mg/kg/min further out. That width belongs to the published `kp1`, `kp2` and `kp3` values.

### The algorithms

Three control algorithms are used, and each is reported separately.

A stand-in for Control-IQ reproduces Tandem's published description: an automatic correction at
most hourly when glucose is predicted above 180 mg/dL half an hour ahead, at 60 per cent of a
correction towards 110, with basal suspended below 70, reduced below 112.5, raised from 160 and
at its ceiling above 180. What Tandem do not publish is how far basal may be raised, how large a
single automatic correction may be, and how much insulin on board the loop tolerates. Both a
variant using guessed values for those and a variant fitted to the trial are reported.

oref0 SMB, the OpenAPS reference algorithm, is driven unmodified from its own source across a
node process boundary with one decision marshalled per cycle.

A reactive correction loop supplied with this package is the fixed regimen under which settings
are titrated. It is not a shipped product, is not a model of one, and is not reported as an arm.

### Settings

A virtual subject's correction factor can be computed from its own model, which produces a value
no real person has access to. The corresponding real quantity, taken from the recorded pump
settings of the 112 DCLP3 closed-loop participants and summarised per participant, has a median
of 40.0 mg/dL per unit with an inter-quartile range of 30.0 to 50.0.

Each subject's basal was reduced in steps until its own record cleared the consensus
hypoglycaemia limits of below 54 mg/dL under 1 per cent and below 70 under 4, with the correction
factor weakened only where no basal reduction inside a 20 per cent bound sufficed. Titration ran
under the reactive correction loop for every subject, since tuning a bench with the system under
test in the loop would let a system that provokes hypoglycaemia be answered by weakening its
subjects' settings.

Titration closes about half of the settings gap rather than all of it: across the titrated
cohort the correction factor ends at a median of 23.6 mg/dL per unit against the real 40.0, so
these subjects are still dosed more aggressively than real people are.

### The reference populations, and what each one licenses

The DCLP3 trial supplies the closed-loop arm of a six-month randomised trial of Control-IQ.
Outcomes are computed from the trial's own traces, per participant, over the calibration half of
a stratified split, with the held-out half reserved for the fitted controller. It contributes the
traits the cohort is matched on and the outcome figures the Control-IQ arms are set beside. It
does not supply the algorithm.

The OpenAPS Data Commons supplies people running the algorithm under test. The April 2026 export
holds 240 user directories, of which 131 carry a readable glucose series. For each, the exported
files were merged, deduplicated to the minute and sorted, and a single 28-day window taken from
the middle of that user's record; a window was kept when it held at least 70 per cent of the
8,064 readings a five-minute sensor would produce, which 103 users met. Of those, 71 also hold
pump records across that window, which a reconstructed daily requirement needs. That set of 71
is the one a cohort is matched to. Restricting the outcome reference to those 71 does not move it.

Filenames in the export carry a user-id prefix for some users and not others, so files are
matched on a pattern admitting both. The narrower pattern returns about a tenth of the sample and
is the origin of several figures in earlier work here that later measurement contradicted.

The CLOSE-IT trial supplies the only randomised evidence of what withdrawing meal announcement
does to an oref-derived system in life. Seventy-five adults ran the Android Artificial Pancreas
System through a 12-week run-in with meal announcement and were then randomised to continue or
discontinue for a further 12 weeks. Participant-level data is not published, so the cohort
standing in for it is drawn from published summaries rather than matched to people, and it is
reported as a stand-in.

### Matching a cohort to a reference

Each real person is matched to the nearest unused virtual subject in standardised age and
log-insulin space, sampling without replacement, so the cohort follows the reference's joint
distribution rather than each margin separately. Insulin is matched on a log scale because its
spread is multiplicative. The distance achieved is recorded with each cohort, so that a cohort
matched to a reference the population cannot reach says so rather than looking matched.

Two limits of the population show up here and are reported rather than worked around. Its adults
all need more insulin than real do-it-yourself-looping adults: the adult pool runs 41.8 to 83.9
U/day with a median of 56.0, against a Commons median of 38.4 with a tenth percentile of 24.2.
Matching the Commons on requirement therefore draws in adolescents. And the hundred subjects
supply about three disjoint cohorts of fifteen matched to DCLP3 before the pool runs out of
adults, which bounds how many independent groups this bench can produce.

### How far an answer moves when only the participants change

A simulated median is reported beside a real one and the difference called a gap. That is only
meaningful once it is known how far either moves when nothing changes but which people were
drawn, so both are measured.

On the real side, each population is split at random in two and the difference between the half
medians recorded, repeated 5,000 times. On the simulated side, two things are measured: the
subjects within a cohort are resampled with replacement to give an interval on that cohort's
median, and the same algorithm is run on disjoint cohorts matched to the same reference.

A gap is reported as distinguishable only when the real median falls outside the simulated
cohort's 95 per cent interval. Quoting a gap in units of the between-person spread, as earlier
work here did, does not answer the question, because a cohort of twenty can place a median far
less precisely than the spread suggests.

### Comparisons and statistics

Every outcome is the share of one person's own readings meeting a condition, computed with the
same function on both sides and summarised across people only afterwards. Simulated runs are 28
days at five-minute resolution, which matches the window taken from each real record. Arms are
paired over the subjects completing both arms of the comparison in question. Completion counts
and the direction of every early termination are reported alongside outcomes, because a run ends
when glucose leaves the range the model is defined over and a completion count averages a
hypoglycaemia failure with a hyperglycaemia one.

## Results

### How far the bare model is from a real cohort, and how far the layers move it

Distance is the simulated median minus the real median, in units of the real tenth-to-ninetieth
percentile spread, so a distance of one is the width of the real population. Computed on the
same subjects before and after, for each of three pairings of a cohort with the algorithm its
reference population runs.

| Pairing | Measures | Bare S2008 | Layered | Change |
|---|---|---|---|---|
| DCLP3, Control-IQ stand-in | in range, above 180, mean, CV | 0.75 | 0.30 | −60% |
| DCLP3, oref0 SMB | in range, above 180, mean, CV | 0.53 | 0.41 | −22% |
| Commons, oref0 SMB | in range, above 180, mean, CV | 0.32 | 0.17 | −47% |
| DCLP3, Control-IQ stand-in | below 70, below 54 | 0.95 | 1.49 | +57% |
| DCLP3, oref0 SMB | below 70, below 54 | 1.06 | 1.36 | +28% |
| Commons, oref0 SMB | below 70, below 54 | 0.22 | 0.21 | unchanged |

On the four measures describing where glucose sits, the layers move the population towards the
real one in every pairing, by between a fifth and three fifths. On hypoglycaemia they move it
further away from the trial cohort and leave it where it was against the do-it-yourself users.
That split runs through everything below.

### The bare model sits where no real population sits

Holding one algorithm fixed and varying only the bench beneath it, on the cohort matched to the
DCLP3 closed-loop arm under a stand-in for Control-IQ built from Tandem's published description.
Medians across the fifteen subjects completing both arms, with the paired difference over the
same subjects.

| Measure | S2008 bare | Layered | Paired difference | DCLP3 |
|---|---|---|---|---|
| Completed | 23/24 | 15/24 | | 67 participants |
| Time in range 70–180, % | 93.12 | 79.79 | −12.33 ± 3.14 | 71.29 |
| Time below 70, % | 2.96 | 3.21 | +0.64 ± 1.18 | 1.36 |
| Time below 54, % | 0.61 | 0.98 | +0.66 ± 0.48 | 0.20 |
| Time above 180, % | 3.44 | 14.06 | +11.69 ± 2.35 | 26.87 |
| Mean sensor glucose, mg/dL | 126.53 | 141.53 | +15.21 ± 1.69 | 155.45 |
| Variability, CV % | 23.97 | 34.59 | +9.34 ± 2.86 | 33.37 |
| Insulin, U/day | 41.09 | 51.94 | +7.70 ± 1.97 | |
| Rescue helpings per 30 d | 0.00 | 50.36 | +60.36 ± 18.96 | |

On the bare patient this controller holds 93.1 per cent of readings in range at a mean of 126.5
mg/dL and spends 3.4 per cent above 180. No published closed-loop cohort achieves that, and the
trial it is set beside sits 21.8 percentage points and 28.9 mg/dL away. The layered bench moves
the same algorithm to 79.8 per cent and 141.5 mg/dL.

The same experiment under oref0 SMB on the same cohort moves the same way, from 85.8 per cent
and 123.0 mg/dL to 80.4 and 139.9, and against the OpenAPS Data Commons users under the
algorithm they actually run, from 86.8 per cent and 121.9 mg/dL to 83.7 and 130.3.

Five movements appear in every pairing and none of their intervals spans zero. Mean glucose
rises by 12.3 to 16.2 mg/dL. Time above 180 mg/dL rises by 6.7 to 11.7 points. Variability
rises. Delivered insulin rises by 26 to 30 per cent. And rescue carbohydrate appears at 50 to 69
helpings per thirty days where the bare patient has none, because the bare patient has no
mechanism to treat a low.

Time in range falls in every pairing, by 5.4 to 12.3 points, which is the least informative of
the five: it is the measure the two benches differ on least in the Commons pairing and the one
most often quoted.

Every one of those movements is towards the real population. The bare model is too flat, too
low and too predictable, it delivers too little insulin, and it never eats anything nobody told
it about. The layers supply each of those and the distance closes accordingly.

### Fitting the unpublished half of Control-IQ, and testing it on data it never saw

Tandem publish the cadence, the thresholds and the correction fraction. How far basal may be
raised, how large a single automatic correction may be and how much insulin on board the loop
tolerates are not published, and they are what drives the result. Across twelve configurations
of those three the distance to the calibration half ranges from 0.035 to 1.3, a factor of
thirty-seven on numbers nobody outside Tandem knows.

The best configuration raises basal at most twofold rather than the threefold guessed, and
tolerates 4 U of insulin on board rather than 6. It scores 0.035 against the 67 calibration
participants and 0.069 against the 45 held out, so it transfers: a fit that had found the
calibration half rather than the algorithm would have degraded considerably more.

| Measure | Fitted | Held-out half | Gap in spreads |
|---|---|---|---|
| Time in range, % | 76.50 | 73.76 | +0.09 |
| Time below 70, % | 1.78 | 1.23 | +0.24 |
| Time below 54, % | 0.32 | 0.14 | +0.52 |
| Time above 180, % | 21.74 | 25.71 | −0.13 |
| Mean glucose, mg/dL | 151.02 | 154.67 | −0.08 |
| Variability, CV % | 34.43 | 32.14 | +0.23 |

### How far an answer moves when only the participants change

Three disjoint cohorts of fifteen, matched to the same trial, sharing no subject, under the same
algorithm and bench. Beside them, the same quantity measured on people by splitting each real
population at random in two. Both in units of the real between-person spread.

| Measure | Simulated group effect | Real split-half |
|---|---|---|
| Time in range | 0.11 | 0.17 |
| Mean glucose | 0.16 | 0.18 |
| Time above 180 | 0.22 | 0.16 |
| Variability | 0.24 | 0.18 |
| Time below 70 | 0.62 | 0.22 |
| Time below 54 | 1.63 | 0.25 |

On time in range and mean glucose the bench is as reproducible across groups of subjects as the
trial is across groups of participants. On hypoglycaemia it is three to six times less so.

### What survives that

A difference is reported as real only where the real median falls outside the simulated cohort's
95 per cent interval.

| Pairing | Same as real | Differs from real |
|---|---|---|
| Commons, oref0 SMB | time in range, time above 180, mean, CV | below 70, below 54 |
| DCLP3, fitted Control-IQ | time in range, CV | below 70, below 54, time above 180, mean |
| DCLP3, oref0 SMB | none | all six |

The pairing where the simulated and real sides genuinely run the same algorithm agrees with real
people on four of six measures. Where the algorithm is a stand-in for the trial's, two of six.
Where it is neither, none, which is the arrangement that should agree least and does.

So the improvement is not merely a smaller number. On the pairing built to answer the question
properly, the layered population is statistically indistinguishable from real people on
everything except how low it goes.

Hypoglycaemia differs in every pairing. It is also the measure with the largest group effect, at
1.63 spreads under DCLP3 against differences of comparable size, so in that pairing the finding
rests on a statistic this bench cannot place reliably. In the Commons pairing the group effect
is 0.35 and the same difference is on firmer ground.

### Meal behaviour

The model's response to an uncovered meal is larger than the real one and arrives at the same
time. A meal on basal alone raises glucose by 22.20 mg/dL per 10 g across 51 subjects, linear in
size at 22.13, 22.20 and 22.30 for 30, 50 and 70 g, peaking at 225 minutes.

The real figure depends on what counts as uncovered, and the dependence is reported rather than
resolved by choosing one: across five definitions, from no insulin within half an hour to
bolus-free for a full insulin action duration before and four hours after with the loop within
0.5 U of the scheduled basal, it runs from 15.7 to 19.7 mg/dL per logged 10 g on samples of
7,996 down to 320 meals. Peaks run 177 to 248 minutes. Logged grams under-state intake, so the
real rise per gram eaten is lower still.

### Withdrawing meal announcement

Each algorithm met three conditions differing only in what the person said about their meals,
drawn from the same random stream.

| Arm | Announced | Unannounced | Difference |
|---|---|---|---|
| Control-IQ stand-in, DCLP3 cohort | 80.48 | 73.81 | −6.34 ± 2.37 |
| oref0 SMB, DCLP3 cohort | 81.82 | 81.45 | −1.78 ± 1.83 |
| oref0 SMB, Commons cohort | 83.66 | 81.76 | −1.47 ± 2.67 |
| oref0 SMB, CLOSE-IT cohort | 78.64 | 78.49 | −0.88 ± 1.36 |
| CLOSE-IT, 75 adults | 69 ± 13 | 66 ± 8 | −2.2, 95% CI −6.2 to 1.7 |

The two algorithms separate in the direction their designs predict. The Control-IQ stand-in has
no meal detection and loses 6.34 points of time in range when announcement is withdrawn. oref0
SMB, which microboluses on deviation from prediction, loses between 0.9 and 1.8 points with
every interval spanning zero, in three different cohorts. CLOSE-IT randomised that question in
75 adults on an oref-derived system and reported 2.2 points with an interval that also spans
zero.

The simulated arms sit about ten points of time in range above the trial in absolute terms.

## Discussion

A model whose limitations are well documented can be brought closer to real cohorts from outside
its equations, on most of what is usually measured, and the improvement divides along a line
that is worth setting out.

The measures describing where glucose sits close substantially. Time in range, time above 180
mg/dL, mean glucose and variability all move towards the real population in the three pairings,
by between a fifth and three fifths of the distance they started at, without altering a
published parameter. What supplies the movement is the meals nobody announced, the carbohydrate
people eat when they go low, a sensor carrying error and an infusion set that fails. The bare
model is flatter, lower and more predictable than a real cohort because it contains none of
those rather than because its physiology is wrong.

Hypoglycaemia does not close. Against the DCLP3 cohort the layers take time below 70 and below
54 mg/dL further from real, by 57 and 28 per cent, because the mechanisms that correct the
centre of the distribution overshoot its lower tail: a person who eats when they go low and
misses meals produces more excursions than a trial population running a conservative commercial
system. Against the do-it-yourself users, who run lower and more hypoglycaemic themselves, the
same arms sit where they started. How far the simulated hypoglycaemia is from real therefore
depends on which real population is taken as the standard, and that choice belongs before the
comparison rather than after it.

Where the simulated and real sides run the same algorithm, the simulated cohort is
indistinguishable from real people on time in range, time above 180 mg/dL, mean glucose and
variability, and its answer moves no more when the participants change than the trial's does
across groups of participants. A bench has to establish that before a difference it reports
about an algorithm can be attributed to the algorithm.

Agreement across the three pairings follows the closeness of the comparison. It is best where
the algorithm matches the reference population, worse where the algorithm is a stand-in for the
one the trial ran, and absent where it is neither.

Hypoglycaemia is the exception, and the available evidence supports a narrower statement than
the outcome tables alone suggest. It differs from real in every pairing, and it survived a
controller whose free
parameters were fitted specifically to minimise the distance, so it is not an artefact of the
controller being a stand-in. It is also the measure this bench places least reliably: redrawing
which fifteen subjects are used moves the median time below 54 mg/dL by 1.63 of the real
between-person spread, which is larger than most of the differences being reported. So
hypoglycaemia is the worst-measured statistic here as much as the
worst-fitting one, and separating those would need either much larger cohorts or a population
that supplies more independent groups than this one does.

The model's response to an uncovered meal is larger than the real one and its timing sits inside
the real range, so an algorithm that detects meals is not presented with a gentler challenge on
this bench than it will meet in use.

The announcement experiment shows that the bench separates two algorithms in the
direction their designs predict, and agrees with the only randomised trial of that question on
the same algorithm family. oref0 SMB is insensitive to meal announcement in three different
simulated cohorts and in CLOSE-IT; the Control-IQ stand-in, which has no meal detection, is not.
The absolute level is about ten points of time in range optimistic against CLOSE-IT, so the
bench supports the relative question and not the absolute one.

Two results bear on how in-silico work of this kind should be reported. A difference quoted in
units of the between-person spread does not establish that a difference exists, because a cohort
of fifteen or twenty places a median far less precisely than that spread implies; the
interpretability floor has to be measured, on both sides, and quoted with the result. And the
direction of an incomplete run matters as much as the count: on the bare model every incomplete
run ends low, and on the layered bench most end high, so a completion count alone averages two
opposite failures and invites the wrong reading of both.

## Limitations

Every cohort figure is conditioned on survival, and what survival selects on differs by bench: on
the bare model every incomplete run ends low, and on the layered bench most end high.

The population carries about 45 per cent of the real between-subject spread in mean glucose, its
sensor behaviour is far more uniform than real people's because every virtual subject wears the
same sensor, and its glucose production at a clamped hypoglycaemic plateau varies far too much in
the other direction.

The Commons users are self-selected do-it-yourself loopers whose records span 2015 to 2022, are
not demographically characterised, and are not fully independent of this work, since other
quantities here are calibrated against the same export.

The CLOSE-IT comparison is against published summary statistics, with a cohort drawn from them
rather than matched to participants.

Titration leaves these subjects more insulin-sensitive than the people they stand for. Across
the titrated store the correction factor ends at a median of 23.2 mg/dL per unit against the
40.0 recorded by DCLP3 participants, so it closes about half of the gap. Four subjects clear the
hypoglycaemia floors at no combination tried and are excluded, which selects towards subjects
that can be made safe.

The population bounds the design. Its adults all need more insulin than real do-it-yourself
looping adults, so matching the Commons on requirement draws in adolescents, and it supports
about three disjoint DCLP3-matched cohorts of fifteen, which is what limits the precision of the
group effect reported here.

The distinguishability test compares a real median against a simulated interval and is not a
formal test of equality. It answers whether a difference is establishable at the cohort size
used, which is a weaker question than whether the two populations agree.

## Provenance

Every figure above is reproducible from the repository against population `2af095014f6c1c75`.

| Section | Produced by | Output |
|---|---|---|
| Bench comparisons, announcement | `examples/bench_matrix.py`, `examples/bench_tables.py` | `bench_matrix.json` |
| Fitted Control-IQ | `examples/fit_control_iq.py` | `control_iq_fit.json` |
| Group effect | `examples/cohort_replicates.py` | `cohort_replicates.json` |
| Interval and split-half baseline | `examples/cohort_variation.py` | `cohort_variation.json` |
| Meal behaviour | `examples/meal_response.py`, `examples/real_meals.py` | `meal_response.json`, `real_meals_dia.json` |
| Cohorts | `examples/build_cohorts.py` | `cohorts.json` |
| Commons reference | `examples/commons_cohort.py`, `examples/commons_requirement.py` | `commons_cohort.json`, `commons_requirement.json` |
| Defence gain | `examples/calibrate_hypo_defence.py` | `hypo_defence_gain.json` |

Each script writes its output with a stamp of the population fingerprint, the titrated settings
digest and the code revision, and any analysis combining results refuses inputs whose stamps
disagree.
