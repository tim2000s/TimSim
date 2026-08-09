# TimSim: what it does and how to use it

## 1. The idea in one paragraph

A physiological simulator describes a body. Point one at real continuous glucose data and
the differences that survive are mostly not about the body. They are about a person eating
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
  therapy/      the profile an algorithm reads, and the ceilings it doses within
  controller/   a baseline correction loop, and a reference algorithm with known defects
  sensor/       measurement jitter and compression lows, applied inside the loop
  simulation/   running one subject or a cohort
  analysis/     the eleven fidelity statistics, and the safety record
  validation/   graded checks on whether any of it can be believed
```

It sits on top of simglucose rather than forking it. simglucose supplies the differential
equations, the sensor and pump models, and the environment loop, and its interfaces are
used unchanged, so a controller written for simglucose runs here without modification.

The model underneath is described in [MODEL.md](MODEL.md).

### The person, and what is not part of it

| Layer | What it adds | Why it exists |
|---|---|---|
| `physiology` | insulin sensitivity varying by time of day and day to day | the published subjects are identical from one day to the next, and real people are not |
| `behaviour` | meals announced imperfectly, lows treated with carbohydrate, a sensitivity setting that adapts | none of this is in the equations, and it dominates several real-world statistics |
| `sensor` | high-frequency jitter and compression lows | the model's sensor is about half as noisy as a real one and has no compression mechanism |
| `site` | infusion sets whose absorption fails, and gets noticed late or slept through | the largest single fidelity gap: it is where most real time above 180 mg/dL comes from, and nothing else in the model can produce it. It costs three signatures and is in the default anyway, because a classifier finds the cohort with it harder to tell from real data in ten splits out of ten |

Each layer is independent. Switching one off changes only what that layer does, which is
checked rather than assumed.

Two things that are not layers, because they are not properties of a person. The rig is the
monitor and the pump the algorithm reaches the person through, always present, with the
delivery ceilings in `therapy/limits.py`. The controller is whatever is dosing:
`controller="reference"` for the built-in correction loop, which is the default and what
every figure in these documents was measured against, `controller="basal-bolus"` for open
loop, or your own algorithm. A correction loop was listed among the layers until it was
noticed that a dosing algorithm is not a property of a body, and passing `"loop"` in
`layers` now raises rather than being quietly accepted.

The consequence is worth carrying: the fidelity figures validate this person plus the
reference controller against real people plus Control-IQ. Swapping in your own algorithm
replaces half of what was validated.

### The population

The published parameter tables have 62 columns, of which only 29 are free. The rest are
either constant across all thirty subjects or determined exactly by the model's own
balance equations at the basal steady state, and `population/derive.py` writes those
relations out. They reproduce all thirty published subjects to twelve significant figures.

That is what makes generating a subject tractable: sample the 29 free parameters from the
joint distribution of the published subjects of the same class, close the rest, then
screen. Carbohydrate ratio and correction factor are not sampled at all. They are measured
from each subject's own model, the way a clinician titrates. Give a unit from a settled
state and see how far glucose falls, give a small amount of carbohydrate and see how far
it rises, take the ratio.

A candidate is rejected for diverging on basal alone, for failing to hold its fasting
glucose over a day, for leaving the 40 to 500 mg/dL band when given three meals with
matched boluses, for needing an implausible daily insulin dose, or for ending up with
measured settings outside the human range. Refusals are counted and written to
`params/vpop_report.json`.

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
| `cgm` | what the analysis sees, including sensor artefacts |
| `bg` | the underlying blood glucose |
| `minutes` | elapsed minutes for each sample |
| `completed` | False if the subject did not survive the run |
| `insulin_units` | total insulin the body received, whichever controller asked for it |
| `insulin_series` | units delivered in each step, which is what a rolling-hour peak needs |
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
        step = info["sample_time"]                      # five minutes
        grams = info["meal"] * step                     # info["meal"] is grams per minute
        bolus = grams / self.cr if grams > 0 else 0.0
        return Action(basal=self.basal, bolus=bolus / step)

results = simulate_cohort(days=28, controller_factory=MyLoop)
```

`info["meal"]` carries the announced carbohydrate in grams per minute, averaged over the
step, which is simglucose's own convention. Multiply by `info["sample_time"]` for grams.
Getting that conversion wrong is worth guarding against: the runner itself had it wrong
until recently and under-bolused every run with the behaviour layer switched off.

The announced amount is not the true amount. An unannounced meal arrives as an unexplained
rise, which is what the behaviour layer is for, and rescue carbohydrate is never announced,
because someone treating a low does not enter it as a meal bolus.

`controller_factory` is called per subject and must return a fresh controller, so no state
leaks between subjects.

Four things to know about what your controller is handed:

- `observation.CGM` is the reading after the sensor layer, so it carries the jitter and any
  compression low in force at that moment. It is the same value recorded in `Result.cgm`,
  which means an artefact in the output is an artefact the algorithm saw.
- `info["profile"]` is the subject's therapy profile: a 24-hour basal schedule, sensitivity
  and ratio by time block, a target range, a duration of action, and the delivery ceilings.
  `info["clock_minutes"]` is the time the algorithm believes it is, which a clock fault can
  move away from the real elapsed minute.
- `info["stale_minutes"]` counts how long since a new reading arrived. It is zero unless a
  fault is withholding readings, and an algorithm that ignores it is dosing on stale data.
- Whatever you return passes through the limits in `timsim/therapy/limits.py` before it
  reaches the pump. Every clamp is counted in `Result.meta["limit_bound"]`, so an
  algorithm that keeps hitting its ceiling says so.

The `loop` layer belongs to the built-in controller, so supplying your own switches it off.
The runner warns and records the layers that actually ran rather than the ones requested.

Driving a real automated insulin delivery system through this harness still needs an
adapter, because the interface above is per-cycle rather than temp-basal-and-history.
[OSAID.md](OSAID.md) sets out what one needs.

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

Pair. Use the same subjects and the same seed in both arms. An unpaired comparison throws
away most of the power, because between-subject variation is far larger than the effect of
any sensible controller change.

Establish the null first. Run the same controller twice with different seeds and see what
difference that produces. That is the noise floor, and a difference smaller than it is not
evidence of anything.

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
               ("physiology", "behaviour", "sensor"),
               ("physiology", "behaviour", "sensor", "site")]:
    r = simulate("adult#001", days=28, layers=layers)
    print(layers, round(r.cv, 1), round(r.time_below_70, 1))
```

`examples/layer_ablation.py` does this at cohort scale and writes the table in
`docs/FIDELITY.md`. An algorithm that looks good only with a particular layer switched off
is worth knowing about before it reaches anyone.

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

`docs/FIDELITY.md` has the measured table and, more usefully, the statistics that are
still outside the real range and what each one means.

## 10. Judging an algorithm on safety rather than on time in range

Time in range is the wrong thing to lead on. Section 8 of `docs/VALIDATION.md` shows why:
the simulated person defends against lows with carbohydrate, so an algorithm that doses
too hard can hold its mean steady while driving that person through repeated rescues.

```python
from timsim.analysis import safety

record = result.safety()          # one subject
worst = safety.worst_of(safety.cohort(results))
```

The record carries minutes below 54 per day, the longest single episode, LBGI and HBGI,
peak insulin in any rolling hour, peak insulin on board against the declared ceiling, and
rescue carbohydrate. Glucose figures come from `Result.bg` rather than from the sensor, so
a compression low does not count as hypoglycaemia and an algorithm that causes a real low
its own sensor understates gets no credit for it. `worst_of` names the worst subject,
because a median hides an algorithm that is dangerous for five people in a hundred.

Faults are how you find behaviour that a cohort average will never show:

```python
from timsim.validation import faults

run = simulate("adult#001", days=3, seed=11, controller=MyLoop("adult#001"),
               faults=faults.Faults(faults.NoReadings(start_min=26*60, duration_min=180)))
```

`faults.SCENARIOS` has the standard set: dropouts, a sensor restart with an offset on
resumption, a stuck reading, a compression low, delivery loss, and a clock shift. Run each
against an unfaulted control on the same seed and read the traces. What you are looking
for is a fallback and a recovery rather than a number.

And the verdict, with its criteria fixed before the run:

```python
from timsim.validation import gate

print(gate.fingerprint(design=gate.design_of(results)))   # record this first
print(gate.report(gate.evaluate(results)))
```

`examples/safety_gate.py` runs the whole sequence end to end.

## 11. Checking the simulator itself

```
python -m timsim.validation.run --fast     # a few minutes
python -m timsim.validation.run            # about 90 minutes
```

Six graded levels, running from whether the code does what it claims through to how large
a difference it can actually resolve. Currently 24 of 24 on the fast levels.
`docs/VALIDATION.md` explains what each level licenses and reports the current results,
including a section on where two of the checks are weaker than they look. It is worth
reading before trusting a result from here, particularly the part about what the simulator
cannot do.

## 12. The limits, stated plainly

It cannot price a dosing change for a particular person. The spread of where glucose lands
half an hour after a stuck high is the quantity a dosing decision bets on, and the
simulator sits at the confident end of the real range: 27.0 mg/dL against a real 26.5 to
33.5, on ten subjects with a wide interval. That is much closer than it was, and not
settled. Use TimSim to stress-test an algorithm and to
rank options; use a trial to decide.

The subjects are a resampling rather than new data. They are drawn from the joint
distribution of thirty published subjects, so they inherit whatever that cohort does not
represent and carry no independent information about human variability. What they add is
resolution.

There is no exercise, no illness, no alcohol. The model has no mechanism for any of them,
and the behaviour layer does not invent one. Infusion site failure is modelled, in the one
form the DCLP3 traces show: absorption drops away, the loop cannot fix it, and the person
notices hours later or sleeps through it. A set that leaks, bleeds or hurts enough to be
changed straight away looks nothing like that and is not covered.

Carbohydrate is about half as potent as it is in real people, 1.9 mg/dL per gram against
4.2 measured from DCLP3 participants' own settings. Anything driven by a carbohydrate error,
which is most of what the behaviour layer does, is correspondingly damped.

Rebound after a low is overstated. The simulator over-treats lows about twice as often as
these cohorts appear to, 66.1% against a real 23 to 28. An algorithm judged on how it
handles rebound highs is being judged on a harsher world than the real one.

Rare events are out of reach. A hundred subjects over 28 days is 2800 subject-days, which
is not enough exposure to bound a severe hypoglycaemia rate at a level that would still
matter clinically. Section 7 of [OSAID.md](OSAID.md) does the arithmetic.

Regenerate before believing anything. The subjects are sampled, so a conclusion could be a
property of one draw:

```
python -m timsim.population.build --n 100 --seed 7
```

A result that does not survive that was never a result.
