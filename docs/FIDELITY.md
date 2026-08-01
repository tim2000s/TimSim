# How closely does this match real data, and where does it fail

Read this before using anything from this package to argue for a change in treatment.

## The measurement

Eleven statistics, computed identically on simulator output and on real continuous
glucose data. The real reference is the envelope across four cohorts of closed-loop
users, 192 people in total, taken as the minimum and maximum of the four cohort medians.
Each simulator figure is the median across ten adult subjects run for 28 days, with a
bootstrap 95% interval.

Each column adds one mechanism to the column before it, so a movement is attributable to
a named cause rather than to the bundle.

| Signature | Real range | 2008 | +physiology | +behaviour | +loop | +sensor | In range |
|---|---|---|---|---|---|---|---|
| Glucose variability (CV%) | 29.5–34.3 | 23.1 | 31.6 | 36.1 | 28.0 | 28.2 | no |
| Rise tail P(ΔBG>10/5min) % | 3.7–6.6 | 1.0 | 1.4 | 2.1 | 2.6 | 3.8 | yes |
| Autocorrelation @30min | 0.78–0.87 | 0.84 | 0.90 | 0.93 | 0.85 | 0.85 | yes |
| Autocorrelation @60min | 0.50–0.68 | 0.66 | 0.76 | 0.81 | 0.61 | 0.60 | yes |
| Outcome SD @stuck-high (mg/dL) | 26.5–33.5 | 20.8 | 20.4 | 22.0 | 23.7 | 23.9 | no |
| Diurnal amplitude (mg/dL) | 34.7–56.3 | 46.9 | 64.2 | 46.3 | 39.4 | 39.2 | yes |
| Hypo recovery to 100 (min) | 50–59 | 112 | 110 | 62 | 62 | 60 | marginal |
| Hypo rebound >180 % | 23.2–28.4 | 0.0 | 0.0 | 41.3 | 52.8 | 44.9 | no |
| Compression lows /30d | 1.9–5.3 | 0.0 | 0.0 | 0.5 | 0.0 | 3.2 | yes |
| Sensor jitter (mg/dL) | 4.5–6.7 | 2.4 | 2.3 | 2.4 | 2.4 | 5.6 | yes |
| ISF drift (weekly %CV) | 8.2–21.7 | 0.0 | 0.0 | 10.6 | 5.2 | 5.2 | no |

Three of eleven for the stock personae, six of eleven with all four layers.

Reproduce it with `examples/fidelity_check.py`.

## Reading it

The layers do different work and the split is clean.

The physiology layer moves the physiology-linked statistics and nothing else. It closes
glucose variability and pushes the diurnal amplitude and both autocorrelations out. That
is the measured version of a general point: refining the differential equations fixes the
statistics that depend on the differential equations and leaves the disturbances alone.

The behaviour layer supplies the disturbances. Unannounced meals lift the rise tail,
rescue carbohydrate takes hypoglycaemia recovery from 110 minutes to 62 against a real 50
to 59, and an adapting setting gives the drift statistic something to read where it had
been a structural zero. It also pulls the diurnal amplitude back inside, undoing the
overshoot the physiology layer introduced.

The loop layer supplies the damping. Each added disturbance had raised both
autocorrelations further out of range because nothing was correcting them, and continuous
correction brings both back inside. Glucose variability follows the same path,
overshooting to 36.1% without a loop and settling at 28.2% with one. This was missing
from the comparison rather than from the model: every real cohort here is running
automated insulin delivery, and the simulated person was on open-loop basal-bolus.

## The three that did not come right

They are reported rather than tuned away, which matters, because fitting a parameter to a
statistic turns that row from a test into a restatement.

**Hypoglycaemia rebound overshoots**, 45% against a real 23 to 28. The assumption that a
person takes a second helping on 35% of rescues is too aggressive for what these cohorts
do. Read as a measurement, it says real closed-loop users over-treat less than the
standard clinical account of over-treatment implies, presumably because the loop is still
running and mops it up. One parameter would close this row and it has deliberately not
been touched.

**Sensitivity drift falls below range** once the loop is added, 10.6% to 5.2% against a
real 8.2 to 21.7. The loop holds glucose closer to target, so the weekly adaptation has
less error to chase. Real drift is partly physiological rather than purely a response to
outcomes, and this adapter only responds to outcomes.

**Outcome spread at stuck-high** moves from 20.8 to 23.9 mg/dL against a real 26.5 to
33.5. This is the one statistic nothing has closed, across this work and everything before
it, including a stochastic insulin-efficacy process aimed straight at it. Whatever makes
real insulin action unpredictable at the half-hour horizon is still not in the model.

That last one is the important limitation and it is worth stating plainly. The spread of
where glucose ends up half an hour after a stuck high is precisely the quantity a dosing
decision is betting on. The simulator is too confident about it. So this package can
stress-test an algorithm for pathological behaviour, and it can rank options, and it
cannot tell you what a dosing change would have done to a particular person. That still
requires a trial.

## Survival

simglucose ends an episode when blood glucose falls below 10 mg/dL, so a truncated series
means the virtual subject did not survive the run. This is easy to miss, because the
analysis is handed whatever series it is given.

Over 28 days, the physiology layer on its own loses 2 of 10 subjects and produces time
below 70 mg/dL of 4 to 31%. With the behaviour and loop layers, 10 of 10 complete and time
below range is 0.8 to 6.9%. The reason is not subtle: a virtual patient with no
carbohydrate to eat and no loop to withdraw insulin has nothing to stop a low.

`Result.completed` records this per subject and `examples/fidelity_check.py` reports it.
Any comparison that silently drops incomplete runs is conditioning on survival.

## What the population does and does not add

The 100 subjects are drawn from the joint distribution of the 30 published subjects, so
they are a resampling of that cohort rather than new clinical data. They inherit whatever
the published cohort does not represent, and they carry no independent information about
human variability.

What they add is resolution. With 10 subjects per class, one awkward subject moves a
cohort median noticeably; with 33 it moves it less. Regenerating with a different seed is
the check on whether a result depends on one draw, and it is cheap:

```
python -m simperson.population.build --n 100 --seed 7
```

The acceptance rate and the breakdown of why candidates were refused are written to
`simperson/population/params/vpop_report.json`.

## Provenance of the parameters

No parameter in the behaviour layer was fitted to any statistic in the table above.
Announcement rates, carbohydrate-counting error and rescue-treatment sizes are clinical
literature figures or explicit modelling choices, recorded with their reasoning in
`simperson/person/behaviour.py`. The sensor layer's two parameters were fitted, on a
different cohort from the one they are evaluated against, and that is stated in
`simperson/sensor/realism.py`.
