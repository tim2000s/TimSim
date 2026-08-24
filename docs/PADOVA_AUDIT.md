# Where UVA/Padova S2008 diverges from measured human physiology

An audit of the model this package simulates people with, kept separate from
`docs/DESIGN_ALIGNMENT.md`, which is a ledger of mechanisms tried against the residual. This is
about the model rather than about the layers around it, and an entry belongs here when a quantity
the model computes can be set beside a measurement in people and disagrees with it.

The audit exists because of a constraint rather than a suspicion. This package's value rests on
simulating a published, independently validated model, and every edit to that model spends some of
it. So a change to S2008 needs the divergence measured and sourced first, and an entry that says
what a change would cost is as useful as one that says a change is warranted. Several entries are
expected to conclude that no change should be made.

## How an entry is made

The model side is measured by reproducing the human protocol in silico rather than by reading
parameters or deriving quantities analytically, because the derivations need assumptions that the
measurement makes unnecessary and that tend to run in whichever direction the hypothesis wanted.
The human side is a published measurement with its citation and its population. Where the two
protocols differ, the difference is stated with the comparison.

Entries are ranked by how much the divergence bears on what this simulator is used for, not by how
large it looks.

## 1. Glucose effectiveness is about a third of the published human value

### What was measured

A hyperglycaemic basal-insulinaemic clamp, in silico, on 40 subjects
(`examples/glucose_effectiveness.py`). Insulin is held at basal replacement, glucose is walked up
to plateaus at 160, 210, 260 and 310 mg/dL by an infusion a proportional-integral controller
titrates, and the infusion rate holding each plateau is the disposal at that glucose. Plateaus run
eight hours with the last two measured, and a plateau is reported as settled only when the
infusion matches the flux balance to within 0.15 mg/kg/min.

| Plateau, mg/dL | Held at | Infusion | Production | Uptake | Renal | Settled |
|---|---|---|---|---|---|---|
| 160 | 159.9 | 0.21 | 2.32 | 1.54 | 0.00 | 40/40 |
| 210 | 210.0 | 0.86 | 2.01 | 1.80 | 0.02 | 28/40 |
| 260 | 260.0 | 1.47 | 1.62 | 2.03 | 0.07 | 28/40 |
| 310 | 310.0 | 2.15 | 1.26 | 2.25 | 0.12 | 26/40 |

Rates are mg/kg/min. The three upper plateaus settle in about seven subjects in ten, and the
median residual between infusion and flux balance is 0.003 mg/kg/min against disposals of 0.86 to
2.15, so the unsettled subjects are close rather than adrift and the medians are not carried by
them.

Glucose effectiveness, the fractional disposal rate, comes out flat across the range at 0.0065
min^-1, with quartiles of 0.0040 to 0.0093 and no trend from 160 to 310 mg/dL.

### The human comparison

Glucose effectiveness at zero insulin is reported at 0.021 min^-1 in people without diabetes and
0.011 min^-1 in type 2 diabetes, by hierarchical minimal-model analysis. The model's 0.0065 is
about a third of the non-diabetic figure and about 60 per cent of the type 2 one.

Two things limit the comparison and neither closes the gap. Minimal-model effectiveness is
estimated around basal glucose during an intravenous tolerance test, and this is measured between
hyperglycaemic plateaus where Michaelis-Menten saturation would already have reduced the slope;
the model's own basal is 142 mg/dL so the lowest step sits close to it, and in any case the
measured slope is flat rather than falling, so saturation is not what produces the low value.
And glucose effectiveness is reduced in type 1 diabetes relative to people without it, which is
the direction that would excuse the model, but the published type 2 figure is still well above it
and a type 1 figure low enough to reach 0.0065 has not been found.

### What follows

The divergence is real and it runs against the residual rather than explaining it. Lower glucose
effectiveness means a high persists longer, not less, so correcting the model towards the
published human value would shorten simulated excursions further and widen the gap this package
is trying to close. The hypothesis that led to this measurement, that the model disposes of
glucose too readily by the glucose-driven route, is refuted by the measurement it predicted.

The clamp also settles what the spontaneous fall means. A static calculation from the equations
puts it at 55 mg/dL per hour from 260 mg/dL with insulin at basal, which reads as a lot. The clamp gives
0.0065 min^-1, which predicts 46 mg/dL per hour from 260 towards the model's equilibrium of 142,
and the open-loop arm of `examples/excursion_recovery.py` measured 44. All three agree, and what
they agree on is a modest effectiveness producing an unremarkable fall. The number looked large
because a fractional rate acting across a 118 mg/dL displacement produces a large absolute rate,
not because the fraction is large.

### Recommendation

No change. The direction is wrong for the residual, and the model is already conservative on this
route relative to people. Recorded so that nobody measures it again.

## 2. Fasting equilibrium sits at 142 mg/dL

### What was measured

At basal insulin with no meals, no loop and nothing else acting, the population settles at its own
basal glucose, whose median is 141.8 mg/dL with an interquartile range of 137.4 to 145.9 and a
range of 127 to 159 across the 600 generated subjects. This is a parameter of the published
subjects rather than a behaviour of the simulation: `Gb` is what the model was closed at.

### The human comparison

The DCLP3 closed-loop participants' hour-of-day profile reaches its nadir at 06:00 at a mean of
134.8 mg/dL, so their fasting glucose under a working closed loop is about 7 mg/dL below the
model's unperturbed equilibrium. That is a smaller difference than any of the figures in
`docs/BASELINE.md` and does not obviously need correcting.

### What follows

The entry exists because the equilibrium constrains what the clamp in entry 1 could measure: an
infusion can only add glucose, so no plateau below 142 mg/dL is reachable at basal insulin, and
a protocol targeting 120 mg/dL holds the infusion at zero and measures wherever the model settles
instead. A sub-basal plateau needs an insulin infusion as well.

It also bears on the population's narrowness. Every generated subject is closed at a steady state
that its own parameters define, and the spread of that equilibrium is 137 to 146 at the quartiles,
which is far narrower than the spread of fasting glucose across real people. That narrowness is
one of the reasons the population carries 0.46 to 0.68 of the real between-subject spread on the
measures describing where glucose sits.

### Recommendation

No change to the model. The entry is a constraint on protocols and a contribution to the
population-narrowness question.

## Entries not yet made

The counterregulation floor is documented in `docs/DESIGN_ALIGNMENT.md` and in
`timsim/patient/varying.py` and belongs here, restated as an audit entry against the clamp
literature rather than as a withdrawn mechanism. Insulin pharmacokinetics against published
subcutaneous absorption data has not been measured here. Meal absorption against tracer studies
has been measured only through the meal-response comparison, which is an outcome rather than a
flux. Whether the licensed successors S2013 and S2017 close any of these is a separate question
and a smaller step than editing S2008.
