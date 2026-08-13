# What this simulator is

TimSim is a person built on top of a metabolic model. The model is UVA/Padova S2008, reached
through simglucose, and [MODEL.md](MODEL.md) describes it. This document describes what is put
on top, why each piece is there, and what the separation between them is for.

## The three things a run contains

A run has a person, a rig and a controller, and keeping them apart is what makes any result
attributable.

The person is the metabolic model plus the layers below. It is everything that would still be
true if you swapped the algorithm.

The rig is the sensor, the pump and the delivery limits. It sits between the person and the
controller and distorts what each knows about the other. Sensor artefacts are inside the loop
rather than applied afterwards, so an algorithm reacts to the compression lows and the jitter
and so does the simulated person.

The controller is whatever is dosing. It is not part of the person and is not recorded as a
layer. Four are available: open-loop therapy, a built-in correction loop, and two systems
compiled from other people's source and driven across a pipe, Boost through a JVM and oref0
SMB through node.

## The layers

Each is switchable, and each is in the default stack only after it has been measured.

| Layer | What it adds | Default |
|---|---|---|
| physiology | insulin sensitivity that moves through the day, day to day, and across runs of days; meal-to-meal absorption variation | on |
| behaviour | meals announced imperfectly and sometimes not at all, lows treated with carbohydrate | on |
| sensor | jitter, compression lows, dropouts, calibration error | on |
| site | infusion set absorption failure and the person noticing it | on |
| activity | exercise sessions and what they leave behind | off, and see below |

Two things are switchable inside the physiology layer rather than being layers of their own,
because they are properties of the same body: the correlated multi-day sensitivity term and
the per-meal absorption spread.

## What the layers are for

The stock model is deterministic. Given the same meals and the same insulin it returns the
same trace, and three of the eleven fidelity signatures are exact zeros for it because it
contains nothing capable of producing them: compression lows, sensitivity drift, and jitter
beyond quantisation.

The layers exist to supply what a controller under test would otherwise never meet. An
algorithm that has never seen an unannounced meal, a failed infusion set or a sensor reading
that is wrong in a structured way has not been tested against the things that actually go
wrong.

## What is known to be carried by the person

A layer earns its place by moving a signature the same way under every driver, tested
separately for each. The two built-in drivers and the two compiled ones do not coordinate, so
agreement between them is not something this package can arrange.
[LADDER.md](LADDER.md) has the table; twelve of forty-seven movements survive.

| Layer | Carried under all four drivers |
|---|---|
| behaviour | hypoglycaemia recovery, rebound, rise tail, outcome spread, jitter |
| sensor | compression lows, jitter, rise tail |
| site | glucose variability, autocorrelation at thirty and sixty minutes |
| physiology | diurnal amplitude |

## What is deliberately absent

Counterregulation. S2013 adds a glucagon compartment and a risk term; only the risk term can
be implemented, because the glucagon parameters were drawn from a distribution the papers do
not publish. The risk term makes lows deeper rather than shorter, so implementing half of it
would import the harm without the rescue. It is present, off, and measured.

Exercise. Implemented and measured and left off, because it makes the model more predictable
rather than less. The measurement is in [06-four-mechanisms](papers/06-four-mechanisms.md).

Between-subject spread beyond what the population already carries. Every source tried widens
both the spread of mean glucose, which is wanted, and the spread of hypoglycaemia, which is
already the worst-fitting statistic.

## The population

One hundred subjects generated from the published thirty by closing the steady-state
relations, screened, and not committed to the repository so that nothing derived from the
published parameter tables is redistributed. The load-bearing check is that those relations
reproduce all thirty published subjects exactly; a failure there invalidates every generated
one.

## What a result from it means

`Result.bg` is not plasma glucose. simglucose exposes only the subcutaneous compartment
divided by its volume, so `bg` is interstitial glucose without sensor error. It differs from
`Result.cgm` by the sensor model alone and the difference is not small: the same runs give 100
excursions below 54 mg/dL on `bg` and 380 on `cgm`. Comparisons against trial data go on `cgm`
and the comparison harness refuses the other pairing.

[CAPABILITY.md](CAPABILITY.md) states what the whole thing can and cannot be used for.
