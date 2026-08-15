# Audit of the ten studies, August 2026

Every study in the Research-Papers repository under `TimSim/` checked against the
measurements now in `docs/measurements/`, after the population was reseeded and the real-data
anchors were remeasured. Three questions were asked of each: does anything it asserts
contradict a current measurement, are its numbers still reproducible, and does its conclusion
survive.

Two things happened between the studies being written and this audit, and they affect
different studies differently.

The population was reseeded. `generate()` had drawn its per-class stream from Python's salted
`hash`, so it produced a different hundred subjects in every process and the population every
study was measured on could not be rebuilt. Fixing that regenerated all hundred subjects.
Every simulated number in every study was therefore measured on subjects that no longer exist.
The replacement population is close in aggregate, at a correction factor median of 26.9 against
29.8 and a daily requirement of 35.7 against 35.1, so cohort-level conclusions are unlikely to
turn on it, but no per-subject figure can be reproduced and none should be quoted as though it
could.

The real-data anchors moved. The carbohydrate response, the meal peak, the DCLP3 correction
factor and the Commons user count were all remeasured and all changed, three of them because
the original measurement ran on a tenth of the sample.

## Verdicts

| # | Study | Verdict |
|---|---|---|
| 00 | The simulator | Framing only; no measurement to invalidate |
| 01 | Driving shipped algorithms | Numbers void, conclusion stands |
| 02 | The layer ladder under four drivers | Numbers void, conclusion stands, worth rerunning |
| 03 | A statistic that could not see | Numbers void, conclusion stands |
| 04 | Sensitivity detection | Numbers void, conclusion stands, magnitudes now smaller |
| 05 | Where a low comes from | Numbers void, conclusion untested against current runs |
| 06 | Four mechanisms for realism | **A premise is refuted and a conclusion with it** |
| 07 | A gap that was not there | Stands; measures a different quantity from the meal work |
| 08 | No floor under a falling glucose | **Holds for the bare model, reverses on the layered one** |
| 09 | Capability | Numbers void, needs the signatures recomputing |

## 06, four mechanisms: the refused mechanism was refused for a refuted reason

The study declines to implement an arrest of a falling glucose, twice, on this ground:

> The model separately produces four times the endogenous glucose of long-standing type 1
> diabetes during a low, so additional glucose production is not indicated.

That comparison reads the model's glucose production during spontaneous lows under a closed
loop and sets it beside Rickels et al., whose figure comes from a stepped hyperinsulinaemic
clamp. Production in this model is a linear function of glucose and of insulin in a remote
compartment, and remote insulin is 235 in the first state against 441 in the second, so the two
numbers are not measurements of the same thing. Reproducing the clamp protocol in silico gives
0.14 mg/kg/min at a 55 mg/dL plateau and 0.01 at 45, against 0.59 ± 0.12 in twelve people with
long-standing type 1 diabetes and no glucagon response. The model produces nothing where people
who have already lost that arm still produce something.

So the premise is backwards and the conclusion drawn from it does not follow. A hepatic defence
of glucose production has since been implemented and is on by default, calibrated on that clamp,
and `docs/PADOVA_LIMITS.md` and the README both carry it. The study needs rewriting rather than
annotating, because the refusal is one of its four results.

Reproduce the corrected measurement with `examples/hypoglycaemic_clamp.py` and
`examples/production_during_a_low.py`.

## 08, no floor: the direction of failure reverses once a person is present

The study reports that fifteen of forty subjects failed to complete 28 days under an ordinary
correction loop and that fourteen of the fifteen ended between 10 and 13 mg/dL. That is
reproduced here on the bare model and it does not survive the layers.

Across the 380 runs of `examples/bench_matrix.py`, 62 failed to complete, 14 of them
hypoglycaemic and 48 hyperglycaemic. Split by bench:

| Bench | Runs | Failed | Hyperglycaemic | Hypoglycaemic |
|---|---|---|---|---|
| bare S2008 | 95 | 6 | 0 | 6 |
| layered, all meals announced | 95 | 25 | 20 | 5 |
| layered, some announced | 95 | 17 | 16 | 1 |
| layered, none announced | 95 | 14 | 12 | 2 |

On the bare patient every failure is a low, which is the study's finding. On the layered bench
the failures invert, because the person eats when they go low and the missing floor is supplied
behaviourally rather than physiologically. What replaces it is hyperglycaemic failure, which
the layers also cause: an unannounced meal and a failed infusion set both push upward and
nothing in the person opposes that.

The overall rate falls too, from 37.5 per cent of runs to 16.3, and the lowest underlying
glucose across all runs has a median of 38.8 mg/dL and a tenth percentile of 20.1 against the
study's median of 20 and tenth percentile of 10. Titrated settings account for part of that,
since titration weakens a subject's settings until its own record clears the consensus
hypoglycaemia floors.

The study's consequence needs restating rather than withdrawing. Every cohort statistic is
still conditioned on survival. What changes is what survival selects on: on the bare model it
selects on hypoglycaemia, which is the variable most safety statistics measure, and on the
layered bench it selects on hyperglycaemia, which biases time above range and mean glucose
downward instead. Reporting the direction of every termination is what makes the two
distinguishable, which is why `Result.termination` carries it.

## 07, meal peak timing: unaffected

Study 07 measures how long glucose rises after a meal under a closed loop, clocked from the
trough, and finds real meals rising for 112 minutes against a simulated 100. The meal work in
`docs/PADOVA_LIMITS.md` measures the peak of an uncovered meal on basal alone, and gets 225
minutes simulated against 177 to 248 real. Those are different quantities under different
conditions, and neither bears on the other. Study 07's structural finding, that the
carbohydrate entry is the wrong clock because people pre-bolus, stands and is what the two
measurements have in common: both avoid the entry clock.

Its real-side counts are worth rerunning. It cites 26 and 42 users where the export yields 128
with a readable glucose series, so it was probably measured before the file glob was widened.
The conclusion does not depend on the count.

## What has to be rerun before any of these is quoted again

The signatures in study 09 and the ladder in study 02 are the two that carry the most weight
elsewhere, and both are cohort-level measurements on the old population. Neither is likely to
reverse, and neither is currently reproducible.
