# Which layers change the person and which only change the run

## Question

`FIDELITY.md` reports where the fidelity signatures land as each layer is added, and that
table changes the driving algorithm partway up: its first three rungs run open loop and its
last three under the built-in correction loop. So a reader cannot tell whether the sensor and
site layers move those statistics because of what they do to the simulated person or because
of what a loop does in response.

A layer that moves a signature only when an algorithm is reacting is an interaction, and this
package should not describe it as physiology.

## Method

The same ladder walked four times, once per driver, with the layers held constant inside each
walk. The drivers are open-loop therapy, the built-in correction loop, Boost compiled from the
AndroidAPS tree and driven through a JVM, and oref0 SMB driven through node. The last two know
nothing about this package, so agreement between them is not something it can arrange.

Twenty adult subjects, 28 days, seed 0. Per-subject signature values are kept so that every
comparison is paired on the same virtual people, and each rung transition is paired over the
subjects who completed the two rungs it spans.

A movement counts when its paired confidence interval excludes zero. It is carried by the
person when that holds under all four drivers and points the same way each time.

## Results

Twelve of forty-seven movements survive.

| Layer | Carried by the person |
|---|---|
| behaviour | hypoglycaemia recovery, rebound, rise tail, outcome spread, jitter |
| sensor | compression lows, jitter, rise tail |
| site | glucose variability, autocorrelation at thirty and sixty minutes |
| physiology | diurnal amplitude |

The behaviour layer carries the largest single effect: hypoglycaemia recovery shortens by 38.6
minutes under every driver, from 99.4 into the real range. Rescue carbohydrate is a decision
the person makes rather than anything an algorithm sees, which is why no controller changes
the answer.

The sensor layer takes compression lows from nothing to 3.47 per thirty days and jitter from
quantisation to 3.15 mg/dL above it, both under every driver. Nothing a controller does can
alter how a sensor reports, so this is what the design predicts and it works as a check on the
method rather than as news.

Signatures inside the published band: two of eleven for the stock model, seven with four
layers, six with five.

## Discussion

The first walk of this ladder produced a different and weaker answer, and both defects that
caused it are worth recording because both would have been invisible in the output.

It added physiology before behaviour, following the existing table's order. That adds a
mechanism before its antidote: insulin sensitivity that moves through the day and week to
week, with nobody yet able to treat a low, produces subjects who go low and are never treated.
Half the cohort died at that rung under two of the four drivers and only four of ten subjects
completed every arm, so each rung above it described a different and smaller population.
Reordering to put behaviour first took that to thirteen of twenty with no rung losing more
than three.

It also scored agreement with a spread-versus-mean heuristic applied equally to movements of
46 percentage points and of 0.003, so most of its disagreements were noise being tested for
consistency. Replacing that with a paired confidence interval per movement is what turned nine
survivors into twelve.

The physiology layer's result reversed between the two walks. At ten subjects its diurnal
movement appeared under two drivers of four and could not be claimed; at twenty it appears
under all four at 10.0 mg/dL. The earlier negative was a question of power rather than a
finding about the layer, and it was reported as a finding.

One structural limitation. The test demands significance under each driver separately, which
is strict, and the sample is twenty subjects. A mechanism with a real but modest effect will
fail it. That is the intended bias: the cost of wrongly claiming a layer is physiology is
higher here than the cost of missing one.

## What changed

`examples/layer_ladder_by_controller.py` produces the table and
[LADDER.md](../LADDER.md) carries it. `FIDELITY.md` now points at it and states which of its
own choices it supersedes.
