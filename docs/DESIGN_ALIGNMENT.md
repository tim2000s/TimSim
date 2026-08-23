# Two mechanisms for the time-in-range gap, and what would refute each

Written before either is built and before the correction-factor sweep reported, as the
counterregulation and hypoglycaemia designs were, so the criteria cannot be chosen once the
answer is known.

## The gap being addressed

Against the closed-loop arm of DCLP3, the simulator as configured spends 9.5 percentage points
more time in range than the participants, at 80.8 against 71.3. The whole of that difference sits
above the range rather than below it:

    time in range           80.8 against a real 71.3      +9.5
    time above 180 mg/dL    15.4 against a real 26.9     -11.5
    time below 70 mg/dL      3.1 against a real  1.4      +1.7
    mean glucose           141.1 against a real 155.4    -14.4

The simulator is not short of hypoglycaemia. It is short of hyperglycaemia, and it is short of it
in long excursions: the trial spends 9.4 per cent of its time in excursions lasting three to six
hours and 6.6 per cent in excursions past six hours, against 4.7 and 0.9 for the model with the
site layer off.

Four candidate explanations are already refuted by measurement rather than by argument.

Meal announcement is not the explanation. The unannounced arm tells the algorithm about no meal at
all and still reaches 77.0 per cent.

Survivor bias is not the explanation. Twelve of 84 subjects terminate under the layers and they are
the worse-controlled ones, at a stock time in range of 83.2 against 90.8 for those that survive.
Assigning every terminating subject a time in range of 40 per cent moves the cohort median from
80.8 to 80.0.

Insulin quantity is not the explanation. The cohort delivers 47.6 U/day at the median against the
trial's recorded 47.0.

The carbohydrate ratio is not the explanation in the direction required. The population median is
10.4 g per unit where the trial recorded 8.0, so the simulated ratio doses meals more weakly than
the participants' did, which raises glucose rather than lowering it.

## What the settings actually are

Each generated subject carries a correction factor measured from its own model at nominal
parameters. Compared against the clinical rule applied to that same subject's own total daily
insulin:

    physiological correction factor as a fraction of the 1800 rule
      median 0.57, IQR 0.40 to 0.79, tenth to ninetieth percentile 0.28 to 0.98
      90 per cent of subjects are dosed more strongly than the rule would dose them

    rule-derived correction factor   median 40.3 mg/dL per unit, IQR 29.7 to 64.8
    DCLP3 recorded                   median 40.0 mg/dL per unit, IQR 30.0 to 50.0
    titrated value in use            median 19.6 mg/dL per unit, IQR 13.3 to 28.9

The rule applied to this population reproduces the trial's recorded median to within 0.3 mg/dL per
unit. What the benchmark hands the algorithm is roughly half of it.

The titration ladder does not correct this, because it searches basal first and reaches the
correction factor only for subjects that basal alone cannot make safe. Across the store 253 of 295
subjects clear on the basal lever and keep the physiological correction factor untouched, and 204
run at basal scale 1.00 as well, so for two thirds of the population titration changes nothing at
all.

## A. Clinically derived settings

### Structure

A subject's correction factor and carbohydrate ratio come from its own total daily insulin through
the rules a clinic uses, with a per-subject multiplier carrying the spread the trial records,
rather than from its own physiological response. Titration then runs on top exactly as now,
weakening further where the hypoglycaemia floors are not met.

The correction factor takes the 1800 rule directly, since that rule applied to this population
already reproduces the trial's median. The carbohydrate ratio cannot: the 500 rule gives 11.2 g per
unit against a recorded 8.0, so real practice doses meals more strongly than the rule and the
multiplier for that lever is set from the trial's recorded distribution instead.

The multiplier is fitted to the participants' recorded pump settings and to nothing else. It is not
fitted to time in range, to time above 180 or to any glucose outcome, and that distinction is what
keeps the arm a test rather than a calibration.

### Why it should work

It moves the lever that the decomposition points at, in the direction the decomposition requires,
by an amount two independent sources agree on. It also does something no ablation in this package
has done: it widens the settings distribution, where the physiological values are narrow because
they are measured from a population closed at its own steady state. The simulated cohort has no
badly controlled subject at all, with a worst time in range of 66.0 against the trial's 53.4, and
under-corrected subjects are the obvious missing kind.

### What would refute it

Fixed before the sweep reported.

It must carry the DCLP3 median time above 180 mg/dL at least half way from 15.4 to the trial's
26.9, meaning 21.2 or above. Below that the settings are a contributing term and not the
explanation, and the remaining gap belongs to something else.

It must not overshoot past the trial's own interval. A median above 180 exceeding 32 per cent, or a
time in range below 62 per cent, says the lever has been pushed past real practice and the
agreement is coincidental.

It must not degrade hypoglycaemia. Time below 54 mg/dL is already 0.9 per cent against a real 0.2,
and any value above 0.9 refutes the mechanism regardless of what it does above the range. The
expectation is that weaker corrections improve this measure, and failure to improve it is itself
informative.

It must not cost completion. Below 65 of 84 subjects completing, against the present 72, the
cohort has changed identity and the medians are no longer comparable.

It must not break the Commons pairing. Mean glucose there currently agrees with the reference at
132.9 against 134.9, and a mechanism that fixes DCLP3 by moving the Commons out of agreement has
traded one pairing for another rather than improved the model.

Every signature in `docs/FIDELITY.md` is reported with it, whatever the five criteria above say.

### Result: refuted on its primary criterion

Measured by `examples/settings_sweep.py` on the 84-subject DCLP3 cohort under the Control-IQ
stand-in, all four layers, 28 days, multipliers applied on top of the adopted titration:

| Multiplier | Correction factor | Completed | TIR % | TAR180 % | TBR70 % | TBR54 % | Mean glucose | U/day |
|---|---|---|---|---|---|---|---|---|
| 1.00 | 17.1 | 72 | 80.8 | 15.4 | 3.1 | 0.9 | 141.1 | 47.6 |
| 1.50 | 27.9 | 76 | 80.7 | 16.4 | 2.6 | 0.7 | 144.3 | 46.8 |
| 2.00 | 34.5 | 76 | 81.0 | 16.8 | 2.2 | 0.6 | 145.7 | 46.0 |
| 2.50 | 46.6 | 75 | 80.8 | 16.9 | 2.1 | 0.5 | 146.1 | 45.3 |
| real | 40.0 | 67 | 71.3 | 26.9 | 1.4 | 0.2 | 155.4 | 47.0 |

Time in range does not move at all. Across a 2.7-fold weakening of the correction factor, which
carries it from well below real practice to well above it, the cohort median stays between 80.7 and
81.0 per cent. Time above 180 mg/dL rises by 1.5 points against the 5.8 the criterion required, so
the mechanism is refuted as an explanation of the gap.

The reason is visible in the last column. Total insulin falls by 5 per cent, from 47.6 to 45.3
U/day, while the correction factor weakens by a factor of 2.7. The loop replaces what the
correction channel stops delivering, because basal modulation rises with predicted glucose and
carries on doing so whatever the correction factor says. A feedback controller with a second
channel is not sensitive to the first.

This contradicts the older arm in `docs/gap_settings.json`, where the same lever at a comparable
magnitude took time in range from 83.3 to 76.7 per cent. That arm ran under the `trend` driver,
which corrects towards 120 mg/dL on every five-minute reading, so the correction factor is its
dominant control channel and there is nothing to compensate. Sensitivity to settings is a property
of the controller rather than of the person, and a settings result measured under one driver does
not transfer to another.

Two of the five criteria pass and are worth keeping. Hypoglycaemia improves monotonically: time
below 54 mg/dL falls from 0.9 to 0.5 per cent against a real 0.2, and time below 70 from 3.1 to 2.1
against a real 1.4. Completion rises from 72 to 75 of 84. So clinically derived settings are
defensible on their own terms and address the hypoglycaemia gap, which is the other place this
package sits furthest from real people. They are not an answer to the time-in-range gap.

## B. Closed-loop downtime

### Structure

The simulated system closes the loop on every cycle of every run. Real systems do not: sensors
warm up, sessions end, transmitters drop out and pumps are disconnected, and through all of it the
algorithm reverts to scheduled basal with no automatic correction. DCLP3 participants were in
closed loop about 90 per cent of the time.

The mechanism is a per-subject uptime drawn to reproduce that distribution, realised as episodes
rather than as scattered minutes, since an hour without a sensor is a different thing from twelve
five-minute gaps.

### Why it should work

It removes correction from a tenth of the run without touching the settings, and it removes it in
blocks long enough for glucose to run. It also carries between-subject spread of the kind the
population lacks, because uptime varies far more between people than the median suggests.

### What would refute it

It must move the DCLP3 median time above 180 mg/dL by at least 2.5 percentage points. Less than
that and a tenth of the run is not where the missing hyperglycaemia lives, which would itself be
worth knowing, since it would say the gap is in how the loop behaves rather than in whether it is
running.

It must not raise time below 54 mg/dL above the present 0.9 per cent. Open-loop basal during a
fall is a route to hypoglycaemia as well as to hyperglycaemia, and if the measure moves the wrong
way the mechanism is trading the gap it addresses for the one that is already worst.

It must widen the between-subject spread of time in range from the present 0.70 of the reference
towards 1.0. A mechanism that shifts the median without widening the distribution has not supplied
the missing tail, and the tail is half of what is wrong.

## C. One-sided episodic insulin resistance

Added after A was refuted, so its criteria are fixed before it is built but not before A reported.

### Structure

Occasional episodes during which a subject's insulin sensitivity is reduced, lasting from half a
day to several days, with no matching episodes of raised sensitivity. Real people have intercurrent
illness, menstrual cycles, corticosteroids and periods of stress, and all of them raise insulin
requirement for a while and then stop. Nothing in this package represents any of them.

The asymmetry is the point and distinguishes it from `SLOW_CV` in `patient/varying.py`, which
already supplies a multi-day sensitivity term at a coefficient of variation of 0.15 and a
correlation time of nine days. That term is lognormal and centred, so it gives a resistant week and
a sensitive week in equal measure, and the sensitive weeks return glucose that the resistant weeks
took away. A one-sided term does not.

### Why it should work

It is the only remaining structure that produces sustained hyperglycaemia a feedback loop cannot
correct. The sweep above shows that weakening the settings does not, because the loop compensates.
The site layer already supplies episodic under-delivery and is calibrated against the trial's
excursion duration distribution, and pushing it further overshoots the excursion peaks by 17 mg/dL
at the ninetieth percentile, which is recorded in `therapy/site.py`. A resistance episode raises
insulin requirement without capping delivery, so it lengthens excursions without sharpening them.

It should also add hyperglycaemia without adding hypoglycaemia, which matters because time below 54
mg/dL is already four times the reference and is the measure every other mechanism has made worse.

### What would refute it

It must carry the DCLP3 median time above 180 mg/dL at least half way from 15.4 to 26.9, meaning
21.2 or above, at a magnitude and frequency set from the literature on illness and cycle-related
insulin requirement rather than from the outcome.

It must not raise time below 54 mg/dL above its present 0.9 per cent. A one-sided resistance term
that produces lows has been implemented wrongly.

It must lengthen the excursion duration distribution rather than raise its peaks. The trial spends
9.4 per cent of its time in excursions of three to six hours and 6.6 per cent past six hours; the
ninetieth percentile of excursion peaks is 293 mg/dL against a simulated 260 to 282. A mechanism
that reaches the time by raising peaks past 293 has matched a total by the wrong route.

It must not narrow the between-subject spread of time in range, presently 0.70 of the reference.

## What the gap may not be the person's at all

The DCLP3 pairing runs a stand-in for Control-IQ whose unpublished parameters are, by the admission
in `controller/loop.py`, the ones that drive the result: the basal multiplier when glucose is
predicted high, the ceiling on a single automatic correction, and the prediction itself. The
Commons pairing runs oref0 SMB, which is the real algorithm rather than a shape resembling it, and
its gap is 4.6 percentage points of time in range against the DCLP3 pairing's 9.5.

That difference has to be accounted for before any person-side mechanism is judged, because a
mechanism sized to close 9.5 points will overshoot if half of the 9.5 belongs to the controller.
The measurement that separates them runs one cohort under both controllers and compares the
simulated arms with each other, which needs no real reference and costs one cohort-pair of runs.

## What is deliberately not proposed

A term fitted to time in range. Every parameter in this package that was fitted to the statistic it
is judged on has had to be withdrawn, and the counterregulation gain is the most recent.

Turning on the activity layer. It is off because it makes the simulated person more predictable
rather than less, and its own docstring records the measurement. It may well belong in the model
for other reasons, but it is not a candidate for this gap.

Widening the physiological population. Individual population fitting is refuted and recorded as
such, and the between-subject spread on the location measures is a consequence of every subject
being closed at its own steady state, which is load-bearing for the titration and for the
published-subject closure test.
