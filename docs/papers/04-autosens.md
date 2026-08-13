# Sensitivity detection, and the hypothesis it was built to confirm

## Question

Running oref0 SMB on this simulator gives 6.5% of time below 70 mg/dL against 1.3% for Boost
and 2.4% for the built-in loop on the same twenty subjects. The obvious explanation was that
the adapter pinned oref's sensitivity ratio at 1.0, so the algorithm never backed off after a
run of lows. If so, the effect runs one way and the hypoglycaemia figures are upper bounds.

## Method

Autosens was implemented, following AndroidAPS's Oref1 form. It runs an eight-hour and a
twenty-four-hour window and takes the lower ratio, discards positive deviations below 80
mg/dL, and excludes carbohydrate absorption, the 45 minutes after any carbohydrate entry, and
any rise while insulin on board is high.

This is the one part of the arm that is reimplemented rather than shipped code, and the
reversal was deliberate. oref0 ships autosens twice. The JavaScript reads Medtronic pump
history and rebuilds insulin and meals from it through four more modules, so running it would
mean synthesising a pump history and putting the reconstruction in charge of the answer.
AndroidAPS's plugin takes a store whose deviations are computed elsewhere, so bridging it
would leave the part that matters on this side of the pipe. Reimplementing eighty lines of
arithmetic is the smaller risk, and unlike a pump history it can be tested directly.

The arm was then run twice on the same twenty-one subjects, once with detection running and
once with the ratio pinned, paired per subject.

## Results

| | Pinned at 1.0 | Detection running | Paired difference |
|---|---|---|---|
| Insulin, U/day | 63.39 | 67.44 | +4.05, interval 9.53 |
| Time in range | 74.38% | 74.16% | -0.22, interval 1.11 |
| Below 70 | 6.95% | 6.47% | -0.47, interval 0.65 |
| Below 54 | 2.40% | 2.13% | -0.27, interval 0.37 |
| Above 180 | 18.68% | 19.37% | +0.70, interval 1.21 |

Every interval spans zero.

The detector is not idle. Per-subject median ratios run from 0.70 to 1.00, and six of the
twenty-one sit at the 0.70 clamp, which means for those subjects it is asking for a larger
reduction than oref permits and the hypoglycaemia is unmoved regardless.

## Discussion

The hypothesis is refuted. The figures below 70 and 54 stand as they are rather than as upper
bounds, and the caveat recorded in this repository saying otherwise was wrong and has been
removed.

Attention then moved to where the insulin causing a low is delivered. In the half hour before
a low oref has delivered nothing at all, median 0.00 U against a scheduled 0.72, so it sees
the fall coming and is already fully suspended. In the five hours before, it delivered 12.93 U
against a scheduled 7.24, which is 79% above schedule and 24% more than the built-in loop
delivers before its own lows. That 24% is the same figure by which its total daily insulin
exceeds that loop's. The excess is distributed rather than concentrated, and by the time it is
visible there is nothing left to withhold.

The insulin action curve was the next candidate and was also refused. Compared against the
glucose response of the simulated body to a bolus small enough to stay in a linear region,
checked by doubling the dose and confirming the response doubled, the reported curve tracks
the body closely to two hours and overstates remaining insulin by five to nine points from two
to four. That bias makes an algorithm believe more insulin is working than is, so it doses
less, which is the wrong direction.

Two earlier versions of that curve measurement were wrong and both produced confident numbers.
The first gave a whole unit at fasting, which drove glucose to zero, so it measured the
approach to the floor and reported the curve as twice too slow. The second corrected the dose
but multiplied it by 6000/BW, which the patient model already does, delivering about eighty
times what was intended so that only one subject in five stayed in a linear region.

## What changed

`controller/autosens.py` exists, is tested on fifteen behaviours including that a meal is not
read as insulin resistance, and runs by default in the oref adapter. It is kept because it is
part of the algorithm under test and its absence would be a difference from the shipped
system, not because it improves anything measured here.
