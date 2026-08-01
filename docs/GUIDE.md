# TimSim: what it does and how to use it

## 1. The idea in one paragraph

A physiological simulator describes a body. Point one at real continuous glucose data and
the differences that survive are mostly not about the body: they are about a person eating
without telling the algorithm, drinking juice when the alarm goes off, a sensor that is
noisier than the model says, and an algorithm correcting continuously in the background.
TimSim adds those as separable layers on top of simglucose, together with a virtual
population of 100 screened subjects rather than 30, so that a comparison between two
algorithms is not decided by which of ten subjects happened to be awkward.

## 2. What it is made of

```
timsim/
  population/   generating and screening virtual subjects
  patient/      a subject whose insulin sensitivity varies
  person/       what the person eats, announces, and does about a low
  controller/   a baseline correction loop
  sensor/       measurement jitter and compression lows
  simulation/   running one subject or a cohort
  analysis/     the eleven fidelity statistics
  validation/   graded checks on whether any of it can be believed
```

It is a layer on top of simglucose, not a fork. simglucose supplies the differential
equations, the sensor and pump models and the environment loop, and its interfaces are
used unchanged, so a controller written for simglucose runs here without modification.

### The four layers

| Layer | What it adds | Why it exists |
|---|---|---|
| `physiology` | insulin sensitivity varying by time of day and day to day | the published subjects are identical from one day to the next, and real people are not |
| `behaviour` | meals announced imperfectly, lows treated with carbohydrate, a sensitivity setting that adapts | none of this is in the equations, and it dominates several real-world statistics |
| `loop` | continuous correction bounded by insulin on board, with basal withdrawal | every real cohort worth comparing against is running one |
| `sensor` | high-frequency jitter and compression lows | the model's sensor is about half as noisy as a real one and has no compression mechanism |

Each is independent. Switching one off changes only what that layer does, which is
checked rather than assumed.

### The population

The published parameter tables have 62 columns, of which only 29 are free. The rest are
either constant across all thirty subjects or determined exactly by the model's own
balance equations at the basal steady state, and `population/derive.py` writes those
relations out. They reproduce all thirty published subjects to twelve significant figures.

That is what makes generating a subject tractable: sample the 29 free parameters from the
joint distribution of the published subjects of the same class, close the rest, then
screen. Carbohydrate ratio and correction factor are not sampled at all. They are measured
from each subject's own model, the way a clinician titrates: give a unit from a settled
state and see how far glucose falls, give a small amount of carbohydrate and see how far
it rises, take the ratio.

Each candidate has to survive five gates: the balance equations must admit a positive
steady state; the measured settings must fall in the human range; glucose must hold near
its fasting value on basal alone for a day; and given three meals with matched boluses it
must stay inside 40 to 500 mg/dL on a plausible daily dose. Refusals are counted and
written to `params/vpop_report.json`.

## 3. Installing

```
pip install simglucose
pip install -e .
python -m timsim.population.build --n 100
```

The population is generated on your own machine from your own simglucose install, and is
not committed to the repository, so nothing derived from the published parameter tables is
redistributed. Generation takes about 50 minutes for 100 subjects and is deterministic
given the seed.

## 4. Running one subject

```python
from timsim import simulate

r = simulate("adult#001", days=28, seed=1)
print(r.summary())
```

`simulate` returns a `Result` carrying the trace and the record of what happened:

| Attribute | What it is |
|---|---|
| `cgm` | what the algorithm saw, including sensor artefacts |
| `bg` | the underlying blood glucose |
| `minutes` | elapsed minutes for each sample |
| `completed` | False if the subject did not survive the run |
| `insulin_units` | total insulin delivered |
| `rescue_events`, `rescue_grams` | how often the person treated a low, and with how much |
| `meals_announced`, `meals_unannounced` | how many meals the algorithm was told about |
| `isf_weekly_cv` | how far the sensitivity setting drifted |
| `compression_events` | sensor artefacts injected |

with `time_in_range`, `time_below_70`, `time_above_180` and `cv` as properties.

`completed` deserves attention. simglucose ends an episode when blood glucose falls below
10 mg/dL, so a short trace means the subject did not survive. Any analysis that takes
whatever series it is handed is conditioning on survival.

## 5. Running a cohort

```python
from timsim import simulate_cohort, signatures
from timsim.population import names

results = simulate_cohort(names("adult"), days=28)
print(signatures.report(signatures.evaluate(results)))
```

`names()` with no argument gives all 100; `names("adult")`, `names("adolescent")` and
`names("child")` give the classes. Runs take roughly three seconds per subject-day, so a
cohort of 34 adults over 28 days is about 45 minutes. The arms of a comparison are
independent, so running them in separate processes is the obvious speed-up.

## 6. Testing your own algorithm

Any object with simglucose's controller interface works:

```python
from simglucose.controller.base import Action, Controller
from timsim import simulate_cohort
from timsim.population import params_for, therapy_for

class MyLoop(Controller):
    def __init__(self, name):
        p, q = params_for(name), therapy_for(name)
        self.basal = float(p["u2ss"]) * float(p["BW"]) / 6000.0
        self.cr, self.cf = float(q["CR"]), float(q["CF"])

    def policy(self, observation, reward, done, **info):
        grams = info.get("meal", 0.0) * info.get("sample_time", 3)
        bolus = grams / self.cr if grams > 0 else 0.0
        return Action(basal=self.basal, bolus=bolus / info.get("sample_time", 3))

results = simulate_cohort(days=28, controller_factory=MyLoop)
```

Two things to understand about what your controller sees.

`info["meal"]` carries the **announced** carbohydrate, not the true amount. An unannounced
meal arrives as an unexplained rise, which is the point. Rescue carbohydrate is never
announced, because someone treating a low does not enter it as a meal bolus.

`observation.CGM` carries the sensor reading including jitter and compression lows. A
compression low is a false low: the reading moves and the glucose does not. An algorithm
that reacts to one is being tested on something real.

`controller_factory` is called per subject and must return a fresh controller, so no state
leaks between subjects.

## 7. Comparing two algorithms

The pattern that makes a comparison readable:

```python
from timsim import simulate_cohort
from timsim.validation import minimum_detectable_difference
from timsim.population import names

subjects = names("adult")

a = simulate_cohort(subjects, days=28, seed=0, controller_factory=ControllerA)
b = simulate_cohort(subjects, days=28, seed=0, controller_factory=ControllerB)

# the same subjects and the same seed in both arms, so day-to-day variation is
# common to both and cancels in the paired difference
paired = [y.time_in_range - x.time_in_range for x, y in zip(a, b)]
```

Two rules for reading the result.

**Pair.** The same subjects and the same seed in both arms. An unpaired comparison throws
away most of the power, because between-subject variation is far larger than the effect
of any sensible controller change.

**Establish the null first.** Run the same controller twice with different seeds and see
what difference that produces. That is the noise floor, and a difference smaller than it
is not evidence of anything.

```python
null_a = simulate_cohort(subjects, days=28, seed=0, controller_factory=ControllerA)
null_b = simulate_cohort(subjects, days=28, seed=1000, controller_factory=ControllerA)
print(minimum_detectable_difference(null_a, null_b, n_subjects=len(subjects)))
```

For the built-in loop over 20 adults and 14 days that null comes out at +0.21 percentage
points [-2.28 to +1.44], with a paired standard deviation of 3.73, which resolves about
2.3 points at 20 subjects and 1.0 across the full hundred. `docs/VALIDATION.md` has the
details.

## 8. Attributing a result to a mechanism

```python
for layers in [(), ("physiology",), ("physiology", "behaviour"),
               ("physiology", "behaviour", "loop"),
               ("physiology", "behaviour", "loop", "sensor")]:
    r = simulate("adult#001", days=28, layers=layers)
    print(layers, round(r.cv, 1), round(r.time_below_70, 1))
```

`examples/layer_ablation.py` does this at cohort scale and writes the table in
`docs/FIDELITY.md`. If an algorithm looks good only with a particular layer switched off,
that is worth knowing before it reaches anyone.

## 9. The fidelity statistics

Eleven statistics, computed identically on simulator output and on real data, with a
reference range measured across four cohorts of closed-loop users, 192 people:

```python
from timsim import signatures
stats = signatures.evaluate(results)
print(signatures.report(stats))
print(signatures.REAL_RANGE["cv"])          # (29.5, 34.3)
signatures.in_real_range("cv", stats["cv"][0])
```

They cover variability, how often glucose jumps, how fast the curve decorrelates, the
spread of outcomes from a stuck high, the daily rhythm, how a low recovers and whether it
overshoots, sensor artefacts, and how far the sensitivity setting drifts. Each returns a
median with a bootstrap interval.

`docs/FIDELITY.md` has the measured table and, more usefully, the four statistics that are
still outside the real range and what each one means.

## 10. Checking the simulator itself

Six graded levels, from whether the code does what it claims through to how large a
difference it can actually resolve. Currently 19 of 19 on the fast levels.


```
python -m timsim.validation.run --fast     # a few minutes
python -m timsim.validation.run            # about 90 minutes
```

Six graded levels, from whether the code does what it claims through to how large a
difference it can actually resolve. `docs/VALIDATION.md` explains what each level licenses
and reports the current results. It is worth reading before trusting a result from here,
particularly the part about what the simulator cannot do.

## 11. The limits, stated plainly

**It cannot price a dosing change for a particular person.** The spread of where glucose
lands half an hour after a stuck high is the quantity a dosing decision bets on, and the
simulator is measurably on the confident side: 25.5 mg/dL against a real 26.5 to 33.5. That
is much closer than it was, but it is still narrow. Use TimSim to stress-test an algorithm
and to rank options; use a trial to decide.

**The subjects are a resampling, not new data.** They are drawn from the joint
distribution of thirty published subjects, so they inherit whatever that cohort does not
represent and carry no independent information about human variability. What they add is
resolution.

**There is no exercise, no illness, no alcohol, no insulin site failure.** The model has no
mechanism for any of them, and the behaviour layer does not invent one.

**Rebound after a low is overstated.** The simulator over-treats lows about twice as often
as these cohorts appear to, 58.5% against a real 23 to 28. An algorithm judged on how it
handles rebound highs is being judged on a harsher world than the real one.

**Regenerate before believing anything.** The subjects are sampled, so a conclusion could
be a property of one draw:

```
python -m timsim.population.build --n 100 --seed 7
```

If a result does not survive that, it was never a result.
