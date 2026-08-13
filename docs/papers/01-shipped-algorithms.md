# Driving the shipped algorithm instead of a port of it

## Question

To test an automated insulin delivery system on a simulator, the system has to run. The usual
approach is to reimplement its decision logic in the simulator's language. A port is a second
implementation, and the question is whether the difference between the two matters enough to
be worth avoiding.

## Method

Boost was already present as a Python port, and its accuracy could be checked directly because
the plugin logs every decision in the field. The port was compared against 704,389 logged
decisions on dose and on state-machine occupancy.

Two bridges were then built. `bridge/boost/build.sh` compiles the five decision files and an
orchestrator straight from the AndroidAPS working tree into a jar, and a line protocol carries
one cycle across a pipe per decision. `bridge/oref/build.sh` gathers `determine-basal.js` and
`basal-set-temp.js` from the same tree, where they are the reference implementation the Kotlin
port is tested against, and calls them under node. Neither gathered copy is committed.

Both were then run over the same subjects and compared with the port and with the field.

## Results

The port reproduced the logged dose to 0.0000 U on replayed inputs and still disagreed with
the logged state machine on 29.1% of decisions, reaching one state on 0.6% of real inputs
against a logged 5.8%.

Driving the shipped code across twenty subjects for 28 days:

| State | Logged | Port | Bridge |
|---|---|---|---|
| IDLE | 65.0 | 43.0 | 30.7 |
| OBSERVING | 21.2 | 48.6 | 32.0 |
| RECOVERING | 5.8 | 2.9 | 8.6 |
| COMMITTED | 5.4 | 3.8 | 24.9 |
| CONFIRMED | 2.5 | 1.7 | 3.9 |
| Mean dose, U | 0.0826 | 0.1163 | 0.0834 |

The port was over-delivering by 41%. The bridge removes that outright.

Four input reconstructions were then corrected against the AndroidAPS source rather than by
inference. The three delta figures now follow `DeltaCalculator`'s own windows, where every
earlier reading contributes `(current - then) / minutesAgo * 5` averaged over 2.5 to 7.5, 2.5
to 17.5 and 17.5 to 42.5 minutes, so the maximum delta is the signed maximum of the three
rather than the largest absolute recent difference. Insulin on board is measured against the
scheduled basal and goes negative on 21% of cycles, which real users do at the fifth
percentile and an adapter counting boluses alone never does. Together those moved time in
range from 71.0% to 75.8% and time above 180 from 27.9% to 22.8%.

oref0 required more. It returns a temporary basal rate with a duration rather than a dose, and
expects to be told next cycle how much of that duration remains, so the running temporary
basal is held in the adapter where a pump would hold it. It also takes insulin on board as a
forward array rather than a number, and walks it to build every prediction it makes. Two
defects in building that array were caught by tests: the insulin curve reports a full unit for
a negative age, which is right looking backwards and wrong looking forwards, so every
projected delivery counted in full at the present tick; and a deviation covering an interval
was stamped at its start rather than its end. Together they put the zero-delivery floor half a
unit below zero and corrupted the array on the 82% of cycles with a temporary basal running.
Correcting them cut the mean dose by 30%.

## Discussion

The bridge is worth the trouble when the algorithm has few dependencies, which both of these
did: Boost's decision core has none on AndroidAPS at all, and oref's `determine_basal` is a
pure function with a single import. That will not generalise. For Loop or Trio the same job
means linking against or reimplementing a Swift dosing path, and an emulator becomes the
cheaper option.

What does generalise is where the remaining error sits. With the port gone, everything left is
the input reconstruction and the simulator, and those can be attacked separately. The
reconstruction is now shared between both adapters in `controller/inputs.py`, because two
adapters computing insulin on board slightly differently would produce a difference between
Boost and oref that belongs to neither.

One gap is unresolved. Boost's COMMITTED state holds 24.9% of cycles against a logged 5.4%.
Four hypotheses about it have been refuted by measurement, most recently that a starved delta
history was blocking the exit, which moved it by 0.3 points. Reading the source has not worked
and instrumenting the transitions has not been done.
