# simperson

A person-in-the-loop layer over the UVA/Padova virtual patient, and a virtual population
of 100 screened subjects instead of 30.

## Why

A physiological simulator describes a body. Compare its output against real continuous
glucose data and the differences that survive are mostly not about the body at all.

We measured this. Taking eleven statistics that distinguish a real glucose trace from a
simulated one, computed identically on both, the published 2008 personae match three of
them against a reference envelope of 192 real closed-loop users. Adding the headline
refinement of the licensed S2013 model, time-varying insulin sensitivity, closes one more
and pushes two others out. The remaining gaps do not move for any change to the
differential equations, because they are not properties of the equations:

- people eat without telling the algorithm, so real traces carry a fat tail of sharp
  rises that a simulator with announced meals cannot produce
- people eat carbohydrate when they go low, so real hypoglycaemia recovers in about an
  hour rather than nearly two, and overshoots
- the sensor is noisier than the model says, and produces compression lows the model has
  no mechanism for at all
- the algorithm's own sensitivity setting drifts week to week
- and every real cohort is running an automated loop, correcting continuously, which the
  simulated person was not

This package adds those, as layers you can switch on and off independently. With all four
the same eleven statistics go from three in range to six, and the three that remain are
reported rather than tuned away.

## What it does not do

It does not reproduce a specific person's counterfactual trajectory under a dosing change.
Nothing here changes that. One statistic in particular, the spread of where glucose ends
up thirty minutes after a stuck high, is where varying insulin efficacy shows up, and no
layer in this package or any predecessor has closed it. That is the honest limit: this is
a stress-test simulator, and it is not a substitute for a trial.

The 100 subjects are a resampling of a published cohort of thirty. They inherit whatever
that cohort does not represent and they do not add independent information about human
variability. What they add is resolution, so a comparison is less at the mercy of one
awkward subject.

## Install

```
pip install simglucose
pip install -e .
python -m simperson.population.build --n 100
```

The population is generated on your machine rather than shipped, so nothing derived from
the published parameter tables is redistributed here. It takes a few minutes and the
result is deterministic given the seed.

## Use

```python
from simperson import simulate, signatures

r = simulate("adult#001", days=28)
print(r.summary())
# {'name': 'adult#001', 'days': 28, 'completed': True, 'mean': 147.0, 'cv': 29.4,
#  'tir': 77.0, 'tbr': 1.1, 'tar': 21.9, 'insulin_per_day': 56.3, 'rescues': 24,
#  'unannounced_meals': 34, 'isf_weekly_cv': 5.8}
```

A cohort, and how well it matches real data:

```python
from simperson import simulate_cohort, signatures
from simperson.population import names

results = simulate_cohort(names("adult"), days=28)
print(signatures.report(signatures.evaluate(results)))
```

One layer at a time, which is how any claim about a mechanism should be made:

```python
for layers in [(), ("physiology",), ("physiology", "behaviour"),
               ("physiology", "behaviour", "loop"),
               ("physiology", "behaviour", "loop", "sensor")]:
    r = simulate("adult#001", days=28, layers=layers)
    print(layers, round(r.cv, 1), round(r.time_below_70, 1))
```

Your own algorithm, driven through simglucose's controller interface, with the behaviour
layer still supplying unannounced meals and rescue carbohydrate around it:

```python
from simglucose.controller.base import Controller, Action

class MyController(Controller):
    def policy(self, observation, reward, done, **info):
        return Action(basal=0.02, bolus=0.0)

results = simulate_cohort(days=28, controller_factory=lambda name: MyController(None))
```

## The layers

| Layer | Mechanism | What it moves |
|---|---|---|
| `physiology` | insulin sensitivity varying by time of day and day to day | glucose variability, diurnal amplitude |
| `behaviour` | meals announced imperfectly, lows treated with carbohydrate, an adapting sensitivity setting | rise tail, hypoglycaemia recovery, sensitivity drift |
| `loop` | continuous correction with an insulin-on-board bound | autocorrelation, variability |
| `sensor` | measurement jitter and compression lows | the two sensor statistics |

Each is a small, readable module. `simperson/person/behaviour.py` is the one that matters
most and is about 200 lines.

## The population

`simperson/population/derive.py` records something worth knowing about the published
parameter tables: of their 62 columns, only 29 are free. The rest are either constant
across all thirty subjects or determined exactly by the model's own balance equations at
the basal steady state. Those relations are written out there and verified against all
thirty published subjects to twelve significant figures, which is what makes generating
new subjects a matter of sampling the free parameters and closing the rest, rather than
sampling 62 numbers and hoping.

Each candidate is drawn from the joint distribution of the published subjects of its own
class, in a space where the parameters are roughly Gaussian, with the covariance shrunk
towards its diagonal because ten subjects cannot support a 29-dimensional covariance.
Each then has to survive three gates: the balance equations must admit a positive steady
state; left alone on its own basal rate glucose must actually hold near its fasting value;
and given three meals with matched boluses it must stay inside 40 to 500 mg/dL on a
plausible daily dose. The acceptance rate and the breakdown of refusals are written to
`params/vpop_report.json` rather than hidden.

## Relationship to simglucose

This is a layer on top, not a fork. simglucose supplies the differential equations, the
sensor and pump models and the environment loop, and its interfaces are used unchanged, so
a controller written for simglucose runs here without modification. The published
parameter tables are read from your simglucose install and are not redistributed.

## Reading a result

Statistics are reported with a bootstrap interval and an explicit verdict against the real
range. A point estimate on its own is not a finding. Where this package's output is used
to argue for a change in treatment, the counterfactual caveat above applies and should be
stated: the simulator ranks options, and a within-person trial decides.

## Licence

MIT. simglucose has its own licence; this package depends on it and does not vendor it.
