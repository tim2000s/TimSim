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
same quantity rather than measurements of a 28-day window. The Commons window is one month
taken from the middle of a record whose median length is 315 days, so a user contributes a
month chosen by position rather than by anything clinical.

Say which set of Commons users a figure covers, because there are three and they are nested.
240 user directories are exported, 131 carry a readable glucose series, 103 hold a middle
28-day window with at least 70 per cent of the readings a five-minute sensor would produce, and
71 of those also hold pump records across that window, which a reconstructed daily requirement
needs. Figures quoted here as 221 users predate the count and match no set.

## Titrate the settings before benchmarking anything

A subject's correction factor computed from its own model is not what a real person carries. The
real figure is 40.0 mg/dL per unit, the median of the recorded pump settings of the 112 DCLP3
closed-loop participants with an inter-quartile range of 30.0 to 50.0, and the generated
population's median sits well below it. Handing oref0 SMB the derived value doubles its time
below 70 mg/dL, a paired difference of 2.36 points with an interval of 0.79, and doubles the
rescue carbohydrate the simulated person needs. Titration closes about half of the gap rather
than all of it: across the titrated cohort the correction factor ends at a median of 23.6 mg/dL
per unit.

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
| n | 112 participants, 67 in the calibration half | 103 users, 71 with pump records |
| System | Control-IQ | oref-family loops |
| Time in range, % | 71.29 | 79.60 |
| Time below 70, % | 1.36 | 2.74 |
| Time below 54, % | 0.20 | 0.39 |
| Time above 180, % | 26.87 | 15.05 |
| Mean, mg/dL | 155.45 | 134.72 |
| CV, % | 33.37 | 33.45 |

Both columns are medians across people, each person's outcomes computed from their own
readings first. The trial column is the calibration half of the closed-loop arm, so a figure
reported against it can be checked against the 45 held-out participants, who sit at 73.76 time
in range and 154.67 mg/dL. The Commons column is the 71 users carrying pump records as well as
glucose, which is the set a cohort can be matched to; across all 103 it reads 79.90, 2.87, 0.43,
15.05, 134.16 and 33.76, so the restriction does not move it.

Compare an arm against the population running the algorithm it is testing. Against DCLP3 an
untuned oref arm looks too low and too flat; against the Commons its mean glucose and time in
range are ordinary and what is wrong is its hypoglycaemia. Both readings are arithmetically
correct and they support different work.

Also distinguish a band of cohort medians from a distribution of individuals. `docs/CAPABILITY.md`
sets out why: a band built from four cohort medians is narrow because averaging removes the
spread between people, and scoring against it once selected a rescue carbohydrate helping of 35 g
where real people give 15.

## Every subject needs its own random stream

`simulate` starts one generator per run and it supplies the meal schedule, the seed the sensor
noise model is started from, the infusion set failure times and the day-to-day sensitivity
movement. Seeding it from the integer alone gave every subject at that seed the identical
stream: three different subjects at seed 11 ate at minutes 367.8, 701.7, 1073.5, 1373.8, 1883.1
and 2229.2 and wore one sensor noise realisation, so a cohort was one random month applied to N
bodies. `subject_seed(name, seed)` folds the name in through sha256, which reproduces across
processes where Python's salted `hash` does not, and `simulate_cohort` no longer offsets by
position so a subject's month does not depend on where it sits in the list.

Paired within-subject comparisons were unaffected, since both arms saw the same stream. What
was affected is any statement about spread across subjects. Note that the fix did not widen the
one spread it was expected to: sensor jitter across ten subjects spans 5.588 to 5.692 mg/dL on
the shared stream and 5.614 to 5.683 with the name folded in, against a real 3.8 to 12.4, so
that uniformity belongs to the sensor model.

`population/generate.py` still uses `seed + hash(klass) % 10_000`, which is the salted hash, so
the generated population is not reproducible across processes at a fixed seed. Changing it
regenerates every subject and invalidates the measured figures in these documents, so it is
recorded here rather than repaired.

## A missing input must fail, not default

The bridge to the compiled Boost algorithm read three of its inputs off the cycle with
`getattr(cycle, name, default)`, and none of the three names was a field on that object. Every
run sent the defaults and nothing reported it. The consequences were large and none of them
looked like an error: the cumulative rise arrived as zero, which pins the algorithm's velocity
factor to its floor of 0.40 and removed 60.0 per cent of the raw dose on every cycle of every
subject, and both dose caps arrived as literals, so an experiment built to vary them varied
nothing the algorithm saw and its 0.5 U/day movement in the wrong direction came from a
side effect elsewhere.

Marshal inputs by name against the receiving contract and let a missing one raise. A default
that is plausible is worse than a crash, because the run completes and the number is wrong by an
amount nobody can see. The row builder already length-checks itself against the compiled
field list, which catches a field added on the far side and cannot catch a field silently
defaulted on this one.

Related: a controller's insulin ledger must record what was delivered rather than what was
decided. The bridge inherited the ported adapter's decision path, which appends its own dose,
then discarded that dose and sent the compiled one, so the algorithm read insulin on board that
nothing had given it: 56.08 U a day against 33.45 actually delivered, feeding its eventual
glucose, its minimum guard and the headroom clamping its request.

## Report why runs ended, not just how many

A completion count averages a hypoglycaemia failure with a hyperglycaemia one, and on this
bench both happen: under oref0 SMB on the layered bench five of seven terminations were
hyperglycaemic, which is the opposite of what a completion count invites a reader to assume.

`Result.termination` carries the account, populated where the run ends rather than
reconstructed by a caller: direction, day, final and extreme glucose, insulin over the last
hour and six hours, rescue helpings in the last six hours, and whether the infusion site was
still failing. `analysis/cohort.py::format_failure_report` prints it per arm, and every
comparison should print it beside the outcome table.

## The infusion site's detection is coupled to the controller

The person notices a failed set only by being above 230 mg/dL for 90 waking minutes, so how
long a failure lasts depends on how high the controller lets them get. A controller that
partially compensates keeps the reading under that threshold, the person never suspects
anything, and the set runs to its scheduled replacement. Measured across three subjects, the
built-in loop's failures ran a median 8.6 hours and a maximum of 24.0; oref0 SMB's ran a median
8.1 and a maximum of 44.6, and one failure at 65 per cent absorption lasted 44.6 hours while the
reading peaked at only 311 mg/dL.

The consequence is that the challenge is not held constant across arms, and a better controller
earns a longer failure and more insulin buried in tissue that is not absorbing it. This is
recorded as a design decision in `therapy/site.py` rather than repaired, because the feedback is
faithful to how people actually find a failed set. What bounds the exposure is the scheduled
replacement, which is why the interval is now a parameter: pass `set_life_days` to `simulate`,
a scalar for a fixed interval or a pair for a range, and state the value any comparison assumed.
The default remains 2.5 to 3.5 days.

## Hold everything else, and pair per subject

An arm that loses different subjects is a different population, so pair over the subjects
completing every arm and report a paired difference with an interval.
`analysis/cohort.py::paired_subjects` returns that set and raises rather than producing a
comparison from partial overlap, since summarising each arm over its own survivors compares
different people and the bias always runs favourable. Report the completion count
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

## Report the way the trials report

Time in range, time below range and time above range are given as a median, a mean and the range
of values across subjects. All three, and not one of them.

The reason is like-for-like. DCLP3 and CLOSE-IT report time in range as a mean with a spread, and
the CLOSE-IT reference held here is a mean and a standard deviation because that is all its paper
published. Quoting a simulated median against a published mean is a comparison computed
differently on the two sides, which is the failure this document exists to prevent.

The median stays as well, and deliberately. A third of subjects sit at zero on time below 54
mg/dL, so the mean and the median disagree there by about a factor of two and a symmetric
interval around the mean describes neither the centre nor the tails. The median is the robust
statistic and the mean is what the paper being compared against printed, so both are carried and
the table says which the real side is quoted on.

The range across subjects is a third thing and is not the bootstrap interval on the median. The
interval says whether the centre differs from the trial. The range says how varied the simulated
population is, and a population can sit on the real median while being far narrower than the real
cohort, which makes a bench look more decisive than it is.

## What a result has to carry

A benchmark figure from this package is not interpretable without its settings provenance, its
target, its reference population, and its completion count. Across four configurations of one
unmodified algorithm, time below 70 mg/dL spans 2.75 to 7.61 per cent, while the difference
between the two algorithms this package compares on one fixed configuration is 3.37 points with
an interval of 1.30. The configuration moves the safety measure further than the algorithms do,
so an absolute outcome quoted on its own says more about the harness than about the system.
