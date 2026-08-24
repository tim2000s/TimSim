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

## 3. Insulin suppresses hepatic production for eight hours, peaking at five

### What was measured

A single-dose euglycaemic clamp, in silico, on 40 subjects (`examples/insulin_kinetics.py`). Each
subject is clamped at its own basal glucose for four hours so the start is a steady state, given
0.3 U/kg subcutaneously, and held for ten hours more. The infusion needed to hold the clamp is the
action profile of that dose, which is what a single-dose clamp measures in a person.

| Quantity | Median | p10 to p90 | Human reference |
|---|---|---|---|
| Plasma insulin peak, min | 49.5 | 38.9 to 57.0 | 52 to 60 for aspart |
| Peak infusion, mg/kg/min | 9.1 | 4.9 to 13.9 | 8.70 in healthy subjects |
| Total infusion over 10 h, mg/kg | 2086 | 1285 to 3580 | 2054 in healthy subjects |
| Infusion peak, min | 115 | 78 to 169 | 45 to 90 clinically, 141 to 169 in one healthy cohort |
| Time to 95 per cent of effect, min | 540 | 420 to 546 | 180 to 300 clinically |

Absorption is right. Plasma insulin peaks at 49.5 minutes against a published 52 to 60 for
aspart, and the height and total area of the action curve sit on the reference figures. What
diverges is how long the dose goes on acting: a quarter of its effect, 25.4 per cent with a tenth
to ninetieth percentile of 14.7 to 33.4, is delivered after five hours, and 17.1 per cent after
six.

Decomposing the curve into fluxes says which pathway carries the tail. Changes from the pre-bolus
steady state, in mg/kg/min, median over subjects by hour:

| Hour | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Plasma insulin | 34.6 | 32.2 | 18.3 | 9.2 | 3.8 | 1.5 | 0.6 | 0.2 | 0.1 | 0.0 |
| Insulin-dependent uptake | +3.85 | +6.54 | +5.16 | +3.25 | +1.72 | +0.84 | +0.38 | +0.15 | +0.07 | +0.04 |
| Endogenous production | -0.11 | -0.72 | -1.24 | -1.54 | -1.58 | -1.53 | -1.08 | -0.74 | -0.58 | -0.44 |
| Glucose infusion | 2.95 | 6.91 | 6.54 | 4.83 | 3.47 | 2.35 | 1.69 | 1.12 | 0.80 | 0.42 |

Plasma insulin is gone by the sixth hour and uptake follows it down, at 0.04 mg/kg/min by the
tenth. Production does not. Its suppression peaks in the fifth hour, three hours after plasma
insulin has peaked and begun falling, and is still at 0.44 mg/kg/min in the tenth. From the sixth
hour onward, suppressed production rather than stimulated uptake is most of what the dose is still
doing.

The pathway is `ki`, the rate constant of the two-stage delay carrying plasma insulin to its
action on the liver. Its median is 0.0086 min^-1, a time constant of 116 minutes applied twice,
which puts the peak of the liver signal at 280 minutes with a tenth to ninetieth percentile of 177
to 385.

### The human comparison

Insulin's suppression of hepatic glucose production is fast, and the measured time course is a
matter of tens of minutes rather than hours.

| Source | Measurement |
|---|---|
| Edgerton DS et al., *Diabetes* 2010;59(11):2766-2775 | Under hyperinsulinaemia, hepatic glucose output falls 75 per cent within 30 minutes and is completely inhibited by 60 minutes. Net hepatic glycogenolytic flux falls 43 per cent by 30 minutes and is completely inhibited by 60 |
| Clamp literature, human | Suppression begins within about 15 minutes and is at or near maximal within 20 to 80 minutes |
| Product labelling, insulin aspart | Total duration of action 3 to 5 hours |

The Edgerton figures are from tracer studies in conscious dogs, which is the preparation this
kinetics is usually measured in, and the human clamp figures agree with them on the scale.

The model's suppression peaks at 5 hours and persists past 10. That is not a slower version of the
measured shape. A signal peaking three hours after the insulin driving it has peaked and begun
falling is a different shape, and the direction of the disagreement is that the model's liver keeps
responding to insulin that is no longer there.

### Whether the licensed successors fix it

They do not. Both were checked because adopting a successor would be a much smaller step than
editing S2008.

S2013 (Dalla Man C, Micheletto F, Lv D, Breton M, Kovatchev B, Cobelli C, *Journal of Diabetes
Science and Technology* 2014;8(1):26-34) leaves the gastrointestinal tract, glucose kinetics and
insulin kinetics identical to S2008, and rewrites the liver only to add glucagon. Its production
equation becomes `EGP = kp1 - kp2*Gp - kp3*XL + xi*XH`, where `XL` is the same delayed insulin
signal under the same parameter `ki`, and the new term carries glucagon action rather than
changing the insulin pathway. Subcutaneous absorption is unchanged.

S2017 (Visentin R, Campos-Nanez E, Schiavon M et al., *Journal of Diabetes Science and Technology*
2018;12(2):273-281) makes `kp3` and `Vmx` vary through the day to represent insulin-sensitivity
classes and the dawn phenomenon. That changes the gain of insulin's action on the liver and leaves
its delay alone. This package already implements those classes, in `SI_CLASSES` in
`timsim/patient/varying.py`, so the S2017 feature bearing on the liver is present here and does not
touch this entry.

So the delay is common to S2008, S2013 and S2017, and no licensed version of the model available
to adopt has a different one.

### What follows

This is the first entry whose direction matches the residual, and it matches both halves of it.

Prolonged suppression of production is what stops the simulated trace ratcheting upward through
the day. `docs/measurements/day_profile.json` records real participants whose inter-meal troughs
climb, 136.8 mg/dL at 07:00 to 151.4 at 11:00 to 156.3 at 17:00, against a simulated cohort
returning to its fasting level between every pair of meals. A bolus that goes on holding
production down for eight hours is a mechanism for exactly that difference, and it acts through
the flux that sets where glucose sits between meals rather than through the peaks.

It also explains why three input-side perturbations were absorbed. Weakening the correction
factor, withholding a third of meal boluses and raising night intake all change how much insulin
arrives and when; none of them changes the fact that whatever did arrive over the preceding eight
hours is still suppressing production.

And it bears on hypoglycaemia, which is the measure this package sits furthest from real on. Every
algorithm here is told the duration of insulin action is 300 minutes, which is what
`therapy/profile.py` supplies and what the shipped algorithms assume. A quarter of each dose acts
after that, so insulin-on-board is understated by construction and the loop redoses against
insulin it cannot see.

### Recommendation

This is the first entry where a change to S2008 is worth considering. Two of the three questions
that were open when it was written are now answered: there is a quantitative human time course, and
neither licensed successor revises the pathway, so there is nothing to adopt instead.

What that leaves is the change itself, and it should be made carefully rather than quickly. A
faster `ki` moves every simulated minute, so every measurement in this repository would describe
the model as it was before it. It has to be switchable, defaulting to the published value, so that
S2008 as published remains runnable and every existing figure stays reproducible.

The value should come from the human time course rather than from any glucose outcome here.
Edgerton's 75 per cent suppression by 30 minutes and completion by 60 gives a target the pathway
can be fitted to directly, on its own clamp, with the fit checked against the same clamp before any
cohort is run. Fitting `ki` to time in range would be the largest single instance of the thing this
repository has had to withdraw work for twice, and the strength of the prior here is what makes it
a live risk rather than a theoretical one.

One caveat belongs with the change. The parameter was identified on healthy subjects under a triple
tracer meal protocol, where endogenous insulin rises and falls with the meal, and a delay fitted in
that setting may be standing in for something else the model does not represent. A `ki` that
reproduces Edgerton's suppression curve is not guaranteed to reproduce the meal responses the
original identification matched, and both need checking rather than one.

## Where the audit stands

| Entry | Divergence | Direction against the residual | Recommendation |
|---|---|---|---|
| 1. Glucose effectiveness | 0.0065 min^-1 against a published 0.011 to 0.021 | Against: correcting it would shorten excursions further | No change |
| 2. Fasting equilibrium | 142 mg/dL against a real nadir of 134.8 | Neutral, 7 mg/dL | No change |
| 3. Liver insulin delay | Suppression peaks at 5 h against a measured 20 to 80 min | With: explains both halves | Change, carefully, switchable |

Two of three entries conclude that the model is right or close enough, which is the outcome the
audit was written to be able to reach. The third is the one that matters, and it is the only place
so far where S2008 and its successors disagree with a measurement in a direction that would account
for what this package cannot reproduce.

## Entries not yet made

The counterregulation floor is documented in `docs/DESIGN_ALIGNMENT.md` and in
`timsim/patient/varying.py` and belongs here, restated as an audit entry against the clamp
literature rather than as a withdrawn mechanism. Insulin pharmacokinetics against published
subcutaneous absorption data has not been measured here. Meal absorption against tracer studies
has been measured only through the meal-response comparison, which is an outcome rather than a
flux. Whether the licensed successors S2013 and S2017 close any of these is a separate question
and a smaller step than editing S2008.
