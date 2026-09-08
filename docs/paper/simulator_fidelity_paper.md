# How far the UVA/Padova simulator sits from real closed-loop data, and how much of that distance lies outside the model

*Candidate for publication. Real-world figures are traceable to the cohorts recorded under
Provenance; simulator figures to the release files and the package source at the commit recorded
there. The analysis code is open and the processing steps are reproducible.*

## Abstract

Background. The UVA/Padova type 1 diabetes simulator has been accepted since 2008 as a substitute
for animal trials in the pre-clinical testing of automated insulin delivery. Algorithms bound for
regulatory approval are screened on it, so its resemblance to real-world glucose data bears
directly on which systems are judged safe. That resemblance has seldom been measured at scale, and
where a gap is found it is usually assumed to lie in the differential equations.

Methods. Two questions were asked in sequence. First, how far the open reference implementation
sits from real data: the 2008 model, all thirty personae across three age classes, was compared
with four independent real-world cohorts covering roughly 192 users, on eleven statistics of
glucose dynamics computed identically on both sides. The later S2013 model was then reconstructed
as closely as the open literature allows and measured the same way. Second, whether the remaining
distance closes without altering the model: four layers were added around it, being insulin
sensitivity that moves, a person who eats and treats their own hypoglycaemia, sensor error inside
the loop, and infusion sets that fail. Cohorts of 64 to 79, matched to each reference on what that
reference publishes, ran 28 days under a Control-IQ stand-in and under oref0 SMB, with distance to
the real population computed on the same subjects before and after.

Results. The four real cohorts converged closely, which licenses treating their spread as an
envelope. The simulator reproduced short-horizon autocorrelation for every persona class and
reached real glucose variability only through its child personae. Five of the eleven statistics
were reproduced by no persona at any age: the fat tail of unannounced-meal rises, the speed of
hypoglycaemia recovery, its rebound, sensor compression artefacts, and high-frequency sensor noise.
A sixth, week-to-week sensitivity drift, is zero by construction. The S2013 reconstruction reached
the real range on none of the eleven for adults, raised variability part-way without arriving,
pushed autocorrelation and diurnal amplitude out of range where the 2008 model had matched them,
and left the structural gaps untouched. Adding the four layers around the unaltered 2008 model then
cut the distance on the four measures describing where glucose sits by 55, 39 and 76 per cent
across three pairings, at a cost of 5.4 to 12.3 points of time in range from a bare 93.1 to 95.6
against real cohorts at 71.3 and 80.1. On hypoglycaemia the same layers moved the population
further from the real one in all three pairings, by 118, 321 and 53 per cent.

Conclusions. Most of the distance between the open simulator and a real closed-loop cohort lies
outside the differential equations, in the person and the hardware, and closes substantially when
those are represented. Hypoglycaemia does not, and moves the wrong way under every pairing tried,
which is the region in-silico screening exists to interrogate. Simulator fidelity should be
reported as a measured quantity alongside any in-silico result.

Keywords. type 1 diabetes; automated insulin delivery; in-silico testing; UVA/Padova simulator;
model validation; regulatory science

## 1. Background

The UVA/Padova simulator occupies an unusual position. It is not one model among several but the
accepted substitute for animal trials in pre-clinical testing of automated insulin delivery, and
control algorithms bound for regulatory approval are screened on it in place of animal studies. It
is also the standard platform for in-silico work on new controllers. What it does and does not
reproduce therefore shapes which systems reach people.

Real-world data at the scale needed to check it did not exist when it was accepted. It does now.
Several open cohorts carry more than a year of five-minute continuous glucose data from people
running automated delivery in ordinary life, and comparing the two is a matter of computing the
same statistics on both sides.

Where a gap is found, the reflex is to attribute it to the model. That is worth testing rather
than assuming, because a simulator is not only a set of differential equations. It is those
equations plus a sensor, a meal schedule, an announcement policy, a set of infusion hardware
assumptions and a person who does or does not respond to what is happening. The equations are the
part that is hardest to change and the part a licence governs. The rest is not.

## 2. What testing in silico currently exercises

The open 2008 release presents a controller with a noiseless sensor, a patient who announces every
meal accurately, an infusion set that never fails, and insulin sensitivity that does not move from
one day to the next. A low, once entered, is not treated by the person experiencing it.

Each of those is a modelling choice rather than an oversight, and each removes a source of
difficulty that a deployed controller meets daily. Whether their combined absence matters is an
empirical question.

## 3. Methods

### 3.1 Real-world cohorts

Four independent real-world datasets were used, covering roughly 192 users, many with more than a
year of five-minute data: a fully closed loop (Boost), an iAPS/Trio cohort, the OpenAPS/oref0
cohort from the OpenAPS Data Commons, and a pre-dynamic-ISF AndroidAPS cohort. They differ in
algorithm, in country and in era, which is what makes their agreement informative.

### 3.2 Signatures

Eleven statistics of glucose dynamics were computed the same way on both sides, taken per user and
pooled with bootstrap confidence intervals: glucose variability, the tail of the rise distribution,
autocorrelation at 30 and 60 minutes, outcome spread following a stuck high, diurnal amplitude,
hypoglycaemia recovery time and rebound rate, compression-low rate, sensor jitter, and week-to-week
insulin-sensitivity drift. For each we asked whether any persona class reproduced it, not only the
adults.

### 3.3 The S2013 reconstruction

The main change from 2008 to S2013 is time-varying insulin sensitivity, within and across days and
with a dawn component, fitted from clinical data. S2013 also adds glucagon counter-regulation
raising endogenous glucose production during a low, and improves hypoglycaemia glucose kinetics.
The first two were added to the 2008 personae together and the whole reconstruction measured; the
improved kinetics were not implemented, which is a caveat on the result. The sensitivity factor
scales insulin-dependent glucose uptake and hepatic insulin action with a day-to-day coefficient of
variation of 22 per cent and a dawn amplitude of 20 per cent. Counter-regulation raises endogenous
glucose production in proportion to how far below 80 mg/dL glucose has fallen and how fast. Meals,
announcement, sensor and controller are identical to the baseline, so any difference is due to the
two additions. Their magnitudes are clinically plausible values rather than certified per-subject
parameters, so the reconstruction isolates what the additions do rather than reproducing the
licensed model.

### 3.4 The four layers

Four layers were added around the unaltered 2008 model.

Insulin sensitivity that moves, within and between days. A person who eats on their own schedule
and treats their own hypoglycaemia. Sensor error inside the loop rather than a clean signal. And
infusion sets that occlude or fail.

Settings were titrated to consensus hypoglycaemia floors under a fixed regimen, so the comparison
is not between a well-tuned bare model and a badly tuned layered one.

### 3.5 Cohorts, matching and distance

Cohorts of 64 to 79 were matched to each reference on what that reference publishes, and ran 28
days under a Control-IQ stand-in and under oref0 SMB. Distance is the absolute difference between
simulated and real medians, in units of the real tenth-to-ninetieth percentile spread, averaged
over the measures in each group, so a distance of one is the width of the real population. It is
computed on the same subjects before and after adding the layers, which makes the comparison
paired.

Two groups of measures are reported separately throughout. Where glucose sits: time in range, time
above 180 mg/dL, mean glucose and variability. Hypoglycaemia: time below 70 and below 54 mg/dL.
Keeping them apart turned out to matter more than anything else in the study.

## 4. The four real cohorts agree with each other

The first result is what makes the rest interpretable. The four cohorts, built and worn
independently, sit in a tight band on almost every measure. Glucose variability is between 30 and
34 per cent for all four. The outcome spread 30 minutes after a stuck high runs from 27 to 34
mg/dL. Hypoglycaemia recovers to 100 mg/dL in 50 to 59 minutes and then overshoots above 180 mg/dL
about a quarter of the time. Sensor jitter runs from 4.5 to 6.7 mg/dL, and week-to-week
insulin-sensitivity drift from 8 to 22 per cent.

Nothing forced that agreement, and it is the load-bearing assumption of the method. Because four
different algorithms worn by different people give nearly the same numbers, those numbers describe
closed-loop life in general rather than one idiosyncratic group. Where the cohorts disagree, as
they do to a degree on compression lows, the envelope is wider and the test on that statistic is
correspondingly more forgiving.

## 5. Reproduced and unreproduced signatures

Table 1. Per-user median with a bootstrap 95 per cent interval. Simulator values outside the
real-world envelope are marked with an asterisk.

| Signature | Boost | Trio | OpenAPS | AAPS-classic | adult | adolescent | child |
|---|---|---|---|---|---|---|---|
| Glucose variability (CV%) | 30 | 33 | 34 | 32 | 23* | 24* | 30 |
| Rise tail P(rise>10)/5min (%) | 4.3 | 6.6 | 3.8 | 3.7 | 1.0* | 1.6* | 2.6* |
| Autocorrelation at 30 min | 0.8 | 0.8 | 0.9 | 0.8 | 0.8 | 0.9 | 0.8 |
| Autocorrelation at 60 min | 0.5 | 0.6 | 0.7 | 0.6 | 0.7 | 0.7 | 0.6 |
| Outcome SD after a stuck high (mg/dL) | 30 | 34 | 27 | 29 | 21* | 22* | 28 |
| Diurnal amplitude (mg/dL) | 35 | 41 | 48 | 56 | 47 | 59* | 52 |
| Hypoglycaemia recovery to 100 (min) | 59 | 50 | 55 | 50 | 113* | 119* | 110* |

Short-horizon autocorrelation is reproduced by every persona class. Glucose variability is reached
only through the child personae, which is a strange route to a match, since a controller under test
is not being screened on children as a proxy for adults.

Five of the eleven statistics were reproduced by no persona at any age: the fat tail of
unannounced-meal rises, the speed of hypoglycaemia recovery, its rebound, sensor compression
artefacts, and high-frequency sensor noise. A sixth, week-to-week insulin-sensitivity drift, is
zero in the 2008 model by construction and therefore cannot be reproduced at all.

## 6. The limits of refining the model

The obvious objection is that this tests the 2008 model and later versions are better. Part of that
is correct, so it deserves a measured answer.

The reconstructed S2013, carrying time-varying sensitivity and glucagon counter-regulation
together, reached the real range on none of the eleven signatures for the adult personae. Its
additions raised variability part-way without reaching the real band. They pushed autocorrelation
and diurnal amplitude, which the 2008 model had matched, out of range. And they left the structural
gaps untouched, because none of the five unreproduced statistics is a property the additions
address: an absent sensor artefact is not created by making sensitivity vary.

Refining the equations is therefore not obviously the route to closing this particular distance.
That prompts the second question.

## 7. What closes when the model is left alone

Adding the four layers around the unaltered 2008 model, with its published parameters untouched,
moves the population a long way towards the real one on where glucose sits, and further away on
hypoglycaemia, in every pairing tried.

Table 2. Distance to the real population, before and after, on the same subjects.

| Pairing | n | Where glucose sits, bare | layered | change | Hypoglycaemia, bare | layered | change |
|---|---|---|---|---|---|---|---|
| DCLP3, Control-IQ stand-in | 79 | 0.89 | 0.40 | -55% | 0.29 | 0.62 | +118% |
| DCLP3, oref0 SMB | 77 | 0.83 | 0.51 | -39% | 0.35 | 1.48 | +321% |
| Commons, oref0 SMB | 64 | 0.52 | 0.13 | -76% | 0.19 | 0.29 | +53% |

The cost in time in range is 5.4 to 12.3 points, from a bare 93.1 to 95.6 against real cohorts at
71.3 and 80.1. A bare simulator holding a virtual population at 95 per cent time in range is not
describing anything that happens to people, and most of that discrepancy turns out to live outside
the differential equations.

Holding one controller fixed and varying only the bench beneath it, at a scenario where some meals
are announced:

| Measure | bare | layered | paired difference | DCLP3 |
|---|---|---|---|---|
| Time in range 70-180, % | 95.59 | 83.26 | -12.33 [-13.55, -10.04] | 71.29 |
| Time below 70, % | 0.84 | 2.29 | +1.45 [+1.00, +1.98] | 1.36 |
| Time below 54, % | 0.06 | 0.55 | +0.48 [+0.35, +0.79] | 0.20 |

Time below 70 moves from well under the real figure to somewhat over it, and time below 54 from
0.06 per cent, which is barely any hypoglycaemia at all, to 0.55 against a real 0.20. The direction
is right and the magnitude overshoots, which is what the distance table records as an increase.

## 8. Withdrawing meal announcement

Removing announcement cost the controller without meal detection 4.84 points of time in range (3.58
to 7.22). It cost oref0 SMB, which detects rises, between 0.08 and 0.84 points, with every interval
spanning zero. The published CLOSE-IT figure is 2.2.

The two controllers respond to the same withdrawal very differently, which is the expected result
and a useful check that the bench discriminates between algorithms rather than flattening them.

## 9. Discussion

Two findings run together and neither is complete without the other.

The open simulator exercises a smooth, announced-meal, stationary, clean-sensor regime. It is
largely blind to the unannounced meals, variable insulin efficacy, sensor artefacts and drifting
sensitivity that shape real-world safety, and refining the equations towards S2013 does not close
that, while breaking two things the earlier model had right.

Most of the distance, though, is not in the equations. Representing the person and the hardware
around an unaltered 2008 model closes between two fifths and three quarters of the gap on where
glucose sits. That is a considerably more optimistic finding than the first half alone suggests,
and it points somewhere practical: an in-silico bench can be made substantially more realistic
without a licence to the model and without touching a differential equation.

Hypoglycaemia is the exception, and it is the exception that matters. Under every pairing tried the
layers moved hypoglycaemia further from the real population, by between 53 and 321 per cent. The
bare model's hypoglycaemia is unrealistically absent; the layered model's is present but
mis-sized. Since screening a dosing algorithm in silico is very largely an exercise in asking how
often it causes hypoglycaemia, that is the measure this bench places worst, and no result about
hypoglycaemia frequency obtained on either configuration should be read as calibrated.

None of this is grounds to distrust simulation. It is grounds to change how simulation is validated
and reported. Simulator fidelity is a measurable quantity, measurable against real-world data that
now exists in quantity, and an in-silico result that does not report it is asking to be taken on
trust.

## 10. Limitations

The S2013 reconstruction is a reconstruction. The improved hypoglycaemia kinetics were not
implemented, and the magnitudes used are clinically plausible values rather than certified
per-subject parameters, so it isolates what the additions do rather than reproducing the licensed
model. A reader with licensed access could do better and should.

The real-world cohorts are self-selected users of open-source systems, which is the population that
publishes data at this scale and is not a random sample of people with type 1 diabetes. Their
agreement with one another bounds that concern without removing it.

Distance as defined here is scaled to the real population's own spread, so a reference population
with narrow spread makes the same absolute discrepancy look larger. The three pairings differ in
that spread, which is one reason the percentage changes vary as widely as they do.

A distinguishability verdict, meaning whether a virtual and a real cohort could be told apart by a
reader given both, depends on cohort size and is not offered here.

## Provenance

Real-world figures derive from the four cohorts named in Section 3.1. Simulator figures derive from
the open reference implementation at the commit recorded in the repository, with the layered results
traceable to the measurement files under `docs/measurements/`.

## References

1. Dalla Man C, Micheletto F, Lv D, Breton M, Kovatchev B, Cobelli C. The UVA/PADOVA type 1
   diabetes simulator: new features. J Diabetes Sci Technol. 2014;8(1):26-34.
2. Visentin R, Dalla Man C, Cobelli C. One-day Bayesian cloning of type 1 diabetes subjects:
   towards a single-day UVA/Padova type 1 diabetes simulator. IEEE Trans Biomed Eng.
   2016;63(11):2416-2424.
3. Xie J. simglucose: a type 1 diabetes simulator implemented in Python for reinforcement learning
   purposes. 2018.
