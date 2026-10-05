# Two mechanisms for the hypoglycaemia gap, and what would refute each

Written before either is built, as the counterregulation design was, so the criteria cannot be
chosen once the answer is known. That discipline earned its keep last time: the glucagon gate
returned 14.6 per cent where the floor was set at 10, and a criterion written afterwards would
very likely have called it a success.

## The gap being addressed

Hypoglycaemia is the one place the person-in-the-loop layers move the model away from real
rather than towards it, on every pairing of the bench matrix. It appears in four measurements
which may or may not be the same defect:

    time below 54 mg/dL      +1.42 spreads under Control-IQ, +2.54 under oref0 SMB
    hypoglycaemia rebound    36 to 40 per cent against a real 23.2 to 28.4
    recovery to 100 mg/dL    65 to 70 minutes against a real 50 to 59
    production at a clamp    79 of 232 subjects produce nothing where no human produces nothing

The fourth is the one nothing has touched, and the reason is structural rather than a matter of
tuning.

## Why every mechanism tried so far has failed

Production in S2008 is `kp1 - kp2*Gp - kp3*Id`, and it floors at zero once the clamp's insulin
suppresses it faster than the falling glucose raises it. Every mechanism the package has tried
multiplies something:

    HYPO_DEFENCE_GAIN     scales insulin-dependent uptake      held at 0, moves away from the reference
    HYPO_EGP_DEFENCE      scales insulin's action on kp3       fitted to 0.05
    HYPO_RISK_GAIN        scales Vmx by a risk term            held at 0, costs more than it buys
    glucagon secretion     adds through the same kp3 pathway    refuted, supplies 14.6 per cent

Multiplying a quantity that has already reached zero returns zero. The sweep shows it plainly:
raising `HYPO_EGP_DEFENCE` fivefold, from 0.05 to 0.25, removes twenty of seventy-nine subjects
from the floor and carries the median from 0.57 to 1.03 mg/kg/min, outside the human band
(`hypo_defence_gain.json`, 300 adults, 6 September 2026).
It moves the centre of a distribution to reach its tail.

## E. A production floor

### Structure

A minimum endogenous glucose production, applied after the balance equation, binding only where
that equation has driven production to or near zero. Not a gain and not a term added to every
subject: a subject already producing 0.6 mg/kg/min sees nothing.

### The target, and why it is not a fit

Rickels et al. measured a mean of 0.59 mg/kg/min (SE 0.12, so an SD near 0.42) in twelve people
with long-standing type 1 diabetes and no glucagon response at all. The band 0.42 to 0.84 used
below is this package's choice around that mean; it does not appear in the paper (checked 5
October 2026 against its Table 2, which states mean ± SE). That population is the right one
for a floor: it is what people produce when the counterregulatory arm this package cannot model
is absent, which is the condition the floor represents.

So the floor's value is read off a published measurement rather than tuned to an outcome. That
is the distinction between this and `HYPO_EGP_DEFENCE`, which is fitted.

### What would refute it

**E is refuted if** raising the tail also moves the median outside 0.42 to 0.84, which would
mean the floor is not binding selectively and is behaving as another gain. Or if, with the tail
corrected at the clamp, time below 54 mg/dL on the bench matrix does not move by more than the
group variation the replicates measure, which would mean the clamp defect and the outcome defect
are unrelated and fixing one says nothing about the other.

**E succeeds if** the number producing nothing at the 55 mg/dL plateau falls below ten of a
hundred and ten while the median stays inside the human band, and time below 54 mg/dL falls on
the paired matrix comparison.

### Tests

    the count producing nothing at the clamp falls, and the median does not move outside the band
    a subject already producing 0.6 mg/kg/min is unchanged, so the floor binds selectively
    the p10 of production rises and the p90 does not
    switching the floor off returns the model to its current behaviour exactly
    run completions rise, since fourteen of fifteen failures end between 10 and 13 mg/dL

## F. Rescue carbohydrate absorption

### The observation this rests on

Two measurements that may be the same defect seen twice. Rebound is 36 to 40 per cent against a
real 23.2 to 28.4, in every configuration the capability decomposition tested, so no choice this
package has made accounts for it. And the carbohydrate response is 21.1 to 21.6 mg/dL per logged
10 g against a real 15.9 to 19.7 across every defensible filter.

Rebound is what over-treating a low looks like. If simulated carbohydrate raises glucose by a
fifth more than real carbohydrate, the same rescue helping overshoots by about that much.

### Structure

A scale on the carbohydrate reaching the gut for rescue treatments only, leaving meals alone.
`docs/PADOVA_LIMITS.md` considered scaling carbohydrate absorption and declined it, on the
grounds that the real figure moves between 15.7 and 19.7 mg/dL per logged 10 g depending on the
filter and that logged grams are under-reported by an unmeasured amount. Both objections are
about meals. Neither applies to a rescue treatment, which is not logged as a meal, is not
under-reported in the same way, and is the specific event rebound measures.

### What would refute it

**F is refuted if** scaling rescue absorption to the real carbohydrate response does not move
rebound by more than the interval on the rebound measurement itself, or if it moves rebound at
the cost of recovery time, which is already too slow at 65 to 70 minutes against 50 to 59. The
two are linked: slower carbohydrate means less overshoot and a longer climb, and a mechanism
that trades one failure for another has not helped.

**F succeeds if** rebound falls towards 23.2 to 28.4 with an interval excluding zero, and
recovery time does not rise.

### Tests

    a rescue raises glucose by the real amount per gram, measured as the meal response is
    rebound falls on the paired comparison and recovery time does not rise
    meals are unaffected, so the meal response measurement is unchanged
    switching the scale off returns the model to its current behaviour exactly

## The order they are tested in, and why it matters

E first, alone, then F on top of E. They act on the same outcome through different routes, and
running them together would leave neither attributable. If E succeeds, the floor changes how
deep lows get, which changes how much rescue carbohydrate is eaten, which is the input F acts
on: so F must be measured against a bench that already has E, not against the current one.

Both are measured on the paired matrix comparison rather than on the clamp alone, because the
clamp is where the defect was found and the matrix is where it matters.

## What was found

E was refuted on 19 August 2026 on its second criterion: the floor clears the clamp and moves
time below 54 mg/dL by less than the group variation, because a spontaneous low under a
withdrawing loop never reaches the insulin the clamp infuses (`examples/calibrate_egp_floor.py`).
F was adopted at a bioavailability of 0.83 (`examples/hypoglycaemia_arms.py`, `rescue_bio_alone.json`).

On 5 September 2026 the same criterion was applied to `HYPO_EGP_DEFENCE` at 0.25, after
`examples/low_recovery.py` found that gain, and not the floor, stops subjects falling through
40 mg/dL when the person does not eat. On the outcome table under the shipped person it fell
the same way: time below 54 mg/dL moved by 0.14 to 0.31 points paired, inside the 0.34 to 0.56
the replicates measure, while runs ending below 40 mg/dL fell from 18 of 242 to 4 and runs
ending above 500 rose from 3 to 5 (`egp_defence_outcome.json`). The gain stays at 0.05, and the
completion difference is recorded as a modelling choice not taken.
