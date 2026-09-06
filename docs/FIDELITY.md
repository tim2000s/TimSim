# How closely does this match real data, and where does it fail

Remeasured in August 2026 against population `2af095014f6c1c75` at a hepatic defence gain of
0.20. Two things changed underneath every figure here. The generator had drawn its per-class
random stream from a salted hash, so it produced a different hundred subjects in every process
and nothing measured before could be rebuilt; and the defence gain was recalibrated across the
whole adult class rather than its first twenty. The classifier arbiter, the signature ablation,
the clamp and the settings comparison have all been rerun. Sections carrying figures that have
not been remeasured say so where they appear.

Two tests, and they disagree. Take the stronger one first.

A classifier given 24-hour windows of this simulator and of the DCLP3 closed-loop
participants, holding out whole subjects, separates them at an area under the curve of
0.739. The floor for the same test is 0.926, which is what a published subject with no
layers scores, and a null built by permuting subject labels sits near 0.52. So the default
configuration is recognisably a simulator, by a margin that has narrowed rather than closed,
and what carries the separation is time above 180 mg/dL.

The weaker test is the eleven marginal statistics below, where the same configuration scores
five of eleven. A four-layer configuration without the infusion site layer scores six of
eleven and is easier for the classifier to tell from real data.
Both numbers are real. The signature table asks whether eleven medians land in eleven
ranges; the classifier asks whether a day of this looks like a day of that. The second is
the question worth answering, which is why the default is the arm that answers it better and
scores worse below.

The table is still here, still reported whole, and still the thing to watch when anything
changes. It is level 3 of the seven in [VALIDATION.md](VALIDATION.md) and on its own the
weakest of them: matching marginal statistics says nothing about whether the response to an
intervention is right. Read it alongside levels 4 and 5, which are what a controller
comparison actually rests on.

## What is being compared

Every figure here describes a simulated person **plus the reference controller**, measured
against real people plus whatever algorithm they were running, which for DCLP3 is
Control-IQ. That is the right comparison, since a real person cannot be observed without
their algorithm either. It does mean these numbers validate the pair rather than the person
alone, and an algorithm under test replaces half of it. The `+loop` column below is
therefore not a layer being switched on but the driving controller changing from open-loop
basal-bolus to the correction loop.

## The measurement

Eleven statistics, computed identically on simulator output and on real continuous glucose
data. The real reference is the envelope across four cohorts of closed-loop users, 192
people in total, taken as the minimum and maximum of the four cohort medians. Each
simulator figure is the median across the first ten adult subjects, run for 28 days.

Each column adds one mechanism to the column before it, so a movement is attributable to a
named cause rather than to the bundle.

This table changes the driving algorithm partway along, at the `+loop` column, so the
columns to its right are measured under a different driver from those to its left. It also
adds physiology before behaviour, which adds a mechanism before its antidote and loses half
the cohort at that rung. `LADDER.md` walks the ladder four times with the driver held
constant, behaviour first, and reports which movements survive that. Nine of forty-seven do:
three from the sensor layer, two each from behaviour, physiology and the site layer.

Two of the eleven signatures below should be read differently as a result. `ISF drift` is not
computed from the glucose and cannot detect the person, so it is no longer counted as
evidence; `insulin_cv`, the week-to-week variation in total daily insulin, replaces it and is
referenced against 115 real users' delivery records.

| Signature | Real range | stock 2008 | +physiology | +behaviour | +loop | +sensor | +site | In range |
|---|---|---|---|---|---|---|---|---|
| Glucose variability (CV%) | 29.5–34.3 | 25.7 | 34.9 | 36.0 | 35.2 | 35.9 | 39.7 | no |
| Rise tail P(ΔBG>10/5min) % | 3.7–6.6 | 1.0 | 1.8 | 2.2 | 2.4 | 4.1 | 4.0 | yes |
| Autocorrelation @30min | 0.78–0.87 | 0.89 | 0.93 | 0.94 | 0.90 | 0.89 | 0.92 | no |
| Autocorrelation @60min | 0.50–0.68 | 0.73 | 0.82 | 0.85 | 0.71 | 0.69 | 0.78 | no |
| Outcome SD @stuck-high (mg/dL) | 26.5–33.5 | 18.8 | 23.1 | 20.7 | 26.6 | 28.8 | 25.7 | no |
| Diurnal amplitude (mg/dL) | 34.7–56.3 | 65.1 | 55.6 | 40.7 | 50.1 | 53.3 | 51.0 | yes |
| Hypo recovery to 100 (min) | 50–59 | 95.0 | 125.0 | 73.8 | 80.0 | 75.0 | 77.5 | no |
| Hypo rebound >180 % | 23.2–28.4 | 0.0 | 11.1 | 36.6 | 34.8 | 49.4 | 46.2 | no |
| Compression lows /30d | 1.9–5.3 | 0.0 | 0.0 | 0.0 | 0.0 | 4.3 | 3.2 | yes |
| Sensor jitter (mg/dL) | 4.5–6.7 | 2.4 | 2.5 | 2.5 | 2.5 | 5.6 | 5.7 | yes |
| ISF drift (weekly %CV) | 8.2–21.7 | 0.0 | 0.0 | 16.7 | 6.6 | 6.0 | 15.5 | yes |

The default simulator is the `+site` column, which is every layer. The "In range" column
scores that arm and allows the 10% padding `signatures.in_real_range` applies.

None of eleven for the bare subjects, six of eleven with four layers, five of eleven with all
five. The five-layer arm is the default despite scoring worse here, for the reason at the top
of this document and in the arbiter section below.

The stock column scoring zero is the more informative half of that. The bare personae are
too flat, too predictable and too quiet: variability at 25.7 against a real 29.5 to 34.3,
both autocorrelations above their ranges, a rise tail of 1.0 against 3.7 to 6.6, no
compression lows, no jitter beyond quantisation, no sensitivity drift, and hypoglycaemia
rebound at exactly zero because nothing rebounds when nothing eats. Every one of those is a
consequence of what the model omits rather than of what it gets wrong.

Survival belongs in the headline rather than in a footnote. The physiology-only arm loses one
of its ten subjects over 28 days and its survivors spend up to 14.9% of the run below 70
mg/dL, so its column is computed on whoever lived and its hypoglycaemia rebound of 11.1%
should be read that way: the subjects that would have rebounded hardest are the ones that
failed. Four of the six arms lose a subject.

Reproduce with `python examples/layer_ablation.py`, about an hour and a half serially. The
`--arm` flag runs one column, so the six can go in parallel. Raw output in `docs/*.json`.

Every figure in this table was remeasured in August 2026 on the regenerated population and at
the recalibrated hepatic defence gain of 0.20. The counts moved: bare from three of eleven to
none, four layers from eight to six, and the shipped five-layer arm unchanged at five.

## The arbiter: which configuration is hardest to tell from real data

The table above counts marginal medians, one at a time. That cannot settle a choice between
configurations where each gains one signature and loses another, and by this point there
were four such choices sitting unresolved.

So the question goes to the classifier in `validation/replication.py` instead. Twenty-four
hour windows of real DCLP3 participants against windows of each candidate, whole subjects
held out, subject labels permuted for the null. It tests every axis at once, including axes
nobody chose to measure, and it has a floor: a subject with no layers at all scores 0.937.

Measured on the same 34 subjects over 28 days in every arm, against 3,023 real windows from
the 67 closed-loop calibration participants, across ten cross-validation splits:

| Configuration | AUC | Excess over null | Completed | Signatures in range |
|---|---|---|---|---|
| Default plus the site layer | 0.739 | +0.216 | 32/34 | 5 of 11 |
| Default plus real settings | 0.761 | +0.230 | 32/34 | not measured |
| Both | 0.774 | +0.248 | 30/34 | not measured |
| Default, four layers | 0.785 | +0.269 | 31/34 | 6 of 11 |
| Default plus Visentin's classes | 0.833 | +0.313 | 20/34 | not measured |
| No layers at all | 0.926 | +0.384 | 34/34 | 0 of 11 |

Lower is better. Every configuration keeps the rank it held before the population was
regenerated, which is the property this table is used for:

| Configuration | AUC before | AUC now |
|---|---|---|
| Default plus the site layer | 0.677 | 0.739 |
| Default plus real settings | 0.695 | 0.761 |
| Both | 0.706 | 0.774 |
| Default, four layers | 0.716 | 0.785 |
| Default plus Visentin's classes | 0.769 | 0.833 |
| No layers at all | 0.936 | 0.926 |

The ordering is identical and the decision it supports is unchanged. What moved is the
absolute level: every layered arm became more separable by 0.06 to 0.07 while the bare arm
stayed where it was, so the layers close less of the distance to real data than this document
previously reported. The drop from bare to the best configuration was 0.259 and is now 0.187.

Two things changed at once between the two runs, the regenerated population and the hepatic
defence gain moving from 0.25 to 0.20, so this measurement cannot say which is responsible.
Separating them would need a third run holding one fixed.

The Visentin arm should be read with its completion count rather than its AUC. It finishes 20
of 34 subjects where the others finish 30 to 32, so its windows come from the subjects that
survived it and its score is the most favourably conditioned in the table.

The result disagrees with the signature count, which is why the arbiter was worth running.
The site layer scores worst of any configuration on the eleven signatures and is the hardest
to tell from real data. Both statements are true and they are measuring different things:
the signature table asks whether eleven medians land in eleven ranges, and the classifier
asks whether a day of this looks like a day of that.

Two further things it settles. Site failure and conservative settings do not compose, and
running both is worse than either alone, which is the same overshoot visible directly in the
excursion bands. And Visentin's diurnal classes come out worse than the default here as
well, agreeing with the ablation rather than adding to it.

What it does not say is that any of this is indistinguishable. The best configuration is
still separable at 0.739 against a null 95th percentile near 0.52. Time above 180 mg/dL is
what carries the separation in every arm, and it is the top feature in five of the six. Better is not the same as good, and the honest
summary is that this simulator remains recognisably a simulator, by a margin that has
narrowed rather than closed.

Reproduce with `python examples/configuration_arbiter.py`, which needs the DCLP3 data. The
six arms are independent, so `--config` runs one.

## The infusion site layer, and the trade it makes

The eleven statistics above measure shape and dynamics. None of them measures glycaemic
burden, and that is how a model that matches eight of eleven turned out to be nine
percentage points short on the one number most clinicians would look at first.

Measured against the closed-loop arm of DCLP3 on 34 adults over 28 days, the default
simulator spends 18.2% of the time above 180 mg/dL where the trial spends 27.1%. Decomposed
by excursion rather than totalled, the difference is specific:

| | DCLP3 | default | with site layer |
|---|---|---|---|
| Excursions above 180 per day | 3.56 | 3.19 | 3.31 |
| Median peak, mg/dL | 210 | 201 | 202 |
| p90 peak, mg/dL | 293 | 269 | 282 |
| Median duration, min | 65 | 55 | 60 |
| p90 duration, min | 265 | 195 | 250 |
| Total time above 180, % | 27.08 | 18.19 | 23.16 |

The count was already right and the heights were already right. The whole of the difference
was in how long an excursion lasted, and almost all of that past three hours: 61% of it in
excursions over six hours and a further 38% between three and six, with everything shorter
already matching. Real participants had 0.73 excursions a day over three hours against the
simulator's 0.41, and the longest real one ran for 54 hours of continuous wear.

Those long real excursions do not look like meals. Glucose enters them at 0.68 mg/dL per
minute, which is a fifth of a meal's rate and about what basal insulin going missing would
produce, plateaus around 242 and peaks around 306. Every one of the 67 participants examined
had them, at a median of 3.8 per 30 days. A working closed loop cannot hold someone at 242
for seven hours while delivering correction, so the insulin was not arriving.

That is infusion site failure, and `therapy/site.py` models it: absorption at the cannula
drops to a fraction of what the pump sends, the loop drives basal into its ceiling and
achieves little, and the person notices hours later or sleeps through it until morning.
Adding it recovers over half the missing time and reproduces the duration distribution.

It costs autocorrelation. At thirty minutes the simulator moves from 0.86 to 0.90 against a
DCLP3 interquartile range of 0.85 to 0.89, and at sixty from 0.65 to 0.72 against 0.62 to
0.71. Both directions are outward. The reading is that the simulator's long highs are
smoother than real ones, which have people bolusing, eating and changing sets through them
rather than simply waiting them out.

The layer was off by default until the arbiter above settled it. It is the largest
correction available on the statistic that matters most clinically and a regression on three
this table has always reported, so the choice was made by the test that weighs both at once
rather than by counting. It is now in `DEFAULT_LAYERS`. Run without it by passing the four
layers explicitly, and read `therapy/site.py` before reading anything into either result.

The gate's criteria were re-registered when this changed, because thresholds fixed against a
simulator with no unfixable hazard in it are not thresholds for one that has. The old
fingerprint is kept beside the new one in `validation/gate.py`.

Two things it does not fix. The hours after midnight are still well short, 18% above 180
against the trial's 35% at hour zero, while breakfast now runs over, 30% against 19% at hour
eight. That pattern points at overnight insulin resistance rather than at anything
mechanical, and it is the next thing to chase. And the remaining four percentage points of
burden are unattributed.

Reproduce with `python examples/hyperglycaemia_gap.py`, which needs the DCLP3 data.

## What the diurnal sensitivity papers changed, which was less than expected

Two papers describe the diurnal pattern this package's physiology layer models. Hinshaw et
al. (2013) is the measurement: 19 subjects with type 1 diabetes, triple-tracer mixed meals
at 07:00, 13:00 and 19:00 in a Latin square. Visentin et al. (2015) is the model built on
it, for the S2013 simulator.

The measurement puts postprandial sensitivity at 5.1, 7.5 and 7.2 (10^-4 dL/kg/min per
uU/mL) at breakfast, lunch and dinner, so breakfast sits at 0.68 of the highest meal. This
package's cosine gives 0.68 at 07:00, which is a good match for the one number it was aimed
at. It then keeps rising, making dinner the most insulin-sensitive meal by 13% over lunch,
where the measurement has the two within 4% of each other.

The more interesting part of Hinshaw is what it failed to find. The difference across meals
was not significant (P = 0.34), the between-subject spread was nearly three times what the
study was powered for, and the conclusion is that any diurnal pattern in type 1 diabetes
"is individual specific" and cannot be extrapolated to the population. Applying one common
curve to every subject, which is what the cosine does, is the thing that finding rules out.

Visentin's answer is a per-subject class. Each subject's sensitivity is normalised to its
own maximum, above 60% called high and below called low, giving seven distinguishable daily
patterns assigned with measured probabilities, low at 40% of high, transitions at 04:00,
11:00 and 17:00, and multiplicative noise. It is implemented in `patient/varying.py` and
run with `--arm visentin`.

It is worse here, and not marginally:

| | Real range | cosine | Visentin | Visentin, no day-to-day term |
|---|---|---|---|---|
| Diurnal amplitude (mg/dL) | 34.7–56.3 | 56.8 | 109.2 | 108.3 |
| Glucose variability (CV%) | 29.5–34.3 | 33.6 | 39.1 | 37.4 |
| Hypo recovery to 100 (min) | 50–59 | 62.5 | 75.0 | 76.3 |
| ISF drift (weekly %CV) | 8.2–21.7 | 3.5 | 10.9 | 7.6 |
| Signatures in range | 11 | 8 | 6 | 6 |
| Subjects surviving 28 days | 10 | 10 | 6 | 8 |

The fourth column exists because Visentin's noise term describes day-to-day variation that
this package already models separately, so running both compounds them. Removing this
package's term recovers two subjects and leaves the amplitude where it was, which says the
amplitude comes from the structure rather than from the double count.

A step held for six to eleven hours is a different object from a smooth curve of similar
range, and the validation behind it was six-hour postprandial windows in a controlled
inpatient protocol with therapy settings adjusted to suit. This package runs 28 days of free
living under a closed loop with settings titrated at nominal parameters. The model does not
transfer to that, which is worth knowing and is why it is kept rather than deleted.

The one thing it does improve is sensitivity drift, from 3.5 into the real range at 10.9,
because per-subject variation is what that statistic measures. That is the part of Hinshaw
worth carrying forward, and doing it without the rest is not something either paper offers a
model for.

## The settings real people actually use

DCLP3 records each participant's pump programming, which answers two questions this package
had been reasoning about rather than measuring. Read with `dclp3.therapy_settings`.

Basal is flat. Taking each of the 67 closed-loop calibration participants' half-hourly
profile relative to their own 24-hour mean, the population median sits between 0.97 and 1.03
at every hour. There is no dawn shape in prescribed basal at population level, so this
package's flat default is right, and the overnight hyperglycaemia it is short on is not a
basal-shaping problem.

The correction factor disagrees by a factor near two and a half, and the disagreement is
inherited. Measured across all 112 closed-loop participants from their recorded pump settings,
summarised per participant before the cohort median is taken:

| | Carbohydrate ratio, g/U | Correction factor, mg/dL/U | Implied mg/dL per gram |
|---|---|---|---|
| DCLP3 participants | 8.0 | 40.0 | 5.00 |
| Clinical 500 and 1800 rules | 8.5 | 30.6 | 3.60 |
| Generated subjects, all classes | 10.8 | 26.9 | 2.49 |
| Generated adults | 8.2 | 17.2 | 2.09 |
| The ten published adults | 9.5 | 12.6 | 1.98 |
| simglucose's own settings table | 9.5 | 11.5 | 1.59 |

The trial's correction factor has an inter-quartile range of 30.0 to 50.0, so the disagreement
is not a matter of where inside a wide distribution the median falls. Earlier versions of this
table quoted 35.0, which was never measured from the release.

Carbohydrate ratio agrees where the populations are comparable, at 8.0 in the trial against 8.2
across generated adults, and the all-classes figure of 10.8 is higher only because children need
more grams per unit. Correction factor does not agree, and the model agrees with
the table rather than with the clinic:
`check_published_cohort_obeys_clinical_rules` puts the measured response at 1.10 times the
stated factor, so the physiology and the settings table describe the same person. Applying
the 1800 rule to the published subjects' own stated daily insulin gives 30.6 against the
11.5 they are tabulated with.

What follows from that is a bound on the behaviour layer, and it needs stating carefully because
a second measurement of the same words points the other way. Read off the settings, a gram is
credited with about 2.1 mg/dL in a generated adult where it is credited with 5.0 in a DCLP3
participant. That is a statement about what an algorithm dosing from those settings will do, and
it is a property of the UVA/Padova model rather than of anything added here.

It is not a statement about what a gram does to the body. Measured as an excursion, by giving a
subject one meal on basal alone and running the same subject again eating nothing, the model
rises 22.2 mg/dL per 10 g against 15.7 to 19.7 per logged 10 g across real uncovered meals, and
logged grams under-state intake. So the model's settings credit a gram with less than a real
person's settings do, and its body does more with a gram than a real body appears to. The two
quantities have both been called the carbohydrate response here and they point opposite ways;
`docs/PADOVA_LIMITS.md` carries both with the code that measures them.

An earlier version of this section drew the further conclusion that a meal miscounted,
unannounced or eaten to treat a low moves a virtual subject roughly half as far as a real one,
and that no work on meal timing or size could recover the other half. The excursion measurement
does not support it.

It also explains why the infusion site layer succeeded where two attempts at the meal model
did not. Site failure acts on insulin delivery and never touches the carbohydrate path, so
it is not subject to the same halving.

## Is the model's correction factor a defect? No, and testing it found something else

The measured disagreement above invites an obvious inference: simglucose's settings table
puts the correction factor near 11.5 mg/dL per unit where the clinic uses 35, so perhaps the
table is wrong and this package should diverge from it. Three measurements say otherwise.

The table agrees with the model. `check_published_cohort_obeys_clinical_rules` puts the
measured response at 1.10 times the stated factor, so diverging from the table means
diverging from the physiology it describes, which is the thing being simulated.

Roughly half the apparent damping was this package measuring at the wrong operating point.
`measure_settings` gives one unit from a settled basal state, but a correction factor
describes correcting a high, and in the model's equations insulin-dependent utilisation
carries a factor of G/(Km0+G). Measured as a paired difference against an untreated copy of
the same subject on the same trajectory, one unit moves the ten published adults by:

| Starting glucose | mg/dL per unit | IQR |
|---|---|---|
| Settled basal, mean 143 | 12.6 | 9.6–20.7 |
| 180 | 17.4 | 12.5–28.6 |
| 250 | 18.5 | 15.0–28.6 |
| 300 | 23.4 | 14.3–37.5 |
| The 1800 rule on their own stated daily dose | 31.5 | |
| DCLP3 participants | 40.0 | |

A first pass at this raised glucose with a fixed 90 g load, which only six of the ten
subjects reached 300 on, and reported 32.5 at that level. Escalating the load until every
subject reaches every level drops it to 23.4. The selection was doing a third of the work.

So the operating point accounts for about half the difference and the rest is real. That
still leaves the question of which side is wrong, and the third measurement answers it by
running the experiment backwards.

If the model's insulin were defectively weak, then handing the algorithm a weaker setting
still, so that it doses even less, should push the simulator further from reality. The
opposite happens. Setting the correction factor to 40 mg/dL per unit, which is what DCLP3
participants ran, in place of the 14.7 measured from the subjects' own physiology:

| | DCLP3 | default | with real settings | with site layer | both |
|---|---|---|---|---|---|
| Excursions above 180 per day | 3.56 | 3.19 | 3.63 | 3.31 | 3.57 |
| Total time above 180, % | 27.08 | 18.19 | 23.01 | 23.16 | 29.02 |
| Band 3–6h | 9.38 | 5.97 | 10.39 | 7.54 | 10.05 |
| Band over 6h | 6.55 | 1.16 | 2.35 | 4.94 | 9.49 |
| Hypo recovery to 100, min | 38.7–55.0 | 56.3 | 48.8 | 55.0 | 48.8 |

Worse settings fit better. That relocates the finding from the physiology to the therapy:
this package's subjects carry correction factors measured from their own models, and no real
person has that. Real settings are conservative, chosen against hypoglycaemia rather than
for the fastest return to target, so real people under-correct highs and their highs last
longer.

Visentin et al. hit the same wall from the other side and said so. Their virtual population
needed a carbohydrate ratio of 15.9 g/U against a real 8.6, and they cut the premeal bolus
by about 2 U from the optimal because with the optimal ratio "plasma glucose would have
returned to the target within the 3-h experiment, whereas the data show that the plasma
glucose level was still above target at t = 360 min". A simulator whose subjects are dosed
optimally clears glucose faster than people do.

The two mechanisms turn out to be complementary rather than competing. Conservative settings
fill the three-to-six hour band, which the site layer could not reach, and site failure fills
the tail past six hours, which conservative settings barely touch. Applying both overshoots:
29.0% above 180 against the trial's 27.1, and 9.5% in the tail against 6.6. So they are not
independent and neither is a free parameter to be turned up.

Site failure is now on by default and conservative settings are not, which is what the
arbiter ordered: it prefers the site layer alone to either the default or the two together,
in ten splits out of ten. `simulate(..., isf_scale=2.4)` puts the median correction factor
at 35.3 for anyone testing how an algorithm copes with badly tuned therapy, which is a real
scenario and not the default one. What neither fixes is the shape by hour: every arm runs
high at breakfast and short after midnight, which is a separate problem and still open.

## Does a virtual subject exist for each real one?

The eleven signatures compare cohort medians. That is a claim about a population, not about
people, and a simulator can match every median while containing nobody who resembles anyone.
Visentin et al. validated this model against a clinical trial by asking the other question:
for each real subject, does a virtual subject exist behaving similarly in the same clinical
zones. `validation/compare.coverage` asks it.

A real subject counts as covered when some virtual subject matches it on time below 54,
below 70, in range, above 180, above 250, mean and variability, all to within one standard
deviation of the real population's own spread. The distance is the largest standardised
difference rather than the average, because a virtual subject matching on four zones and
wildly out on the fifth has not matched.

Against the 67 closed-loop calibration participants, 28 days each. Running the whole
population, 98 of the 100 subjects survived the month:

| Subjects run | Real subjects covered | Virtual subjects resembling a real one |
|---|---|---|
| 10 | 47.2% | 73.0% |
| 20 | 66.9% | 74.0% |
| 34 | 72.5% | 71.5% |
| 50 | 83.0% | 71.2% |
| 75 | 87.5% | 71.3% |
| **100** | **91.0%** | **72.0%** |

The two columns behave completely differently, and that is the result. Coverage grows with
how many subjects are run, because each one is another chance to resemble somebody.
Plausibility does not move at all, because it is a property of what the population is made
of rather than of how much of it is used.

So the two questions separate. Can this population stand in for real people: yes, for 91% of
the trial's participants, when all of it is run, with six left that nothing resembles.
Is this population made of real people: about 28% of it resembles nobody in the trial, at
any cohort size, and running more of it will never fix that.

Coverage depends heavily on how many subjects are run, which has to be controlled for before
those columns are compared: 31% at five subjects, 51% at ten, 69% at twenty, 84% at
thirty-four. Subsampled to a common 25 over forty draws, the two cohorts cover
indistinguishably, 75.1% plus or minus 4.3 against 73.1%, and the age-matched one is
meaningfully worse on plausibility, 60.0% against 70.4% plus or minus 4.5.

That is a genuine tension with the section above. Matching the cohort's ages to the trial
improved insulin, time above 180 and the duration of a high, and it does not improve
per-subject coverage and makes the virtual subjects less like real people. Both are measured
and neither cancels the other. The likely reason is that the matched cohort brings in
adolescents, whose hypoglycaemia here is more extreme than any trial participant's.

The spread is the more useful part, because it is wrong in both directions at once. The figures
below were computed by hand and pooled across pairings, and both of those turned out to matter.
`examples/spread_ratio.py` now recomputes them per pairing into
[spread_ratio.json](measurements/spread_ratio.json), with intervals from resampling both sides:

| Statistic | DCLP3, Control-IQ | DCLP3, oref0 | Commons, oref0 | Pooled figure previously quoted |
|---|---|---|---|---|
| Time below 54 | 4.38 [3.26, 5.96] | 4.73 [3.61, 6.38] | 1.09 [0.77, 1.76] | 2.74 too wide |
| Time below 70 | 1.93 [1.50, 2.50] | 2.14 [1.67, 2.79] | 0.93 [0.72, 1.23] | 1.38 too wide |
| Variability | 1.17 [0.97, 1.43] | 1.22 [1.01, 1.47] | 1.01 [0.79, 1.29] | 1.67 too wide |
| Time in range | 0.68 [0.57, 0.82] | 0.64 [0.51, 0.78] | 0.54 [0.39, 0.82] | 0.76 to 0.81 |
| Time above 180 | 0.62 [0.51, 0.76] | 0.59 [0.48, 0.73] | 0.48 [0.34, 0.75] | 0.76 to 0.81 |
| Mean glucose | 0.57 [0.46, 0.71] | 0.67 [0.54, 0.83] | 0.46 [0.32, 0.74] | 0.59 too narrow |

Pooling hid the largest effect in the table. The hypoglycaemia spread is 4.38 to 4.73 times the
trial's and 1.09 of the do-it-yourself population's, because the trial participants barely go
below 54 mg/dL and their between-participant standard deviation there is 0.20 percentage points
against 0.96 in the Commons. A single number for "the" hypoglycaemia spread does not exist.

Excluding the runs that stopped early, which the table above does, understates it further.
Including them at the duration each survived gives 6.81 and 6.08 against the trial and 1.11
against the Commons, because the runs that stop are the ones that went furthest low and the
Commons' own spread is wide enough to absorb them.

So the population is too alike in where its glucose sits and far too different in how much
hypoglycaemia it has. A narrow spread of mean glucose makes a bench look more decisive than
it is, since two algorithms are compared across a population with less between-subject
variation than the one they will meet. A wide spread of severe hypoglycaemia does the
opposite, and puts subjects in the cohort that no real participant resembles.

Neither is visible in the eleven signatures, which is the argument for this criterion.

## Is the spread between subjects, or between runs?

The spread ratios above are measured on one run per subject, which conflates two things.
Eight subjects were run at four seeds each to separate them:

These figures were taken when `simulate` seeded its generator from the integer alone, so
subjects sharing a seed shared a random month. That made the between-subject column a clean
measure of body alone, with meals, infusion set failures and sensor noise identical across the
column. Subjects now draw independent streams from `subject_seed(name, seed)`, so repeating
this decomposition requires holding the stream explicitly rather than relying on a shared seed
to do it, and a naive repeat would put month variation into the between-subject column and
inflate it. The numbers below are the controlled ones and are quoted as measured.

| Statistic | Between subjects | Within one subject, across seeds | Ratio |
|---|---|---|---|
| Mean glucose, mg/dL | 7.43 | 5.89 | 1.26 |
| Time below 54, % | 0.49 | 0.33 | 1.45 |
| Time in range, % | 7.14 | 5.69 | 1.26 |

Changing which random month a subject gets moves its mean glucose nearly as far as changing
which subject it is. One adult spans 156.4 to 171.4 mg/dL across four seeds while the whole
between-subject spread is 7.4.

Removing the seed component leaves a true between-subject spread of 6.0 to 6.8 mg/dL against
an implied 14.2 in the trial. So the population carries about 45% of the real between-subject
variation in mean glucose, and the 0.59 reported above is itself partly run noise. A
comparison averaged across this population is averaging over less person-to-person
difference than it appears to, which matters for reading any result that leans on the
population being varied.

Correlating each subject's outcome against its own parameters explains little: the strongest
association across body weight, basal glucose, insulin sensitivity, carbohydrate ratio,
correction factor, age and daily basal is 0.35, for carbohydrate ratio against mean glucose.
The physiological differences between subjects are largely erased before they reach the
outcome, because every subject is dosed by settings measured from its own model and a loop
that corrects towards one target.

The covariance shrinkage in `population/generate.py` is not the cause and cannot be, which was
tested rather than assumed after it was proposed as one. `examples/covariance_estimator.py`
writes [covariance_estimator.json](measurements/covariance_estimator.json) and reports three
things. The estimator returns `(1-a)*S + a*diag(S)`, so every diagonal entry survives at every
intensity and the marginal spread is the sample one regardless: measured, the generated
marginals are 0.83 to 1.07 of the published ones with a median of 0.92 to 0.94, the shortfall
being the 2.5-sigma truncation and the screen. The correlation between basal production and
insulin sensitivity, which the shrinkage halves from a published +0.773 to +0.386 in adults,
falls inside the 95% Fisher interval of the published estimate at +0.279 to +0.943, and the
same holds in the other two classes; that correlation is +0.773, +0.442 and -0.321 across
adults, adolescents and children, and +0.287 pooling all thirty with class means removed. And
the intensity minimising expected squared error towards a diagonal target is 0.422, 0.483 and
0.893 against the 0.50 in use, so restoring correlations would move away from the optimum in
every class. Of 406 pairwise correlations per class, 8 to 11% clear the n=10 critical value
against 5% expected by chance.

The narrow spread is therefore inherited from thirty published people whose fasting glucose
lies between 133.4 and 152.8 mg/dL, and from what the model does not represent at all. Widening
the marginals to reach the trial's 14.2 mg/dL needs a factor near 2.2, which widens the
hypoglycaemia spread in the same proportion, and that spread already runs at 4.38 to 4.73
times the trial's.
[The spread paper](paper/spread_paper.md) puts this beside two populations built by other
groups, which land at 0.50 to 0.63 and about 0.35 on the same quantity.

That points at a mechanism the package does not have. Real settings are titrated against an
imperfect history and then left alone, so they diverge from what a person's physiology would
give, and the size of the divergence differs between people. `therapy/profile.py` now carries
a per-subject settings-accuracy factor for that, drawn once from the subject's name so a
cohort is reproducible without regenerating the population, centred on 1.0 because the level
and the spread are separate questions. It is off by default until it has been measured.

### What actually produces a low, instrumented

Since no parameter predicts which subject spends time in hypoglycaemia, the episodes were
instrumented instead, on the twelve subjects with the most and the twelve with the least,
run for 28 days each. Comparing the three hours before each nadir:

| | Fewest lows | Most lows |
|---|---|---|
| Episodes below 70 per day | 0.07 | 1.00 |
| Insulin, U/day | 38.4 | 41.1 |
| Bolus insulin in the three hours before a nadir, U | 1.29 | 0.27 |
| Glucose fall over that window, mg/dL | 98 | 123 |
| Rescues per day | 0.43 | 2.42 |
| Body weight, kg | 48.2 | 62.0 |

The subjects with the most hypoglycaemia take essentially the same daily insulin and less
bolus insulin before a low, and fall further. Their lows are not caused by boluses. A fall of
123 mg/dL over three hours is 0.68 mg/dL per minute, which is the signature of basal insulin
against no meal rather than of a correction overshooting.

Rescue treatment is not the cause either. Across 787 treatments in the high group and 140 in
the low:

| | Fewest lows | Most lows |
|---|---|---|
| Treated from, mg/dL | 90.9 | 69.1 |
| Carbohydrate given, g | 33.6 | 33.1 |
| Glucose rise achieved, mg/dL | 75.6 | 132.3 |
| Peak reached, mg/dL | 175.6 | 197.4 |
| Reaching 100 mg/dL | 100% | 95% |

Treatments work and overshoot, to a median peak of 197 mg/dL in the group that has the most
lows. What differs is where treatment starts: 69 mg/dL against 91. The low group is catching
falls early on the pre-emptive trigger, and the high group is treating once already below the
threshold.

So the picture is a slow drift down on basal insulin, caught late, then over-treated. Not an
overshoot from a correction, and not a treatment that fails to clear. Every subject's basal
is closed at its own fasting steady state, so what has not been established is why that basal
runs some subjects down and not others once meals and a correction loop are in play. The
adaptive sensitivity setting in the behaviour layer is the obvious next place to look and has
not been measured.

### Hepatic autoregulation does not explain the hypoglycaemia spread

The population's spread of time below 54 mg/dL is the worst-fitting statistic in the
coverage table, and endogenous glucose production during a low varies between subjects by more
than an order of magnitude, so the obvious candidate was that a defence varying that widely
would produce exactly that signature. Measured across 97 subjects, it does not:

| Against time below 54 | Correlation |
|---|---|
| `kp2`, the autoregulation coefficient | -0.17 |
| Production on crossing 54 mg/dL | -0.23 |
| Production as a multiple of the subject's own basal | -0.26 |
| Basal production | -0.05 |

The six subjects with the most hypoglycaemia span production from 1.35 to 3.50 mg/kg/min and
`kp2` from 0.0024 to 0.0112 without a pattern. This joins body weight, basal glucose, insulin
sensitivity, carbohydrate ratio, correction factor, age and daily basal, none of which
correlates above 0.35 with any outcome. No single parameter in this model predicts which
subject spends time in hypoglycaemia.

Two things did come out of the measurement.

The level is confirmed and quantified on the whole population. Production on crossing 54
mg/dL has a median of 2.61 mg/kg/min and ranges from 1.18 to 6.23, against 0.59 plus or minus
0.12 measured by Rickels et al. in long-standing type 1 diabetes. One caveat on that
comparison: their clamp holds insulin at a fixed high level while a low here is produced by a
bolus that is decaying, so the insulin exposure is not identical.

And a correction. The claim recorded earlier, that production rises during a low, holds for
the ten published adults where it goes from 2.36 to 2.60 mg/kg/min. Across the generated
hundred the median lift over each subject's own basal is 0.97, so it is flat rather than
rising. Flat is what Rickels reports for this population, described as suppressed to levels
no different from euglycaemia, so the model is qualitatively right about the shape of the
response and wrong about its level by a factor of four.

The spread also shrinks once run-to-run noise is removed, from 2.74 times the trial's to
2.17, on the same correction applied to mean glucose. Both figures sit on the pooled basis
that the per-pairing table above supersedes, so what survives from them is the fifth they
differ by rather than either value. It remains the worst-fitting statistic
and it remains unexplained. Since no parameter predicts it and every source of variation
widens it, the likeliest reading is that it is emergent: a subject goes low when a meal bolus
overshoots, which depends on the joint behaviour of carbohydrate ratio, meal size and insulin
action rather than on any one of them.

### Per-subject treating style, measured and not adopted

Every subject shares one set of rescue parameters, and the rescue rate shows the size of
that. Across the 30 real closed-loop users the rate has a median of 0.44 a day with
quartiles at 0.09 and 1.30, a factor of fourteen. The cohort spans a factor of 2.6.

`behaviour.rescue_style` draws a per-subject treating threshold and refractory period from
the subject's name. At a coefficient of variation of 0.30, across all 100 subjects:

| | Without | With | Trial |
|---|---|---|---|
| Rescue rate, quartile ratio | 2.6 | 4.2 | 14.4 |
| Between-subject sd of mean glucose, mg/dL | 8.44 | 10.21 | 14.24 |
| Spread ratio, mean glucose | 0.58 | 0.70 | 1.00 |
| Spread ratio, time below 54 | 2.75 | 3.10 | 1.00 |
| Spread ratio, variability | 1.63 | 1.90 | 1.00 |
| Real participants covered | 91.0% | 94.0% | |
| Virtual subjects resembling a real one | 73.5% | 64.9% | |

The spread-ratio rows here and in the settings table below are on the pooled basis that the
per-pairing table earlier in this document supersedes. Both columns were computed the same
way, so the movement between them is what the mechanism did; the levels are not comparable
with the per-pairing figures, which put the same hypoglycaemia spread at 4.38 to 4.73 against
the trial and 1.09 against the Commons. Recomputing these two tables per pairing needs the
with and without arms rerunning.

It is the best lever found and the only one that has improved per-subject coverage. It also
takes the share of plausible virtual subjects down by 8.6 points and widens the spread of
time below 54, which was already the worst-fitting statistic in the table.

The pattern across every mechanism tried is the same, and it is the useful part. The
population needs the spread of its mean glucose widened and the spread of its hypoglycaemia
narrowed. Settings divergence widened both. Treating style widened both. Any source of
between-subject variation widens both, because the two statistics are driven by the same
underlying differences between subjects.

So the missing ingredient is not more variation. It is something that reduces how differently
these subjects respond at the bottom of their range while leaving the middle alone, and
nothing in the layers currently does that.

### Settings divergence between people, measured and not adopted

Real settings are titrated against an imperfect history and left alone, so they diverge from
what a person's physiology would give and by different amounts for different people. That is
a source of between-subject variation the package has none of, and `therapy/profile.py`
carries a per-subject accuracy factor for it, drawn once from the subject's name.

At a coefficient of variation of 0.30, across all 100 subjects over 28 days:

| | Without | With | Trial |
|---|---|---|---|
| Between-subject sd of mean glucose, mg/dL | 8.44 | 9.68 | 14.24 |
| Spread ratio, mean glucose | 0.58 | 0.66 | 1.00 |
| Spread ratio, time below 70 | 1.38 | 1.59 | 1.00 |
| Spread ratio, time below 54 | 2.75 | 2.73 | 1.00 |
| Real participants covered | 91.0% | 86.6% | |
| Virtual subjects resembling a real one | 73.5% | 69.0% | |

It moves the right statistic in the right direction and closes about a fifth of the gap. It
also costs 4.4 points of coverage and 4.5 of plausibility, and widens the spread of time
below 70 which was already too wide. A badly tuned subject moves away from the trial faster
than it widens the population, so the mechanism stays off.

What remains untested is per-subject behaviour. Every subject here announces meals with the
same probability, misestimates carbohydrate with the same coefficient of variation, and eats
the same template scaled by body weight. Real people differ in all three by more than they
differ in physiology, and none of that variation is currently present.

## Are these the right people?

A virtual population is not a cohort, and for a long time this was scored by running the 34
adults against whatever real group was to hand. Those are different populations. The
closed-loop arm of DCLP3 has a median age of 29, a range of 14 to 63, and is 28% under 18.
The adults here have a median of 49 and no adolescents at all.

`population/cohort.matched` picks subjects to follow a reference age distribution, and the
difference it makes is not marginal:

| 28 days | Adults only, n=34 | Age-matched, n=25 | DCLP3 |
|---|---|---|---|
| Median age | 49 | 32 | 29 |
| Under 18 | 0% | 28% | 28% |
| Insulin, U/day | 64.9 | 54.5 | 47.0 |
| Time above 180, % | 23.91 | 24.00 | 24.65 |
| Median high, min | 55 | 65 | 65 |
| Time in range, % | 74.0 | 73.5 | 71.0 |
| Severe lows a day | 0.35 | 0.42 | 0.22 |

Insulin closes most of its gap, time above 180 and the duration of a high land on the trial,
and hypoglycaemia gets slightly worse because adolescents have more of it. None of that is a
change to the simulator. It is the same simulator asked about the right people.

Age is the only demographic available to match on, because weight, height and HbA1c are all
stripped from the public DCLP3 release. It stands in for body weight, insulin sensitivity
and total requirement, which are what actually differ and which the model does carry. A
cohort matched on age is closer than one matched on nothing and is not a cohort matched on
physiology.

The matched cohort is smaller than asked for, 25 rather than 34, because the population is
thin on 26 to 40 year olds. When a bin cannot supply its share every bin scales down to the
one that binds, so the composition is preserved rather than the shortfall being absorbed
into whichever age group has spare subjects. An earlier version took fewer from the short
bin alone and turned a 28% adolescent cohort into a 50% one.

## Making the baseline match Control-IQ, which did not work

Everything here is scored against DCLP3, DCLP3 is the pivotal Control-IQ trial, and the
baseline correction loop is nothing like Control-IQ. It corrects every five minutes on the
current reading at half the calculated need; Tandem describe an automatic correction at most
once an hour, on a thirty-minute prediction crossing 180 mg/dL, at 60% of a correction
towards 110, with basal suspended below 70, reduced below 112.5, raised from 160 and at its
ceiling above 180. Twelve times the cadence looked like enough to make every hypoglycaemia
comparison unreadable.

So a loop shaped like the published description was built, and measured, and it is worse:

| 34 adults, 28 days | trend | control-iq | DCLP3 |
|---|---|---|---|
| Time in range, % | 74.0 | 75.5 | 71.0 |
| Time above 180, % | 23.9 | 20.0 | 24.65 |
| Insulin, U/day | 64.9 | 74.2 | 47.0 |
| Rescues a day | 1.14 | 2.25 | 0.44 |
| Severe lows a day | 0.35 | 0.70 | 0.22 |

Closer on none of them. The cadence, the thresholds and the correction fraction are Tandem's;
the basal multiplier when glucose is predicted high, the ceiling on a single automatic
correction, and the prediction model are not, and those are what drive the outcome. Fitting
them until the cohort matched the trial would make the trial useless for validating the
person, because the pair would have been tuned to it. So the eager loop remains the baseline
despite having the wrong cadence, and the shaped one is available as `controller="control-iq"`
and honest about what it is.

The exercise did find one thing worth keeping. The first version predicted from a single
five-minute difference. The sensor error here has a standard deviation near 12 mg/dL, so that
difference carries about 3.4 mg/dL per minute of noise, which is over 100 mg/dL once
extrapolated half an hour: the controller was firing on noise, delivering 76 U a day against
the trial's 47. A least-squares slope over thirty minutes takes the prediction noise from 101
mg/dL to 14. Any predictive algorithm driven from this sensor needs to do something
equivalent, and one that does not will look far more aggressive here than it is.

One number in that table is not about the controller at all. Both arms deliver far more
insulin than the trial, 64.9 and 74.2 against 47.0 U a day, and the generated subjects have a
median body weight of 84 kg. That is a property of the population and it has not been chased.

## Should this package add counterregulation? The evidence says no

S2008 has no counterregulation, and a simulator of hypoglycaemia without it looks obviously
incomplete. Chasing that turned up two errors of ours before it turned up anything about
the model, so the working is kept.

### What went wrong first

The gate has a criterion on the longest single episode below 54 mg/dL, at 120 minutes. The
reference algorithm failed it at 150, then 180. Two real defects turned up in that algorithm
and were fixed: its meal bolus carried a full correction with no insulin-on-board
subtraction and no cap, and it tracked insulin on board from what it had requested rather
than what the pump reported delivering, which took its own estimate to 41.7 U against a real
10. Neither moved the number. Driving a published adult below 54 with no algorithm at all
gave 203 minutes untreated, saturating near 22 minutes however much carbohydrate was given,
against a real median of 10.

That looked conclusive and it was wrong. The safety metrics read `Result.bg`, the blood
glucose. DCLP3 reports a sensor, which is smoothed, lagged and floored at 40 mg/dL. On the
same signal:

| Episodes below 54 mg/dL | n | median | p90 | p99 | max |
|---|---|---|---|---|---|
| This package, blood glucose | 100 | 48 | 85 | 131 | 180 |
| This package, sensor reading | 380 | 10 | 55 | 110 | 135 |
| DCLP3, real sensor, 11x the exposure | 2322 | 10 | 25 | 60 | 160 |

The medians agree exactly and the longest simulated episode is shorter than the longest real
one. One caveat on that agreement, since it cuts both ways: real sensors fragment real
excursions too, and if this package's sensor is noisier than a real one it will fragment
harder and shorten measured episodes. There is no ground truth in DCLP3 to settle it, so
what can be said is that the two agree on the signal both actually record.

### What the physiology says

The assumption underneath the whole exercise was that the model's liver shuts down during a
low. Whether it does depends on the insulin it is asked at, and the first attempt to settle
it did not control for that.

`EGP = kp1 - kp2*Gp - kp3*Id` contains a hepatic autoregulation in the `-kp2*Gp` term that
strengthens as glucose falls, and an insulin suppression in `-kp3*Id` that does not. Measured
across the ten published adults during spontaneous lows under the reference loop, endogenous
glucose production on crossing 54 mg/dL is 2.60 mg/kg/min against a basal of 2.36. It rises.

Rickels et al. (Diabetes 2015) put a stepped hyperinsulinaemic clamp down to 45 mg/dL in
twelve people with long-standing type 1 diabetes and severe hypoglycaemia, against eight
non-diabetic controls:

| | EGP at hypoglycaemia, mg/kg/min | Glucagon, pg/mL | Epinephrine, pg/mL |
|---|---|---|---|
| Long-standing type 1 diabetes | 0.59 ± 0.12 | 33 ± 3 | 130 ± 16 |
| The same people after islet transplant | 1.18 ± 0.13 | 60 ± 7 | 253 ± 21 |
| Non-diabetic controls | 1.42 ± 0.14 | 95 ± 13 | 419 ± 46 |

Their finding was that endogenous glucose production in the diabetic group was "suppressed
during hypoglycemia to levels not different from under euglycemic conditions". Flat. The
counterregulatory response was absent, and islet transplantation restored it.

Setting 2.60 beside 0.59 gave a model producing four times what it should. That comparison
was wrong, and wrong in the way this project's comparisons usually go wrong: the two figures
were measured at different insulin. Rickels's number comes from a clamp holding insulin high
while glucose is walked down. A spontaneous low under a closed loop is the opposite state,
reached because the algorithm withdrew insulin. In model units the remote-compartment insulin
`Id` at a spontaneous low below 54 mg/dL has a median of 235 across the fifteen of twenty
subjects that reach one, against 441 at the clamped 55 mg/dL plateau and 188 at euglycaemia,
and production read there is 1.28 mg/kg/min rather than the 0.14 the clamp gives.

### The clamp, run in silico

The protocol was therefore reproduced on the model: insulin infused at a fixed 1.0 mU/kg/min
on top of basal replacement while glucose is held at successive plateaus by a variable
glucose infusion titrated by a proportional-integral controller, with the last 30 minutes of
each plateau measured. Glucose is infused into the plasma compartment as it is in the human
protocol rather than fed as a meal. Median across twenty subjects:

| Plateau, mg/dL | Held at | EGP | Insulin-dependent uptake | Glucose infusion | `Id` |
|---|---|---|---|---|---|
| 90 | 90.4 | 2.00 | 4.02 | 2.79 | 203 |
| 80 | 79.6 | 1.39 | 3.75 | 3.39 | 293 |
| 65 | 64.2 | 0.77 | 3.25 | 2.69 | 380 |
| 55 | 54.9 | 0.49 | 2.89 | 2.49 | 441 |
| 45 | 44.7 | 0.46 | 2.44 | 1.99 | 460 |

Remeasured on the regenerated population, twenty adults, defence off. The plateau medians moved
upward from the figures this section was written against, at 0.14 and 0.01 for the two lowest
plateaus, and that movement is mostly not the reseed. The distribution is zero-inflated, so the
median tracks how many subjects are pinned at zero and it is unstable on the choice of subset:
across the whole adult class of thirty-four the 55 mg/dL plateau reads 0.18 rather than the 0.49
twenty give. The robust statement is the zero count, at six of twenty and fourteen of
thirty-four with the defence off.

Production collapses towards nothing rather than running at four times the human figure, and in
a third to a half of subjects it reaches exactly zero. The suppression term outruns the
autoregulation term once the clamp's insulin is present, and `max(..., 0)` takes it the rest of
the way. Real people with no glucagon response at all hold 0.42 to 0.84 mg/kg/min here, and none
of them holds nothing.

Disposal is not the problem. A human glucose infusion of 3.1 mg/kg/min against production of
0.42 to 0.84 implies total disposal near 3.5, and the model at the 45 mg/dL plateau disposes
of 2.22 by the insulin-dependent route plus insulin-independent `Fcns`. It is already at or
below the human value, so suppressing uptake further, which is what adrenaline does and what
`HYPO_DEFENCE_GAIN` was built to do, moves away from the reference. That arm stays at zero.

### What was implemented

`HYPO_EGP_DEFENCE` opposes insulin's suppression of production as glucose falls, on the same
logistic centred at 58 mg/dL, which is the hepatic arm of the adrenaline response. Four gains
were run through the clamp:

`HYPO_EGP_DEFENCE` was recalibrated in August 2026 across the whole adult class of thirty-four
rather than the first twenty, on the regenerated population. Median production at the two
hypoglycaemic plateaus, against a human 0.42 to 0.84 with a mean of 0.59:

| Gain | at 55 mg/dL | zeros | at 45 mg/dL | zeros |
|---|---|---|---|---|
| 0 | 0.18 | 14/34 | 0.01 | 17/34 |
| 0.05 | 0.29 | 12/34 | 0.10 | 15/34 |
| 0.10 | 0.42 | 11/34 | 0.25 | 15/34 |
| 0.15 | 0.54 | 9/34 | 0.41 | 8/34 |
| 0.20 | 0.65 | 7/34 | 0.57 | 8/34 |
| 0.25 | 0.76 | 7/34 | 0.73 | 7/34 |

0.20 is the gain whose median lands closest to the human mean while staying inside the human
interval at both plateaus, and it is the shipped value. 0.15 is marginally closer at 55 mg/dL
and falls below the interval at 45. The previous 0.25 is inside the interval too and sits near
its top.

The median is the weaker half of this and should not be quoted as a point estimate. With the
defence off it reads 0.18 across thirty-four adults and 0.49 across the first twenty, because
the distribution is zero-inflated and the median tracks how many subjects are pinned at zero.

The between-subject spread is not inside anything, and no gain fixes it. Seven of thirty-four
subjects still produce nothing at the 55 mg/dL plateau at the shipped gain, where none of
Rickels's twelve produced nothing, and the ninetieth percentile sits above 2.0 against their
0.59 ± 0.12. The mechanism moves the centre of the
population into range and leaves it far wider than the human one, and that width belongs to the
published `kp1`, `kp2` and `kp3` values rather than to the defence. A gain large enough to lift
the subjects producing nothing drives the ones already producing too much further out, because
it scales a term they were never short of.

Reproduce the calibration with `examples/calibrate_hypo_defence.py`.

The glucagon arm is still not implemented and should not be. S2013's secretion half is
unpublished, Visentin et al. flagged that including glucagon secretion "could be not
appropriate for all T1DM patients with a long duration", and people with established type 1
diabetes lose the alpha-cell response, which is what the 33 pg/mL above shows. What is
implemented is the arm those same people retain.

### The regression

Twenty subjects, 28 days at a fixed seed with the full stack, run twice under each of two
drivers with the hepatic defence as the only difference. The signatures are paired over the
subjects completing both arms, since an arm that loses different subjects is a different
population.

| Driver | Completing, defence off | Defence on |
|---|---|---|
| Open loop with meal boluses | 13/20 | 16/20 |
| Reference correction loop | 16/20 | 18/20 |

| Signature | Real range | Off | On | Paired difference, 95% |
|---|---|---|---|---|
| Lowest glucose reached, mg/dL | | 42.6 | 51.8 | +8.07 ± 4.4 |
| Readings at or below 40 mg/dL, % | | 0.050 | 0.025 | -0.069 ± 0.062 |
| Glucose variability, CV% | 29.5 to 34.3 | 36.7 | 35.0 | -1.76 ± 1.7 |
| Autocorrelation at 30 min | 0.78 to 0.87 | 0.880 | 0.878 | -0.009 ± 0.008 |
| Autocorrelation at 60 min | 0.50 to 0.68 | 0.699 | 0.693 | -0.024 ± 0.021 |
| Time in range, % | | 74.0 | 76.6 | +1.38 ± 1.4 |
| Time below 54 mg/dL, % | | 0.43 | 0.27 | -0.21 ± 0.24 |
| Diurnal amplitude, mg/dL | 34.7 to 56.3 | 49.2 | 47.4 | -6.12 ± 7.6 |
| Hypoglycaemia recovery, min | 50 to 59 | 62.5 | 65.0 | -0.17 ± 3.6 |
| Hypoglycaemia rebound, % | 23.2 to 28.4 | 47.8 | 45.2 | +0.64 ± 5.9 |
| Rise tail, % | 3.7 to 6.6 | 4.71 | 4.97 | -0.07 ± 0.24 |
| Outcome spread at a stuck high | 26.5 to 33.5 | 28.4 | 28.9 | +0.34 ± 1.3 |
| Compression lows per 30 days | 1.9 to 5.3 | 3.21 | 3.21 | -0.21 ± 0.85 |
| Sensor jitter, mg/dL | 4.5 to 6.7 | 5.68 | 5.69 | -0.002 ± 0.027 |
| Insulin week-to-week CV, % | 4.5 to 11.1 | 5.24 | 5.23 | +0.44 ± 0.60 |

Values are under the reference correction loop, paired over the 15 subjects completing both
arms. Six intervals exclude zero: the lowest glucose reached, readings at or below 40 mg/dL,
variability, both autocorrelations and time in range. Under the open-loop driver, paired over
13 subjects, the lowest glucose reached moves +5.65 ± 4.8 and nothing else reaches
significance.

Everything that moved significantly and was not the target moved towards its reference range
rather than away, because all three were already outside it on the high side. Nothing on which
the population already sat inside its range was pushed out. The rebound and recovery figures,
which are the two worst-fitting statistics in the table, did not move, so the defence is not
the explanation for either and the account in `08_no_floor.md` that attributes them to the
absent floor is not supported by this.

The paired comparison understates the effect, since the three and two subjects the defence
rescues under each driver are excluded from it by construction, and they are the subjects
reaching the lowest glucose. Fifteen and thirteen subjects also leaves most of these intervals
wide enough that only a large movement would show, so the absence of an asterisk on a row is
weak evidence that the row is unaffected.

### The rate, and whose rate it is

What looked like a remaining gap was a comparison against one cohort. Severe lows across
every real cohort available here, all measured on a sensor reading with breaks in wear split
out:

| Cohort | Days | Episodes | Per day | median | p90 | p99 | max |
|---|---|---|---|---|---|---|---|
| DCLP3 closed loop, Control-IQ, 67 people | 10,676 | 2,242 | 0.21 | 10 | 25 | 60 | 160 |
| Nightscout do-it-yourself closed loop, 4 people | 339 | 233 | 0.69 | 15 | 50 | 85 | 165 |
| This package, 34 subjects | 952 | 380 | 0.40 | 10 | 55 | 110 | 135 |

It sits between two real populations rather than outside them, nearer the do-it-yourself
loop users than the trial, and its longest episode is shorter than either. The DCLP3
sensor-augmented pump arm cannot be added to this: `Pump_CGMGlucoseValue.txt` is the
Control-IQ pump's own log, so it carries the closed-loop arm only. Four Nightscout users
over 339 days is a thin reference and is quoted as one.

Which raises the question of whose rate this is. A low needs insulin and the insulin comes
from the controller, so a severe-low rate is a property of the person and the algorithm
together, in the same way the eleven signatures are. The reference controller here corrects
every five minutes, reactively, at half the calculated need. Control-IQ delivers an
automatic correction bolus at most once an hour, on a 30-minute prediction crossing 180
mg/dL, at 60% of the correction factor. Twelve times the cadence is the obvious reason this
package looks more like a do-it-yourself loop than like the trial it is scored against, and
it is a fact about `controller/reference.py` rather than about the body.

### What to carry from this

Read a gate failure on `longest_below_54_min` knowing it is measured on blood glucose while
every field reference is a sensor, and that in this simulator a sensor understates severe-low
duration by about a third. The criterion was briefly retired on the mismatched comparison
above and restored once it was found.

Sources: Rickels MR et al., Restoration of Glucose Counterregulation by Islet Transplantation
in Long-standing Type 1 Diabetes, Diabetes 2015;64(5):1713-1718.

## S2013's hypoglycaemia work, measured and then switched off

simglucose implements S2008. S2013 added two things to fix hypoglycaemia, and they oppose
each other by design: insulin-dependent glucose utilisation rises as glucose falls, which
deepens a low, and a glucagon compartment raises endogenous glucose production, which
recovers from one. Only the first is reconstructable from the literature. Dalla Man et al.
give the risk function and its threshold, and the glucagon parameters were "randomly
generated from an appropriate joint distribution" that is not published.

The first half was implemented and measured. It works as advertised on the thing it was
built for: time below 70 mg/dL moves from 2.79% to 4.18% against 4.07% measured across 30
real closed-loop users, correcting S2008's documented under-reporting of hypoglycaemia.

It is off by default, for two reasons.

Holding the sensitivity layer constant and adding only the risk term, diurnal amplitude
goes from 73.1 to 86.3 mg/dL against a real 34.7 to 56.3, and hypoglycaemia rebound does
not move, 3.4 to 3.6. Across the full stack the table falls from eight of eleven to six,
losing variability and diurnal amplitude, and one more subject in ten stops surviving. The
rebound row it was aimed at closed two points of a thirty-five point gap.

The second reason is about the calibration rather than the result. The gain is a property
of the body and it was calibrated against time below 70, which is a property of the body
and the algorithm together. Dalla Man et al. calibrated the same mechanism against
hyperinsulinaemic clamps in 32 subjects with glucose driven down at 1 mg/dL/min to 50
mg/dL, a challenge with no controller in it. That is the right kind of target and this
package does not have the data for it.

Shipping the half that deepens lows without the half that recovers from them is not a
partial S2013. It is a different model. `--arm hypo` remeasures it for anyone who wants the
numbers, and `HYPO_RISK_GAIN` in `patient/varying.py` carries the reasoning.

## What the rescue calibration changed

The rescue model was recalibrated on 2026-08-07 against carb entries logged by 30 real
closed-loop users over 5008 days, and against nothing else. Real users record 0.44 rescues
a day at a mean of 33.8 g. This package was giving 2.11 a day at 25.4 g: far too often, far
too small. Details and the reasoning are in `person/behaviour.py`.

| Signature | Before | After | Reading |
|---|---|---|---|
| Glucose variability (CV%) | 35.0 | 33.6 | now inside the range, from outside it |
| Diurnal amplitude | 58.5 | 56.8 | now inside, from a fraction outside |
| Hypo rebound >180 % | 73.5 | 66.1 | improved and still far outside |
| Hypo recovery | 58.8 | 62.5 | now outside, from inside |
| Statistics in range | 7 of 11 | 8 of 11 | |

The variability row is the one worth pausing on, because three independent measurements
predicted it would move and it did. The table itself had glucose variability outside the
real range on the high side. Counted straight off the traces, this package produced
sustained hour-long climbs of 50 mg/dL twice as often as real users. And a real automated
insulin delivery algorithm, run on it, sat in its meal-observing state about twice as much
as it does in the field. None of those three share any machinery, and the parameter they
agreed on was the one `CONTRIBUTING.md` had flagged as deliberately untouched.

Two things went the other way and both are the same mechanism. A person who treats less
pre-emptively lets a low go deeper before treating it, so recovery to 100 mg/dL takes
longer, and one subject in the loop arm no longer survives the run. That is a real cost of
a more accurate rescue model rather than a modelling error, and it is the second time in
this table that making the simulated person less protective has cost a life.

## What moved when the harness was fixed, and why

This table was remeasured after the nine defects in [OSAID.md](OSAID.md) were fixed. The
count with all four layers is unchanged at seven of eleven, and reporting only that would
hide two things that changed a great deal.

The baseline got much better. The bare subjects were scoring one of eleven and now score
three, because they were being bolused a fifth of what they should have been. That is the
ninth defect, and it flattered every claim this package makes about the value of its
layers. The argument the layers were added to support is now a smaller argument: three to
seven rather than one to seven.

| Signature | Before | After | Why |
|---|---|---|---|
| Bare subjects in range | 1 of 11 | 3 of 11 | the bare arms were under-bolused by a factor of the step length |
| Outcome SD @stuck-high | 25.5 | 27.6 | inside the real range; the sensor artefacts are in the loop, so an algorithm reacting to a false low genuinely makes the world less predictable |
| Hypo rebound >180 % | 58.5 | 73.5 | worse; a compression low now reaches the simulated person, who treats a fall that never happened |
| Diurnal amplitude | 49.5 | 58.5 | outside, by 0.08 past the padded bound; the five-minute grid makes the built-in loop correct more often, which costs more lows and bigger swings |
| Glucose variability (CV%) | 33.2 | 35.0 | outside, by 0.26 past the padded bound; same cause |
| Compression lows /30d | 5.4 | 3.2 | the old figure came off a rate calculation that read every trace as 1.67 times its true length |
| Physiology arm survival | 7 of 10 | 5 of 10 | properly bolused subjects with varying sensitivity and nobody to defend them |
| Hypo recovery | 60.0 | 58.8 | comfortably inside rather than marginal |
| ISF drift | 4.0 | 4.9 | still well below range |

Three of those deserve more than a table row.

The outcome spread crossing into the real range is the most consequential change, because
that statistic was the stated reason this package could not be used to price a dosing
change. It is worth being careful how much weight it takes. The bootstrap interval is 22.0
to 30.7 across ten subjects, which overlaps both the real range and the old value, so this
is one statistic moving from just outside to just inside on a small cohort. The mechanism
is credible and the measurement is weak. Treat the counterfactual caveat as standing until
it survives the full population and a second seed.

The two that moved out did so by 0.26 and 0.08 past a padded bound whose padding is 10% of
a range measured from four cohort medians. Neither is a change in the model's behaviour.
They are the same numbers landing on the other side of a line, and calling them failures
would be reading the line more precisely than it deserves.

Hypoglycaemia rebound got materially worse and that one is real. Sensor artefacts inside
the loop mean a false low now provokes real carbohydrate, on top of an over-treatment rate
that was already too high. The mechanism is right and the magnitude is wrong, in the
direction that makes this a harsher world than the real one.

None of this was tuned. The built-in loop corrects more often on a five-minute grid than it
did on a three-minute one, and adjusting it to bring the table back would be fitting a
parameter to the statistics it is being judged on.

## Reading it

The layers do different work and the split between them stays clean.

The physiology layer moves the physiology-linked statistics and leaves the disturbances
alone. Its column has to be read alongside the survival line above, because it is computed
on the half of the cohort that lived. Variability rises, both autocorrelations rise out of
range, and hypoglycaemia recovery gets worse rather than better. The rise tail does not
move at all, and neither do the sensor rows or the drift row. That is the measured version
of a general point worth internalising before reaching for a more refined model: refining
the differential equations fixes the statistics that depend on the differential equations,
and here it made the population less survivable while fixing nothing.

The behaviour layer supplies the disturbances, and it is what makes the population viable.
Rescue carbohydrate takes hypoglycaemia recovery from 110 minutes to 71, against a real 50
to 59, and takes survival from five of ten back to ten of ten. An adapting setting takes
drift from a structural zero to 15.3%, inside the real range. Unannounced meals take the
rise tail from 2.5 to 3.4 and the diurnal amplitude down from 73 to 53.

The loop layer supplies the damping, and it now also supplies part of the unpredictability
the outcome-spread statistic reads. Both autocorrelations come inside: 0.92 to 0.86 at
thirty minutes and 0.79 to 0.63 at sixty. The outcome spread at a stuck high moves from
22.6 to 26.8, into the real range for the first time. Diurnal amplitude goes the wrong way,
from 52.8 to 66.5, because a loop correcting every five minutes buys more lows and the
rescues that follow them are large.

The sensor layer closes the two sensor rows, as the only layer that can, and it now does
more than that. Putting the artefacts inside the loop adds 1.3 to the rise tail and 0.8 to
the outcome spread, because an algorithm reacting to a false low makes the world genuinely
less predictable. It also brings the diurnal amplitude back down from 66.5 to 58.5.

## What DCLP3 says about this table's own reference

The real range every row is scored against is the minimum and maximum of four cohort
medians. It has now been checked against an independent dataset: the DCLP3 trial, 67
closed-loop participants in the calibration half, 10,754 days of free living, read from the
CGM the pump actually received rather than from a smoothed export.

Eight of the ten statistics that can be read off a glucose trace land inside the existing
range. Glucose variability, the rise tail, autocorrelation at sixty minutes, outcome spread,
diurnal amplitude, compression lows and sensor jitter all agree. That is a substantial
independent validation of a reference this package leans on throughout.

One disagrees materially, and it is the row this package has spent the longest failing.

| | DCLP3 closed loop | This table's range |
|---|---|---|
| Hypoglycaemia rebound | 45.97 [38.31, 53.23] | 23.2 to 28.4 |

Real closed-loop users rebound above 180 after a low far more often than the four-cohort
reference says. The figure reads 41.4 off the Clarity export as well, so it is not an
artefact of which source is used. Roughly half of the gap on that row was the reference
rather than the simulator, which puts the repeated failures to close it in a different
light.

Hypoglycaemia recovery reads 47.5 against 50 to 59, marginally faster than the range, with
an overlapping inter-quartile range.

## The source question, and why it nearly cost the sensor layer

Read off the Dexcom Clarity export instead, sensor jitter in DCLP3 is 2.66 mg/dL against
this table's range of 4.5 to 6.7, which would have condemned the sensor layer as adding
noise that modern sensors do not have.

It does not. Clarity smooths. On the same sensor, the same person and the same window, the
second-difference spread is 2.53 from Clarity and 5.28 from what the pump received, a ratio
of 2.05 across 49 participants. The pump figure sits inside the existing range, and the
pump is what a closed-loop algorithm acts on.

Smoothing does not only move the noise row. It raises autocorrelation and suppresses the
sharp reversing dips the compression detector looks for, so three rows read off Clarity
disagree with this table and none of the three disagrees once the right source is used.
Any statistic taken from a vendor export is suspect in a direction that is easy to mistake
for a finding.

## The three that did not come right

They are reported rather than tuned away, which matters, because fitting a parameter to a
statistic turns that row from a test into a restatement.

Hypoglycaemia rebound overshoots badly, at 66.1% against a real 23 to 28. The rescue
calibration improved it from 73.5% and nowhere near closed it, which is informative:
treating less often and more generously moves the rebound rate only a little, so whatever
is driving it is not the rescue frequency. Compression lows reaching the simulated person
account for some of it, since a false low now provokes real carbohydrate. Read as a
measurement, the row says an algorithm judged here on how it handles rebound highs is
judged on a harsher world than the real one.

Hypoglycaemia recovery is now outside at 62.5 minutes against a real 50 to 59, having been
inside at 58.8 before the rescue calibration. A person who treats less pre-emptively lets a
low run deeper before treating it. This is the cost side of a more accurate rescue model
and it is reported rather than split the difference on.

Sensitivity drift falls below range once the loop is added, from 14.9% to 3.5% against a
real 8.2 to 21.7. The loop holds glucose closer to target, so the weekly adaptation has
less error to chase. Real drift is partly physiological rather than purely a response to
outcomes, and this adapter responds only to outcomes.

Two rows that used to head this list have left it. Glucose variability is now 33.6 against
a real 29.5 to 34.3, and the diurnal amplitude 56.8 against 34.7 to 56.3. Both moved
because of the rescue calibration, and both were predicted to move by measurements taken
outside this table.

The outcome spread at a stuck high remains inside at 27.0 mg/dL against a real 26.5 to
33.5, having been 21.0 before the therapy settings were corrected. It is the quantity a
dosing decision bets on. Ten subjects and a wide interval, so the counterfactual caveat
still stands until it survives the full population and a second seed.

## Survival

simglucose ends an episode when blood glucose falls below 10 mg/dL, so a truncated series
means the virtual subject did not survive. This is easy to miss, because the analysis is
handed whatever series it is given, and any comparison that silently drops incomplete runs
is conditioning on survival.

The physiology layer alone loses five of ten subjects over 28 days, and the survivors spend
up to 28% of the run below 70 mg/dL. Every arm with the behaviour layer or the loop
completes ten of ten. The reason is not subtle: varying insulin sensitivity produces days
on which the subject needs much less insulin than it is getting, and a virtual patient with
no carbohydrate to eat and no loop to withdraw insulin has nothing to stop the resulting
low.

That is worth stating as a finding rather than a footnote, and it got sharper when the
bolus units were fixed. A properly dosed population with a more refined physiology is half
as survivable as a badly dosed one, and only the person and the loop make it viable again.

It also means the physiology column of the table above is conditioned on survival, which is
why its hypoglycaemia rebound reads 3.4% against 15.0% for the bare subjects. The subjects
that would have rebounded are the ones that died.

`Result.completed` records this per subject, `examples/fidelity_check.py` reports it, and
`validation/gate.py` fails any cohort with a non-completion in it.

## The defects that moved this table before

Three earlier defects are worth keeping on the record, because none of them was visible at
this level and each moved the table more than anything aimed at the table did.

The first was found at level 2. Carbohydrate ratios and correction factors had been drawn
from the published cohort's distribution conditioned on body weight and basal rate. The
published subjects respond at 1.10 times their stated correction factor and the generated
ones came out at 0.63, so every generated subject was being dosed on somebody else's
settings on every cycle of every run. Settings are now measured from each subject's own
model.

The second was found by a level 1 check that was itself wrong twice before it was right.
Every run opened with a zero-insulin step, inherited from simglucose's own examples, which
kicked each subject off the steady state its parameters were closed at and left a slow
ring through the first days. Runs now open at the subject's own scheduled basal, and a
quiet subject holds its fasting glucose to within 0.02 mg/dL over four days.

The third was found by reading the code against its own documentation. The sensor layer
was applied to the finished trace after the run had ended, so the compression lows were in
the output and no algorithm and no simulated person had ever seen one. The level 1 check
that was supposed to catch it could not fail, because the layer could not possibly have
fed back into a body it never touched. Two rows of this table were also mis-calibrated by
a rate calculation that assumed a five-minute grid while the harness ran at three.

None of the three would have been caught by looking at this table. That is the argument
for the graded structure in [VALIDATION.md](VALIDATION.md): distributional fidelity is a
consequence of getting the mechanics right rather than a substitute for checking them.

## What the population does and does not add

The 100 subjects are drawn from the joint distribution of the 30 published subjects, so
they are a resampling of that cohort rather than new clinical data. They inherit whatever
the published cohort does not represent, and they carry no independent information about
human variability.

What they add is resolution, quantified at level 5: the design resolves about 1.8
percentage points of time in range across 34 adults and about 1.1 across all 100,
remeasured on the current harness.

## Provenance of the parameters

No parameter in the behaviour layer is fitted to any statistic in the table above.

Announcement rates and carbohydrate-counting error are clinical literature figures,
recorded with their reasoning in `timsim/person/behaviour.py`.

The rescue-treatment parameters were clinical figures until 2026-08-07 and are now fitted,
to measured behaviour rather than to this table: carb entries following a low, counted
across 30 real closed-loop users over 5008 days, giving 0.44 rescues a day at a mean of
33.8 g. That is a different dataset from the four cohorts this table is scored against, and
none of these eleven statistics appears in the fit. The distinction matters, because it is
what leaves the variability and diurnal rows able to fail. Both were predicted to move
before the calibration was run, by two measurements taken outside this table, and both did.

The real figures count carbohydrate that was logged, and people treat lows without
recording them, so 0.44 a day is a lower bound. The calibration lands at about 1.0 a day
rather than being driven down to the logged rate. The sensor layer's two parameters were fitted, on a different
cohort from the one they are evaluated against, and that is stated in
`timsim/sensor/realism.py`.
