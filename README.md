# TimSim

A person-in-the-loop layer over the UVA/Padova virtual patient, with a virtual population
of 100 screened subjects in place of the usual 30.

## Why

A physiological simulator describes a body. Compare its output against real continuous
glucose data and most of the differences that survive turn out to have nothing to do with
the body.

We measured that. Eleven statistics distinguish a real glucose trace from a simulated one,
computed the same way on both. Against a reference envelope drawn from 192 real closed-loop
users, the bare subjects match three of the eleven: how wide the glucose distribution is,
and how fast the curve decorrelates at thirty and sixty minutes. Adding the headline
refinement of the licensed S2017 model, which is time-varying insulin sensitivity, takes
that to none of the eleven and kills half the cohort, because a subject whose sensitivity
moves and who has nobody to eat carbohydrate for them does not survive a month. That is not
a quirk. simglucose implements S2008, which has no counterregulation at all, so a subject
going low here is defended by carbohydrate or by nothing. The gaps
that remain are unaffected by changes to the differential equations, because they are not
properties of the equations:

- people eat without telling the algorithm, so real traces carry a fat tail of sharp rises
  that a simulator with announced meals cannot produce
- people eat carbohydrate when they go low, so real hypoglycaemia recovers in about an
  hour rather than nearly two, and overshoots
- the sensor is noisier than the model says, and produces compression lows that the model
  has no mechanism for
- the algorithm's own sensitivity setting drifts week to week
- every real cohort is running an automated loop, correcting continuously, so the
  simulator has to be driven by one to be comparable at all

This package adds those as layers, each of which can be switched on and off independently,
along with a fifth the comparison turned up later: infusion sets that stop absorbing and get
noticed hours afterwards, which is where most real time above 180 mg/dL comes from.

How well that works is judged two ways, and they disagree. A classifier given 24-hour
windows of this simulator and of the DCLP3 trial's closed-loop participants, holding out
whole subjects, separates them at 0.671 where a published subject with no layers scores
0.937 and a null sits near 0.52. On the eleven marginal statistics the same configuration
scores five of eleven, and a four-layer version without the site layer scores eight while
being easier to tell from real data in ten splits out of ten. The default is the arm that
wins the stronger test and loses the weaker one. Both numbers, and the argument, are in
[docs/FIDELITY.md](docs/FIDELITY.md).

## What it does not do

It will not reproduce a specific person's counterfactual trajectory under a dosing change.
The statistic that decides this is the spread of where glucose ends up thirty minutes after
a stuck high, which is where varying insulin efficacy shows up and which is the quantity a
dosing decision bets on. That spread has moved a long way, from 21.0 mg/dL through 25.5 to
27.0 against a real 26.5 to 33.5, so it is now inside the range for the first time. It is
one statistic on ten subjects with a bootstrap interval from 22.0 to 30.7, which is not
enough to relax the caveat. Treat this as a stress-test simulator rather than a stand-in
for a trial until that survives the full population and a second seed.

The 100 subjects are a resampling of a published cohort of thirty. They inherit whatever
that cohort fails to represent, and they carry no independent information about human
variability. What they add is resolution, so that a comparison is less at the mercy of one
awkward subject.

Carbohydrate moves these subjects about half as far as it moves real people. Measured
against the DCLP3 participants' own pump settings, a gram raises glucose by 4.2 mg/dL in the
trial and 1.9 in the model, while the carbohydrate ratio agrees at 8.0 against 8.9. The
difference sits entirely in the correction factor, which the model and simglucose's settings
table agree on and the clinic does not. So a miscounted meal, an unannounced one, or
carbohydrate eaten to treat a low costs a virtual subject roughly half what it costs a real
one. That is inherited from the UVA/Padova model and bounds what the behaviour layer can
produce.

## Install

```
pip install simglucose
pip install -e .
python -m timsim.population.build --n 100
```

The population is generated on your own machine rather than shipped with the package, so
nothing derived from the published parameter tables is redistributed here. Generation
takes a few minutes and is deterministic given the seed.

To reproduce a published figure rather than just run the package, install
`requirements-lock.txt` first. It pins the environment every number in `docs/` was measured
in, including simglucose itself, which is the physiological model and not an incidental
dependency.

The validation suite also wants a copy of the DCLP3 trial data, which is public but not
redistributed here. `docs/VALIDATION.md` covers where to get it and what to set `DCLP3_DIR`
to.

## Use

```python
from timsim import simulate, signatures

r = simulate("adult#001", days=28)
print(r.summary())
# {'name': 'adult#001', 'days': 28, 'completed': True, 'mean': 147.0, 'cv': 29.4,
#  'tir': 77.0, 'tbr': 1.1, 'tar': 21.9, 'insulin_per_day': 56.3, 'rescues': 24,
#  'unannounced_meals': 34, 'isf_weekly_cv': 5.8}
```

A cohort, and how well it matches real data:

```python
from timsim import simulate_cohort, signatures
from timsim.population import names

results = simulate_cohort(names("adult"), days=28)
print(signatures.report(signatures.evaluate(results)))
```

One layer at a time, which is how any claim about a mechanism should be made:

```python
for layers in [(), ("physiology",), ("physiology", "behaviour"),
               ("physiology", "behaviour", "sensor"),
               ("physiology", "behaviour", "sensor", "site")]:
    r = simulate("adult#001", days=28, layers=layers)
    print(layers, round(r.cv, 1), round(r.time_below_70, 1))

# and the controller is a separate axis, not a layer
open_loop = simulate("adult#001", days=28, controller="basal-bolus")
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

Judging that algorithm on safety rather than on time in range, with the criteria fixed
before the run:

```python
from timsim.validation import faults, gate

print(gate.fingerprint(design=gate.design_of(results)))   # record this first
print(gate.report(gate.evaluate(results)))
```

`examples/safety_gate.py` runs the whole sequence: register the criteria, measure the
noise floor, inject the fault scenarios, then run the cohort that produces the verdict.
[docs/EVIDENCE.md](docs/EVIDENCE.md) explains what has to be true for that verdict to mean
anything, and [docs/OSAID.md](docs/OSAID.md) covers what an adapter for one of the
open-source systems still needs.

[docs/MODEL.md](docs/MODEL.md) describes the UVA/Padova simulator underneath, taken from the
equations as implemented rather than from the papers, since most of the arguments in the
other documents turn on what that model does and does not contain.
[docs/SIMULATOR.md](docs/SIMULATOR.md) describes what this package puts on top of it, and
[docs/CAPABILITY.md](docs/CAPABILITY.md) states what the result can and cannot be used for,
against the licensed S2013 and S2017 releases and against 101 real users.

The studies live in the Research-Papers repository under `TimSim/`, one file each, written so
that a piece of work can be read on its own: the question, how it was measured, what came out,
and what it means. [docs/papers/](docs/papers/) indexes them. Most are negative, which is not an
accident of presentation. More mechanisms and explanations were refused than adopted, and the
ones that survived did so after two or three candidates had been eliminated by measurement.

## The person, the rig, and the controller

These are three different things and the package keeps them apart. An earlier version did
not, and listed a correction algorithm among the properties of a body.

The person is the layers, each of which switches off independently so that a difference
between two runs is attributable to a named mechanism:

| Layer | Mechanism | What it moves |
|---|---|---|
| `physiology` | insulin sensitivity varying by time of day and day to day | glucose variability, diurnal amplitude |
| `behaviour` | meals announced imperfectly, lows treated with carbohydrate, an adapting sensitivity setting | rise tail, hypoglycaemia recovery, sensitivity drift |
| `sensor` | measurement jitter and compression lows, on the reading everything acts on | the two sensor statistics |
| `site` | infusion sets whose absorption fails and gets noticed late | time above 180, and how long a high lasts |

The rig is how an algorithm reaches that person: a monitor reporting every five minutes,
and a pump with the delivery ceilings in `timsim/therapy/limits.py`. It is always present,
because there is no other way to touch a body. Without the ceilings the bench is
unphysical, and they bind in practice: the reference algorithm has been observed asking
for a 35 U bolus, which the pump clamped to 11.

The controller is whatever is driving, and it is not part of the person.
`controller="reference"` is the built-in correction loop and the default,
`controller="basal-bolus"` is open-loop therapy, and anything with simglucose's
`policy(observation, reward, done, **info)` is the algorithm under test.

One thing that follows is worth knowing before quoting any figure here. The fidelity
numbers compare this person plus the reference controller against real people plus
Control-IQ. That is the right comparison, since a real person cannot be observed without
their algorithm either, but it validates the pair. Bringing your own algorithm replaces
half of what was validated.

Each layer is a small module. `timsim/person/behaviour.py` does most of the work and runs
to about 200 lines.

The sensor layer sits inside the loop rather than being applied to the finished trace, so
a compression low reaches the algorithm and the simulated person while the underlying blood
glucose in `Result.bg` stays untouched. Everything an algorithm asks for then passes
through the delivery ceilings in `timsim/therapy/limits.py`, and every clamp is counted.

## The population

`timsim/population/derive.py` records something worth knowing about the published
parameter tables. Of their 62 columns, only 29 are free. The rest are either constant
across all thirty subjects, or determined exactly by the model's own balance equations at
the basal steady state. Those relations are written out in that module and checked against
all thirty published subjects to twelve significant figures. That is what makes generating
a new subject tractable: sample the free parameters, close the rest, then screen.

Candidates are drawn from the joint distribution of the published subjects of their own
class, in a space where the parameters are roughly Gaussian, with the covariance shrunk
towards its diagonal because ten subjects cannot support a 29-dimensional covariance.
Carbohydrate ratio and correction factor are not sampled at all. They are measured from
each subject's own model, the way a clinician titrates.

A candidate is then rejected for any of the following: diverging on basal alone, failing
to hold its fasting glucose, leaving the 40 to 500 mg/dL band when given three meals with
matched boluses, needing an implausible daily insulin dose, or ending up with measured
settings outside the human range. The acceptance rate and a breakdown of the refusals go
to `params/vpop_report.json`.

## Relationship to simglucose

This sits on top of simglucose rather than forking it. simglucose supplies the
differential equations, the sensor and pump models, and the environment loop, and its
interfaces are used unchanged, so a controller written for simglucose runs here without
modification. The published parameter tables are read from your simglucose install and are
not redistributed.

## Is it any good?

There are six graded levels of check in [docs/VALIDATION.md](docs/VALIDATION.md), running
from whether the code does what it claims through to how large a difference it can
actually resolve. Two of them carry most of the weight for a comparison.

Running the same controller twice gives -0.27 percentage points of time in range
[-1.65 to +1.72], so the null comes out null, and the design resolves about 1.1 points
across the full 100 subjects.

Closing the loop gives +12.9 points [8.2 to 15.4]. The DCLP3 trial randomised that same
comparison in 168 people over 26 weeks of free living and measured +13.9 points, with a
headline figure of about eleven. The simulator's interval covers both, on a trial it was
never fitted to.

The graded structure has already paid for itself. It caught two defects that no amount of
distributional comparison would have found. Subjects were being dosed on somebody else's
settings, because ratios had been drawn from the published cohort rather than measured
from each subject's own model. And every run opened with a zero-insulin step that kicked
each subject off its steady state. Fixing both improved the fidelity table by three
statistics.

## Can it say an algorithm is safe?

Not on its own, and the reason is exposure rather than fidelity. A hundred subjects over
28 days is 2800 subject-days, and seeing no severe events across all of it bounds the
underlying rate no lower than about one per 2.6 subject-years. A system whose true rate is
one per five subject-years would show nothing.

What it can support is a pre-clinical gate: criteria fixed in advance, a cohort run
against them, and a verdict quoted with the exposure that produced it. That is the claim
the UVA/Padova simulator was accepted for in 2008, ahead of a trial rather than instead of
one.

Whether the gate means anything turns on whether the bench orders algorithms correctly,
which is checked against algorithms broken on purpose rather than against real systems
whose true ordering nobody knows. `timsim/controller/reference.py` supplies a plain
algorithm and four named defects, and `timsim/validation/ranking.py` requires the safety
score to rise at every step as one defect is dialled from none to severe.
[docs/EVIDENCE.md](docs/EVIDENCE.md) sets out all six mechanisms and what each one is still
missing.

## Reading a result

Statistics come with a bootstrap interval and a verdict against the real range. A point
estimate on its own is not a finding. Where output from this package is used to argue for
a change in treatment, the counterfactual caveat above needs stating alongside it: the
simulator ranks options, and a within-person trial decides.

## Licence

MIT. simglucose has its own licence; this package depends on it and does not vendor it.
