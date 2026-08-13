# A gap that was not there

## Question

Calibrating meal absorption variability turned up something the calibration was not looking
for. Across six users of the OpenAPS Data Commons export, real meals of 30 to 80 g eaten from
a starting glucose of 80 to 160 mg/dL peaked 135 minutes after the carbohydrate entry. The
same measurement on this simulator gave 88 to 95 minutes, at every setting of the variability
being calibrated.

Forty-five minutes is a large discrepancy in a quantity that governs when an algorithm sees a
meal and how long it has to respond. Where does it come from?

## Method

Three mechanisms were proposed and each tested by sweeping it and remeasuring the peak.

Absorption rate, by scaling gastric emptying and intestinal absorption together over 1.0, 0.7,
0.5 and 0.35.

Bolus timing, by measuring when real people actually dose relative to the carbohydrate entry,
across every user in the export with at least twenty-five meals and twenty-five boluses.

Dose size, by scaling the announced carbohydrate over 1.0, 0.9, 0.8 and 0.7 while leaving the
meal itself unchanged, which is what systematic under-counting does.

## Results

Absorption rate does not do it. Slowing every rate threefold moves the peak from 90 to 100
minutes and then saturates, while dragging the rise per gram from 1.21 down to 0.85 against a
real 1.41.

| Scale | Time to peak | Rise per gram |
|---|---|---|
| 1.00 | 90 min | 1.21 |
| 0.70 | 98 min | 1.22 |
| 0.50 | 99 min | 1.02 |
| 0.35 | 100 min | 0.85 |

Bolus timing does not do it. Across 39,619 meals from 42 users, the median bolus lands on the
carbohydrate entry, 75.1% within two minutes of it, 7.2% more than a quarter of an hour late,
and 1.2% of meals are never bolused inside ninety minutes. Mean lateness is 1.4 minutes.

Dose size does not do it either.

| Announced fraction | Time to peak | Rise per gram |
|---|---|---|
| 1.00 | 102 min | 1.32 |
| 0.90 | 92 min | 1.40 |
| 0.80 | 91 min | 1.27 |
| 0.70 | 95 min | 1.48 |

Non-monotonic and inside the noise. Under-dosing raises the peak without delaying it, because
when the peak arrives is set by the absorption profile and insulin scales its height.

The fourth possibility was that the comparison was wrong. Real time to peak was clocked from
the carbohydrate entry and the simulated from the meal, and those are not the same event:
pre-bolusing is standard practice, so an entry can precede any food by fifteen or twenty
minutes. Clocking both sides from the trough after the entry measures the duration of the rise
itself and is identical on both sides.

| | Trough to peak | Rise |
|---|---|---|
| Real, 5,189 meals, 26 users | 112 min (p25 70, p75 165) | 75 mg/dL |
| Simulated, 442 meals | 100 min (p25 75, p75 144) | 84 mg/dL |

## Discussion

The gap was mostly an artefact of clocking the two sides from different events. Twelve minutes
separate them on a like-for-like measurement, with quartiles that overlap almost entirely, and
the simulator's meals are slightly faster and slightly higher.

This is a different failure from the others in this collection. Elsewhere the explanations
were wrong and the gap was real. Here three mechanisms were built or swept against something
that was not there, and the fault is in the comparison rather than in any of the candidates.
The lesson is narrow and worth stating: a quantity is only comparable if both sides are
clocked from the same event, and "the meal" and "the carbohydrate entry" are not the same
event for anybody who pre-boluses.

One consequence follows for a calibration made earlier. The 0.51 within-person coefficient of
variation of time to peak, used to set meal absorption variability, was measured on the entry
clock and therefore carries whatever variation there is in how long before eating somebody
doses. It is an upper bound on absorption variability, and the 0.9 setting fitted to it is
probably too high. On the trough clock the real quartile spread is 0.85 of the median against
a simulated 0.69, so the direction holds and the magnitude is smaller than the entry-clock
figures suggest. That setting is not default, so nothing downstream depends on it.

## What changed

Nothing in the model. `CARB_ESTIMATE_BIAS` exists at 1.0 with the sweep recorded, and
`MEAL_ABSORPTION_SCALE` stays at 1.0 with its sweep recorded. Both are left in place because
the next person to notice a 45-minute discrepancy should find the three tests already done.
