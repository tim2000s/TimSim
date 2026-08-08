# Showing that this works, and what "works" is allowed to mean

Two things have to be true before a verdict from this bench is worth anything. The
simulated people have to stand in for real people well enough for the question being
asked. And the bench has to order algorithms the way reality would, because an ordering is
what it actually produces.

Those are separate claims and they need separate evidence. Most simulator validation
addresses only the first, by showing that the output resembles real data, and then quietly
assumes the second. The assumption does not follow. A simulator can match every marginal
statistic of real glucose and still rank two algorithms backwards, because resemblance is
a property of the traces and ranking is a property of the response to an intervention.

## What "safe" can mean here

A simulator cannot certify a system as safe. Section 7 of [OSAID.md](OSAID.md) has the
arithmetic: the whole population run for 28 days is 2800 subject-days, and observing no
severe events over that exposure bounds the underlying rate no lower than about one per
2.6 subject-years. A system with a genuine rate of one severe event per five subject-years
would show nothing. No amount of further work on the model changes that, because the limit
is exposure rather than fidelity.

What a simulator can support is a pre-clinical gate: fix the acceptance criteria in
advance, run the cohort, and report whether anything trips them. A failure is a
demonstration and stands on its own. A pass says no reason was found here not to proceed,
quoted together with the exposure that produced it. This is the claim the UVA/Padova
simulator was accepted for in 2008, as a replacement for animal testing ahead of a trial
rather than as a replacement for the trial, and it is the strongest honest position
available.

So "rank the system as safe" resolves to: rank it against algorithms whose relative safety
is known, gate it against criteria fixed beforehand, and report the exposure. The six
mechanisms below are how each of those is earned.

## The mechanisms

| Mechanism | The claim it supports | Status |
|---|---|---|
| 1. Discriminability | the simulated traces are not distinguishable from real ones | run against DCLP3: separable at 0.709, and the axis is hyperglycaemia |
| 2. Coverage and spread | the simulated population is as wide as the real one, not just centred on it | function built, blocked on the same data |
| 3. Known-ordering validation | the bench orders algorithms correctly | monotone; separates three defects of four at twelve subjects, and names the cohort size the fourth needs |
| 4. Fault tolerance | the bench exercises the conditions that produce real incidents | six fault classes, eight preset scenarios, all producing attributable differences |
| 5. Pre-registered gate | a verdict that cannot be reverse-engineered from the result | implemented, with a fingerprint |
| 6. Negative controls | a null reads as a null | A/A and the deaf controller, both passing |
| 7. A real algorithm with a known answer | the simulator exercises an algorithm the way the field does | reference established on 193,714 real cycles; TimSim currently fails it |

### 1. Can a classifier tell a simulated person from a real one?

Level 3 compares eleven cohort medians against an envelope of four cohort medians. That is
a weak test in a specific way: a simulator can match every median while getting the spread
across people badly wrong, and it is reachable by tuning, which is why `FIDELITY.md`
insists on the whole table whenever anything changes.

The stronger version is the standard two-sample test for generative models. Train a
classifier to separate windows of simulated trace from windows of real trace. An area
under the curve near 0.5 means the two are indistinguishable on everything the features
encode, which is a far larger claim than eleven medians landing in range. The features
carrying the weight name what is still wrong, which a table of medians cannot do.

`validation/replication.py` implements it with a logistic regression over a dozen
interpretable window statistics, cross-validated, with a permutation null so the figure
has a scale. Deliberately small: a larger model would separate the two on artefacts of
sample size and teach nothing.

A discriminability test is worthless without both halves of its calibration, so both are
run on data this package can generate. The null half splits one cohort in two and requires
the classifier to do no better than chance. The power half asks it to separate the full
simulator from one with the layers switched off, and requires it to succeed. A test that
cannot see a simulator missing unannounced meals, rescue carbohydrate and sensor artefacts
is not sensitive enough for its null to be believed.

Running the null half is what made the test usable, and it is worth recording what it
found. The first version cross-validated over windows and permuted window labels, giving a
null at 0.5. It then reported an area under the curve of 0.85 for one half of a simulated
cohort against the other half. Nothing was wrong with the simulator. Windows from one
person share that person's mean and rhythm, people differ, and a classifier separates any
two groups of different people. The comparison this test exists for, simulated against
real, is also a comparison between two groups of different people, so 0.5 was never the
right thing to measure against.

Both halves are now grouped by subject: cross-validation holds out whole subjects, and the
null permutes subject labels, so it reproduces the between-subject structure. The question
becomes whether the classifier separates simulated from real any better than it separates
a random regrouping of the same people. That is a much harder test to pass and the only
one that means anything.

#### The answer, against DCLP3

3,752 windows from 67 real closed-loop participants against 1,870 from 34 simulated
subjects, whole subjects held out, subject labels permuted.

The classifier separates them, at an area under the curve of 0.709 against a null whose
95th percentile is 0.546. That is a long way from the 1.000 it scores against a simulator
with its layers switched off, and a long way from indistinguishable.

What separates them is hyperglycaemia.

| Feature | DCLP3 | TimSim | Standardised shift |
|---|---|---|---|
| Time above 180 | 24.65% | 16.49% | -0.54 |
| Mean | 150.6 | 142.3 | -0.42 |
| Maximum | 259.0 | 239.0 | -0.38 |
| Standard deviation | 43.6 | 38.5 | -0.33 |
| Sensor jitter | 4.39 | 5.53 | +0.23 |
| Time below 70 | 0.00% | 0.69% | +0.22 |
| Autocorrelation, 30 and 60 min | 0.84, 0.58 | 0.84, 0.58 | +0.03, -0.03 |

The simulated population is better controlled than real closed-loop users. It spends a
third less time above 180, runs 8 mg/dL lower, and peaks 20 mg/dL lower, while spending
slightly more time below 70.

For a safety bench that is the wrong direction. An algorithm tested here meets an easier
hyperglycaemic world than the one it will be used in, so the corrections it exists to make
are under-exercised. It is consistent with the Boost work, where TimSim reached the
committed meal state less often than the field does.

Two smaller readings. Sensor jitter runs slightly hot at 5.53 against a real 4.39, even
against the correct pump-received source. And the two autocorrelations now match almost
exactly, which retires the score-persistence gap recorded in `validation/boost.py`: that
was an adapter artefact rather than a property of the simulator.

### 2. Is the population as wide as the real one?

Related and separate. A simulated cohort can sit inside the real range on every statistic
and be far narrower than the real population, and a narrow population is exactly what
makes a bench look more decisive than it is. It is also the failure mode TimSim already
had until recently: the spread of outcomes after a stuck high sat at 21.0 mg/dL against a
real 26.5 to 33.5, and is now 27.6, which is inside the range on ten subjects with a wide
interval rather than settled.

`replication.coverage` reports the overlap in both directions and the ratio of the spreads,
per statistic. Reporting only "simulated inside real" is what hides a narrow population.
Blocked on the same per-user data as mechanism 1.

### 3. Does the bench order algorithms correctly?

This is the one that matters most and the one that is almost always missing, so it is
worth being explicit about the logic. You cannot check an ordering against systems whose
true ordering you do not know, which rules out validating against real AID systems. You
can check it against algorithms you have broken on purpose, where the direction of the
answer is fixed by the mechanism before the run.

`controller/reference.py` is a plain automated insulin delivery algorithm with four named
defects, each taking a magnitude: an insulin sensitivity setting that is too strong, no
ceiling on insulin on board, no basal withdrawal on a fall, and acting on readings that
are half an hour old. `validation/ranking.py` runs three checks over them.

Monotonicity is the load-bearing one. Dial a single defect from none to severe and the
safety score has to rise at every step. A score that is not monotone in the size of a
defect it can see cannot be trusted to order two algorithms that differ by less. This is
the safety analogue of the level 2 monotonicity check, and it does the same job: it tests
the response to an intervention rather than the appearance of the output.

Separation asks whether each named defect clears the noise floor measured by running the
reference twice on different seeds. A defect that is real and invisible means the bench is
underpowered for that hazard, which someone needs to know before reading a null as
reassurance.

The trade-off check exists because an algorithm can always buy hypoglycaemia safety with
hyperglycaemia, and a bench that reports one arm of that will rank the timid algorithm
best every time.

The score is the low blood glucose index, a published asymmetric measure of hypoglycaemia
risk. Inventing a composite would make every result a property of the weights.

### 4. Does it exercise the conditions that produce incidents?

Fidelity says nothing about behaviour when the sensor stops reporting or the pump stops
delivering, and those are what incident reports are about. `validation/faults.py` injects
eight of them: dropouts of an hour and three hours, a sensor restart with a warm-up gap and
an offset on resumption, a stuck reading, a compression low placed where you want it,
delivery loss of one and two hours, and a clock shift.

Each runs against an unfaulted control on the same subject and seed, so the difference is
attributable. The useful output is a trace rather than a statistic, because what you are
looking for is a behaviour: a fallback, a recovery, and the absence of something large and
wrong at the moment the input returns. Each fault class states in words what a sensible
system does, so a reviewer knows what they are looking at.

None of this needs a cohort. One subject on a fixed seed that reproduces exactly is more
useful than a median, because a maintainer can rerun it.

### 5. Can the verdict be reverse-engineered from the result?

Not if the criteria are fixed first. `validation/gate.py` hashes the criteria together
with the design into a fingerprint to be recorded before the run and quoted with the
result. A verdict whose fingerprint does not match the registered one had its thresholds
moved, and that becomes visible instead of invisible.

Each criterion names the hazard it covers, so the coverage gap is readable: anything in a
hazard analysis with no criterion against it is untested. The gate lists what it does not
cover rather than leaving it implied. Population thresholds come from the consensus
continuous-glucose targets; the tail thresholds are this package's own choice and say so.

Two design decisions are worth stating. The gate reads the worst subject as well as the
median, because an algorithm that is excellent for 95 subjects and dangerous for five is
not acceptable and a median conceals that entirely. And it includes a time-in-range floor,
so the gate cannot be passed by an algorithm that simply withholds insulin.

### 6. Does a null read as a null?

Three negative controls, all passing. The A/A test runs the same controller twice on
different seeds and requires the interval to span zero, which also calibrates the minimum
detectable difference. The discriminability null splits a cohort in two and requires the
classifier to fail. The deaf-controller check runs a controller that ignores the sensor
and requires the sensor layer to leave the body bit-identical, which is the isolation test
that the old post-hoc sensor layer could not fail.

### 7. Does the simulator exercise a real algorithm the way reality does?

The strongest test available, and the one that needed data this repository did not have.
Boost is a shipped automated insulin delivery algorithm, and the AndroidAPS development
branch logs every decision it makes: 226,829 of them in a `boost_decisions` table, each
carrying the state the plugin was in and the dose it delivered to a real person.

That is the reference, and it answers a question no fidelity table can. A simulator that
keeps an algorithm in its idle states will match every marginal statistic and report that
the algorithm is safe, because it never ran the part of it that doses hard.

| State | Share of decisions | Mean dose |
|---|---|---|
| IDLE | 65.0% | 0.036 U |
| OBSERVING | 21.2% | 0.063 U |
| RECOVERING | 5.8% | 0.080 U |
| COMMITTED | 5.4% | 0.278 U |
| CONFIRMED | 2.5% | 1.045 U |

The two states that carry the risk are 7.9% of decisions and roughly thirty times the dose
of the idle state. A simulator that misses them misses the algorithm.

#### The port was missing a whole stage of the dose chain

The obvious route to a reference was to replay cached input records through the Python port
of the plugin. That assumes the port is faithful, and the in-silico README on the same
branch names the check the assumption needs: "the port must reproduce the logged
boostv5_finaldose within tolerance. No fidelity, no A/B."

It did not. The port delivered 2.24 times the insulin the plugin logged on the same inputs.
Reading `DetermineBasalBoostV5.kt` found why: the Kotlin runs a Phase 2.5 between the
decision and the safety gates, and the port had none of it.

    velocityScaled = budget x actionMult x velocityScaledDoseFactor(cumulativeRise30min)
    capped         = applyStateDoseCap(state, velocityScaled, 1.0 U, 0.25 U)

The caps carry most of it. The logged mean dose in CONFIRMED is 1.045 U against a cap of
1.0, and in COMMITTED 0.278 U against a cap of 0.25, so nearly every meal-state dose the
plugin gives sits on its ceiling. A port without them is not dose-limited at all.

Restoring the stage was verified against the plugin's own logged intermediates rather than
inferred: `boostv5_doseaftercaps` matches to a mean absolute error of 0.0000 U, with every
row inside 0.01 U. End to end the dose ratio moved from 2.24 to 0.86 and the mean absolute
error halved.

What did not move is the timing. State agreement is still 70.9%, and on real inputs the
port reaches RECOVERING on 0.6% of decisions against a logged 5.8% and CONFIRMED on 0.3%
against 2.5%. The meal scoring survives translation at a correlation of 0.815; the state
machine does not. That is the remaining known gap.

#### A units defect in the cached cohort

The input cache stored `target_bg` in mmol/L for all nineteen users, and `eventual_bg` and
`min_guard_bg` in mmol/L for fourteen, in fields the harness reads as mg/dL. A predicted
minimum of 5.6 sits below the 80 mg/dL hard gate on every cycle, so the algorithm was
disabled outright on 74% of them against a real 8.8%, and the mean dose read 0.062 U against
0.238 U.

The logged decisions settle it: every glucose field in the database is mg/dL. The cache has
been rewritten in mg/dL, and the detector stays in the loader so a stale copy is caught.
Anything calibrated against the old cache was tuned against an algorithm gated off three
quarters of the time.

#### Separating the simulator from the port

A TimSim result cannot be scored straight against the plugin's logs, because the port sits
in between and has errors of its own. Running the same port on real inputs gives the control
that cancels them: the port's failures then appear on both sides, and what is left is the
simulator.

Doing that the first time showed the gap was mostly not the simulator. It was the adapter,
reconstructing two oref internals that TimSim has no equivalent for and getting both badly
wrong. Both are recoverable from the plugin's own logs, so both were calibrated against
them rather than guessed at again.

| Reconstruction | Naive | Calibrated | Logged |
|---|---|---|---|
| eventualBG minus glucose, median | -45 mg/dL | -6 mg/dL | -12 mg/dL |
| Crosses the confirm threshold | 3.5% | 17.2% | 18.4% |
| insulinReq against the naive quotient | 1.00x | 0.41x | 0.41x |

A third gap was structural rather than numerical. Boost decides only the microbolus; the
basal decision belongs to oref's determine-basal, which is not ported. Without something
in its place the profile basal ran at full rate underneath every microbolus, and the two
added up: time below range 9.2%, seventy per cent more insulin than the field. Implementing
oref's own low-glucose behaviour, a zero temp below target and a half rate near it, brought
that to 5.2%.

Fitting an input reconstruction to ground truth is not the same as fitting to the statistic
under judgement. What is being tested is the simulator's state occupancy, and it appears in
none of these fits.

| State | Logged | Port on real | Port on TimSim | Port error | Simulator effect |
|---|---|---|---|---|---|
| IDLE | 65.0 | 73.7 | 45.4 | +8.7 | -28.4 |
| OBSERVING | 21.2 | 18.9 | 44.9 | -2.3 | +26.0 |
| RECOVERING | 5.8 | 0.6 | 3.5 | -5.2 | +2.9 |
| COMMITTED | 5.4 | 6.5 | 4.4 | +1.1 | -2.1 |
| CONFIRMED | 2.5 | 0.3 | 1.8 | -2.2 | +1.5 |

The two states that carry the dosing are now within a point or two of the field, where
COMMITTED began at 0.87% against 5.4%. The simulator reaches them.

#### What is left is the simulator, and it took six wrong guesses to find

One residual survives, and unlike everything above it is a property of TimSim. Finding it
took six hypotheses, five of which the measurements refuted. Recording them is the point:
each was plausible, and tuning to any of them would have made things worse while a chosen
statistic improved.

| Hypothesis | Test | Result |
|---|---|---|
| The meal template under-produces excursions | 196 real segments over 102 days against simulated traces | refuted; TimSim over-produces them, 1.9 times as many sustained climbs |
| The S2017-style sensitivity layer drives it | run with the layer on and off | refuted; removing it makes things slightly worse |
| The controller drives it | run with no correction at all | refuted; the body alone is already at CV 39.2 against a real 31.9 |
| Rescue over-treatment drives it | calibrated against 30 users' logged carbohydrate | half right; fixed variability, did not touch the residual |
| The rises are the wrong shape | 1,058,439 real deltas against 20,926 simulated | refuted; every measure within 11% |
| The missing meal-likelihood model drives it | supplied the signal from its real distribution | refuted; the gap does not close |

The rescue calibration is worth keeping despite not fixing what it was aimed at. Real users
log 0.44 rescues a day at a mean of 33.8 g; this package was giving 2.11 a day at 25.4 g.
Correcting that took glucose variability from 35.0 to 33.6, inside the real range, and the
fidelity table from seven of eleven to eight. It cost one subject's survival in the loop
arm, which is the second time in that table that making the simulated person less
protective has cost a life.

A correction to an earlier claim in this document. The observing-state excess was reported
as roughly double the field rate, which compared TimSim scored by the port against the
plugin's own logged score. Those are two different scorers and the port's own scoring
differs by about eight points. Run both sides through the same scorer, the entry-threshold
crossing rate is 34.2% against 29.3%, and the mean score is 0.371 against 0.372.

So what is left is not the level of the meal signal, which matches, nor its distribution,
which matches to within five points in every band. It is the persistence.

| | Real | TimSim |
|---|---|---|
| Mean meal score | 0.372 | 0.371 |
| Cycles above the entry threshold | 29.3% | 34.2% |
| Exit conditions per 100 cycles | 31.5 | 30.3 |
| Score autocorrelation, lag 1 | 0.092 | 0.283 |

A real user's meal signal is close to uncorrelated from one cycle to the next. TimSim's is
three times more persistent. The state machine leaves its observing state only after two
consecutive cycles below the exit threshold, so a signal that lingers holds the algorithm
there even when it crosses the entry threshold barely more often. That is how a five-point
difference in the marginal distribution becomes a twenty-six point difference in occupancy.

The glucose deltas themselves are not the cause: their autocorrelation matches at 0.607
against 0.618. Whatever is smoothing the signal is in the components derived from them, and
that is the next place to look.

## What it currently measures

Twelve adults over 14 days for the ranking work, ten adults over 28 days for the
discriminability calibration. Small designs, chosen so they finish; the exposure line in
any verdict says what the run you actually did supports.

### The ladder of deliberately broken algorithms

| Algorithm | LBGI | p90 LBGI | min <54 /day | mean BG | Time in range | Rescue g/day |
|---|---|---|---|---|---|---|
| reference | 0.80 | 1.14 | 2.0 | 143.5 | 73.0% | 77.5 |
| insulin sensitivity 30% too strong | 1.03 | 1.55 | 7.1 | 139.6 | 73.5% | 114.8 |
| no ceiling on insulin on board | 3.18 | 5.09 | 70.7 | 131.4 | 69.0% | 285.5 |
| no basal withdrawal on a fall | 1.07 | 1.52 | 4.3 | 136.8 | 77.4% | 120.2 |
| acting on half-hour-old readings | 1.06 | 1.58 | 8.8 | 152.5 | 66.5% | 116.5 |
| deliberately timid | 0.30 | 0.55 | 0.0 | 155.6 | 69.4% | 33.5 |

Read the time in range column against the LBGI column. The algorithm with the best time in
range in the whole table, at 77.4%, is the one with no basal withdrawal on a fall: it
spends twice as long below 54 mg/dL as the reference and needs 55% more rescue
carbohydrate to stay there. The one with insulin sensitivity 30% too strong also scores a
better time in range than the reference while more than tripling minutes below 54. An
algorithm ranked on time in range would put both of them above the algorithm they were
built by breaking.

That is the concrete version of the argument for the safety metric set, and it is worth
more than the argument itself, because it is a demonstration rather than a claim.

### Monotonicity

Dial the algorithm's insulin sensitivity setting down from correct and median LBGI rises
at every step: 0.80, 0.88, 1.03, 1.07 at scale factors of 1, 0.85, 0.70 and 0.55. This is the
load-bearing result for any claim that the bench can rank, and it passes.

### Separation, and where the bench runs out of power

The reference run twice on different seeds gives the noise floor: a paired standard
deviation of 0.218 in LBGI, so at twelve subjects the smallest shift this design resolves
at 80% power is 0.176.

| Defect | Paired median LBGI shift | Detected at 12 subjects |
|---|---|---|
| no ceiling on insulin on board | +2.31 | yes, by a factor of thirteen |
| no basal withdrawal on a fall | +0.25 | yes |
| acting on half-hour-old readings | +0.24 | yes |
| insulin sensitivity 30% too strong | +0.17 | no, against a floor of 0.176 |

Three of four separate. The sensitivity error misses by 0.006, which is as marginal as a
result gets: the arithmetic says the design needed 12.9 subjects and it had twelve.

The right reading is that the bench is underpowered for that hazard at that cohort size,
not that the defect is benign. It more than triples minutes below 54 mg/dL in the table
above and adds 48% to rescue carbohydrate. Thirteen subjects would resolve it, thirty-four
would resolve a shift of 0.105, and the full hundred would resolve 0.061. Anyone reading a
null on a hazard of this size at this cohort size is reading an underpowered design rather
than a safe algorithm, which is exactly what this check exists to make visible.

That is also the honest answer to what the bench can rank. It separates a gross defect
trivially and a subtle misconfiguration only with enough subjects, and it now tells you
which of those situations you are in.

This check also caught a mistake in its own criterion, and the correction turned out not to
change the verdict. It first used the mean absolute paired difference of the A/A arm as its
floor, which is the typical size of the noise on one subject rather than the smallest shift
detectable across a cohort, so it does not shrink as subjects are added. Measured here it
is 0.159 against a detectable shift of 0.176, so the two are close at twelve subjects and
diverge from there: for a roughly normal paired difference the per-subject figure stays at
about 0.8 standard deviations whatever the cohort size, while the detectable shift falls as
its square root. The old criterion would have been unintentionally strict on any cohort
large enough to be worth running.

Both figures are reported now. That the error surfaced only when a defect failed against it
is the argument for running these checks against known answers rather than reasoning about
them.

### The trade-off

The timid algorithm comes out safer on lows and worse everywhere else: LBGI 0.80 to 0.30,
minutes below 54 down to zero, mean glucose 143 to 156 mg/dL, time in range 73.0% to
69.4%. A bench that reported only the hypoglycaemia half would rank it best in the table.

### Discriminability

Both halves of the calibration pass. Splitting a cohort in two gives a held-out area under
the curve of 0.401 against a subject-permuted null of 0.396, with a 95th percentile of
0.664 and p 0.48, so the classifier does no better on two halves of one population than on
a random regrouping of the same people. Separating the full simulator from one with every
layer switched off gives 1.000 with p 0.000, carried by jitter, mean absolute change and
variability. The test has a null and it has power.

Neither figure says anything yet about real data. That needs per-user traces.

### Faults

All eight preset scenarios run and produce attributable differences over the six hours from onset,
measured against an unfaulted control on the same subject and seed. The reference algorithm
does badly on the ones it should, which is what the scenarios are for.

| Scenario | Insulin over six hours, against control |
|---|---|
| sensor restart, 25 mg/dL offset on resumption | 11.00 U against 9.35, up 18% for a rise that did not happen |
| compression low | 10.65 U against 9.35, up 14% chasing a false low and the rescue that followed it |
| three-hour dropout | 9.78 U against 9.35, up 5% |
| one-hour dropout | 9.66 U against 9.35, up 3% |
| 45-minute stuck reading | 9.28 U against 9.35, unchanged within 1% |
| clock moved forward an hour | 9.29 U against 9.35, unchanged within 1% |

The last two are the interesting ones. The reference algorithm never reads
`info["stale_minutes"]`, so a frozen trace and a withheld one both leave it dosing on a
delta that is structurally zero, and it does so without noticing. A real system is supposed
to fall back. This is the bench doing its job on an algorithm written to be plain rather
than to be good.

The fault scenarios run against a dawn-shaped basal profile rather than a flat one. A clock
shift against a flat schedule changes nothing at all, so testing it there tests nothing.

## What would take this from defensible to strong

In descending order of value.

Per-user real traces, from cohorts that can be released. They unblock mechanisms 1 and 2
and would turn the strongest claim available from "matches eleven medians" into "a
classifier cannot separate them".

A real adapter for one of the open-source systems. Everything above is validated against
this package's own reference algorithm, which is honest and is not the same as validating
against oref. Section 3 of [OSAID.md](OSAID.md) lists what an adapter needs.

A held-out cohort. The sensor parameters were fitted on one cohort and evaluated against
others, which is the right shape. Nothing else has been held out, and a cohort reserved
from the start would let the whole table be scored once, blind.

A pre-registered prediction of a trial result. This is the strongest evidence a simulator
can produce and nobody does it. Every known-answer check here is retrospective, which
means the answer was known while the model was being built, and no amount of care fully
removes that. Registering a predicted effect size before a trial reports, and then
publishing the comparison whichever way it goes, is a different order of evidence from
reproducing a result that was already in the literature.

## The gate, measured

Nothing above says what the gate actually returns, and it is worth stating because it is not
a pass. Run on this package's own reference algorithm, 34 subjects over 28 days, against the
registration in `validation/gate.py`:

| Criterion | Limit | Four layers | Default, with the site layer |
|---|---|---|---|
| Longest single episode below 54 mg/dL, worst subject | 120 min | 150, fails | 180, fails |
| Peak insulin per hour, worst subject | 25.0 U | 25.90, fails | 24.30 |
| Time in range, median | at least 70% | 80.07 | 74.85 |
| Time below 54 per day, median | 14.4 min | 2.14 | 2.05 |
| LBGI, 90th percentile | 5.0 | 1.32 | 1.10 |

That criterion has since been retired, because chasing it established that it measured the
simulator rather than the system under test: with no algorithm involved at all the model
sits below 54 mg/dL for 203 minutes untreated and saturates near 22 minutes however much
carbohydrate it is given, against a real median of 10. `docs/FIDELITY.md` has the
measurement. What follows is the verdict as it stood when the criterion was still in force.

Both configurations failed, and on a criterion neither the site layer nor any other change
here introduced. The thresholds were registered before the run, so the finding stands rather
than the threshold moving: a limit relaxed after seeing the result is not a limit. What it
says is that the reference algorithm leaves one subject below 54 mg/dL for two and a half to
three hours, in a model with no counterregulation to end a low that nobody treats. Whether
that is the algorithm or the missing physiology is not settled by this run.

It also corrected a guess. Time in range looked like the criterion the site layer would
threaten, since it costs five points. It is not close, at 4.85 points of margin. The
criterion with almost no margin is peak insulin per hour, which fails without the site layer
and passes with it, because a failed set holds the loop against its basal ceiling rather
than letting it stack a correction. The two configurations do not present the same hazard.

## What stays out of reach

Rare events, for the exposure reason at the top. A verdict about a particular person, for
the outcome-spread reason. Anything the model has no mechanism for, which is exercise,
illness and alcohol. How long a severe low lasts, for the counterregulation reason in
`docs/FIDELITY.md`. Infusion site failure is now modelled, but only as absorption dropping
away and being noticed late, which is the form that showed up in the DCLP3 traces and not
the only form a bad site takes. And the two biases whose direction is known:
hypoglycaemia rebound is overstated, so an algorithm judged on how it handles rebound highs
is judged harshly, and the outcome spread is narrow, so an algorithm that relies on
prediction is flattered. They run in opposite directions and do not cancel usefully.
