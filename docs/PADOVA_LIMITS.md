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

## The carbohydrate response is larger than real, not smaller

Earlier versions of this document reported the opposite, that the model rose 20.3 mg/dL per 10 g
against a real 30.7 and was short by 1.2 to 1.4 times, across 848 real carbohydrate entries with
no insulin within half an hour. No code in this repository produced those numbers. Measured on
the full export under that same filter the real figure is 19.71 mg/dL per logged 10 g across
7,996 entries from 128 users, and 848 is a tenth of 7,996, which is the sample the
`entries_*.json` glob returned before it was widened to `*entries*.json` to catch the users
whose filenames carry no prefix.

Both sides are now measured by committed code. On the simulated side each subject is given one
meal on basal alone and run again eating nothing, so the meal is separated from whatever the
subject was doing anyway: 22.20 mg/dL per 10 g across 51 subjects at 50 g, with the response
linear in size at 22.13, 22.20 and 22.30 for 30, 50 and 70 g. On the real side the definition of
an uncovered meal is recorded per meal rather than applied, and the answer sits between 15.7 and
19.7 mg/dL per logged 10 g across every defensible choice:

    no insulin within 30 min, any baseline                       7996   19.71
    no insulin within 30 min, baseline 80 to 180                 5343   18.53
    bolus-free 30 min before to 120 after, baseline 80 to 180    2501   15.69
    bolus-free a full action duration before and 4 h after        388   17.38
    the same, and the loop within 0.5 U of schedule over 4 h       320   16.00

Logged grams under-state what was eaten, so the real rise per gram consumed is lower still,
which widens the difference rather than closing it. Two features of the real subset push its
figure up rather than down: the filter admits meals where the loop withheld basal as well as
meals where it delivered the schedule, and any carbohydrate the person did not log inside the
window is counted as part of the response to the carbohydrate they did.

So an unannounced meal is not easier here than in life, and the conclusion drawn from that,
that any algorithm relying on meal detection scores better here than it should, does not follow
from this measurement. Reproduce with `examples/meal_response.py` and `examples/real_meals.py`.

The parameters governing this are published and the generated population reproduces them: `kabs`
spans 0.0510 to 0.4535 across generated adults against 0.0373 to 0.5805 across the ten published
ones, with two of thirty-four below the published tenth percentile.

## The meal peak arrives inside the real range without insulin

Also previously reported as a defect, at 206 minutes in generated subjects against 145 for a
real unbolused meal. The real figure was measured on the same tenth of the sample. Across the
filter variants above real meals peak between 177 and 248 minutes, and the model peaks at 225
with an inter-quartile range of 188 to 278, so it sits inside the real range rather than an hour
outside it.

Under a loop the earlier finding stands: clocked from the trough that follows a carbohydrate
entry, real meals rise for 112 minutes and simulated ones for 100, with overlapping quartiles.
Insulin dominates the shape there, which is why the two measurements do not contradict each
other.

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
It was going to be used on the carbohydrate response, by scaling what reaches the gut rather
than what is reported. That is no longer indicated. The response is not short, so there is
nothing to scale up, and scaling it down towards the real figure would be calibrating the
person against a real measurement whose own filter moves it between 15.7 and 19.7 mg/dL per
logged 10 g, on grams that are known to be under-reported by an unmeasured amount.

What remains worth doing at the interface is hypoglycaemia, which is the gap that survives
everything tried against it. Fitting the unpublished parameters of a Control-IQ stand-in to one
half of DCLP3 and testing on the other leaves time below 70 and below 54 mg/dL at +0.55 and
+0.59 of the real between-person spread on the held-out half, against +0.76 and +1.42 for the
unfitted variant. A controller chosen to minimise the distance removes about half of it, so
most of what is left belongs to the person rather than to the algorithm driving it.
