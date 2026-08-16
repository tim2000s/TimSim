# Adding a Person to the UVA/Padova S2008 Simulator: Two Algorithms Measured Against the Real Populations That Run Them

Status: methods written, results and discussion pending the runs listed at the end of this
file. Every figure quoted below is traceable to a file in `docs/measurements/`. Nothing is
carried over from the drafts dated 14 and 15 August 2026, which are marked superseded in the
Research-Papers folder and whose figures did not survive remeasurement.

## Abstract

*Pending. Written last, from the results.*

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

The validation question is deliberately narrow. We do not ask whether the simulator predicts an
individual's glucose, which it cannot. We ask whether the population it generates sits where a
real population sits on the statistics a safety comparison uses, and where it does not.

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

The generator is reproducible from its seed. It previously drew each class's random stream from
Python's salted string hash, so it produced a different hundred subjects in every process and
the population any figure had been measured on could not be rebuilt. Subject names are
positional, so regenerating reuses every name for a different body; the titration store
therefore records a digest of the population it was fitted to and refuses to be applied to
another. Population `2af095014f6c1c75` is the one every figure here was measured on.

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

Three appear, and they are kept separate.

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
pump records across that window, which a reconstructed daily requirement needs, and that is the
set a cohort is matched to. Restricting the outcome reference to those 71 does not move it.

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

*Pending the runs listed below.*

Planned structure, with the source for each already established:

1. A reactive stand-in for Control-IQ against the DCLP3 closed-loop arm, on both benches.
2. The same, with the unpublished parameters fitted on the calibration half and reported on the
   held-out half.
3. oref0 SMB against the OpenAPS Data Commons users, on both benches.
4. What the two comparisons have in common, and where the two real populations disagree.
5. Meal behaviour of the underlying model, against real uncovered meals.
6. Withdrawing meal announcement, against CLOSE-IT.
7. How far each answer moves when only the participants change, which every gap above is read
   against.

## Discussion

*Pending the results.*

## Limitations

*Pending, but four are already established and will appear whatever the results show.*

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

## What this file is waiting on

| Run | Gives | Status |
|---|---|---|
| `bench_matrix.py` on defence gain 0.20 | Results 1, 3, 4, 6 | running |
| `rerun_studies.sh` on gain 0.20 | Meal behaviour for result 5, and the signature and ladder figures the discussion draws on | running |
| `fit_control_iq.py` on gain 0.20 | Result 2 | to rerun |
| `cohort_replicates.py` | Result 7, the group effect | needs 9 subjects titrated |
| `cohort_variation.py` | Result 7, the within-cohort interval and the real split-half baseline | rerun once the matrix lands |
