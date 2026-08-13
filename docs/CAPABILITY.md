# What this can be used for, against the licensed releases and against real people

Two comparisons matter and they answer different questions. The first is what the model
contains, against the UVA/Padova releases it descends from. The second is whether the people
it produces resemble real people, which is what a bench for testing algorithms actually needs.

## Against S2008, S2013 and S2017

simglucose implements S2008. Its parameter table carries 62 columns, none of them glucagon,
and its equations contain no counterregulation and no risk term. S2013 and S2017 are licensed
and not redistributable, so everything here works from S2008 and adds what it can defend.

| Mechanism | S2008 | S2013 | S2017 | TimSim on S2008 |
|---|---|---|---|---|
| Meal model, glucose and insulin kinetics | yes | yes | yes | inherited |
| Time-invariant parameters | yes | yes | no | no, sensitivity moves |
| Risk term deepening hypoglycaemia | no | yes | yes | implemented, off, measured |
| Glucagon kinetics, secretion, action | no | yes | yes | not implemented, and the absence has consequences |
| Intraday insulin sensitivity variation | no | no | yes | implemented, on |
| Dawn phenomenon | no | no | yes | implemented, on |
| Diurnal basal and carbohydrate ratio | no | no | yes | implemented, off |
| Multi-day correlated sensitivity | no | no | no | implemented, on |
| Meal-to-meal absorption variation | no | no | no | implemented, calibrated |
| Sensor error inside the loop | no | no | no | implemented, on |
| A person who eats and treats lows | no | no | no | implemented, on |
| Infusion site failure | no | no | no | implemented, on |
| Physical activity | no | no | no | implemented, off, harmful |

Two of the boxes need their reasons stated rather than left as a mark in a table.

The risk term is S2013's and is implementable, because its risk function is Kovatchev's Low
Blood Glucose Risk Index with published constants, leaving one free parameter. It is off
because it imports half of a mechanism: it makes lows deeper without the glucagon compartment
that ends them, and that compartment's eight parameters were drawn from a distribution the
papers do not publish. Calibrated at 0.05 it moved time below 70 from 2.79% to 4.18% against
4.07% measured across 30 real closed-loop users, so it does what the papers say. It also took
the diurnal amplitude from 73.1 to 86.3 mg/dL and the fidelity count from eight of eleven to
six.

Physical activity is in none of the releases and is implemented here. It is off because it
made the model worse, taking the count from eight of eleven to five and raising both
autocorrelations out of range where lowering them was the purpose.

So against the licensed lineage this sits between S2008 and S2017 on sensitivity variation,
behind S2013 on hypoglycaemia mechanism, and ahead of all three on everything that is not the
body: the sensor, the person and the infusion set.

## Against real people

The eleven signatures were computed on 101 users of the OpenAPS Data Commons export over
matched 28-day windows, using the same functions the simulator is scored with, and compared
with twenty simulated subjects run under all four drivers with the full stack.

| Signature | Published band | Real p10-p90 | Simulated p10-p90 | Overlap |
|---|---|---|---|---|
| Glucose variability, CV% | 29.5-34.3 | 29.9-41.4 | 27.2-43.4 | 100% |
| Rise tail, % | 3.7-6.6 | 1.9-6.6 | 2.3-6.4 | 88% |
| Autocorrelation at 30 min | 0.78-0.87 | 0.81-0.92 | 0.86-0.95 | 51% |
| Autocorrelation at 60 min | 0.50-0.68 | 0.51-0.77 | 0.61-0.86 | 64% |
| Outcome SD at a stuck high | 26.5-33.5 | 22.4-34.6 | 19.0-33.8 | 93% |
| Diurnal amplitude, mg/dL | 34.7-56.3 | 32.9-78.8 | 30.4-102.0 | 100% |
| Hypoglycaemia recovery, min | 50-59 | 40.0-80.0 | 33.0-78.5 | 96% |
| Hypoglycaemia rebound, % | 23.2-28.4 | 16.7-52.9 | 23.9-87.5 | 80% |
| Compression lows per 30 d | 1.9-5.3 | 0.0-7.5 | 2.1-5.4 | 43% |
| Sensor jitter, mg/dL | 4.5-6.7 | 3.8-12.4 | 5.6-5.7 | 2% |

Nine of ten simulated medians fall inside the real tenth-to-ninetieth percentile. Four of ten
fall inside the published band. The simulated column predates the rescue helping being
remeasured, which took the cohort median of the rebound row from 64.6% to 47.0%.

The two numbers are not in conflict and the difference between them is arithmetic. The
published band is the minimum and maximum of four cohort medians, so it describes where the
centre of a cohort sits and is narrow because averaging over users removes their spread. The
percentile range describes where individuals sit. A simulator that has to produce a population
of virtual people for an algorithm to meet is answerable to the second, and this package has
been marking itself against the first.

That correction should be applied to earlier conclusions in this repository, including some
recorded as failures. The cluster described as showing the model is too predictable, the two
autocorrelations and the outcome spread, sits inside the real individual range on all three.

It also changes a decision rather than only a description. The rescue helping was remeasured
on 4,544 real entries and its median fell from 22 g to 15 g. Scored three ways on the same
twenty subjects:

| Draw | Grams | Inside the published band | Inside the real p10-p90 |
|---|---|---|---|
| Uniform 20-40 g | 35.2 | 10 of 11 | 9 of 10 |
| Fitted at 22 g | 26.1 | 8 of 11 | 9 of 10 |
| Fitted at 15 g | 21.5 | 8 of 11 | 10 of 10 |

The measured helping is the worst of the three against the band and the only one with every
signature inside the range of real people. The signature that separates them is hypoglycaemia
rebound, at 64.6% under the uniform draw against a real ninetieth percentile of 52.9, falling
to 47.0% and inside. Choosing by the band would have kept a draw that gives 35 g where real
people give 15.

## What is genuinely weak

Three things, and the first was found only after the rest of this document was written.

Nothing in the model arrests a falling glucose. Fifteen of forty subjects fail to complete 28
days under the default controller, fourteen of them by glucose reaching 10 to 13 mg/dL, and
the population sits at or below 40 mg/dL on 0.44% of readings against a real 0.07%. The
distribution is ordinary and the tail runs to zero, so no statistic computed over the body of
it shows this. It also means every cohort figure here is conditioned on survival, and survival
is selection on the variable most of them measure. See
study 08 of the Research-Papers repository.

Hypoglycaemia rebound is the worst-fitting statistic by a distance, though the remeasured
rescue helping brought the median inside the real range for the first time, from 64.6% to
47.0% against a real ninetieth percentile of 52.9%.

What remains is not the rescue dose, not the response to carbohydrate and not the share of
lows treated; all three were measured and eliminated in
study 05 of the Research-Papers repository. It is how a low ends. The model
takes 80 minutes to recover from an untreated low against a real 59.4 and rebounds 1.83 times
as often, and the same factor appears in treated lows, so nothing the person does reaches it.

The population is too uniform in everything the rig contributes. Sensor jitter spans 5.6 to
5.7 mg/dL across every simulated subject against a real 3.8 to 12.4, an overlap of 2%, and
compression lows manage 43%. Every virtual person is given the same sensor. Real people's
sensors differ more than their bodies do on these measures, and nothing in the package varies
them per subject.

## What it can be used for

A pre-clinical gate, in the sense the UVA/Padova simulator was accepted for in 2008: fix the
acceptance criteria before the run, run the cohort, and report whether anything trips them.
That is a substitute for animal testing ahead of a trial and not for the trial.

Surfacing a failure mode is stronger still, because a failure found this way is a
demonstration rather than an estimate. Put an algorithm in front of a person who eats without
announcing it, treats their own lows and whose infusion set fails, and watch for stacking,
oscillation or a failure to withdraw basal.

## What it cannot be used for

Certifying a system as safe, or pricing a settings change for an individual. The exposure
arithmetic in [OSAID.md](OSAID.md) puts both out of reach and no further work on the model
changes that.

Any claim resting on hypoglycaemia rebound, or on the depth or duration of a low, until the
missing floor is dealt with. The relevant statistics are computed over survivors.

Any claim resting on between-subject variation in sensor behaviour, which is absent.

## Provenance of the comparison

The 101 users are self-selected do-it-yourself loopers whose data covers 2015 to 2022, so they
are not a clinical cohort and are not independent of everything here: some measurements in
this repository were calibrated against the same export, though not against these signatures.
The published band comes from a separate 192 users of four systems. Where the two overlap they
agree: weighting the real hypoglycaemia strata by the real treated share gives a pooled
rebound of 26.6%, inside the published 23.2 to 28.4.
