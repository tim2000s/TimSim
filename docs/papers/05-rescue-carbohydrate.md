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

All of the figures below were remade on 13 August after the first pass globbed filenames in a
way that missed any carrying a user-id prefix, so it drew on eight to thirteen users where
thirty qualify. Both sets are given where they differ, because one of them changed the model.

Real helpings are 15 g at a reading of 65 to 75, 18 g between 55 and 65, 20 g between 45 and
55 and 22 g below that, with a ninetieth percentile of 45 g throughout, across 4,544 entries
from thirty users. The mean at 65 to 75 is 21.0 g on a median of 15.0, so the distribution is
strongly skewed. Dependence on depth is weak, -0.117 g per mg/dL. This simulator gave 34.4 g.

The first pass put those medians at 20, 24, 25 and 25 g on 1,001 entries from eight users. The
slope and the ninetieth percentile survived; the centre did not.

Drawing the measured distribution instead moved the rebound from 63.9% to 54.5%, a paired
difference of -12.0 with a 95% interval of 4.4 over twenty subjects.

The response to a helping was then measured and the model was found to be right. Across 1,395
isolated real rescues the rise is 4.30 mg/dL per gram, with an interquartile range of 2.46 to
8.07. The simulator gives 4.91. The first pass gave 4.23 on 309 rescues from eight users, so
this is the measurement that held best.

Only 19.4% of real excursions are treated at all, across 16,987 excursions from thirty users,
and the share is flat with depth. The simulator treated more than all of them, 108%, because
it also treats pre-emptively.

That looked decisive until the strata were separated.

| | Recovery to 100 | Rebound above 180 | n |
|---|---|---|---|
| Real, untreated | 59.4 min | 21.0% | 10,876 |
| Simulated, untreated | 80.0 min | 38.5% | 366 |
| Real, treated | 59.9 min | 28.2% | 4,075 |
| Simulated, treated | 65.0 min | 55.5% | 128 |

The model is worse in both strata by about the same factor on the rebound, 1.83 times
untreated and 1.97 times treated.

One thing the first pass got wrong here. On thirteen users it put real treated recoveries at
50.0 minutes against 62.4 untreated, which looked like treating a low shortening it. On thirty
users the two are the same, 59.9 against 59.4. Treating a low does not bring it back faster;
it raises the chance of overshooting, 28.2% against 21.0%.

Sweeping the simulated treated share over 1.0, 0.6, 0.4 and 0.25 moved the rebound from 53.3%
to 40.5% without order, 50.0 at 0.6 and 55.1 at 0.4, which is mostly noise at twenty subjects,
and recovery left its range at every reduced level.

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
treat without recording it, so 19.4% of excursions is a lower bound. And the simulated side was measured
under the built-in correction loop while the real users were on oref and AndroidAPS, so a
difference in how promptly insulin is withdrawn would appear here as a difference in the
person. That confound is unresolved and is the first thing to settle before anything is
concluded about physiology.

One result supports the method rather than the model. Treated recoveries are 27.3% of the
total, and weighting the two strata by that gives a pooled rebound of 23.0% against the 23.2
to 28.4 that the signature carries from a separate 192 users. It sits just below the band
rather than inside it, which is closer agreement than two differently-drawn cohorts owe each
other and is the best available evidence that the reference range is sound. The first pass put
the same figure at 26.6%.

## What changed

`person/behaviour.py` draws a helping from a lognormal about a median of 15 g at 65 mg/dL,
shifting with the reading by -0.117 g per mg/dL, with a sigma of 0.857 that reproduces the
observed mean of 21.7 g and ninetieth percentile of 45. Timing is untouched. `P_TREAT_LOW`
exists as a parameter and is left at 1.0, with the sweep recorded as the reason.

The fit is good at the shallow end, where most lows are, and poorer at the deep end: at 50
mg/dL it gives a median of 16.8 g against a real 20.0 and a ninetieth percentile of 50.5
against 45. A linear term in the reading cannot follow a distribution whose centre and spread
both move, and a second parameter was not added for it.
