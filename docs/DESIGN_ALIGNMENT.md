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
trial's recorded 47.0. That is the reference loop on the cohort of the table below; the 40
subject meal panel under oref0 SMB delivers 69.1 U/day against 41.1 for the adult Loop
participants, measured 4 September 2026 in `examples/insulin_by_peak.py`, and the matching does
not carry to it.

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
correction factor only for subjects that basal alone cannot make safe. Across the store 272 of 330
subjects clear on the basal lever and keep the physiological correction factor untouched, and 229
run at basal scale 1.00 as well, so for seven tenths of the population titration changes nothing
at all.

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

### Result: the controller accounts for 3.6 points and in the opposite direction

Measured by `examples/controller_crosscheck.py`, both cohorts under both controllers, all four
layers, 28 days, paired per subject over those completing both arms.

| Cohort | Control-IQ stand-in | oref0 SMB | Paired difference, 95 per cent interval | n |
|---|---|---|---|---|
| DCLP3, 84 subjects | 80.8 | 84.4 | -3.32 (-3.89 to -2.10) | 64 |
| Commons, 64 subjects | 82.9 | 84.6 | -2.93 (-3.78 to -1.19) | 48 |

The stand-in is the less favourable controller, not the more favourable one. It spends 4.25
percentage points more time above 180 mg/dL than oref0 does on the same subjects and 1.23 points
less below 70. Running the DCLP3 cohort under the real algorithm instead widens its distance from
the trial participants from 9.5 percentage points to 13.1, so nothing in the gap is explained by
the stand-in flattering the simulator.

The measurement settles a second question it was not built for. The two simulated cohorts behave
almost identically under the same controller, differing by 2.1 points under the stand-in and 0.3
under oref0. The two real populations differ by 8.8, at a median time in range of 71.3 for the
trial arm and 80.1 for the Commons users. So the disagreement between the pairings is not a
property of either cohort or of either algorithm:

    difference between the two pairings' gaps      5.0 points
      of which the controller                      3.6
      of which the cohort                          0.2
      of which the two real populations            8.8, in the opposite direction

A randomised trial arm and a self-selected group of people who chose to build their own closed
loop are different populations, and this simulator resembles the second. Any statement about how
far it sits from real people carries the reference in it, and the honest range is 4.6 percentage
points against the Commons and 9.5 to 13.1 against DCLP3 depending on the algorithm.

The consequence for mechanism C is that it has more to close rather than less. Against the trial
arm under the algorithm those participants actually ran, the shortfall in time above 180 mg/dL is
11.5 percentage points, and under the shipped algorithm it is larger still.

## D. Per-subject engagement

Written after the decile measurement and before implementation. It is the mechanism to build
rather than C, for the reason in the next paragraph.

### What the deciles changed

Time above 180 mg/dL by percentile of subject says the shortfall is not a displacement of the whole
population:

| Percentile | 10 | 25 | 50 | 75 | 90 |
|---|---|---|---|---|---|
| DCLP3 simulated | 8.9 | 10.7 | 15.4 | 19.8 | 25.0 |
| DCLP3 real | 12.0 | 18.5 | 26.9 | 35.7 | 40.6 |
| Commons simulated | 6.0 | 8.0 | 10.9 | 16.7 | 20.5 |
| Commons real | 5.0 | 9.7 | 15.1 | 22.7 | 29.3 |

Against the Commons the simulated best-controlled tenth already carries slightly more time above
180 than its real counterpart, and the difference grows at every percentile above it. A
within-subject episodic term of the kind C proposes moves every subject and would close the median
while leaving the ninetieth percentile 9 to 16 points short. What is missing is a group of people
who do badly, not a worse day for everybody.

### Structure

Every subject in this package announces 80 per cent of main meals and 35 per cent of snacks,
misestimates carbohydrate at a coefficient of variation of 0.25, and carries settings measured from
its own physiology. Real people differ from each other in all three, and they differ together: the
person who misses boluses is also the person counting carbohydrate carelessly and running settings
nobody has revisited. `therapy/profile.py` already names per-subject behaviour as the untested
candidate for the population's narrowness.

So this is one latent draw per subject, held for the run, driving all three. It acts on the odds of
missing a bolus rather than on the probability, which keeps every subject inside zero and one
without a clipping rule, and the same draw scales the carbohydrate estimation error and the
settings accuracy in the same direction.

The population mean is held at its present value and only the spread is added, so the mechanism
supplies a distribution rather than a shift. Any movement in the median is then a consequence of
the outcome being a convex function of the behaviour, which is a property of the model rather than
something imposed.

### Where the spread comes from

Not from either reference population, since both are what the mechanism is judged against. The
between-person spread comes from the published literature on missed and mistimed insulin doses,
which reports a mean of 4.9 missed meal boluses a week with a standard deviation of 3.7 across
individuals, a between-person coefficient of variation of 0.76 on the rate at which a person misses
a bolus (Robinson et al., *Diabetes Technology and Therapeutics* 2021;23(8):845-857, and the pump
alarm study it reviews).

That figure sets one parameter. Solving for the log-odds spread reproducing it gives 1.047, and
holding the population mean while spreading on that scale needs an offset of -0.287, because the
inverse logit is not linear and a spread applied without it would lower the announcement rate as
well as vary it. Both are solved in `engagement_spread_for_cv` rather than asserted, so they can be
rederived if the announcement rate moves. The population it produces announces 80.7 per cent of
main meals against a population value of 80.0, with a tenth to ninetieth percentile of 0.60 to
0.96, a worst subject at 0.17 and 5.2 per cent of subjects announcing fewer than half.

Nothing in the mechanism is chosen by looking at time in range, time above 180 or any glucose
outcome in either reference, which is what keeps every row below a test.

### What would refute it

The criteria are about shape rather than level, because a mechanism that adds spread should be
judged on the distribution it produces.

It must widen the between-subject spread of time in range, presently 0.70 of the reference against
DCLP3 and 0.54 against the Commons, to 0.85 or above in both. Below that it has not supplied the
missing variation whatever it does to the median.

It must produce the tail rather than a shift. The ninetieth percentile of time above 180 mg/dL must
rise from 25.0 towards the real 40.6 by at least half, meaning 32.8 or above against DCLP3, and the
tenth percentile must not rise by more than 3 points. A mechanism that moves both ends equally has
displaced the population and failed on the thing the deciles asked for.

It must not raise time below 54 mg/dL above its present 0.9 per cent. Missing a bolus raises
glucose and cannot lower it, so a mechanism that produces lows has been implemented wrongly.

It must not disturb the meal-announcement contrast, which currently costs the simulated cohort 2.3
percentage points of time in range against a published 2.2. Outside 1.0 to 3.5 points, a result
this package currently gets right has been broken to fix one it gets wrong.

It must not cost completion below 65 of 84 subjects on the DCLP3 cohort.

### Result: refuted, and the loop absorbed it

Measured by `examples/engagement_arm.py`, each cohort under the algorithm its reference population
ran, all four layers, 28 days, both arms rerun on one code version and one settings store.

| | DCLP3 off | DCLP3 on | DCLP3 real | Commons off | Commons on | Commons real |
|---|---|---|---|---|---|---|
| Time in range % | 80.8 | 82.1 | 71.3 | 84.6 | 84.3 | 80.1 |
| Time above 180 % | 15.4 | 15.7 | 26.9 | 10.9 | 11.1 | 15.1 |
| Time below 54 % | 0.9 | 0.7 | 0.2 | 1.1 | 1.2 | 0.4 |
| Spread ratio, time in range | 0.699 | 0.727 | 1.0 | 0.537 | 0.523 | 1.0 |

Paired over the subjects completing both arms, the difference in time above 180 mg/dL is -0.07
percentage points with a 95 per cent interval of -0.47 to +0.34 on DCLP3, and -0.06 with -0.32 to
+0.13 on the Commons. Nothing moved.

The mechanism did what it was built to do at the behavioural level. The share of meals a subject
actually announced ran from 0.57 to 0.78 across the cohort with it off and from 0.32 to 0.93 with
it on, so the arms are not two copies of one configuration and this is a refutation rather than a
plumbing failure. Subjects announcing less do run higher, at a correlation of -0.22 between
announced share and time above 180 on DCLP3, but the effect is far too small to move the cohort.

Every criterion fails. The spread ratio reaches 0.727 against DCLP3 where 0.85 was required and
falls to 0.523 against the Commons. The ninetieth percentile of time above 180 moves from 25.0 to
25.7 where 32.8 was required. Time in range moves the wrong way on DCLP3, rising 1.3 points.

Two criteria that were about not breaking things pass: time below 54 mg/dL falls from 0.9 to 0.7
per cent, and completion holds at 70 of 84.

### What the two refutations have in common

This is the second mechanism to change what reaches the person and leave the outcome where it was.
Weakening the correction factor by a factor of 2.7 moved time in range by 0.3 percentage points
because basal modulation replaced the withdrawn correction insulin. Withholding a third of a
subject's meal boluses moves it by 0.29 because the same modulation covers the meal after the fact.

So the model's difficulty is not in what happens to the simulated person. It is in how completely
the loop recovers from whatever happens, and that is a property the excursion durations already
recorded: DCLP3 excursions above 180 mg/dL have a median duration of 65 minutes and a ninetieth
percentile of 265, against 40 and 190 for this model with the site layer off. The peaks match and
the durations do not. A simulator whose excursions end too quickly cannot accumulate time above
range however many excursions are provoked, which is what both of these arms have now demonstrated
from opposite directions.

The next measurement is therefore about recovery rather than about provocation, and
`examples/hyperglycaemia_gap.py` already produces the duration distribution it needs.

### Disposition

Kept and off, as `BEHAVIOUR_SPREAD_CV` and the activity layer are. The mechanism is a better
description of a population than a single announcement rate applied to everybody, it costs
nothing, and it slightly improves the measure this package is furthest out on. It does not do what
it was built for and the row above says so.

## The recovery rate matches, and the durations say something else

Both refutations above ended by pointing at excursion durations: this model's excursions above 180
mg/dL have a median of 40 to 45 minutes against the trial's 60 to 65, which was read as the loop
recovering too completely. Measured directly (`examples/excursion_recovery.py`, 40 subjects, 28
days, 2,496 simulated excursions against 37,502 from the trial's calibration participants), the
durations do not support that reading.

| Arm | Excursions/day | Median duration | p90 duration | Median peak | Fall rate | U/day |
|---|---|---|---|---|---|---|
| Configured, closed loop | 2.70 | 45 min | 200 min | 198 | 62.7 | 46.6 |
| Scheduled basal only | 3.80 | 30 min | 545 min | 190 | 44.0 | 23.4 |
| DCLP3 | 3.49 | 60 min | 265 min | 209 | 59.5 | not comparable |

Fall rate is mg/dL per hour from the peak back to the threshold.

The descent rate is right. At 62.7 mg/dL per hour against the trial's 59.5, this model brings a
high down at very nearly the rate the trial's participants did. The duration difference is a
consequence of where the excursion starts from: a peak of 198 is 18 mg/dL above the threshold and
takes 17 minutes to clear at that rate, and a peak of 209 is 29 above and takes 29. Observed fall
times are 20 and 30 minutes. Peak height accounts for the whole of it and nothing is left for the
loop to explain.

The shortfall in time above 180 mg/dL is then frequency multiplied by duration. At 2.70 excursions
a day of 45 minutes against 3.49 of 60, the ratio is 0.581, against a measured ratio of time above
180 of 0.572. So the model needs 29 per cent more excursions and peaks 11 mg/dL higher, and it does
not need slower recoveries.

The open-loop arm settles the other half of the question. Removing the loop entirely halves
delivered insulin, from 46.6 to 23.4 U/day, and the descent still runs at 44.0 mg/dL per hour, so
S2008 does dispose of a glucose load largely by itself. Holding insulin action at basal, the median
subject's net disposal at 260 mg/dL is 1.68 mg/kg/min, a spontaneous fall of 55 mg/dL per hour,
split roughly half between suppression of endogenous production through `kp2` and mass-action
uptake, with renal excretion contributing 3 per cent above the model's threshold of 183 mg/dL.

That glucose effectiveness is worth suspecting on the literature, since glucose-induced suppression
of endogenous glucose production is impaired in insulin-deficient type 1 diabetes and needs
permissive insulin to act at all. But it cannot be adjusted on the strength of the durations,
because the durations are already right. Lowering it would raise the peaks, which is wanted, and
slow the descent, which is not: the descent has 3.2 mg/dL per hour of headroom before it leaves the
trial's rate behind. Any change to that term has to be judged on peak height with the descent rate
held as a constraint rather than as a target, and it does nothing about the 29 per cent shortfall
in how often an excursion happens at all.

## Where in the day the deficit lives

Measured by `examples/day_profile.py`, 72 completing subjects of the DCLP3 cohort against the
trial's calibration participants, mean glucose by hour of day, both sides' hours computed from
their own clocks.

The deficit is not uniform. It spans +8.0 to -26.8 mg/dL across the day, so the displacement
reading, under which peaks 11 mg/dL low and 29 per cent fewer crossings were one downward shift,
does not survive either. Its share by window:

    21:00 to 03:00    43.0 per cent of the whole day's deficit, in a quarter of the day
    03:00 to 09:00     2.6 per cent
    09:00 to 15:00    25.4 per cent
    15:00 to 21:00    29.0 per cent

The two traces have different shapes rather than different levels. The participants' day is one
long climb: from a nadir of 134.8 mg/dL at 06:00 they rise more or less monotonically to 167.7 at
22:00, hold above 160 from 20:00 to midnight, and decay slowly through the night to the next
nadir. The simulated day is flat with three bumps: meal rises at 08:00, 14:00 and 20:00, each
returned to a baseline near 134 within about three hours, including the dinner rise, which is
cleared by 02:00 while the participants' evening glucose is still at 152.

The inter-meal troughs say it most compactly. The simulated cohort returns to 132 to 135 mg/dL
between every pair of meals, which is its own fasting level, so each meal starts from scratch. The
participants' troughs ratchet upward through the day, 136.8 at 07:00, 151.4 at 11:00, 156.3 at
17:00, so each meal starts from the incompletely cleared remains of the last. The descent rate
being right and the excursions being too short are reconciled here: real excursions are long
because the next input arrives before the last one has cleared, not because the fall is slow.

Two hours of the day the simulator is not low but high: +8.0 at 07:00 and +4.3 at 06:00, which is
the template's 07:00 breakfast landing at the participants' nadir. Real breakfasts evidently land
later.

This points away from mechanism B. Closed-loop downtime raises the trace wherever it falls and
would fill the 03:00 to 09:00 window, where the deficit is 2.6 per cent of the total, as readily
as the evening, where it is 43. What the shape asks for is input into the evening and night that
the template does not currently supply, and a check on when the template eats at all. Both are
measurable from records rather than tunable: the Commons carbohydrate entries carry timestamps,
`examples/real_meals.py` already parses them, and an hour-of-day distribution of real logged
intake is usage data of the same standing as the announcement literature, not a glucose outcome.
The candidate the evening deficit suggests beyond timing is absorption that outlasts the entry,
since a mixed evening meal absorbing over four to six hours puts glucose into exactly the 22:00 to
02:00 window this table finds empty, and that has literature to ground it independently of any
reference trace.

## E. The intake clock

Written after the day decomposition and the intake extraction, and before any glucose measurement
of the change.

### Structure

The meal template is regrounded on when real people log carbohydrate. The extraction
(`examples/intake_clock.py`) places 292,140 entries from 147 Commons users at their local hour
through the timezone each user's own profile records, so no clock is inferred. The measured
distribution disagrees with the template at both ends of the day: real intake peaks at 08:00 where
the template's breakfast sat at 07:00, and the six hours from 21:00 to 03:00 carry 12.8 per cent
of real grams against the template's 3.6. That empty night window is the one carrying 43 per cent
of the mean-glucose deficit against DCLP3, and the too-early breakfast is the one window where the
simulator runs high.

The new template reproduces the measured share of grams in every window to within 0.7 percentage
points, at 5.2 eating occasions a day against a logged 5.56 and the old template's 3.64. Total
intake is held near the old level, 192 g/day expected at 70 kg against a logged median of 162,
because logged grams under-state eaten grams and the under-statement cannot be placed by hour.

Nothing in the template was chosen by looking at a glucose trace. The grounding is logged usage
from the Commons; DCLP3 was not consulted at all, and the Commons glucose outcomes were not
consulted either, so both pairings remain tests.

### What it forces

The meal schedule is part of the person rather than a layer, so this changes every arm including
stock, and it changes what titration finds. The whole chain reruns: titration, the four baseline
arms, and the day profile. When the chain lands, every measurement bound to settings store a37df6ce, including the tables in
`docs/BASELINE.md`, describes the previous template and says so in its provenance.

### What would refute it

Fixed before the chain runs.

The night deficit must close by at least a third. The six hours from 21:00 to 03:00 carry 43.0 per
cent of the whole day's mean-glucose deficit, with per-hour gaps of -20 to -27 mg/dL from 22:00 to
02:00; after the change the mean gap over that window must shrink by at least a third of its
current size.

The breakfast overshoot must close. The simulator runs +8.0 mg/dL at 07:00 and +4.3 at 06:00
against participants at their nadir; both hours must come to within 5 mg/dL of the reference or
below it.

Time below 54 mg/dL must not exceed 0.9 per cent on the DCLP3 pairing. Night eating with a loop
active is a route to overnight lows, and hypoglycaemia is already the measure furthest from real.

The meal-announcement contrast must stay between 1.0 and 3.5 percentage points of time in range on
the means, against CLOSE-IT's published 2.2. More night snacks means more unannounced
carbohydrate, and a contrast pushed outside that band has broken a result the package gets right.

Completion must not fall below 65 of 84 on the DCLP3 cohort.

Every signature in `docs/FIDELITY.md` is reported with the change, whatever the criteria above
say.

### Result: refuted on its primary criterion, and the template is kept anyway

The chain ran overnight on 23 to 24 August: retitration, the four arms, the day profile. Verdicts
against the criteria as fixed:

    night deficit closes by a third      FAIL   mean gap over 21:00-03:00 went 22.4 to 20.4
                                                mg/dL, a 9 per cent reduction
    breakfast overshoot closes           PASS   +8.0 at 07:00 became -1.7, +4.3 at 06:00
                                                became -0.4
    time below 54 at or under 0.9        PASS   0.55 per cent, from 0.9
    announcement contrast 1.0 to 3.5     PASS   +1.29 points on the means
    completion holds                     PASS   79 of 86, above the scaled floor of 67

The night window took some of what it was given, its share of the deficit falling from 43.0 to
36.1 per cent, but most of the added intake was absorbed as everything else has been: the loop
covers an announced snack and trails an unannounced one, and either way glucose is returned before
the hours the deficit lives in. Meanwhile the rest of the day moved the wrong way. Splitting the
old template's three large meals into smaller and more frequent ones makes each rise easier to
correct, so time above 180 mg/dL on the default arm fell from 15.4 to 13.7 per cent and time in
range rose from 80.8 to 83.3 against a reference 71.3. Eleven more subjects also cleared
titration, 306 against 295, for the same reason.

The template stays despite the refutation, because its grounding does not depend on what it was
hoped to do to glucose. It reproduces the logged intake clock of 147 real users to within 0.7
percentage points per window where the old template disagreed with that record by a factor of 3.6
at night, and the two criteria that measure its local consequences, the breakfast hours and the
announcement contrast, both pass. What is refuted is the hypothesis that the intake clock explains
the night deficit, and the row above records that.

### Three absorbed perturbations are a finding about the model

Every input-side change tried has now been absorbed by the loop and the model together:

    correction factor weakened 2.7-fold        time in range moved 0.3 points
    a third of meal boluses withheld           0.29 points
    night intake raised 3.6-fold               night gap closed 9 per cent

Real closed-loop cohorts do not behave this way: their evening glucose persists into the night at
150 to 167 mg/dL under the same class of controller. A model in which no input-side perturbation
can produce sustained elevation, combined with a measured spontaneous disposal of 55 mg/dL per
hour at 260 mg/dL with insulin held at basal, says the disposal side is too strong rather than the
input side too gentle. The remaining candidate is glucose effectiveness, `kp2` and the
insulin-independent part of utilisation, which the clamp literature reports impaired in type 1
diabetes and which S2008 inherited from identification that included people without it. Any change
there is a physiology change, to be made switchable, grounded on the published impairment rather
than on any reference trace, and judged on peak height with the descent rate held as a constraint,
since the descent is currently right at 62.7 against a real 59.5 mg/dL per hour and has 3.2 of
headroom.

## Where the residual is now believed to live

This section has been rewritten twice and the previous version is recorded here because it was
acted on. It attributed the residual to the liver's insulin delay, measured in `docs/PADOVA_AUDIT.md`
entry 3, and reported that no value of `ki` met both the clamp and the meal, so that the model
could not represent the response and correcting it meant two insulin actions on the liver. A
two-timescale liver was built on that reading. Both halves are withdrawn. The two gates were
measured on different populations and the meal gate returned the same verdict with the mechanism
switched off (`docs/ISSUES.md` 44 and 45), and the two-timescale liver satisfied both gates only at
a fast fraction of 1.0, which is a single-timescale liver at 10.5 times the published rate with
the published pathway carrying none of the gain (`docs/SPEC_VS_OUTPUT.md`,
`docs/measurements/liver_two_timescale.json`). The delay is still the largest divergence the audit
has measured whose direction matches the residual, and nothing has been shown either way about
whether it produces it.

What is currently supported is a gap on one quantity, measured on one protocol. Reading every meal
a subject eats over 42 days through the definition in `timsim/analysis/meal_shape.py`, on the
record a person leaves (the meals they entered, at the grams they entered), the simulated rise
under oref0 SMB at a 240 minute window is 11.8 mg/dL per 10 g (8.8 to 14.6 across 36 subjects)
against a real 15.8 (10.4 to 22.9 across 470 adult Loop participants), from
`docs/measurements/sim_meal_shape_announced_oref.json` and `real_meal_shape.json`. Covered meals
read 11.5 against 15.1 and uncovered 15.7 against 21.4. Time to peak on the same record is 95
minutes against 85. Until 4 September 2026 the reference pooled Loop's children with its adults
and read 17.0, 16.5, 23.6 and 80 (issue 52); the panel being adult, the adult figures are the
comparison, and the covered gap is 3.6 mg/dL per 10 g rather than 5.0.

Two explanations for that gap have been tested this week and neither holds. The controller was
not it: on a panel held fixed across four drivers the spread between them is 3.3 mg/dL per 10 g
against a gap to real of 6.5 to 9.5, and the earlier attribution to oref0 was the panel changing
under it (issue 50). The denominator was not it either: the simulated side had divided by grams
eaten where the real side can only divide by grams logged, and correcting the record moved the
rise 0.4 mg/dL per 10 g [-0.1, 1.1] paired on 35 subjects (issue 51,
`docs/measurements/meal_record_pairing.json`). Weakening the glucose brake `kp2` symmetrically
raises the rise and terminates 17 to 22 of 40 subject-arms hypoglycaemic, because the same
coefficient is the stock model's only glucose-driven defence against a fall (audit entry 5); the
asymmetric form has not been shown to close the gap.

The carbohydrate estimate bias was the next candidate. `CARB_ESTIMATE_BIAS` in
`timsim/person/behaviour.py` is held at 1.0 while the meal schedule already assumes people log
0.84 of what they eat, and a value of 0.84 was pre-registered and run on 4 September 2026
(`examples/carb_bias.py`). Paired on the 32 subjects that completed both biases under oref0 SMB,
the covered rise on the announced record moved from 11.2 to 12.8 mg/dL per 10 entered grams,
+1.8 [0.8, 2.8], which is less than the 13.3 the denominator alone gives and short of the 13.9
the rule required; on the eaten record it moved -0.2 [-0.7, 0.7], so the smaller bolus added
nothing the controller did not replace. Insulin fell under 1 per cent where the entry fell 16,
no outcome or signature moved past its interval, and the hypoglycaemia rebound left the real
range (28.5 to 37.7 per cent against an upper edge of 39.2 on the base interval). The parameter
stays at 1.0.

The insulin delivered by the peak was then measured on both sides, since each of the input-side
perturbations had been absorbed by the loop within the window (`examples/insulin_by_peak.py`,
`docs/measurements/insulin_by_peak.json`). From 30 minutes before the entry to the peak, per 10
entered grams on covered meals at 240 min, the simulated loop delivers 1.96 U (1.41 to 2.87
across 36 subjects) against 1.77 for the adult Loop participants (1.17 to 2.74 across 470) and
1.66 for ReplaceBG, arranged differently: a meal bolus of 0.75 U against 1.00, which is the
titrated carbohydrate ratio, and 1.31 U added after the entry against 0.71. The dose by the peak
is higher on the simulated side, by 11 per cent, on a rise 24 per cent lower, so the controller
cannot be excluded as part of the shortfall and has not been shown to be the whole of it. Over
the day the panel takes 69.1 U/day against 41.1, with the bolus share at 0.70 against 0.38; with
the excess by the peak at 11 per cent, most of that sits after the peaks, on runs recording 2.0
rescue helpings a day.

The run that separates the two was done on 5 September 2026 (`examples/insulin_profile_rise.py`,
`docs/measurements/insulin_profile_rise.json`). Forty subjects over 42 days were driven by the
built-in correction loop between meals and by a fixed insulin profile inside them, in four arms
paired per subject: the loop alone, the simulated loop's quantities (0.75 U per 10 g at the
entry, 1.96 by the peak over 91 min), the adult Loop record's (1.00 and 1.77 over 85 min), and
the real bolus with the loop back after 30 minutes. The profiles reached the body, the insulin by
the peak ordering as the arms were built (1.84, 1.76, 1.69 U per 10 g at 240 min, the loop alone
1.65), and the rise did not follow it: 10.3, 10.3, 10.6 and 9.9 mg/dL per 10 g, with the real
profile against the simulated one at -0.07 [-0.75, 0.50] at 240 min and +0.03 [-0.99, 1.03] at
300. The rule registered before the run placed the gap in the physiology at a difference under
1.0 with the interval clear of 1.8, and both windows meet it. The method check on the simulated
arm fell 0.2 outside its allowance (10.3 against the loop's 11.5 at 240 min, where 1.0 was the
tolerance), which is the profile spreading to the peak what oref0 SMB places in the first half
hour. The four arms span 1.65 to 1.84 U per 10 g by the peak and 9.9 to 10.6 mg/dL per 10 g of
rise, against 15.1 on the adult record, so how the insulin is placed within that range moves the
peak by under 1 mg/dL per 10 g and the shortfall of 4.5 to 5.2 sits in the model's glucose
appearance and disposal. The rise is recorded as a bound in `docs/VALIDATION.md` and is not
pursued further here.

One candidate remains open. The disposal interaction in audit entry 6, where disposal is right
on each axis and 28 per cent too high on both together (13 per cent once production is counted
with it), runs in the direction the residual needs at about a fifth of its size, and neither
`Km0` nor a disposal exponent moves it.

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
