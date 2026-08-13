# Four mechanisms for making the underlying model more realistic

## Question

With every layer on, five signatures sat outside the published band, and three of them said
the same thing: the model is too predictable. Autocorrelation at thirty and sixty minutes
above its range, and the spread of outcomes from a stuck high below its own. No layer had
moved them.

Four candidates were proposed, in the order they seemed most likely to help: meal-to-meal
absorption variation, physical activity, a correction to how a low ends, and a correlated
multi-day component in insulin sensitivity.

## Method

Each was grounded in data where the database allowed it, implemented behind a flag defaulting
to off, and tested for being inert when off and bit-identical to the stock model when never
switched on. Then all were regressed together: one arm per mechanism differing from the
baseline by exactly one thing, plus an arm with two of them so that an interaction would show
up as the sum not adding. Twenty subjects, 28 days, paired, under the built-in loop.

Absorption variation was calibrated against six real users with at least fifteen isolated
meals each. Multi-day sensitivity was aimed at the week-to-week variation in total daily
insulin, measured at 7.3% across 115 real users. Activity could not be grounded at all,
because the records carry no exercise events, so its schedule comes from the literature.

## Results

How a low ends was never implemented, and the reason is the result. S2013's risk term, already
in the package and switched off, makes lows deeper rather than shorter. The counterregulation
that would shorten them is a glucagon compartment whose eight parameters the papers do not
publish. And the model has separately been measured to produce four times the glucose of
long-standing type 1 diabetes during a low, so adding glucose production cannot be the answer
to lows that last too long.

The other three:

| Signature | Real | baseline | absorption | slow 0.15 | slow 0.30 | activity |
|---|---|---|---|---|---|---|
| cv | 29.5-34.3 | 30.7 | 35.5 | 33.6 | 34.1 | 35.0 |
| acf30 | 0.78-0.87 | 0.87 | 0.88 | 0.86 | 0.86 | 0.89 |
| acf60 | 0.50-0.68 | 0.64 | 0.69 | 0.61 | 0.62 | 0.71 |
| outcome | 26.5-33.5 | 24.0 | 28.9 | 26.4 | 26.4 | 24.8 |
| hypo_rec | 50-59 | 46.2 | 52.5 | 58.8 | 60.0 | 47.5 |
| insulin_cv | 4.5-11.1 | 5.3 | 5.2 | 3.8 | 4.4 | 5.3 |
| In range of eleven | | 8 | 8 | 9 | 9 | 5 |

Correlated multi-day sensitivity at 0.15 is the only net improvement. It takes the outcome
spread into range, +1.4 with an interval of 1.0, and the recovery time with it, +12.7 with an
interval of 5.1, and pulls both autocorrelations down.

Activity is harmful, eight of eleven down to five. It raises the autocorrelation at thirty
minutes by 0.02 and at sixty by 0.05, both out of range, where lowering them was the entire
purpose. Two schedules were tried and both did it.

Absorption variation is neutral on the count. It fixes the outcome spread decisively, +4.8
with an interval of 1.3, and breaks variability, +4.2 with an interval of 1.9. Combined with
the slow term it is worse than the slow term alone, seven against nine, so the two interact.

## Discussion

One of four helped, and it helped for the wrong reason. The multi-day term was added to raise
the week-to-week variation in total daily insulin towards a real 7.3%, and it lowers it, from
5.3% to 3.8%, taking that statistic out of range. The rationale is refuted and the mechanism
is kept on the evidence of what it does, which is a different claim.

Activity failing is the more interesting negative. A regular daily perturbation of glucose is
not what the predictability signatures were missing, and what did move them acts on a horizon
of days rather than of hours. That was the opposite of where the reasoning pointed.

Two findings arrived that none of the four were built for. Real meals peak at 135 minutes
against this model's 90, and it is not absorption: slowing every rate threefold moves the peak
ten minutes and then saturates, while dragging the rise per gram away from real. It is not
bolus timing either, measured across 39,619 real meals from 42 users, where the median bolus
lands on the meal, 75.1% within two minutes of it, 7.2% more than a quarter of an hour late
and 1.2% never bolused. What is left is the size of the dose rather than its timing.

And a separate reading of the same signatures against 101 individual real users rather than
against four cohort medians puts the predictability cluster inside the real tenth-to-ninetieth
percentile on all three. That does not make this study's result wrong, but it changes what the
result was needed for. See [CAPABILITY.md](../CAPABILITY.md).

Two defects in the first regression were fixed before the numbers above were read. The
baseline inherited the absorption setting from a module default that had just been calibrated,
so the control carried the mechanism it was controlling for and the two columns came out
identical. And the activity schedule put seventy per cent of sessions in a two-hour evening
window, which made every subject dip at the same hour daily and raised the diurnal amplitude
from 51.0 to 58.8 mg/dL.

One limitation. The subject count for the final table was lost in capture; the previous
five-arm run had nine of twenty completing every arm and this has six arms, so it is at most
that. The paired intervals account for the sample size but the in-range counts rest on a small
subset.

## What changed

`SLOW_CV` is 0.15 and on. `MEAL_ABSORPTION_CV` is calibrated at 0.9 and available.
`MEAL_ABSORPTION_SCALE` is 1.0 with the reason recorded. The activity layer exists, is off,
and carries its own failure in its docstring.
