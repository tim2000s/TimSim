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
