# How closely does this match real data, and where does it fail

Read this before using anything from this package to argue for a change in treatment.

## The measurement

Eleven statistics, computed identically on simulator output and on real continuous
glucose data. The real reference is the envelope across four cohorts of closed-loop
users, 192 people in total, taken as the minimum and maximum of the four cohort medians.
Each simulator figure is the median across the first ten adult subjects of the generated
population, run for 28 days.

Each column adds one mechanism to the column before it, so a movement is attributable to
a named cause rather than to the bundle.

| Signature | Real range | stock 2008 | +physiology | +behaviour | +loop | +sensor | In range |
|---|---|---|---|---|---|---|---|
| Glucose variability (CV%) | 29.5–34.3 | 25.1 | 26.5 | 31.9 | 28.9 | 29.1 | yes |
| Rise tail P(ΔBG>10/5min) % | 3.7–6.6 | 1.4 | 1.2 | 1.6 | 2.0 | 3.1 | no |
| Autocorrelation @30min | 0.78–0.87 | 0.93 | 0.93 | 0.94 | 0.89 | 0.89 | no |
| Autocorrelation @60min | 0.50–0.68 | 0.83 | 0.82 | 0.83 | 0.70 | 0.69 | yes |
| Outcome SD @stuck-high (mg/dL) | 26.5–33.5 | 18.1 | 17.1 | 19.1 | 20.8 | 21.0 | no |
| Diurnal amplitude (mg/dL) | 34.7–56.3 | 77.1 | 65.1 | 51.2 | 43.8 | 43.5 | yes |
| Hypo recovery to 100 (min) | 50–59 | 107.5 | 93.8 | 66.2 | 62.5 | 50.0 | yes |
| Hypo rebound >180 % | 23.2–28.4 | 0.0 | 4.2 | 50.0 | 69.7 | 50.1 | no |
| Compression lows /30d | 1.9–5.3 | 0.0 | 0.0 | 0.5 | 0.0 | 5.4 | yes |
| Sensor jitter (mg/dL) | 4.5–6.7 | 2.3 | 2.3 | 2.4 | 2.4 | 5.4 | yes |
| ISF drift (weekly %CV) | 8.2–21.7 | 0.0 | 0.0 | 14.6 | 8.6 | 8.6 | yes |

None of the eleven for the bare subjects, seven of eleven with all four layers. All ten
subjects completed every arm.

Reproduce with `python examples/layer_ablation.py`, which takes about an hour serially;
`--arm` runs one column so the five can go in parallel processes. The raw output is in
`docs/*.json`.

## Reading it

The layers do different work and the split is clean.

The physiology layer moves the physiology-linked statistics and nothing else. Glucose
variability rises and the diurnal amplitude comes down towards the real range; the
disturbance statistics do not move at all. That is the measured version of a general
point worth internalising before reaching for a more refined model: refining the
differential equations fixes the statistics that depend on the differential equations.

The behaviour layer supplies the disturbances. Rescue carbohydrate takes hypoglycaemia
recovery from 94 minutes to 66 against a real 50 to 59, an adapting setting takes drift
from a structural zero to 14.6%, and glucose variability crosses into range. Unannounced
meals move the rise tail, though not far enough.

The loop layer supplies the damping. Every added disturbance had left both
autocorrelations high, because nothing was correcting anything, and continuous correction
brings the 60-minute one inside the real range and the 30-minute one to its edge. Variability
settles rather than running away. This was missing from the comparison rather than from
the model: every real cohort here is running automated insulin delivery, and the simulated
person was on open-loop basal-bolus.

The sensor layer closes the two sensor statistics cleanly, as it is the only layer that
can. It also lifts the rise tail from 2.0 to 3.1, which is worth being honest about:
part of that is jitter contributing to five-minute differences rather than more sharp
rises. The rise-tail row should be read as still open.

## The four that did not come right

They are reported rather than tuned away, which matters, because fitting a parameter to a
statistic turns that row from a test into a restatement.

**Hypoglycaemia rebound overshoots badly**, 50% against a real 23 to 28, and gets worse
when the loop is added. The assumption that a person takes a second helping on 35% of
rescues is too aggressive for what these cohorts do. Read as a measurement rather than a
failure, it says real closed-loop users over-treat less, or are mopped up more, than the
standard clinical account of over-treatment implies. One parameter would close this row
and it has deliberately not been touched.

**The rise tail stays short**, 3.1 against 3.7 to 6.6, and the part of the movement that
came from the sensor layer is not really unannounced meals. Real unannounced eating is
probably larger, faster, or more frequent than the schedule here models, and the meal
template is the obvious next thing to attack.

**The 30-minute autocorrelation stays high** at 0.89 against 0.78 to 0.87. The simulated
curve is still smoother at short range than a real one. The 60-minute figure is in range,
so this is specifically about short-horizon structure.

**Outcome spread at stuck-high** moves from 18.1 to 21.0 mg/dL against a real 26.5 to
33.5. This is the one statistic nothing has closed, across this work and everything before
it, including a stochastic insulin-efficacy process aimed straight at it. Whatever makes
real insulin action unpredictable at the half-hour horizon is still not in the model.

That last one is the important limitation and it deserves stating plainly. The spread of
where glucose ends up half an hour after a stuck high is precisely the quantity a dosing
decision is betting on. The simulator is too confident about it. So this package can
stress-test an algorithm for pathological behaviour, and it can rank options, and it
cannot tell you what a dosing change would have done to a particular person. That still
requires a trial.

## Survival

simglucose ends an episode when blood glucose falls below 10 mg/dL, so a truncated series
means the virtual subject did not survive the run. This is easy to miss, because the
analysis is handed whatever series it is given, and any comparison that silently drops
incomplete runs is conditioning on survival.

Every subject completed every arm above, which is a property of the screened population
rather than of the layers: the screen refuses candidates that go below 40 mg/dL on
matched boluses, and 20 of 121 candidates were refused for exactly that. On the
unscreened published personae the same layer ladder loses subjects, with the physiology
layer alone losing two of ten over 28 days and producing time below 70 mg/dL of 4 to 31%.

`Result.completed` records this per subject and `examples/fidelity_check.py` reports it.

## Why these numbers differ from the published personae

The table above is measured on this package's generated subjects. The same ladder run on
the thirty published personae gives a different starting point, notably a much lower
diurnal amplitude and a lower baseline autocorrelation, so three statistics that are out
of range here start in range there.

That is a reason to read this table as a property of this population and not to carry
either set of numbers across. It is also a reason to regenerate with another seed before
believing any result:

```
python -m timsim.population.build --n 100 --seed 7
```

## What the population does and does not add

The 100 subjects are drawn from the joint distribution of the 30 published subjects, so
they are a resampling of that cohort rather than new clinical data. They inherit whatever
the published cohort does not represent, and they carry no independent information about
human variability.

What they add is resolution. With ten subjects per class one awkward subject moves a
cohort median noticeably; with thirty-three it moves it less. The acceptance rate and the
breakdown of why candidates were refused are in
`timsim/population/params/vpop_report.json`.

## Provenance of the parameters

No parameter in the behaviour layer was fitted to any statistic in the table above.
Announcement rates, carbohydrate-counting error and rescue-treatment sizes are clinical
literature figures or explicit modelling choices, recorded with their reasoning in
`timsim/person/behaviour.py`. The sensor layer's two parameters were fitted, on a
different cohort from the one they are evaluated against, and that is stated in
`timsim/sensor/realism.py`.
