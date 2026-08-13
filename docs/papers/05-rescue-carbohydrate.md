# Where a low comes from, and why the model overshoots leaving one

## Question

With every layer on, the simulator rebounds above 180 mg/dL after 58.5% of hypoglycaemic
recoveries. Four real cohorts of 192 users give 23.2 to 28.4%. It is the largest single gap in
the fidelity table and the only one no layer had moved.

Overcorrecting a low is a real behaviour and the reference range is real people doing it. The
question is not whether the mechanism belongs in the model but why its rate is roughly twice
what people manage.

## Method

Four candidate causes were separated, each measured on both sides with the same rule.

The size of a helping was measured against the reading the person could see, on carbohydrate
entries made below 75 mg/dL in the OpenAPS Data Commons export. An earlier version of this
measurement summed every entry in a window around each excursion; that is recorded in the
results because it gave a different and wrong answer.

The response to a helping was measured as the reading at the entry, the highest reading within
three hours, and the difference divided by the grams. Entries followed by more carbohydrate
inside that window were dropped on both sides, because the rise would otherwise belong to more
than one of them.

The share of lows treated was measured as the fraction of excursions below 70 mg/dL with a
carbohydrate entry between fifteen minutes before the crossing and thirty after.

Recoveries were then split into treated and untreated on both sides by that same rule, and
recovery time and rebound rate computed within each stratum.

## Results

Real helpings are 20 g at a reading of 65 to 75 and 25 g below 55, with a ninetieth percentile
of 45 g, across 1,001 entries from eight users. Dependence on depth is weak, -0.129 g per
mg/dL with a correlation of -0.074. This simulator gave 34.4 g.

Drawing the measured distribution instead moved the rebound from 63.9% to 54.5%, a paired
difference of -12.0 with a 95% interval of 4.4 over twenty subjects.

The response to a helping was then measured and the model was found to be right. Across 309
isolated real rescues, 25.0 g eaten at 64 mg/dL peaks at 170 within three hours at 4.23 mg/dL
per gram, with an interquartile range of 3.02 to 6.90. The simulator gives 25.6 g at 62,
peaking at 172, at 4.91.

Only 23.4% of real excursions are treated at all, and the share is flat with depth: 23.1%
between 54 and 70 mg/dL, 24.6% between 45 and 54, 24.1% between 35 and 45. The simulator
treated more than all of them, 108%, because it also treats pre-emptively.

That looked decisive until the strata were separated.

| | Recovery to 100 | Rebound above 180 | n |
|---|---|---|---|
| Real, untreated | 62.4 min | 25.3% | 4,660 |
| Simulated, untreated | 80.0 min | 38.5% | 366 |
| Real, treated | 50.0 min | 33.2% | 912 |
| Simulated, treated | 65.0 min | 55.5% | 128 |

The model is worse in both strata by about the same factor, roughly 1.5 times the rebound and
some sixteen minutes slower. Sweeping the treated share over 1.0, 0.6, 0.4 and 0.25 moved the
rebound from 53.3% to 40.5% without order, 50.0 at 0.6 and 55.1 at 0.4, which is mostly noise
at twenty subjects, and recovery left its range at every reduced level.

## Discussion

Three of four candidates are eliminated. The dose schedule is not the cause: splitting a
helping and re-treating on a twenty-minute recheck, which is what the real records show people
doing, made the rebound worse, 72.9% above 180 and 33.5% above 250 against 71.2% and 24.0%.
Carbohydrate takes about twenty minutes to act, so the simulated person is still below the
threshold at every recheck and eats again 1.6 times an episode, the second helping landing
while the first is absorbing. The response to carbohydrate is not the cause either, being
inside the real interquartile range. And the treated share is not the cause, because the gap
is present in both strata at the same size.

What is left is how a low ends, which is neither what the person eats nor how the body handles
it once eaten. That is a property of recovery and nothing in the behaviour layer can reach it.

Two cautions on the numbers. The real treated share counts logged carbohydrate and people
treat without recording it, so 23.4% is a lower bound. And the simulated side was measured
under the built-in correction loop while the real users were on oref and AndroidAPS, so a
difference in how promptly insulin is withdrawn would appear here as a difference in the
person. That confound is unresolved and is the first thing to settle before anything is
concluded about physiology.

One result supports the method rather than the model. Weighting the real strata by the real
treated share gives a pooled rebound of 26.6%, which falls inside the 23.2 to 28.4 that the
signature carries from a separate 192 users. Two independent measurements agreeing where they
overlap is the best evidence available that the reference ranges are sound.

## What changed

`person/behaviour.py` draws a helping from a lognormal about a median of 22 g at 65 mg/dL,
shifting with the reading by the measured coefficient, with the spread reproducing the observed
ninetieth percentile. Timing is untouched. `P_TREAT_LOW` exists as a parameter and is left at
1.0, with the sweep recorded as the reason.
