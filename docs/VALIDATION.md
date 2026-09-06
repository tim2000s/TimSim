# How do you test whether a simulator is telling the truth?

Not with one number. A simulator can be trustworthy for one question and useless for the
next, so the question is never "is it valid" but "valid for what". This document sets out
seven levels of check, what each one licenses, and what TimSim currently scores on each.

Run them with:

```
python -m timsim.validation.run --fast     # levels 1, 2 and 6, a few minutes
python -m timsim.validation.run --ranking  # level 7 only
python -m timsim.validation.run            # everything, a couple of hours
```

## Getting the DCLP3 data

Levels 3 and 4 are scored against the DCLP3 trial, which is not redistributed with this
package for the same reason the virtual population is not. You need your own copy.

It is public. Register at [public.jaeb.org](https://public.jaeb.org/dataset/573) and
download the DCLP3 dataset, which arrives as a zip containing a `Data Files` directory.
Unpack it anywhere and point `DCLP3_DIR` at the directory that contains `Data Files`:

```
export DCLP3_DIR=~/data/dclp3
ls $DCLP3_DIR/"Data Files"/PtRoster_a.txt    # this is what `dclp3.available()` looks for
python -m timsim.validation.dclp3            # builds the cache, prints the split
```

`DCLP3_DIR` defaults to `~/Downloads/dclp3` if unset. The first read parses several
million rows and writes `timsim_cache_pump.npz` beside the data, so subsequent runs take
seconds. Anything that needs the data and cannot find it says so and stops rather than
quietly skipping the comparison, apart from the test suite, which skips.

Two things about the files are worth knowing before reading anything off them.

The trial ships CGM in two forms and they are not interchangeable.
`Pump_CGMGlucoseValue.txt` is what the pump received and acted on;
`DexcomClarityCGM_a.txt` is the Clarity export, which is smoothed by a factor of about two
on the second-difference spread. TimSim reads the pump-received file, and reading the other
one made the sensor layer look wrong when it was not. `dclp3.REFERENCE_VIA_CLARITY` keeps
the same statistics off the smoothed source so the size of that error stays visible.

Roughly 40% of participants are sealed. `dclp3.split` puts them behind the fingerprint in
`SPLIT_FINGERPRINT`, stratified by arm, and everything in this package is calibrated on the
other 60%. The sealed half is worth exactly one scoring, at the end, and spending it early
is not recoverable.

The model underneath is described in [MODEL.md](MODEL.md).

## The seven levels

| Level | Question | What it licenses |
|---|---|---|
| 1 | Does the code do what it claims? | nothing on its own; failure invalidates everything above it |
| 2 | Does it get direction and rough magnitude right? | reasoning about mechanism |
| 3 | Does its output look like real data? | that a trace is not obviously artificial |
| 4 | Does it reproduce a result established elsewhere? | that its response to an intervention is roughly right |
| 5 | How large a difference can it resolve? | reading an A/B result |
| 6 | Do conclusions survive the arbitrary choices? | that a result is not an artefact of a seed |
| 7 | Does it behave when inputs fail, and does it rank correctly? | a safety verdict on an algorithm |

Most published simulator validation stops at level 3, which is the weakest of the seven
taken alone. Matching the marginal statistics of real data says nothing about whether the
response to an intervention is right, and the response to an intervention is the whole
reason to run a simulator. Levels 4 and 5 are what a controller comparison actually rests
on, and level 5 is the one most often skipped. Without it an A/B result has no scale to be
read against.

Level 7 is the one that matters for judging an automated insulin delivery system, and none
of the six below stands in for it. [EVIDENCE.md](EVIDENCE.md) sets out the reasoning
behind it and what a verdict from it is allowed to mean.

## Level 1: internal consistency

Does the code do what it claims?

The steady-state closure reproduces every published subject. The balance equations in
`population/derive.py` complete every generated subject. Applied to the published subjects
they return those subjects exactly. Worst relative residual across all thirty: 5e-12. A
failure here would invalidate everything downstream.

A quiet subject holds its fasting glucose. On its own basal with no meals, blood glucose
does not move. Measured excursion over four days: 0.02 mg/dL. Delivery quantisation is
switched off for this one, because what it tests is whether the parameters and the initial
state agree, and that is a property of the physiology rather than of the device.

That check was wrong twice before it was right, and both mistakes are worth knowing.
Comparing the first reading with the last aliases an oscillation, so it passed at two days
and at four and failed at one. Measuring the excursion on the sensor reading measures the
sensor: the noise model is strongly autocorrelated and wanders about 40 mg/dL either side
over two days while the blood glucose underneath stays put. Getting the check right also
exposed a real defect. Every run had been opening with a zero-insulin step, inherited from
simglucose's own examples, which kicked each subject off the steady state its parameters
were closed at. Runs now open at the subject's own scheduled basal.

Pump quantisation costs what it should. A basal rate delivered to the nearest 0.05 U/h is
out by up to about 2%, which leaves a subject roughly 2 mg/dL from its fasting value. That
is real and bounded rather than a defect, and it is measured rather than assumed. An
intermediate version of the code rounded down instead of to the nearest increment and
produced three times the offset, in the same direction, on every subject. A choice that
looks conservative is not automatically the safe one.

The sensor layer changes the reading and not the body. This check used to compare the
underlying glucose with the sensor layer on and off while the loop was running, and it
passed trivially, because the layer was applied to the finished trace after the run had
ended. Nothing could have failed it. The layer now sits inside the loop, so an algorithm
that reads glucose does dose differently and the body genuinely differs. The isolation has
to be tested against a controller that ignores the sensor, and for that controller the two
runs agree exactly on blood glucose while the reading moves by up to 6.7 mg/dL.

The algorithm is handed the artefacts. The recorded trace is the reading the controller
acted on, so a compression event in the record is an event the controller saw: three over
21 days, with 3.3 mg/dL of added second-difference jitter.

Delivery limits bind. An algorithm asking for a unit a minute of basal and 20 units of
bolus every cycle is clamped 72 times on basal, 72 on bolus and 144 on insulin on board
over two days, and peak insulin on board lands exactly on its 8.6 U ceiling. simglucose's
own pump would have accepted 150 units in a single step. Writing this check is what found
the ceiling being applied to boluses and not to basal above schedule, which had let insulin
on board reach 10.8 U against that same 8.6.

The same seed reproduces the same run, and different seeds do not. Covered in the test
suite.

Status: passing.

## Level 2: face validity

Does it get the direction and rough magnitude right?

The published cohort obeys the clinical dosing rules. One unit of insulin moves the ten
published adults by 1.10 times their stated correction factor; 50 g of unbolused
carbohydrate raises them by 1.19 times grams over ratio times factor; a bolused meal peaks
at a median of 75 minutes. The model and the rules that real settings are built on
describe the same person. This is the independent version of the two rule checks, because
the published subjects' settings were not derived from the model.

Generated subjects obey the same rules. On them this is a consistency check rather than an
independent test, since their settings are measured from their own model. It still earns
its place, because it catches settings measured under one steady state being applied under
another.

More insulin lowers glucose, monotonically: 191, 178, 164, 147, 128 mg/dL at 0.7 to 1.3
times the dose. A simulator that is not monotone in its most important input cannot rank
two controllers, whatever its distributional fidelity looks like.

Extra insulin is met with extra carbohydrate. With the behaviour layer on, the same ladder
gives rescue carbohydrate of 0, 0, 233, 323, 575 g, and mean glucose stops falling cleanly.
That is the person defending against lows rather than a modelling error, and it names a
trap. A more aggressive controller here may show no improvement in mean glucose because
the simulated person eats the difference. The effect turns up in carbohydrate and time
below range instead.

Status: passing.

This level found a real defect. The first version of the population generator drew
carbohydrate ratio and correction factor from the published cohort's distribution
conditioned on body weight and basal rate. The published subjects came out at 1.10 times
their correction factor and the generated ones at 0.63, which means every generated
subject was being dosed on somebody else's settings on every cycle of every run. The
settings are now measured from each subject's own model, and fixing it improved the level
3 table by three statistics. Nothing at level 3 would have found it, because a table of
statistics does not say which mechanism is wrong.

## Level 3: distributional fidelity

Does its output look like real data?

Eleven statistics computed identically on simulator output and on the traces of 192 real
closed-loop users. [FIDELITY.md](FIDELITY.md) has the full table and the layer-by-layer
attribution. In summary: three of eleven inside the real range for the bare subjects and
five of eleven with all five layers, and eight with the four-layer arm that
the discriminability test in level 5 prefers less. The two disagree, and
[FIDELITY.md](FIDELITY.md) opens with why.

The six outside on the default arm are glucose variability, both autocorrelations, diurnal
amplitude, hypoglycaemia recovery and hypoglycaemia rebound. Three of those are the price of
the infusion site layer, which is in the default because the stronger test in level 5
prefers it in ten splits out of ten. Each is discussed there rather than tuned away.

Status: five of eleven on the default arm, and the count is not the headline. The
discriminability figure is, and it is 0.671 against a floor of 0.937.

Worth noting what moved this table most. Fixing the therapy settings, which was a level 2
finding, improved it by three statistics and moved the spread of outcomes from 21.0 to
25.5 mg/dL, and a bolus-units defect found by rereading the run loop took the bare
subjects from one of eleven to three. Nothing aimed at level 3 achieved anything
comparable.

## Level 4: known answer

Does it reproduce a result established elsewhere?

The best-established intervention in this field is closing the loop, and it no longer has
to be taken from the literature. DCLP3 randomised it: 168 participants, 26 weeks, free
living, closed loop against sensor-augmented pump. Measured on the calibration half of that
trial, the difference is +13.9 percentage points of time in range, p = 6e-05. The trial's
own headline figures give about eleven points.

So the simulator is asked the same question: the same subjects, the same seed, the loop
layer on and off. Measured on 20 adults over 14 days, paired:

    TimSim              +12.9 pp  [+8.2, +15.4]
    DCLP3, randomised   +13.9 pp
    trial headline      +11 pp

The interval covers both real figures. This is the strongest single result in the package,
because it is a randomised effect the simulator was never fitted to, measured on data that
postdates every parameter in it.

Two qualifications. The loop being switched off here is a baseline of this package's own
construction rather than a real pump-therapy arm, so it bounds gross error rather than
confirming accuracy. And DCLP3's arms are between-subject where TimSim's are paired, which
is the more favourable design.

## Level 5: discriminating power

How large a difference can it resolve?

The A/A test. Run the same controller twice, same subjects, different seed. Whatever
difference that produces is the noise floor, and no A/B on the same design can be believed
below it. This is the check most often skipped, and skipping it is how a simulator comes to
report a two-point improvement that is indistinguishable from running the same thing twice.

Measured on 20 adults over 14 days: -0.27 percentage points [-1.65, +1.72]. The interval
spans zero, so the null comes out null, and the paired standard deviation is 3.88
percentage points.

The minimum detectable difference is computed from that measured spread, so it is empirical
rather than assumed:

```python
from timsim.validation import minimum_detectable_difference
print(minimum_detectable_difference(null_a, null_b, n_subjects=100))
```

At 80% power and a 5% two-sided level:

| Subjects | Smallest resolvable difference in time in range |
|---|---|
| 20 | 2.43 percentage points |
| 34 (all adults) | 1.86 |
| 100 (whole population) | 1.09 |

Read this before believing any comparison. A difference smaller than the figure for your
design is not evidence of anything, however tidy the plot looks. It is also the argument
for the larger population, since thirty subjects would resolve about 1.9 points where a
hundred resolve about 1.1.

The rows below twenty are projections from the twenty-subject spread, and the one measured
directly disagrees with them. On 6 September 2026 the trend loop was run twice on the
forty-adult panel over 28 days, on the bench month and on `seeds.AA`
(`docs/measurements/driver_ranking.json`): the paired median is +0.86 points [-2.49, 1.90],
the paired standard deviation 6.28 points, and the design resolves 2.78 points rather than
the 1.7 the table would project. The spread is not two outliers, since the median absolute
deviation gives 6.13. Adding subjects added noisier ones, as level 7 found for the low blood
glucose index, so a floor is read at the size and duration it was measured at.

Worth recording that these figures barely moved across the harness rework. The previous
values, measured on the three-minute grid before twelve defects were fixed, were 2.34, 1.79
and 1.04. They were approximately right, and they are now confirmed rather than assumed.

Two design points follow, and they are worth stating separately because they cost nothing
and buy most of the available power.

Pair. Use the same subjects and the same seed in both arms. Between-subject variation is
far larger than the effect of any sensible controller change, and an unpaired comparison
throws that away.

Do not judge on mean glucose alone. Level 2 showed why. The simulated person defends
against lows with carbohydrate, so a more aggressive controller can look identical on the
mean while differing substantially in carbohydrate consumed and time below range.

One thing this level does not cover: rare adverse events. The minimum detectable difference
is a statement about means. Section 7 of [OSAID.md](OSAID.md) works through the exposure
arithmetic for events, and the answer is that a cohort of this size cannot rule out a rate
that would still matter clinically.

## Level 6: robustness

Do conclusions survive the arbitrary choices?

Two population draws describe the same kind of people. Seeds 2026 and 7 give median
carbohydrate ratios of 10.8 and 8.9, within 18%. This check failed before the settings
were measured rather than sampled, at 22.1 against 13.5.

A conclusion does not depend on an unfitted behaviour parameter. The announcement rate was
chosen from the literature rather than fitted. Moving it from 65% to 95% moves mean glucose
from 134 to 130 mg/dL, in the right direction and by a bounded amount.

Regenerate before believing anything: `python -m timsim.population.build --n 100 --seed 7`.
A result that does not survive a different draw of the population was never a result.

Status: passing.

## Level 7: fault tolerance and ranking

Two questions the six levels above do not ask. `docs/EVIDENCE.md` sets out the reasoning
and reports the measured results; this is the summary.

Does an algorithm behave sensibly when its inputs go wrong? `validation/faults.py` injects
eight conditions that produce real incident reports: dropouts of an hour and three hours, a
sensor restart with a warm-up gap and an offset on resumption, a stuck reading, a
compression low placed where you want it, delivery loss of one and two hours, and a clock
shift. Each runs against an unfaulted control on the same subject and seed. The useful
output is a trace rather than a statistic, because what you are looking for is a fallback
and a recovery, and each fault class states in words what a sensible system does.

Does the bench order algorithms the way it should? This cannot be answered against real
systems whose true ordering nobody knows. It can be answered against algorithms broken on
purpose. `controller/reference.py` is a plain automated insulin delivery algorithm with
four named defects, each taking a magnitude, and `validation/ranking.py` requires three
things of the bench.

The safety score has to rise at every step as one defect is dialled from none to severe.
Measured on 12 adults over 14 days, median LBGI goes 0.80, 0.88, 1.03, 1.07 as insulin
sensitivity is scaled to 1, 0.85, 0.70 and 0.55 of its correct value. Passing.

Every named defect has to clear the noise floor measured by running the reference twice.
Measured after the rebuild at three cohort sizes over 14 days
(`docs/measurements/ranking_power.json`), the A/A arm gives a paired LBGI standard deviation
of 0.49 at twelve subjects, 0.51 at twenty and 0.52 at forty, so the shift the design
resolves at 80 per cent power is 0.40, 0.32 and 0.23. Removing the insulin-on-board ceiling
shifts LBGI by +1.57 at twelve and +2.27 at forty and is detected at every size. The other
three defects, removing basal withdrawal (+0.18 at twelve, +0.31 at forty), acting on stale
readings (+0.17, +0.24) and a 30 per cent sensitivity error (+0.15, +0.26), all miss the
floor at twelve and twenty. At forty the check passes on the point estimates, and two of
the three sit inside the floor's own uncertainty: a standard deviation from forty pairs has
a relative standard error near 11 per cent, so the floor is 0.23 give or take 0.026, and
the shifts of 0.24 and 0.26 are not clearly above it. Two defects separate clearly at forty
subjects and two are marginal. That says the bench is underpowered for those hazards at
that size rather than that they are benign. A previous version of this paragraph quoted a
floor of 0.176 at twelve subjects and projections of 0.105 at thirty-four and 0.061 at a
hundred; those were measured before the rebuild on a spread less than half the current one
and are superseded.

A deliberately timid algorithm has to look safer on lows and worse on highs. LBGI 0.80 to
0.30, mean glucose 143 to 156 mg/dL, time in range 73.0% to 69.4%. Passing.

The score is the low blood glucose index, a published asymmetric measure of hypoglycaemia
risk. Inventing a composite would make every result a property of the weights.

One result from that ladder belongs here rather than only in `EVIDENCE.md`. The algorithm
with the best time in range in the whole table, at 77.4%, is the one with basal withdrawal
removed. It spends twice as long below 54 mg/dL as the reference and needs 55% more rescue
carbohydrate. Ranking on time in range would place it above the algorithm it was built by
breaking, which is the concrete version of the warning at level 2.

## What none of this establishes

No check here licenses using TimSim to price a dosing change for a particular person, and
none of them licenses calling an algorithm safe. The second limit is about exposure rather
than fidelity: 2800 subject-days with no severe events bounds the underlying rate no lower
than about one per 2.6 subject-years, so a system with a genuine rate of one per five would
show nothing. `validation/gate.py` reports that bound alongside every verdict for exactly
this reason.

The reason is measured and specific. The spread of where glucose lands thirty minutes
after a stuck high is 27.0 mg/dL in the simulator against 26.5 to 33.5 in real data,
having been 21.0 before the therapy settings were corrected and 25.5 before the harness
was. It is inside the real range for the first time, at the confident end, on ten subjects
with a bootstrap interval from 22.0 to 30.7. That spread is the quantity a dosing decision
bets on, so the caveat stands until the figure survives the full population and a second
seed.

Hypoglycaemia rebound was the other reason and has narrowed. The share of lows followed by a
reading above 180 mg/dL within two hours was 66.1 per cent on 7 August 2026 against a Commons
23 to 28 and a DCLP3 41 to 46; on the current outcome table it reads 31 to 36 per cent across
the three pairings (`docs/measurements/egp_defence_outcome.json`, shipped arm, 242 subjects),
and per person on treated lows 34 per cent (17 to 65 across 40 adults) against the Commons
users' 26 (10 to 49), inside the real spread (`examples/low_recovery.py`).

What has taken its place is the recovery from a low nobody eats for, measured on 5 September
2026 with the person's treatment switched off. The Commons users recover to 100 mg/dL in 65
minutes at the per-person median (41 to 119 across 43 users); the generated adults take 105
under the built-in loop and 114 under oref0 SMB, and swapping the controller moves that by 9
minutes paired, so about 40 minutes of it is the person's. Eight of 40 adults under oref0 SMB
leave the range from below inside 28 days when nothing is eaten, against one when the person
treats. Raising the hepatic defence gain from the shipped 0.05 to 0.25 stops those
fall-throughs and moves the recovery by 6 minutes, and on the outcome table moves time below
54 mg/dL by 0.14 to 0.31 points against a between-group variation of 0.34 to 0.56
(`examples/hypoglycaemia_arms.py --arms shipped defence`), so it changes who completes a run
rather than how much time completers spend low. The gain stays at 0.05, where the clamp put it.
The shipped person hides the slow recovery by treating every low it notices, and an algorithm
judged here on lows it lets happen is judged on a person who turns them more slowly than a real
one and, under a fast-acting controller, sometimes not at all.

The meal rise is a third, and it is a bound rather than an open question. Per 10 entered grams
on covered meals at a 240 minute window, the simulated adult rises 9.9 to 11.5 mg/dL depending
on the driver, where 470 adult Loop participants rise 15.1 (10.1 to 22.3 across people,
`docs/measurements/insulin_by_peak.json`), and time to peak is 70 to 95 minutes against 85. In
the week to 5 September 2026 the controller, the grams denominator, the carbohydrate estimate
bias and the insulin delivered by the peak were each excluded as the cause, the last by driving
the simulated person with the real profile and finding the rise unchanged, -0.07 mg/dL per 10 g
[-0.75, 0.50] against the simulated profile (`examples/insulin_profile_rise.py`; the trail is in
`docs/DESIGN_ALIGNMENT.md`). What is left is the model's glucose appearance and disposal, which
this package does not refit. An algorithm is therefore judged here on meals that rise about a
third less per gram than a real adult's, and what that does to a ranking was measured
(`examples/meal_yield_ranking.py`): raising the yield of the published model until the oref0 SMB
rise reads 15.1 leaves the order of the three closed-loop drivers and the differences between
them where they were, within 2 points of time in range at the estimate and 3.7 at the edge of
the interval, and moves the open-loop arm, whose shortfall on time in range to each loop widens
by 4.4 to 7.3 points and whose time below 70 mg/dL goes from third of four to first. A
comparison among closed loops does not depend on the bound at the size a panel of twenty
resolves; one that includes an open-loop arm does.

What the seven levels do support: stress-testing an algorithm for pathological behaviour,
ranking options where the difference exceeds the measured noise floor, and attributing an
effect to a named mechanism by switching layers off. Deciding what a change does to a
person still needs a trial. `docs/READING_A_RESULT.md` lays the supported and unsupported
comparisons out side by side, each with the residual to carry beside it.

## If you are adding a mechanism

The bar is in `CONTRIBUTING.md`. In short: name the statistic it is meant to move, show it
with and without, show every other statistic too, and do not fit the parameter to the
statistic you are judging it on. Several mechanisms in this package moved their target and
broke something else, which is only visible when the whole table is shown.
