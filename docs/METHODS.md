# Running a simulation so the result means something

What this package has learned about producing a benchmark figure that survives checking. Every
rule below is here because breaking it produced a wrong answer that looked right, and the
measurement that caught it is cited.

## Everything is a time series

A run produces one reading every five minutes, 8,064 over 28 days, held in `Result.cgm` and
`Result.bg` with `Result.minutes` carrying the clock. Every outcome is the share of that
subject's own readings meeting a condition, computed by `therapy/titrate.py::consensus_report`
or by `analysis/signatures.py`.

The real references are computed the same way and at the same level. DCLP3 concatenates each
participant's wear segments and computes that participant's outcomes from the result; the
OpenAPS Data Commons takes each user's middle 28-day window and computes that user's outcomes
from the readings inside it. Only after a per-person figure exists is anything summarised across
people.

Nothing here is an average of averages, and nothing is computed from a summary statistic that
was itself computed from a summary. The reason to insist on it is that the two operations differ
whenever people contribute different numbers of readings, which they always do.

Two properties of the real windows are worth knowing when quoting them. DCLP3 participants
contribute a median of 166 days of wear each, so the trial figures are better estimates of the
same quantity rather than measurements of a 28-day window. Among 221 Commons users, 64 carry
more than 1.2 times the reading count a 28-day window at five minutes implies and 18 carry more
than twice it, so a share of readings weights their densely sampled stretches more heavily than
a share of time would.

## Titrate the settings before benchmarking anything

A subject's correction factor computed from its own model is not what a real person carries. The
median here is 15.1 mg/dL per unit against the 35 DCLP3 participants ran, and handing oref0 SMB
the derived value doubles its time below 70 mg/dL, a paired difference of 2.36 points with an
interval of 0.79, and doubles the rescue carbohydrate the simulated person needs.

Run `examples/titrate_cohort.py` first. It weakens each subject until that subject's own record
clears the consensus hypoglycaemia limits (Battelino et al. 2019: below 54 mg/dL under 1 per
cent, below 70 under 4) and no further, since settings looser than hypoglycaemia requires cost
time in range. `therapy/titrate.py::profile_for` raises rather than falling back, so a benchmark
cannot silently use untitrated settings.

Three rules the procedure follows, each of which cost something to learn:

Titration runs under the built-in `trend` loop. Under the algorithm being benchmarked it is
circular, since a controller that provokes hypoglycaemia would be answered by the bench weakening
its subjects' settings. Under the open-loop arm it returns its own starting point, because that
arm spends 0.25 per cent of time below 70 mg/dL against a real 4.07 and never exercises the
settings; 13 of 15 subjects clear both limits at the physiological value there.

Only hypoglycaemia gates. Time in range, time above 250 mg/dL and variability are computed and
reported, because a subject can miss any of them for reasons no settings change reaches.

A subject that never clears the limits is recorded as untitrated and excluded, not assigned the
loosest available. Assigning it settings would present a failure of the model as a settings
choice.

## Match the target to the comparison

Every arm in this package aims at 100 to 120 mg/dL. Control-IQ, which DCLP3 ran, holds 112.5 to
160. The target is the largest configuration effect measured: raising it alone, with algorithm,
subjects and settings unchanged, removes 4.82 ± 1.34 points of time below 70 mg/dL on the bare
patient and 2.24 ± 0.85 on the layered bench, and moves mean glucose by 17.97 ± 0.85 and 11.17 ±
4.44 mg/dL.

On the bare patient that takes time below 70 from 7.61 to 2.75 per cent, which is a different
verdict rather than a different number: the first is above the ninetieth percentile of real users
of that algorithm and the second is at their median.

Matching a target makes the targets comparable and not the algorithms. oref0 SMB holding 112.5
to 160 is still oref0 SMB, so read that configuration as an ablation of one input rather than as
a reproduction of another system's trial.

## Choose the reference population deliberately

Two are available and they disagree by more than either differs from the simulation:

| | DCLP3 closed loop | OpenAPS Data Commons |
|---|---|---|
| n | 112 participants | 221 users |
| System | Control-IQ | oref-family loops |
| Time in range, % | 71.5 | 82.0 |
| Time below 70, % | 1.28 | 2.99 |
| Time below 54, % | 0.16 | 0.42 |
| Mean, mg/dL | 154.7 | 132.5 |
| CV, % | 32.6 | 33.8 |

Compare an arm against the population running the algorithm it is testing. Against DCLP3 an
untuned oref arm looks too low and too flat; against the Commons its mean glucose and time in
range are ordinary and what is wrong is its hypoglycaemia. Both readings are arithmetically
correct and they support different work.

Also distinguish a band of cohort medians from a distribution of individuals. `docs/CAPABILITY.md`
sets out why: a band built from four cohort medians is narrow because averaging removes the
spread between people, and scoring against it once selected a rescue carbohydrate helping of 35 g
where real people give 15.

## Hold everything else, and pair per subject

An arm that loses different subjects is a different population, so pair over the subjects
completing every arm and report a paired difference with an interval. Report the completion count
beside every figure: runs end when glucose leaves the range the model is defined over, the runs
that fail are the ones that went lowest, and every cohort figure is therefore conditioned on
survival.

Match the cohort to the reference rather than taking whichever class is convenient.
`population/cohort.py::matched` samples by age in the reference's own proportions;
`timsim/validation/dclp3.py::ages` supplies the trial's. The 34 adults have a median age of 49
against the trial's 29 with no adolescents at all, and using them unmatched moves everything age
moves.

Comparisons against real data go on `Result.cgm`, not `Result.bg`. The sensor error has a
standard deviation near 12 mg/dL and fragments threshold crossings rather than blurring them:
the same runs give 100 excursions below 54 mg/dL on `bg` and 380 on `cgm`.
`validation/compare.py` refuses the other pairing.

## Require a statistic to see what it measures

Before trusting a statistic, switch off the mechanism it claims to detect and require the paired
difference to exclude zero. One of the eleven fidelity signatures failed this: it read the
built-in controller's own learned correction factor rather than the simulated person, was
undefined under every other driver, and reported 5.77 per cent with the mechanism removed
against 8.69 with it present.

For a physiological quantity, reproduce the protocol its human reference was measured under
rather than reading the quantity off an ordinary run. Endogenous glucose production read during
spontaneous lows gives 1.28 mg/kg/min and at a clamped 55 mg/dL plateau gives 0.14 on the same
subjects, because the insulin differs; `examples/hypoglycaemic_clamp.py` exists for this.

## What a result has to carry

A benchmark figure from this package is not interpretable without its settings provenance, its
target, its reference population, and its completion count. Across four configurations of one
unmodified algorithm, time below 70 mg/dL spans 2.75 to 7.61 per cent, while the difference
between the two algorithms this package compares on one fixed configuration is 3.37 points with
an interval of 1.30. The configuration moves the safety measure further than the algorithms do,
so an absolute outcome quoted on its own says more about the harness than about the system.
