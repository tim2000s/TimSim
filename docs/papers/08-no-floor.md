# The model has no floor under a falling glucose

## Question

Runs in this package sometimes end early, and `Result.completed` records it. The rate had
never been examined: eight of twelve subjects completing 28 days under the default controller
was noticed while checking something else, and it is high enough that every cohort statistic
in the repository is computed over survivors.

Why do runs fail, and does it matter beyond the arithmetic?

## Method

`simglucose/simulation/env.py` ends a run when `BG < 10 or BG > 600`, where `BG` is
`patient.observation.Gsub`, the interstitial glucose without sensor error, which this package
exposes as `Result.bg`. So a non-completion is glucose leaving the range in which the model is
defined.

Forty subjects were run for 28 days under the built-in correction loop, recording for each the
final value, the lowest reached on both signals, and the day the run ended. The same
statistics were computed on 80 real users of the OpenAPS Data Commons export over matched
28-day windows.

Comparisons against real data are made on the sensor reading, because that is what real
records contain. The underlying glucose is reported separately and is not compared with
anything real, since no real record contains it.

## Results

Twenty-five of forty completed. Fourteen of the fifteen failures ended low, at 10 to 13 mg/dL,
between day 7.7 and day 23.9. One ended high, at 592 mg/dL on day 14.9.

On the sensor reading, which is the like-for-like comparison:

| | Simulated | Real |
|---|---|---|
| Lowest reading, median | 39 mg/dL | 39 mg/dL |
| Lowest reading, p10 to p90 | 39 to 39 | 5 to 46 |
| Readings at or below 40 mg/dL | 0.44% | 0.07% |

The simulated sensor floors at 39, as real devices do, so the lowest reading says nothing on
either side. The frequency does: the simulated population sits at or below 40 mg/dL six times
as often as the real one.

Underneath that floor the underlying glucose has none. Across the forty subjects the lowest
value reached has a median of 20 mg/dL and a tenth percentile of 10.

## Discussion

Nothing in the model arrests a falling glucose. UVA/Padova S2008 contains no
counterregulation, and this repository declined to add it on the grounds that endogenous
glucose production during a low is already four times that of long-standing type 1 diabetes.
That argument is about the level of production and this is about whether a fall is arrested,
which are different claims. Real physiology flattens a fall in the forties through glucagon
and adrenaline. Here the only things that stop one are the loop withdrawing insulin and the
person eating, and when those are outmatched glucose descends to zero.

Three consequences follow.

The tail is not physiological even though the distribution is. Time below 70 sits at two to
four per cent and time below 54 near 1.5%, which are ordinary figures, and the extreme tail
runs to zero. A statistic computed over the body of the distribution will not show this.

Every cohort figure in the repository is conditioned on survival, and survival here is
selection on precisely the variable most of those figures measure. Hypoglycaemia statistics
are computed over the subjects that did not fall through the floor.

And it is the answer to a question this collection had left open. Untreated lows in this model
take 80 minutes to recover against a real 59.4 and rebound 1.83 times as often, with the same
factor in treated lows, and [05-rescue-carbohydrate](05-rescue-carbohydrate.md) concluded that
the cause was how a low ends. This is how: they do not end. They are ended by carbohydrate
arriving, by the loop, or by the run terminating.

## What this does not establish

That the survivors' minima are wrong. A true glucose in the twenties happens in real type 1
diabetes, particularly overnight, and people survive it. The unambiguous part is the fifteen
subjects reaching 10 to 13 mg/dL and the sixfold excess of readings at or below 40.

That real users never record very low values. Their tenth percentile of lowest readings is 5
mg/dL, which is a sensor artefact rather than physiology, since a person at 5 mg/dL is not
wearing a CGM. It means the real tail cannot be cleanly attributed and should not be presented
as a physiological floor.

That S2013's risk term is the fix. It deepens lows rather than arresting them. The half that
would arrest one is a glucagon compartment whose eight parameters the papers do not publish,
so a floor would have to be built and justified on its own terms.

## What changed

Nothing yet. The finding is recorded and the fix is not obvious: adding a floor means adding
physiology this package has no published parameters for, and the alternative of leaving it
means every hypoglycaemia claim carries a survivorship caveat.
