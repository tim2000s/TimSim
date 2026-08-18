# Counterregulation and exercise: what is being built, and what would refute it

Two mechanisms, designed together because both act on hypoglycaemia and both would otherwise be
credited with each other's effect. Written before either is implemented so the criteria cannot
be chosen after the result is known.

The bar is `CONTRIBUTING.md`'s: a new mechanism arrives with the statistic it is meant to move,
the same statistic with the mechanism off, and every other statistic as well.

## Why counterregulation is being revisited at all

`patient/varying.py` currently declines to implement glucagon on two grounds. One is that the
secretion parameters of S2013 are unpublished, which remains true: Pompa et al. 2021 reproduces
the structure and marks those parameters calibrated without giving values, and Resalat et al.
2019 discloses everything but models glucagon infused from a pump rather than secreted by an
alpha cell.

The second ground is the one that has changed. The package says the glucagon response "is lost
within a few years of diagnosis and clamp studies find no discernible rise in that population",
which is true of Rickels et al. 2015: twelve people with long-standing type 1 diabetes and no
glucagon response, producing 0.59 ± 0.12 mg/kg/min at the plateau. The Hypo-RESOLVE clamp study
measures a different and broader population. Across 47 people with type 1 diabetes the glucagon
response to a 2.8 mmol/L clamp is 9.4 ± 0.8 pmol/L against 30.6 ± 4.7 in 16 controls: attenuated
to roughly a third, not absent.

Both are true of different people. What follows is that glucagon responsivity is a property that
varies between subjects, from none to about a third of healthy, and the package currently models
neither the response nor the variation.

This matters beyond glucagon. `HYPO_EGP_DEFENCE` is fitted to Rickels, so it is fitted to a
population with no glucagon at all. Adding a glucagon term on top of a gain calibrated that way
would count the same production twice.

## C. The glucagon secretion gate

### Structure

Three compartments, following the S2013 shape as described in Dalla Man et al. 2014, with
parameters taken from measurements rather than from the unpublished set.

    secretion    S(G, dG/dt) = static term below a threshold + dynamic term on the fall rate
    kinetics     one compartment, clearance from Hinshaw et al. 2015
    action       EGP stimulated with delay, glycogenolysis and gluconeogenesis arms

Per-subject alpha-cell responsivity is drawn so the cohort spans no response to about a third of
healthy, which is the span the two clamp studies together describe.

### Calibration targets, and why there are two

The mechanism is fitted to the glucagon concentration and scored on the glucose production. They
come from different studies on different people, so hitting both is a real constraint rather
than a restatement of the fit.

    target 1   glucagon at a 2.8 mmol/L clamp     9.4 pmol/L (Hypo-RESOLVE, n=47)
    target 2   EGP at the plateau                 0.42 to 0.84 mg/kg/min (Rickels, n=12)

### What would refute it

The arithmetic that has to work is not obviously favourable, and it is stated here so the answer
is not negotiated afterwards. Hinshaw's glycogenolysis sensitivity is 0.112 to 0.272 μmol/kg/min
per ng/mL. A 9.4 pmol/L response is about 0.033 ng/mL, so the glycogenolysis arm contributes
roughly 0.0007 to 0.0016 mg/kg/min. Against a target of 0.42 to 0.84 that is under half a per
cent. The gluconeogenesis arm is quoted as 0.008 to 16.15 μmol/kg/min per ng/mL, a two
thousandfold range, which is a parameter the study could not identify.

So the honest prior is that a glucagon gate calibrated to the measured T1D response will
contribute very little of the production it is meant to explain, and that the room to claim
otherwise lives entirely in an unidentifiable parameter.

**C is refuted if** reproducing 9.4 pmol/L at the clamp requires a gluconeogenesis sensitivity
outside Hinshaw's published range in order to reach the Rickels EGP band, or if the glucagon
contribution to EGP at the plateau is under 10 per cent of the total with the sensitivity at the
top of its range. In either case the mechanism does not carry the production and
`HYPO_EGP_DEFENCE` stays as the empirical stand-in it already is, with this recorded as the
reason.

**C succeeds if** one parameterisation inside the published ranges produces both 9.4 pmol/L and
an EGP inside 0.42 to 0.84 without the defence gain, in which case the gain is removed and
replaced by a mechanism with two independent anchors.

### Tests

    the clamp reproduces the Hypo-RESOLVE glucagon concentration at 2.8 mmol/L
    the clamp reproduces the Rickels EGP band at the same plateau
    a subject with zero responsivity reproduces the Rickels population specifically
    glucagon rises on a falling glucose and not on a low steady one, which is what the
      dynamic term is for
    switching the gate off returns the model to its current behaviour exactly
    the two mechanisms are not both active by default, so production is not counted twice

## D. Grounding the exercise layer

The layer exists in `person/activity.py` with `VMX_GAIN` at 1.6, `VM0_GAIN` at 1.5 and a
post-exercise term decaying over seven hours. Every one of those is a modelling choice with no
citation. It is off by default because it was never grounded, not because it is absent.

### Calibration targets

Observational, from 428,058 exercise sessions across 3,248 people with type 1 diabetes, which is
a far larger base than anything the layer was built against:

    acute glucose fall, walking          -1.24 ± 0.81 mmol/L
    acute glucose fall, aerobic          -1.43 ± 1.02
    acute glucose fall, anaerobic        -0.52 ± 0.81
    delayed hypoglycaemia within 6 h     21.2 per cent aerobic, 11.2 per cent resistance

Resalat et al. 2019 provides a disclosed alternative structure with parameter values, which is
the comparator for whether our two-gain form is adequate or needs replacing.

### What would refute it

**D is refuted as a default** if, with the acute falls calibrated to the figures above, the
fidelity signatures move away from the real ranges on balance. Variability is the specific risk:
the current cohort sits at 38.3 per cent CV against a real 29.5 to 34.3, already above range, and
exercise adds variability. It could still be right to ship it switchable.

**D succeeds as a default** if calibrating the acute falls also moves the autocorrelations down
towards their ranges, which are currently 0.92 and 0.76 against 0.78 to 0.87 and 0.50 to 0.68,
without pushing variability further out.

### Tests

    a session lowers glucose by the measured amount for its type, on basal alone
    the anaerobic and aerobic responses differ in the measured direction
    delayed hypoglycaemia occurs at the measured rate in the six hours after a session
    the post-exercise term needs insulin on board to produce a low, and a session does not
    switching the layer off returns the model to its current behaviour exactly

## The default-or-switchable decision

Decided on evidence rather than preference, by the same rule the infusion site layer was decided
by. Run the full signature panel with the layer off and on, paired on the same subjects, and
count how many of the ten medians sit inside the real ranges. The layer ships by default only if
it does not reduce that count and does not move the classifier the wrong way.

The count to beat is the one this rebuild produced, which is four of ten with six failures
concentrated in variability, both autocorrelations, the outcome spread, hypoglycaemia recovery
and hypoglycaemia rebound. Exercise plausibly helps three of those and hurts one.

# Outcomes

Both mechanisms were built and measured against the criteria above. Recorded here rather than in
a separate document so the design and its result cannot drift apart.

## C: refuted on magnitude

Fitting secretion so a maximally responsive subject reaches the measured 9.4 pmol/L at a
2.8 mmol/L clamp, glucagon drives 0.0864 mg/kg/min at the most favourable parameterisation
inside the published ranges, which is 14.6 per cent of the 0.59 Rickels measured at that depth.
Reaching the bottom of the Rickels band would need a gluconeogenesis sensitivity of 78.5 against
a published upper bound of 16.15.

The design fixed two criteria joined by `or`. The second did not fire, since 14.6 per cent is
above the tenth set as the floor. The first did. `HYPO_EGP_DEFENCE` stays as the empirical
stand-in, and `timsim/patient/glucagon.py` is imported by nothing but its own calibration script.

Two defects in the module are recorded in its docstring rather than repaired, because repairing
a mechanism that cannot carry the production it exists to explain would be effort spent on the
wrong question. Its dynamic arm produces the wrong ordering, giving more glucagon for a slower
fall than a faster one, and the shape of the responsivity distribution between its two anchored
ends is a modelling choice.

## D: calibrated, and switchable rather than default

The layer was too weak by a factor of 2.5, and the claim beside its gains, a 23 mg/dL fall over
a sixty-minute session, was never measured; the old values gave 10.8 mg/dL. At a scale of 2.5 it
reproduces both the acute fall (-24.4 against a real -25.8) and the rate of delayed
hypoglycaemia (25 per cent against a real 21.2), which are separately carried by the
insulin-independent and insulin-dependent terms.

On the signatures, paired over 26 subjects with bootstrap intervals, three of ten movements
exclude zero and two of those move a failing signature towards its range: the autocorrelation at
sixty minutes by -0.017 [-0.030, -0.003] and the outcome spread by +1.123 [+0.584, +1.692].
None moves away. The concern that it would worsen variability is not supported: +0.536
[-0.412, +1.534] spans zero, as do hypoglycaemia recovery and rebound.

That reverses the finding that kept the layer off. The docstring recorded it raising both
autocorrelations "where the whole purpose was to lower them", and that was measured at 40 per
cent of the calibrated magnitude.

On outcomes, paired across all four pairings of the bench matrix, the effect is almost entirely
hypoglycaemia absorbed by eating. Rescue carbohydrate rises by 4 to 7 helpings per 30 days in
every pairing with every interval excluding zero. Time below 70 mg/dL rises in three of four.
Time in range does not move anywhere.

**Switchable, not default.** Three reasons in order of weight. It worsens time below 54 mg/dL,
which is the one measure where the layers already move away from real rather than towards it and
the paper's main negative finding. It cannot represent exercise type, and type is the clearest
signal in the reference dataset, where anaerobic exercise falls least and this layer would fall
most. And its schedule has no local grounding, since the Nightscout records carry no exercise
events.

What it is good for is what the default bench cannot do at all: present exercise-induced
hypoglycaemia as a challenge an algorithm has to handle. That is a capability worth having as an
arm and not worth having as a default that degrades the headline comparison.
