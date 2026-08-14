# What is wrong with the UVA/Padova S2008 model, measured

Every entry is something the model does that people do not, established by a measurement rather
than by argument, with the script that reproduces it. Where this package compensates, the
compensation and its cost are named. Where it does not, that is stated.

The model is used here through simglucose, which implements S2008. S2013 and S2017 are licensed
and not redistributable, so some of what follows is fixed in a later release this work cannot
reach, and that is noted per entry.

## Glucose production is not defended during hypoglycaemia

Reproducing the protocol the human figures come from, a stepped hyperinsulinaemic clamp at 1.0
mU/kg/min with glucose held at successive plateaus, endogenous glucose production falls to a
median of 0.14 mg/kg/min at 55 mg/dL and 0.01 at 45. Rickels et al. measured 0.59 ± 0.12
mg/kg/min at the hypoglycaemic plateau in twelve people with long-standing type 1 diabetes and
no glucagon response at all. The model produces nothing where people with the arm already lost
still produce something, because `kp1 - kp2*Gp - kp3*Id` floors at zero once the clamp's insulin
suppresses it faster than the falling glucose raises it.

Insulin-dependent disposal at the same plateau is 2.22 mg/kg/min plus insulin-independent
uptake, at or below the 3.5 the human figures imply, so the deficit is hepatic and not
peripheral.

Reproduce with `examples/hypoglycaemic_clamp.py`. Compensated by `HYPO_EGP_DEFENCE`, calibrated
on that clamp. S2013 addresses this with a glucagon compartment whose secretion parameters are
unpublished, and which would be wrong for this population in any case.

## A figure for glucose production is uninterpretable without the insulin it was read at

The same subjects report 1.28 mg/kg/min during spontaneous lows under a closed loop and 0.14 at
a clamped 55 mg/dL plateau, because remote-compartment insulin is 235 in the first state and 441
in the second. This follows from the model's linear production term rather than being an error in it,
and it belongs here because a figure quoted without its insulin state supports a wrong
conclusion.

Reproduce with `examples/production_during_a_low.py`.

## Nothing arrests a falling glucose

Fifteen of forty subjects fail to complete 28 days under an ordinary correction loop, fourteen
of them ending between 10 and 13 mg/dL where the model stops being defined. On sensor readings
against 80 real users over matched windows the population sits at or below 40 mg/dL on 0.44 per
cent of readings against a real 0.07, while time below 70 mg/dL is an unremarkable two to four
per cent. The distribution is right and the extreme tail is not, so nothing computed over the
body of it reveals the problem.

Partly compensated: the hepatic defence raises completion from 13 to 16 and 16 to 18 of twenty
under two drivers and halves readings at or below 40 mg/dL. It does not reach zero failures.

## The carbohydrate response is too small

A 50 g meal on basal alone raises glucose 20.3 mg/dL per 10 g. Against 848 real carbohydrate
entries of 30 to 90 g with no insulin within half an hour, real people rise 30.7 mg/dL per
logged 10 g. Under-reporting closes part of that: across 7,034 meals bolused within 30 per cent
of the person's own carbohydrate ratio, glucose four hours later sits a median 19 mg/dL above
where it started, which is 2.9 grams uncovered on a logged 40, or 7 per cent. That is a lower
bound, because the loop was correcting throughout. Taking under-reporting between 7 and 25 per
cent, real is 24.6 to 28.7 mg/dL per true 10 g against the model's 20.3, so the model is short
by roughly 1.2 to 1.4 times.

Not compensated. The consequence is that an unannounced meal is easier here than in life: a
simulated 51 g meal nobody announced peaks at a median 174 mg/dL and stays under 180 on 20 of 33
occasions, where a real unbolused meal a third smaller peaks at 208 and stays under 180 on 31
per cent. Any algorithm relying on meal detection therefore scores better here than it should.

The parameters governing this are published and the generated population reproduces them: `kabs`
spans 0.0510 to 0.4535 across generated adults against 0.0373 to 0.5805 across the ten published
ones, with two of thirty-four below the published tenth percentile.

## The meal peak is late without insulin

A 50 g meal on basal alone peaks at a median 206 minutes in generated subjects and 243 in the
published ones, against 145 minutes for a real unbolused meal. The published subjects are the
slower of the two, so this is the model rather than the generation.

Under a loop the picture differs and the earlier finding stands: clocked from the trough that
follows a carbohydrate entry, real meals rise for 112 minutes and simulated ones for 100, with
overlapping quartiles. Insulin dominates the shape there, which is why the two measurements do
not contradict each other.

## Parameters do not move with time

S2008 fixes insulin sensitivity for the whole run, where real sensitivity moves through the day,
from day to day and across runs of days. S2017 adds intraday variation. Compensated here by the
physiology layer at a published coefficient of variation, with the day-to-day and multi-day
components added on the reasoning that independent daily draws average out over a week and real
runs of days do not.

## The population varies less than real people, except where it varies more

Between-subject spread of mean glucose is 6.0 to 6.8 mg/dL once run-to-run variation is removed,
against an implied 14.2 in the trial it is matched to, so the population carries about 45 per
cent of the real between-subject variation.

In one place it varies far too much. At a clamped 55 mg/dL plateau, glucose production runs from
nothing at all, on nine of twenty subjects, to a ninetieth percentile of 1.43 mg/kg/min, against
0.59 ± 0.12 across twelve real people. That width belongs to the published `kp1`, `kp2` and
`kp3` values, so no mechanism added on top narrows it.

## The model is undefined outside 10 to 600 mg/dL

A run ends when glucose leaves that range, which is recorded as a completion flag. It is not a
clinical event and it is not what happens to a person, who is rescued by counterregulation, by
eating, or by somebody else. Every cohort figure computed here is therefore conditioned on
survival, and survival is selection on the variable most hypoglycaemia statistics measure.

`Result.termination` records the direction and the circumstances, because a completion count
averages a hypoglycaemia failure with a hyperglycaemia one, and under oref0 SMB on the layered
bench five of seven were hyperglycaemic.

## Where this leaves the two options

Making the physiology match real bounds means changing published parameters, which departs from
the release this work is meant to represent and invalidates the closure test that keeps the
generated population honest against the thirty published subjects. It is defensible only where
there is a clean human reference to calibrate against, as the clamp gave for glucose production.

Calibrating at the interface is the alternative, and it has to happen inside the loop to mean
anything: an algorithm that dosed against unscaled glucose cannot be scored on scaled glucose.
For the carbohydrate response that means scaling what reaches the gut rather than what is
reported, which is a change to the person rather than to the model, and it needs the same
treatment as the hepatic defence: calibrated against a real measurement, regressed against every
signature, with the cost reported. The measurement available for it is bounded rather than
clean, at 1.2 to 1.4 times, and that uncertainty has to be carried into whatever is built.
