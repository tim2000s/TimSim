# Running the shipped Boost code against the simulator

This compiles the real AndroidAPS decision code into a jar and drives it from Python over a
pipe. Nothing here is a port. The five decision files and the orchestrator are read straight
from an AndroidAPS working tree, so there is no second copy to drift.

## Why

The Python port in `~/oref-investigations/boost_v5_harness.py` reproduces the logged dose to
0.0000 U and still agrees with the logged state machine on 70.9% of decisions. It reaches
RECOVERING on 0.6% of real inputs where the plugin logged 5.8%, and CONFIRMED on 0.3% against
2.5%. Every comparison against the field therefore needs a control run purely to subtract the
port's own error, and that control is built on stubbed fields, so the two error sources cannot
be fully separated.

Running the shipped code removes one of them outright.

## Build

    ./bridge/boost/build.sh

Needs `kotlinc` and a JVM. On macOS the runtime Android Studio ships is used when there is no
system JDK. `BOOST_SRC` points at the AndroidAPS checkout and defaults to
`~/StudioProjects/Boost-V6`; whichever is used should be recorded in the gate's design
fingerprint, since it decides which version was tested.

## Use

    from timsim.controller import boost_bridge
    from timsim import simulate_cohort

    results = simulate_cohort(days=28, controller_factory=boost_bridge.factory())

One JVM per subject, because the algorithm keeps state between cycles and the plugin keeps
that state in its own store. Holding it on the far side rather than marshalling it each way
removes a place for the two sides to disagree.

## What this does and does not remove

It removes the port. The decision, the state machine, the budget, the multiplier and the gates
are the shipped implementations.

It does not remove the input reconstruction. AndroidAPS computes insulin on board, carbohydrate
on board, the target and oref's projection internally, and the adapter rebuilds them. Three
defects in that rebuilding are recorded in `validation/boost.py`: `max_delta` is a windowed
maximum here and a single absolute delta in the logged reference, neither matching oref's own
definition; the target is fixed at 110 where real users span 80 to 115; and insulin on board is
never negative, where AndroidAPS measures it against scheduled basal so a loop withholding
basal carries a negative figure.

Those are the next piece of work, and they are why a verdict on this algorithm is still not
available.

## What is stubbed

`AAPSLogger` is an empty interface. The orchestrator injects a logger and marks it unused, so
nothing calls it.

`javax.inject` annotations are declared locally so the source compiles without Dagger.

`riskAtProjectedIob` is passed as null, which disables `postActionRiskCheck`, and the two ML
inputs are null because no model runs here. Both match how the algorithm behaves when its
models are unavailable, which is a real operating mode rather than an invention, and both are
reported per cycle so a run cannot be read as though the models were present.
