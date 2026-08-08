# How closely does this match real data, and where does it fail

This is level 3 of the six in [VALIDATION.md](VALIDATION.md), and on its own it is the
weakest of them. Matching the marginal statistics of real data says nothing about whether
the response to an intervention is right. Read it alongside levels 4 and 5, which are what
a controller comparison actually rests on.

## The measurement

Eleven statistics, computed identically on simulator output and on real continuous glucose
data. The real reference is the envelope across four cohorts of closed-loop users, 192
people in total, taken as the minimum and maximum of the four cohort medians. Each
simulator figure is the median across the first ten adult subjects, run for 28 days.

Each column adds one mechanism to the column before it, so a movement is attributable to a
named cause rather than to the bundle.

| Signature | Real range | stock 2008 | +physiology | +behaviour | +loop | +sensor | +site | In range |
|---|---|---|---|---|---|---|---|---|
| Glucose variability (CV%) | 29.5–34.3 | 33.9 | 36.8 | 37.8 | 34.0 | 33.6 | 38.3 | yes |
| Rise tail P(ΔBG>10/5min) % | 3.7–6.6 | 2.6 | 2.5 | 2.9 | 3.6 | 5.3 | 4.9 | yes |
| Autocorrelation @30min | 0.78–0.87 | 0.86 | 0.91 | 0.95 | 0.87 | 0.86 | 0.90 | yes |
| Autocorrelation @60min | 0.50–0.68 | 0.67 | 0.77 | 0.85 | 0.65 | 0.65 | 0.72 | yes |
| Outcome SD @stuck-high (mg/dL) | 26.5–33.5 | 22.7 | 19.7 | 21.7 | 26.1 | 27.0 | 26.3 | yes |
| Diurnal amplitude (mg/dL) | 34.7–56.3 | 69.5 | 73.1 | 61.7 | 59.6 | 56.8 | 63.9 | yes |
| Hypo recovery to 100 (min) | 50–59 | 103.8 | 110.0 | 72.5 | 72.5 | 62.5 | 61.2 | no |
| Hypo rebound >180 % | 23.2–28.4 | 15.0 | 3.4 | 64.9 | 73.4 | 66.1 | 63.1 | no |
| Compression lows /30d | 1.9–5.3 | 0.0 | 0.0 | 0.0 | 0.0 | 3.8 | 4.3 | yes |
| Sensor jitter (mg/dL) | 4.5–6.7 | 2.5 | 2.4 | 2.5 | 2.5 | 5.7 | 5.6 | yes |
| ISF drift (weekly %CV) | 8.2–21.7 | 0.0 | 0.0 | 14.9 | 3.7 | 3.5 | 10.0 | no |

The default simulator is the `+sensor` column. The `+site` column adds a layer that is off
by default, and the section below says why it is both the largest correction in the package
and not something to switch on without knowing what it costs. The "In range" column is the
default arm, and allows the 10% padding `signatures.in_real_range` applies.

Three of eleven for the bare subjects, eight of eleven with the four default layers,
five of eleven with the site layer added.

Survival belongs in the headline rather than in a footnote. The physiology-only arm loses
five of its ten subjects over 28 days and the survivors spend up to 28% of the run below
70 mg/dL. Its column is computed on whoever lived, which is why hypoglycaemia rebound reads
3.4% there: the subjects that would have rebounded are the ones that died. Since the rescue
model was recalibrated the loop arm also loses one of ten, which is the cost of a person who
treats lows less often.

Reproduce with `python examples/layer_ablation.py`, about three quarters of an hour
serially. The `--arm` flag runs one column, so the six can go in parallel. Raw output in
`docs/*.json`.

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

| Configuration | AUC | sd over splits | Excess over null | Signatures in range |
|---|---|---|---|---|
| Default plus the site layer | 0.671 | 0.011 | +0.135 | 5 of 11 |
| Default plus real settings | 0.688 | 0.011 | +0.147 | not measured |
| Both | 0.700 | 0.011 | +0.159 | not measured |
| Default, four layers | 0.710 | 0.009 | +0.164 | 8 of 11 |
| Default plus Visentin's classes | 0.760 | 0.012 | +0.211 | 6 of 11 |
| No layers at all | 0.937 | 0.004 | +0.377 | 3 of 11 |

Lower is better, and the differences are small but not ambiguous. Paired over the same ten
splits, the site layer beats the default by 0.039 with a standard deviation of 0.006, in ten
splits out of ten. Conservative settings beat it by 0.022, also ten out of ten.

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
still separable at 0.671 against a null 95th percentile near 0.52. Time above 180 mg/dL is
what carries the separation in every arm. Better is not the same as good, and the honest
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

So the layer is off by default. It is the largest correction available on the statistic that
matters most clinically and a regression on three that this table has always reported, and
switching it on silently would restate every number in these documents and hand a
pre-registered safety gate a hazard no algorithm can dose its way out of. Pass `"site"` in
`layers` to use it, and read `therapy/site.py` first.

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

The correction factor disagrees by a factor near three, and the disagreement is inherited:

| | Carbohydrate ratio, g/U | Correction factor, mg/dL/U | Implied mg/dL per gram |
|---|---|---|---|
| DCLP3 participants, at midday | 8.0 | 35.0 | 4.17 |
| Clinical 500 and 1800 rules | 8.5 | 30.6 | 3.60 |
| Generated subjects | 8.9 | 14.7 | 1.89 |
| The ten published adults | 9.5 | 12.6 | 1.98 |
| simglucose's own settings table | 9.5 | 11.5 | 1.59 |

Carbohydrate ratio agrees everywhere. Correction factor does not, and the model agrees with
the table rather than with the clinic:
`check_published_cohort_obeys_clinical_rules` puts the measured response at 1.10 times the
stated factor, so the physiology and the settings table describe the same person. Applying
the 1800 rule to the published subjects' own stated daily insulin gives 30.6 against the
11.5 they are tabulated with.

What follows from that is a bound on the behaviour layer. A gram of carbohydrate moves a
virtual subject about 1.9 mg/dL where it moves a DCLP3 participant about 4.2. So a meal that
is miscounted, unannounced, or eaten to treat a low moves a virtual subject roughly half as
far as it would move a real one, and no amount of work on meal timing or size can recover
the other half. This is a property of the UVA/Padova model, not of anything added here.

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
| DCLP3 participants | 35.0 | |

A first pass at this raised glucose with a fixed 90 g load, which only six of the ten
subjects reached 300 on, and reported 32.5 at that level. Escalating the load until every
subject reaches every level drops it to 23.4. The selection was doing a third of the work.

So the operating point accounts for about half the difference and the rest is real. That
still leaves the question of which side is wrong, and the third measurement answers it by
running the experiment backwards.

If the model's insulin were defectively weak, then handing the algorithm a weaker setting
still, so that it doses even less, should push the simulator further from reality. The
opposite happens. Setting the correction factor to 35 mg/dL per unit, which is what DCLP3
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

Both stay off by default. `simulate(..., isf_scale=2.4)` puts the median correction factor
at 35.3, and `docs/FIDELITY.md` is where the cost of that is recorded rather than in a
changed headline. What neither fixes is the shape by hour: every arm runs high at breakfast
and short after midnight, which is a separate problem and still open.

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
