# How do you test whether a simulator is telling the truth?

Not with one number. A simulator can be trustworthy for one question and useless for the
next, so the question is never "is it valid" but "valid for what". This document sets out
six levels of check, what each one licenses, and what TimSim currently scores on each.

Run them with:

```
python -m timsim.validation.run --fast     # levels 1, 2 and 6, a few minutes
python -m timsim.validation.run            # everything, about 90 minutes
```

## The six levels

| Level | Question | What it licenses |
|---|---|---|
| 1 | Does the code do what it claims? | nothing on its own; failure invalidates everything above it |
| 2 | Does it get direction and rough magnitude right? | reasoning about mechanism |
| 3 | Does its output look like real data? | that a trace is not obviously artificial |
| 4 | Does it reproduce a result established elsewhere? | that its response to an intervention is roughly right |
| 5 | How large a difference can it resolve? | reading an A/B result |
| 6 | Do conclusions survive the arbitrary choices? | that a result is not an artefact of a seed |

Most published simulator validation stops at level 3, and level 3 is the weakest of the
six taken alone. Matching the marginal statistics of real data says nothing about whether
the response to an intervention is right, and the response to an intervention is the whole
reason to run a simulator. Levels 4 and 5 are what a controller comparison actually rests
on, and level 5 is the one most often skipped: without it an A/B result has no scale to be
read against.

## Level 1: internal consistency

Does the code do what it claims?

- **The steady-state closure reproduces every published subject.** The balance equations in
  `population/derive.py` are used to complete every generated subject. Applied to the
  published subjects they must return those subjects exactly. Worst relative residual
  across all thirty: 5×10⁻¹². If this fails nothing else is trustworthy.
- **A quiet subject holds its fasting glucose.** On its own basal with no meals, blood
  glucose must not move. Measured excursion over four days: 0.02 mg/dL.

  This check was wrong twice before it was right, and both mistakes are worth knowing.
  Comparing the first reading with the last aliases an oscillation: it passed at two days
  and four and failed at one. Measuring the excursion on the sensor reading measures the
  sensor, because the Dexcom noise model is strongly autocorrelated and wanders about 40
  mg/dL either side over two days while the blood glucose underneath does not move at all.
  Getting it right also exposed a real defect: every run opened with a zero-insulin step,
  inherited from simglucose's own examples, which kicked each subject off the steady state
  its parameters were closed at. Runs now open at the subject's own basal.
- **The sensor layer does not feed back into the body.** The same seed with and without the
  sensor layer must leave the underlying blood glucose bit-identical. It does. Compression
  lows are a false reading, not a real fall, and a bug here would silently make them real.
- **The same seed reproduces the same run,** and different seeds do not. In the test suite.

Status: passing.

## Level 2: face validity

Does it get the direction and rough magnitude right?

- **The published cohort obeys the clinical dosing rules.** One unit of insulin moves the
  ten published adults by 1.10 times their stated correction factor; 50 g of unbolused
  carbohydrate raises them by 1.19 times grams over ratio times factor; a bolused meal
  peaks at a median of 75 minutes. The model and the rules real settings are built on
  describe the same person. This is the independent version of the two rule checks, because
  the published subjects' settings were not derived from the model.
- **Generated subjects obey the same rules.** On them this is a consistency check rather
  than an independent test, because their settings are measured from their own model. It
  still earns its place: it catches settings measured under one steady state being applied
  under another.
- **More insulin lowers glucose, monotonically.** 191, 178, 164, 147, 128 mg/dL at 0.7 to
  1.3 times the dose. A simulator that is not monotone in its most important input cannot
  rank two controllers whatever its distributional fidelity looks like.
- **Extra insulin is met with extra carbohydrate.** With the behaviour layer on, the same
  ladder gives rescue carbohydrate of 0, 0, 233, 323, 575 g and mean glucose stops falling
  cleanly. That is the person defending against lows, not a modelling error, and it names a
  trap: a more aggressive controller here may show no improvement in mean glucose because
  the simulated person eats the difference. It appears in carbohydrate and time below range
  instead.

Status: passing.

This level found a real defect. The first version of the population generator drew
carbohydrate ratio and correction factor from the published cohort's distribution
conditioned on body weight and basal rate. The published subjects came out at 1.10 times
their correction factor and the generated ones at 0.63, meaning every generated subject was
being dosed on somebody else's settings on every cycle of every run. The settings are now
measured from each subject's own model, and fixing it improved the level 3 table by three
statistics. Nothing at level 3 would have found it, because a table of statistics does not
say which mechanism is wrong.

## Level 3: distributional fidelity

Does its output look like real data?

Eleven statistics computed identically on simulator output and on the traces of 192 real
closed-loop users. `docs/FIDELITY.md` has the full table and the layer-by-layer
attribution. Summary: one of eleven inside the real range for the bare subjects, seven of
eleven with all four layers, plus two that miss by a fraction of a unit.

The ones still outside are hypoglycaemia rebound, sensitivity drift, and, marginally, the
spread of outcomes from a stuck high. Each is discussed there; the last is the one that
matters and is covered again below.

Status: seven of eleven, with the misses named rather than tuned away.

Worth noting what moved this table most. Fixing the therapy settings, a level 2 finding,
improved it by three statistics and moved the spread of outcomes from 21.0 to 25.5 mg/dL.
Nothing aimed at level 3 achieved anything comparable.

## Level 4: known answer

Does it reproduce a result established elsewhere?

The best-established intervention in this field is closing the loop. Published hybrid
closed-loop trials against pump therapy report time-in-range improvements in the region of
ten percentage points. So the simulator is asked the same question: the same subjects, the
same seed, the loop layer on and off.

Measured on 20 adults over 14 days, paired: **+14.7 percentage points of time in range
[9.3 to 18.4]**, from 67.9% to 85.1%. That is somewhat larger than the ten points trials
report, which is what you would expect from a comparison where everything except the loop
is held identical and the person is perfectly adherent, but it is the right effect in the
right direction at the right order of magnitude.

Worth noting alongside it: time below 70 is essentially unchanged, 2.4% to 2.2%, and rescue
carbohydrate falls slightly. The loop trims highs without buying them with lows, which is
also the direction real trials report.

This is a weak test in one respect worth admitting: the loop being switched off is a
baseline of this package's own construction, not a real pump-therapy arm. It bounds gross
error rather than confirming accuracy.

## Level 5: discriminating power

How large a difference can it resolve?

**The A/A test.** Run the same controller twice, same subjects, different seed. Whatever
difference that produces is the noise floor, and no A/B on the same design can be believed
below it. This is the check most often skipped, and skipping it is how a simulator comes
to report a two-point improvement that is indistinguishable from running the same thing
twice.

Measured on 20 adults over 14 days: **+0.21 percentage points [-2.28 to +1.44]**. The
interval spans zero, so the null is null, and the paired standard deviation is 3.73
percentage points.

**The minimum detectable difference.** Computed from the paired spread the A/A test
measures, so it is empirical rather than assumed:

```python
from timsim.validation import minimum_detectable_difference
print(minimum_detectable_difference(null_a, null_b, n_subjects=100))
```

From that paired spread, at 80% power and a 5% two-sided level:

| Subjects | Smallest resolvable difference in time in range |
|---|---|
| 20 | 2.34 percentage points |
| 34 (all adults) | 1.79 |
| 100 (whole population) | 1.04 |

Read this before believing any comparison. A difference smaller than the figure for your
design is not evidence of anything, however tidy the plot looks. It is also the argument
for the larger population: thirty subjects would resolve about 1.9 points where a hundred
resolve about 1.0.

Raw numbers in `docs/power.json`.

Two design points follow from this and are worth stating separately, because they cost
nothing and buy most of the available power.

**Pair.** Use the same subjects and the same seed in both arms. Between-subject variation
is far larger than the effect of any sensible controller change, and an unpaired
comparison throws that away.

**Do not judge on mean glucose alone.** Level 2 showed why: the simulated person defends
against lows with carbohydrate, so a more aggressive controller can look identical on the
mean while differing substantially in carbohydrate consumed and time below range.

## Level 6: robustness

Do conclusions survive the arbitrary choices?

- **Two population draws describe the same kind of people.** Seeds 2026 and 7 give median
  carbohydrate ratios of 10.8 and 8.9, within 18%. This check failed before the settings
  were measured rather than sampled, at 22.1 against 13.5.
- **A conclusion does not depend on an unfitted behaviour parameter.** The announcement
  rate was chosen from the literature, not fitted. Moving it from 65% to 95% moves mean
  glucose from 134 to 130 mg/dL, in the right direction and by a bounded amount.
- **Regenerate before believing anything.** `python -m timsim.population.build --n 100
  --seed 7`. If a result does not survive a different draw of the population, it was never
  a result.

Status: passing.

## What none of this establishes

No check here licenses using TimSim to price a dosing change for a particular person.

The reason is measured and specific. The spread of where glucose lands thirty minutes after
a stuck high is 25.5 mg/dL in the simulator against 26.5 to 33.5 in real data. That is much
closer than it was, having been 21.0 before the therapy settings were corrected, but it is
still on the confident side, and that spread is exactly the quantity a dosing decision is
betting on. A decision rule tuned against it is being tuned against a slightly more
predictable world than the one it will meet.

Hypoglycaemia rebound is the other reason. At 58.5% against a real 23 to 28 the simulated
person over-treats lows roughly twice as often as these cohorts appear to, so an algorithm
judged on how it handles the resulting highs is being judged on a harsher world.

What the six levels do support: stress-testing an algorithm for pathological behaviour,
ranking options where the difference exceeds the measured noise floor, and attributing an
effect to a named mechanism by switching layers off. Deciding what a change does to a
person still needs a trial.

## If you are adding a mechanism

The bar is in `CONTRIBUTING.md` and the short version is: name the statistic it is meant to
move, show it with and without, show every other statistic too, and do not fit the
parameter to the statistic you are judging it on. Several mechanisms in this package moved
their target and broke something else, which is only visible if the whole table is shown.
