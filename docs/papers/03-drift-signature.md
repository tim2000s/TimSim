# A statistic that could not see the thing it measured

## Question

`analysis/signatures.py` opens by stating that its eleven statistics are "computed identically
on real data and on simulator output, so the two are directly comparable". One of them is
`drift`, the week-to-week movement of insulin sensitivity, and it was the only in-range result
supporting the physiology layer. Does it measure the person?

The question arose because the physiology layer had just failed a different test. Walking the
layer ladder under four separate drivers, that layer produced no movement in any signature
that was distinguishable from zero under all four, while the behaviour and sensor layers each
produced several.

## Method

Two checks, neither of which requires reading the algorithm.

Where the number comes from. `run.py` populates `Result.isf_weekly_cv` from
`driver.ratios.weekly_cv()`, and only when the driver is the built-in one.

Whether it responds. The physiology layer's week-to-week sensitivity term was switched off
entirely and the statistic compared against the default, paired per subject over ten adults
for 28 days under the built-in loop.

## Results

The statistic is not derived from the glucose. It reads the learned correction factor of the
built-in controller, and `AdaptingSettings.observe` adjusts that factor from glucose sitting
off target rather than from the person's sensitivity. It is undefined for any other driver,
which is why it is blank for Boost and oref throughout the four-driver ladder.

| Person's weekly sensitivity | Signature reads |
|---|---|
| Varies, as default | 8.69 %CV |
| Switched off entirely | 5.77 %CV |
| Paired difference | +1.26, 95% interval 1.55 |

The interval spans zero. The real range is 8.2 to 21.7 %CV, so the in-range verdict in the
published fidelity table was largely the controller reading its own thermostat.

## Discussion

The class that produces the number says so in passing: "it reads the algorithm's setting, not
the person's physiology". An adapting controller had been added specifically so that the
signature would have something to read, which made the signature read the adapter.

A statistic that cannot fail is not evidence, and one that reports a passing grade is worse
than an absent one, because it suppresses the search for a real measurement. The physiology
layer looked supported and was not.

The general lesson is cheap to apply and was not being applied: for each statistic, switch off
the mechanism it claims to detect and require a paired difference whose interval excludes
zero.

There is also a structural reason no glucose statistic could have done this job. A working
closed loop absorbs a sensitivity change by altering delivery, which is exactly what keeps the
glucose flat. The signal moves out of glucose and into insulin as the loop closes, so the
eleven, all computed from glucose, were looking in the one place it could not be.

## What changed

`insulin_weekly_cv` replaces it: the week-to-week coefficient of variation of total daily
insulin, computed as a rolling twenty-four hour total at five-minute resolution, reduced to
one value per day by its median, averaged into weeks. The reference comes from 148 real users'
delivery records, 115 of whom have a usable 28-day window and a daily dose inside a
clinically possible range, giving a median of 7.29% and an interquartile range of 4.52 to
11.08. The median daily dose across them, 50.9 U, independently matches DCLP3's published
47.0, which is the check that the extraction reads what it claims.

Validated on the test the old statistic failed, under each driver separately:

| Driver | Sensitivity varies | Switched off | Paired difference |
|---|---|---|---|
| basal-bolus | 4.02% | 4.31% | -0.15, interval 1.42 |
| trend | 3.33% | 2.68% | +0.59, interval 1.24 |
| boost | 4.37% | 2.90% | +1.76, interval 1.62 |
| oref | 5.87% | 2.87% | +2.06, interval 2.57 |

Open loop is the control and shows nothing, which it must: it delivers from a fixed schedule
and a fixed carbohydrate ratio, so a person whose sensitivity moves receives the same insulin
and the change appears in their glucose instead. All three closed loops move the right way and
one interval excludes zero at these sample sizes.

`drift` is left in place and reported, labelled as not evidence, for continuity with the
published table.

One limitation carried forward. The level of the replacement depends on the driver as well as
the person, 3.3% under the built-in loop and 5.9% under oref for the same subjects, because
how much a loop varies delivery is partly a property of the loop. What is tested is its
response to the person, not its level, and a cohort value belongs beside the driver that
produced it.
