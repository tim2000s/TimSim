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

The measured 141.8 is not a property of this package's population generation. S2008 draws basal
glucose from its joint distribution at an average of 140 mg/dL, so the measurement reproduces the
published release. S2013 lowered that average to 120, which makes this a property of the
unlicensed version specifically and one the licensed successor has already addressed. Entry 4 has
the sources.

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
| 3. Liver insulin delay | Suppression peaks at 5 h against a measured 20 to 80 min | With: explains both halves | No change: no value of `ki` meets both the clamp and the meal |
| 4. Nondiabetic parameter provenance | Subjects derive from a nondiabetic joint distribution | Bears on the population's narrowness | No change available |

All three entries conclude no change, for three different reasons. Entry 1 diverges in the
direction that would make the residual worse. Entry 2 is small enough not to matter. Entry 3
diverges in the direction that would explain the residual and cannot be corrected by the parameter
that carries it, because the same parameter is what makes the meal response right and the two
requirements do not overlap.

That third result is the useful one. The gap this package cannot close is, on the evidence so far,
a structural property of the S2008 liver rather than a tuning error, and closing it would mean
replacing one first-order delay with two rather than adjusting the one that is there.

## Testing entry 3: what would refute a faster liver delay

Written before the parameter is changed and before any cohort is run, so the criteria cannot be
chosen once the answer is known. This is the eighth mechanism proposed against the residual and
seven have been refuted, several of which were argued as confidently as this one.

### The change

`ki` becomes settable, defaulting to the published value, so S2008 as published stays runnable and
every figure measured before the change stays reproducible. Nothing else moves: `kp1`, `kp2` and
`kp3` keep their published values, so the strength of insulin's effect on the liver is untouched
and only its timing changes.

The value comes from Edgerton's suppression curve on its own clamp, fitted before any cohort runs
and checked against that curve rather than against any glucose outcome. The target is 75 per cent
suppression of hepatic production within 30 minutes of a step in insulin and complete suppression
by 60.

### Gate 1: the parameter must reproduce the human suppression curve

On a hyperinsulinaemic euglycaemic clamp, at the fitted value, suppression at 30 minutes must land
between 65 and 85 per cent and suppression at 60 minutes above 90. Outside that the fit has failed
and nothing downstream is worth running.

### Gate 2: the model must still reproduce what it was identified on

`ki` was identified on healthy subjects under a triple-tracer meal protocol, so a faster value may
break the behaviour it was fitted for. After the change the simulated meal response must keep its
agreement with the real one already recorded in `docs/measurements/meal_response.json`: trough to
peak within 20 minutes of the real 112, and rise per gram within 25 per cent of the real 1.41
mg/dL. A change that closes the residual by breaking the model's own validation target has not
improved the model, and this gate is the reason the entry cannot be judged on cohort outcomes
alone.

### Gate 3: the residual

Judged on the DCLP3 pairing at the default announcement condition, against the arms in
`docs/measurements/baseline_2026-08-24/`.

Time above 180 mg/dL must rise from 13.7 per cent at least half way to the trial's 26.9, meaning
20.3 or above. Below that the delay is a contributing term rather than the explanation, whatever
else it does.

It must not overshoot: a median above 32 per cent, or time in range below 62, says the parameter
has been pushed past what the human curve supports and any agreement is coincidental.

Time below 54 mg/dL must not rise above its present 0.5 per cent. Insulin that stops acting sooner
should reduce unseen insulin-on-board and improve this measure, and a failure to improve it would
say the mechanism is not doing what this entry claims.

The Commons pairing must not lose the agreements it holds. Mean glucose and variability both agree
there at present, and a change that fixes DCLP3 by breaking the Commons has traded one reference
for another.

Completion must hold at 65 of 86 or better on the DCLP3 cohort.

### Result: the two gates cannot both be met, and the parameter is not the fix

Gate 1 asks the liver to reproduce Edgerton's clamp. Gate 2 asks it to keep reproducing the meal
response the parameter was identified on. Measured across six values of the scale on 40 subjects
(`examples/liver_delay_fit.py` and `examples/meal_with_bolus.py`):

| `ki` scale | Clamp suppression at 30 min | Gate 1 | Meal trough to peak | Gate 2 |
|---|---|---|---|---|
| 1 (published) | 1 % | fail | 102 min | pass |
| 2 | 6 % | fail | 95 min | pass |
| 4 | 20 % | fail | 62 min | fail |
| 6 | 34 % | fail | 65 min | fail |
| 8 | 47 % | fail | 68 min | fail |
| 11 | 69 % | pass | 68 min | fail |

Gate 1 needs 65 to 85 per cent suppression at 30 minutes, which no value below eleven reaches.
Gate 2 needs trough to peak within 20 minutes of the real 112, which no value above two reaches.
The two requirements do not overlap, and there is no value of `ki` that satisfies both. Rise per
10 g stays inside the real 15.9 to 19.7 at every scale, so the meal failure is a timing failure
and not a magnitude one.

The published value is the one that reproduces the meal. At a scale of 1 the simulated meal peaks
102 minutes after its trough against a real 112, comfortably inside the real spread of 70 to 165,
and speeding the liver moves it to 62 to 68, below the real tenth percentile. So S2008 as
published is right about the thing it was fitted to and wrong about the clamp, and the parameter
cannot be moved without trading one for the other.

### What that means

The divergence in entry 3 is real and it is not a mis-set number. One first-order delay carries
plasma insulin to the liver, and it has to serve two responses with different timescales: the
acute suppression a clamp measures in tens of minutes, and whatever slower behaviour the meal
identification needed. A single time constant can sit at one or the other. The model's authors
put it where the meal data wanted, which is a defensible choice for a meal simulation model and
is the origin of the shape this package runs into over a 24-hour closed loop with repeated boluses.

Fixing it properly means a structural change rather than a parameter: two insulin actions on the
liver with separate time constants, a fast one calibrated on the clamp and a slow one carrying
whatever the meal identification needed. That is a different model, not a re-tuned one, and it
would need identifying against both datasets rather than gated against them.

### Recommendation

No change to `ki`. The switch stays in the code, defaulting to the published value, because the
measurement above needs to be reproducible and because a future two-timescale implementation would
use the same entry point. Entry 3's earlier recommendation to change the parameter is withdrawn on
this evidence.

The residual in `docs/DESIGN_ALIGNMENT.md` therefore remains unexplained after eight mechanisms.
What has changed is that the eighth is the first to fail for a reason worth having: not that the
mechanism was absent or too small, but that the model cannot represent it and the published
parameter is already at the best compromise available within the structure.

### What is reported either way

Every signature in `docs/FIDELITY.md`, the hour-of-day profile against DCLP3, and the excursion
decomposition, since the entry's claim is specifically about inter-meal troughs ratcheting and
about excursion duration rather than about a headline percentage.

## 4. The virtual population descends from nondiabetic parameter distributions

### What the model's own papers say

This entry needs no simulation. It is what the releases record about where their subjects come
from, and it bears on several of the measurements above.

The parameters were identified on people without diabetes. Dalla Man et al. fitted the meal model
to a normal-subject database under a triple-tracer protocol, and the simulator paper states that
"at the time of the first release of the simulator, reliable joint parameter distributions were
available for a nondiabetic adult population". The type 1 subjects were made from those: "the T1DM
parameter joint distributions were derived from those available in the nondiabetic adult
populations", with "certain clinically relevant modifications introduced in the average parameter
vector", of which the paper's example is that basal endogenous glucose production was assumed
higher.

So the virtual population is a nondiabetic joint distribution with adjustments to its mean, rather
than a distribution identified on people with type 1 diabetes. The adjustments act on the average
parameter vector; the covariance structure and the spread are inherited.

S2013 did not change this. It moved the average basal glucose from 140 to 120 mg/dL, and generated
the new counterregulation parameters "from an appropriate joint distribution" rather than from
identification. Its hypoglycaemia utilisation model was validated against 32 subjects with type 1
diabetes under clamp, but that validated the model rather than generating the parameter
distributions. Its glucagon kinetics come from 13 datasets in 11 adults.

### What follows for the measurements above

It supplies a mechanism for the population's narrowness, which is the largest single limitation on
what this package can be used for. The cohorts carry 0.46 to 0.68 of the real between-subject
spread on every measure describing where glucose sits. A joint distribution taken from people
without diabetes should be expected to produce that: glycaemic outcomes vary far less between
people whose glucose is regulated than between people whose glucose is managed. Widening it is not
a matter of adding noise to the parameters, since the covariance rather than the marginal spread is
what was inherited.

It also dates entry 2. The population's basal glucose has a median of 141.8 mg/dL, which is the
S2008 average of 140 rather than anything this package chose, and S2013 already moved that average
to 120. So entry 2 is a property of the unlicensed release specifically, and the licensed successor
has addressed it.

And it explains entry 3 without excusing it. `ki` was identified on a meal protocol in people
without diabetes, whose insulin rises and falls endogenously with the meal. A delay fitted in that
condition is being asked here to describe a liver responding to repeated exogenous subcutaneous
boluses across a closed-loop day, which is not the condition it was measured in.

### The same criticism applied to this audit

The references used against the model above are not drawn from people with type 1 diabetes either,
and the audit should say so rather than let a reader assume otherwise.

Entry 1 compares glucose effectiveness against 0.021 min^-1 in people without diabetes and 0.011 in
type 2 diabetes, because a type 1 figure was not found. Entry 3 compares the suppression of hepatic
production against Edgerton et al., which is a tracer study in conscious dogs, supported by human
clamp figures that are qualitative. Only the outcome references, DCLP3 and the Commons, are type 1
populations, and those are glucose traces rather than fluxes.

That scarcity is not incidental. Measuring endogenous glucose production or glucose effectiveness
requires tracer studies that are rarely done in type 1 diabetes, which is why the model was built
the way it was and why this audit compares against what exists. It bounds both. A divergence
established against a canine or nondiabetic reference is a reason to investigate rather than a
demonstration that the model is wrong about people with type 1 diabetes.

### Recommendation

No change is available. The provenance cannot be corrected without a joint parameter distribution
identified on people with type 1 diabetes, which does not exist publicly and which this package
cannot produce. It is recorded because it is the most likely origin of the population narrowness
that limits every between-subject claim made here, and because a reader of any figure in this
repository should know that the subjects underneath it began as people without diabetes.

## Entries not yet made

The counterregulation floor is documented in `docs/DESIGN_ALIGNMENT.md` and in
`timsim/patient/varying.py` and belongs here, restated as an audit entry against the clamp
literature rather than as a withdrawn mechanism. Insulin pharmacokinetics against published
subcutaneous absorption data has not been measured here. Meal absorption against tracer studies
has been measured only through the meal-response comparison, which is an outcome rather than a
flux. Whether the licensed successors S2013 and S2017 close any of these is a separate question
and a smaller step than editing S2008.

## 5. The liver can produce glucose and never take any up

### What was measured

Read from the model rather than simulated. simglucose's plasma glucose balance is

    dxdt[3] = max(EGPt, 0) + Rat - Uiit - Et - k1*Gp + k2*Gt

and there is no hepatic uptake term anywhere in it. Production is floored at zero, so the liver
is a source or it is nothing. The only way it can respond to a meal is by producing less.

`docs/measurements/meal_appearance.json` measures what that costs. Forty adults, one uncovered
60 g meal, differenced against the same subject eating nothing: of 658.9 mg/kg appearing, 218.2
is taken up by insulin-dependent uptake, 18.3 is excreted renally, and production falls by 242.8.
The liver absorbs more of the meal than the tissues do, and it does it entirely by switching
itself off.

### The human comparison

Hwang et al. (J Clin Invest 1995; 95:783-787) is the measurement, read here on 1 September 2026,
and it is smaller than the first version of this entry assumed. Six subjects with
insulin-dependent diabetes and nine weight-matched controls were followed by 13C nuclear magnetic
resonance through a day of three isocaloric mixed meals on a 35 kcal/kg diet at 60 per cent
carbohydrate. Fasting hepatic glycogen was similar in both groups. By 23:00 the diabetic subjects
had synthesised 30 per cent of what the controls had: a net increment of 44 plus or minus 20 mM
against 144 plus or minus 14.

At a liver volume of 1.5 litres that is 11.9 g of glucose stored across a whole day against 38.9 g
in the controls, on an intake near 368 g for a 70 kg adult. So net hepatic storage is about 3 per
cent of carbohydrate eaten in type 1 diabetes and about 11 per cent without it. The first version
of this entry called it a substantial share, which was wrong for this population by roughly an
order of magnitude, and 3 per cent is the same size as the renal excretion already dismissed here
as too small to matter.

Hwang's subjects had a mean glycosylated haemoglobin of 10.2 plus or minus 0.3 per cent and the
paper calls them poorly controlled throughout. This package titrates its population until each
subject clears the consensus hypoglycaemia floors, so it simulates a well-controlled one, and the
3 per cent belongs to a group it does not represent. A first version of this paragraph concluded
that a model with no hepatic uptake is close to right for type 1 diabetes. That holds for Hwang's
population and was written without checking whose population it was.

What a well-controlled liver does is unresolved, and two reported sources disagree about it.
Gursan and Prompers (Metabolites 2022) is reported to say that net glycogen synthesis and
breakdown fall by about 74 and 47 per cent in poorly controlled type 1 diabetes, that short-term
intensive insulin partially restores them, and that long-term basal-bolus therapy or pump therapy
normalises them completely. Brunasso et al. (Diabetologia 2026) is reported to find postprandial
hepatic glycogen accumulation absent in ten adults at a mean HbA1c of 6.7 per cent, with peak
hepatic glucose higher than in controls at 4.7 plus or minus 2.0 against 3.0 plus or minus 0.8
mmol/l, which reads as reduced extraction rather than restored handling.

So the omission is somewhere between about 3 and about 11 per cent of carbohydrate intake for the
population this package simulates, and which end depends on a disagreement neither paper has been
read to settle. Both reached here through a literature review tool on 1 September 2026 whose own
completion status was reported inconsistently, so they are recorded as claims to check rather than
as measurements.

Hwang also found the gluconeogenic pathway contributing 59 plus or minus 4 per cent of glycogen
synthesis in the diabetic subjects against 35 plus or minus 4 in controls, and concluded that the
storage defect "may result in an impaired glycemic response to counterregulatory hormones".

Bischof et al. (Diabetes 2001; 50:392-398) measured what improving insulin treatment does to the
same quantity and is still unread, behind a paywall as of 1 September 2026.

Expressed as suppression of the subject's own production, which is how the tracer literature
reports it, the model suppresses 23.2 per cent plus or minus 8.8 over an eight-hour window. A
triple-tracer mixed-meal study puts adults with type 1 diabetes at 44.4 plus or minus 16.9 and
adults without at 59.8. The windows are not matched and the model figure is diluted by averaging
over eight hours, so the two are not yet comparable and the gap should not be quoted until they
are.

### What follows

The missing uptake is too small to matter and the suppression is not missing at all, both of which
were settled after this entry was first written.

`docs/measurements/hinshaw_meal.json` reproduces Hinshaw's protocol at 10 kcal/kg over six hours
and puts postprandial suppression of production at 43.3 per cent on basal insulin against a
measured 43.5 to 52.3, so the model suppresses about as much as people do. The 23.2 per cent
quoted earlier was the same quantity diluted over eight hours, which is what comes of comparing
before matching a window.

What that comparison did find is that the model suppresses for the wrong reason. Adding a meal
bolus makes suppression fall to 28.3 per cent, because production here is held down by
hyperglycaemia through `kp2` and insulin arriving through `kp3` peaks at five hours, so inside a
six-hour window the bolus lowers glucose and releases the liver. Entry 3 predicts exactly that
from Edgerton's clamp, and this is the same defect measured on a meal in the population the
package simulates.

So the liver is not the explanation for the small rise. Against Hinshaw, whole-body glucose
disappearance is 6308 micromol/kg over six hours with no bolus and 10177 with a full titrated one,
against a measured 8392 to 8535, so the two arms straddle the human value and the disposal side is
not obviously wrong either. Fasting production at 13.5 micromol/kg/min against a measured 16.2 to
19.5 says the whole glucose turnover runs about three-quarters of the human rate, which is the
remaining candidate and is a statement about the population rather than about any one channel.

### Whether the design is defensible

Partly, and the reference is worth recording because it cuts against the obvious criticism. S2008
drives production from peripheral insulin through a delay, where a real pancreas secretes into the
portal vein and exposes the liver to two to three times the peripheral concentration, a gradient
that subcutaneous insulin reverses in type 1 diabetes (Geho et al., J Diabetes Sci Technol 2009;
3:1451-1459). But Ader and Bergman (Am J Physiol 1990; 258:E1020-E1032) titled their paper
"Peripheral effects of insulin dominate suppression of fasting hepatic glucose production", which
is the model's assumption stated as a finding. The portal question is live rather than settled,
and a single insulin compartment is a defensible reading of it for fasting production.

### Recommendation

No change, and read Hwang 1995 before revisiting. A hepatic uptake term is a structural addition
to a published model, which this package has declined before on the grounds that it should stay
close to what UVA/Padova does, and the two missing mechanisms point away from the gap that
prompted the search. Recording it matters because the next person to find the liver absorbing 38
per cent of a meal should know it is doing so through the only channel it has.

### A shipping mechanism this bears on

Kishore et al. (Diabetes 2006; 55:659-666) analysed hepatic glycogen breakdown during
insulin-induced hypoglycaemia by 13C spectroscopy in 10 non-diabetic and 7 type 1 diabetic
subjects at HbA1c 6.5 plus or minus 0.2 per cent, and concluded that in intensively treated type 1
diabetes hypoglycaemia failed to stimulate hepatic glycogen decomposition or activate endogenous
glucose production. `HYPO_EGP_DEFENCE` ships at 0.05 to make production respond to hypoglycaemia,
calibrated against Rickels et al. 2015 on a stepped clamp. If Kishore's population is the one this
package simulates, the stock model's failure to produce at depth may be the right behaviour for
intensively treated type 1 diabetes rather than the defect the defence was built to correct. Read
before the defence is next touched, again through Jiang rather than at first hand.

### A reframing of entry 3, reported rather than read

Entry 3 treats the five-hour peak of insulin's action on production as a timing defect. A
literature review on 1 September 2026 returned a mechanism that would make it partly deliberate,
and it is recorded here because it changes what a fix would have to do rather than because it is
settled.

Ader and Bergman's result is reported, through Petersen, Vatner and Shulman (Nat Rev Endocrinol
2017), to work through adipose tissue: peripheral insulin suppresses lipolysis, which lowers
non-esterified fatty acid delivery to the liver, which lowers hepatic acetyl-CoA, which
deactivates pyruvate carboxylase and so suppresses gluconeogenesis. On that account the dominant
route from peripheral insulin to production is indirect and runs through a tissue S2008 does not
model at all, and a slow lumped delay is a defensible stand-in for it.

The same review reports the INTIMET trial (Snaith et al., Nat Commun 2025), 40 adults with type 1
diabetes against 20 controls, finding production 64 per cent higher during a low-dose clamp at
5.9 plus or minus 2.2 against 3.6 plus or minus 1.7 micromol/kg fat-free mass per minute, with
non-esterified fatty acids also higher at 0.08 plus or minus 0.01 against 0.02 plus or minus 0.02
mmol/l. If that holds, the substrate route is measurably impaired in this population and the
model has no term for the thing that is impaired.

What it does not explain is Edgerton's clamp, where suppression reaches 75 per cent within 30
minutes. An indirect route through lipolysis is not that fast. So the likeliest reading is that
production responds to insulin on two timescales and S2008 carries only the slow one, which is
what the two-timescale liver was built for and what the gates could not decide.
