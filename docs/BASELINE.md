# What the layers change, against the people they are meant to resemble

The UVA/Padova S2008 model has known weaknesses as a stand-in for a person with type 1 diabetes.
The layers in this package exist to close some of that gap. This document measures how far they
do, so that somebody using the simulator can see what the work is worth on their own terms rather
than take it on assertion.

It is a reference table, not an argument. Every figure comes from
[validation.json](measurements/validation.json), 2,398 runs of 28 days made on 21 August 2026,
and [validation_table.json](measurements/validation_table.json) holds the same numbers in full.
`examples/validation_table.py` reproduces it.

## How to read it

Three pairings, each a real population and the algorithm those people actually ran. DCLP3 under
the Control-IQ stand-in, the OpenAPS Data Commons under oref0 SMB, and CLOSE-IT under oref0 SMB.
Cohorts are drawn from the generated population to match each reference on age and recorded daily
insulin. A fourth pairing, DCLP3 under oref0, is deliberately absent: those participants ran
Control-IQ and no published cohort of them running oref0 exists, so it has nothing to be compared
against.

Every figure is a median, a mean with its standard deviation, and the range across subjects.
DCLP3 and CLOSE-IT report time in range as a mean, and this package reported medians, so the two
were never on the same footing. The median is the more robust statistic on measures where a third
of subjects sit at zero, and the mean is what the paper prints, so both are given.

A difference is called only when the real median falls outside the simulated cohort's 95 per cent
interval. A gap expressed in units of the real spread says how large it is, not whether it
survives the cohort having been drawn differently, which is issue 16 in
[ISSUES.md](ISSUES.md). CLOSE-IT publishes a mean and a standard deviation and no participants,
so it supports no median, no spread, and no verdict at all.

Completion is given for every arm. A run stops when glucose leaves the range the model is defined
over, the runs that stop are the ones that went furthest wrong, and every median is therefore
conditioned on survival.

## The headline: stock against the full stack

Against DCLP3, 84 matched subjects and 67 participants.

| Measure | Stock S2008 | All four layers | Real | Stock verdict | Layered verdict |
|---|---|---|---|---|---|
| Time in range 70-180 % | 90.85 | 82.09 | 71.29 | differs | differs |
| Time below 70 % | 1.95 | 2.59 | 1.36 | differs | differs |
| Time below 54 % | 0.32 | 0.77 | 0.20 | same | differs |
| Time above 180 % | 6.03 | 14.88 | 26.87 | differs | differs |
| Mean glucose mg/dL | 126.05 | 141.68 | 155.45 | differs | differs |
| Variability CV % | 25.83 | 31.29 | 33.37 | differs | differs |

Medians. The layers move every location measure towards the trial and close roughly a third of
the distance: time in range from 19.6 points above the real cohort to 10.8, mean glucose from 29.4
mg/dL below to 13.8. On neither does the simulated cohort become indistinguishable from the trial.

Against the Commons, 63 subjects and 77 users, the same arms are much closer to begin with. Time
in range moves 88.83 to 86.25 against a real 80.05, and mean glucose 121.29 to 131.62 against
134.90, where the full stack is indistinguishable from the reference. That is the closest this
package gets to a real population on any measure of where glucose sits.

Against CLOSE-IT the simulated cohort holds 84 to 85 per cent in range against a published real
mean of 66.0. That is the largest gap in this document and the one that can be quantified least,
because there is nothing to compare a spread against.

## What each layer does on its own

DCLP3, medians, with each layer applied alone to the titrated base.

| Arm | TIR % | TBR70 % | TBR54 % | TAR180 % | Mean | CV % | Completed |
|---|---|---|---|---|---|---|---|
| stock S2008 | 90.85 | 1.95 | 0.32 | 6.03 | 126.05 | 25.83 | 81/84 |
| titrated settings | 90.77 | 1.82 | 0.23 | 6.29 | 128.71 | 25.48 | 84/84 |
| physiology only | 84.86 | 5.16 | 1.62 | 8.89 | 129.86 | 31.82 | 55/84 |
| behaviour only | 91.29 | 1.10 | 0.06 | 7.61 | 131.46 | 24.67 | 84/84 |
| sensor only | 90.24 | 2.00 | 0.32 | 6.34 | 128.57 | 25.72 | 84/84 |
| site only | 83.10 | 1.64 | 0.30 | 13.83 | 138.92 | 30.10 | 82/84 |
| all four | 82.09 | 2.59 | 0.77 | 14.88 | 141.68 | 31.29 | 71/84 |
| real | 71.29 | 1.36 | 0.20 | 26.87 | 155.45 | 33.37 | 67 |

Two layers do nearly all the work and they do different things. The site layer carries
hyperglycaemia: alone it takes time above 180 from 6.3 to 13.8 per cent and mean glucose from
128.7 to 138.9, which is most of the movement the full stack achieves. The physiology layer
carries variability: alone it takes the coefficient of variation from 25.5 to 31.8 against a real
33.4, and it is the only arm on any measure where the simulated cohort cannot be told apart from
the trial.

The sensor layer moves the outcomes very little. That is expected rather than disappointing: it
exists so an algorithm sees compression lows and jitter, and what it changes is what the
controller is reacting to rather than where glucose sits.

The behaviour layer alone improves every measure, which is worth stating plainly because it is
counterintuitive. It supplies rescue carbohydrate, so it lifts subjects out of lows that would
otherwise deepen, and it makes the controller adaptive. Its cost appears only when meals are
unannounced, below.

## The settings, which are not a layer

Titration is this package's work and not the model's, so the table separates it. On DCLP3 it takes
completion from 81 of 84 to 84 of 84 and removes three hypoglycaemic terminations, while leaving
time in range and variability where they were. It is the difference between a subject dosed from
its own physiology, which no real person is, and one dosed from settings a clinician would
plausibly have arrived at.

That step buys safety rather than fidelity, and both matter for different reasons.

## Meal announcement

Announcement lives in the behaviour layer, because it is a person who does or does not announce a
meal. An arm without that layer is told the exact carbohydrate of every meal and the setting does
nothing, so only the two arms carrying behaviour have announced and unannounced variants.

DCLP3, medians:

| Arm | Announced | Normal | Unannounced |
|---|---|---|---|
| behaviour only, TIR % | 95.00 | 91.29 | 82.59 |
| all four layers, TIR % | 82.74 | 82.09 | 77.18 |
| all four layers, mean glucose | 139.69 | 141.68 | 146.09 |

Withdrawing announcement costs about 5 points of time in range on the full stack and 12 on the
behaviour layer alone, and it costs them through hyperglycaemia rather than hypoglycaemia. So the
unannounced arm is the closest any configuration gets to the trial's time in range, at 77.2
against 71.3, and it gets there by being worse rather than by being more realistic in any other
respect.

## Completion, and why the physiology row needs it

| Arm | Completed | Terminations |
|---|---|---|
| stock S2008 | 81/84 | 3 hypoglycaemic |
| titrated settings | 84/84 | none |
| physiology only | 55/84 | 28 hypoglycaemic, 1 hyperglycaemic |
| behaviour only | 84/84 | none |
| sensor only | 84/84 | none |
| site only | 82/84 | 1 each way |
| all four | 71/84 | 13 hypoglycaemic |
| all four, unannounced | 72/84 | 8 hypoglycaemic, 4 hyperglycaemic |

The physiology layer alone loses a third of the cohort, all but one of them hypoglycaemically,
because it carries the physiological variation with no behaviour layer to eat when glucose falls.
So its variability agreement is measured on the subjects that avoided a severe low, and its
hypoglycaemia figures understate what the layer does to the ones that did not. Adding behaviour
restores completion to 84 of 84.

## What this says about using the simulator

The layers make the model harder in the direction real people are harder: more time high, higher
mean glucose, more variability, and a cohort that loses subjects. On DCLP3 they close about a
third of the distance to the trial on where glucose sits, and they close the variability gap
almost entirely.

They do not make the model match a trial. On the strongest pairing no arm is indistinguishable on
time in range, mean glucose or time above 180. Anyone benchmarking an algorithm here is
benchmarking it on a population that still runs about ten points of time in range better than the
DCLP3 participants did.

And they make hypoglycaemia worse. The stock model sits on the real value for time below 54 mg/dL
and every layered arm sits above it. That is the measure this package is furthest from real people
on, it is the measure its own group floor is widest on, and it is the one to distrust first.
