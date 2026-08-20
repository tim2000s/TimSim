# Why Virtual Type 1 Diabetes Populations Under-Represent the Variation Between Real People, and What the Covariance Estimator Has to Do With It

Candidate for publication. The covariance figures are traceable to
`docs/measurements/covariance_estimator.json` and the spread ratios to
`docs/measurements/spread_ratio.json`, both from the population recorded under Provenance. The
spread ratios were quoted in this package's own documentation before either script existed,
having been computed by hand and pooled across pairings; section 2 records what changed when they
were recomputed.

## Abstract

**Background.** A virtual population used to benchmark automated insulin delivery is useful in
proportion to how much of the variation between real people it carries. Populations built from
the thirty subjects published with the UVA/Padova simulator are known to be narrow. The
resampling procedure used to build them shrinks the estimated covariance towards its diagonal,
and that shrinkage has been proposed as the cause, both of the narrow spread and of an
attenuated correlation between basal endogenous glucose production and insulin sensitivity.
Neither charge had been tested.

**Methods.** The spread deficit was quantified as the ratio of the simulated between-subject
standard deviation to the real between-participant one, on the sensor trace, separately for each
algorithm and each of two real populations rather than pooled, with intervals from resampling
both sides and with the effect of excluding runs that stopped early reported alongside. Two
independently built virtual populations reported in the literature were examined for the same
quantity. The shrinkage estimator was then audited: marginal standard deviations of the
generated subjects were compared with the published ones parameter by parameter, the correlation
between production and sensitivity was placed inside a Fisher interval reflecting the ten
subjects it is estimated from, the analytic shrinkage intensity minimising expected squared
error towards a diagonal target was computed per class, and the proportion of the sample
correlation matrix exceeding a significance threshold at n = 10 was counted.

**Results.** The population carries 0.64 [0.51, 0.79] and 0.75 [0.59, 0.93] of the trial's
between-participant standard deviation in mean glucose under two algorithms, and 0.41 [0.29,
0.66] of the do-it-yourself population's. On time below 54 mg/dL it carries 4.75 to 5.11 times
the trial's and 0.91 [0.63, 1.47] of the Commons', because the trial's participants barely go
below 54 mg/dL and their standard deviation there is 0.20 percentage points against 0.96. In an
independently built population matched subject for subject to twenty real patients and run under
the same algorithm, between-subject standard deviations of time in range were 0.63 and 0.50 of
the real ones across two arms. In a second independent study, the published adults driven by real meals
and real insulin from fourteen patients gave a coefficient of variation of 19.6 per cent against
a real 33, time in range of 95.3 per cent against a real 66.85, and an interquartile width in
mean glucose about 0.35 of the real one. On the shrinkage charges: marginal standard deviations
of the generated subjects are 0.83 to 1.07 of the published ones with a median of 0.92 to 0.94,
the residual being truncation rather than shrinkage, since the estimator preserves the diagonal
exactly at every intensity. The published production-sensitivity correlation is +0.773 in adults
with a 95 per cent interval of +0.279 to +0.943, and the value the shrinkage produces, +0.386,
lies inside it; the same holds in adolescents and children. The correlation is +0.773, +0.442
and −0.321 across the three classes and +0.287 when all thirty are pooled with class means
removed. The analytic optimal shrinkage towards a diagonal target is 0.422, 0.483 and 0.893
against the 0.50 in use. Of 406 pairwise correlations per class, 8 to 11 per cent exceed the
critical value at n = 10, against 5 per cent expected under the null.

**Conclusions.** The narrow spread is not caused by the covariance estimator and cannot be
repaired by changing it: the estimator preserves every marginal exactly, and the marginals are
those of thirty published people whose fasting glucose lies between 133.4 and 152.8 mg/dL. The
attenuated correlation is not a distortion either, since the shrunk value cannot be
distinguished from an estimate made on ten subjects, and the intensity in use is close to the
analytic optimum in two classes of three. The deficit is a property of the source population and
of what the model does not represent, and it appears at a similar magnitude in two virtual
populations built by other groups with other methods. A third population reached agreement on
spread by fitting each virtual subject's parameters day by day to its real counterpart's median
glucose, which is unavailable to a benchmark that has to remain independent of the outcome it
scores.

**Keywords.** virtual population, between-subject variability, covariance shrinkage, type 1
diabetes, in-silico testing

## 1. Introduction

A benchmark run on a virtual population answers a question about the average of that population.
How much that answer can be trusted to transfer depends on whether the population spans the
people it stands in for. A population whose members differ from one another less than real people
do will make competing algorithms look more alike than they are, and will make any single
algorithm's result look more certain than it is.

The populations in use are built from thirty published subjects. Resampling procedures transform
the published parameters to an approximately Gaussian space, estimate a covariance within each
of the three age classes, draw from it, and close each draw by the model's steady-state balance
equations. Because a covariance estimated from ten subjects in twenty-nine dimensions is
singular, the estimate is shrunk towards its diagonal before drawing.

That shrinkage has attracted two charges. The first is that it is responsible for the narrow
spread of the resulting population. The second is that it destroys a physiologically meaningful
correlation between basal endogenous glucose production and insulin sensitivity, reported at
+0.79 in the published adults and realised at +0.30 in one generated population.

This paper measures the spread deficit, places it beside two independently built populations,
and tests both charges against the estimator.

## 2. The deficit

The quantity is the standard deviation across subjects of each outcome against the standard
deviation across participants of the same outcome in the real population, both on the sensor
trace. Measured across the three pairings the bench reports, with intervals from resampling
both sides:

| Statistic | DCLP3, Control-IQ | DCLP3, oref0 | Commons, oref0 |
|---|---|---|---|
| Mean glucose | 0.64 [0.51, 0.79] | 0.75 [0.59, 0.93] | 0.41 [0.29, 0.66] |
| Time in range | 0.73 [0.59, 0.88] | 0.68 [0.56, 0.83] | 0.54 [0.37, 0.83] |
| Time above 180 | 0.68 [0.55, 0.82] | 0.64 [0.51, 0.79] | 0.46 [0.32, 0.71] |
| Variability | 1.39 [1.14, 1.69] | 1.32 [1.08, 1.60] | 0.98 [0.73, 1.27] |
| Time below 70 | 1.92 [1.50, 2.47] | 2.30 [1.74, 3.02] | 0.84 [0.64, 1.12] |
| Time below 54 | 4.75 [3.34, 6.73] | 5.11 [3.77, 6.99] | 0.91 [0.63, 1.47] |

The population is too narrow on where glucose sits, at 0.41 to 0.75 of the real spread in mean
glucose, and too wide on hypoglycaemia. A single pooled figure was quoted for this previously,
2.74 times too wide on time below 54 mg/dL, and it conceals the more informative result. The
excess is 4.75 to 5.11 against the trial and 0.91 against the do-it-yourself users, because the
trial participants barely go below 54 mg/dL at all: their between-participant standard deviation
is 0.20 percentage points against 0.96 in the Commons. So the hypoglycaemia spread is not
uniformly wrong. It is close to right against one real population and several times too wide
against another, and which of those a reader is told depends entirely on the reference chosen.

Two things the ratio does not separate. Run-to-run variation sits inside the simulated standard
deviation, since each subject contributes one month and a different month would move it, so the
simulated side is inflated by an amount only seed replication can size. And subjects whose runs
stopped early are excluded above. Including them at the duration each survived widens the
hypoglycaemia ratios considerably, to 7.29 and 8.80 against the trial and 1.87 against the
Commons, because the runs that stop are the ones that went furthest low.

A second measurement points at where the deficit sits. Correlating each subject's outcome
against its own parameters explains little: across body weight, basal glucose, insulin
sensitivity, carbohydrate ratio, correction factor, age and daily basal, the strongest
association is 0.35, for carbohydrate ratio against mean glucose. The physiological differences
between subjects are largely erased before they reach the outcome, because each subject is dosed
by settings measured from its own model and corrected towards a single target.

## 3. The same deficit in populations built by other groups

Resalat and colleagues built twenty virtual patients matched to twenty real patients on total
daily insulin and body weight, then ran both under the identical algorithm with identical meals
[1]. Means agreed. Spreads did not:

| Arm | Virtual time in range | Real time in range | Between-subject SD ratio |
|---|---|---|---|
| Single hormone | 78.1 ± 5.1% | 74.3 ± 8.1% | 0.63 |
| Dual hormone | 75.6 ± 5.5% | 71.9 ± 10.9% | 0.50 |

That is a different model, a different construction method and subject-level matching to a real
cohort, landing between 0.50 and 0.63 on time in range where this package lands at 0.54
to 0.73 on the same measure.

Ahmad and colleagues supply the other end of the same picture [2]. They extracted meals, insulin
and detected exercise from the records of fourteen patients at the Hospital Clínic of Barcelona
and drove the published UVA/Padova adults with them in open loop. The stock population under
real inputs:

| | Clinical, n = 14 | Published adults, real meals | Published adults, typical meals |
|---|---|---|---|
| Mean CGM, mg/dL | 162.2 (145.6–169.3) | 129.2 (126.6–134.9) | 131.8 (126.4–140.8) |
| CV, % | 33 (28.8–38.1) | 19.6 (17.3–25.8) | 25.2 (22.6–27.0) |
| Time 70–180 mg/dL, % | 66.85 (57.4–71.6) | 95.3 (88.8–98.4) | 90.15 (82.6–94.2) |
| Interquartile width, mean CGM | 23.7 | 8.3 | 14.4 |

The stock adults given real meals and real insulin run 33 mg/dL low, at three fifths of the real
variability, with time in range 28 percentage points too high, and their interquartile width in
mean glucose is about 0.35 of the real one. The interquartile widths are computed here from the
published quartiles and rest on ten and fourteen subjects respectively, so they are indicative
rather than precise. Their authors draw the conclusion that including only meals in a simulation
scenario is not enough to achieve realistic outcomes.

The same study then fitted each virtual subject's insulin sensitivity and basal production day
by day to its real counterpart's median glucose, to a tolerance of 0.5 mg/dL, and reported
agreement across almost every statistic, with an interquartile width of 20.0 mg/dL against the
real 23.7. That agreement is the objective function reported as a result. It is a legitimate way
to build a scenario library and it is not available to a population that has to be independent of
the benchmark scoring it, because a population fitted to an outcome cannot then be used to
measure that outcome. Their procedure discarded 46 per cent of candidates, and one published
adult could not be forced to match any of the fourteen real patients.

## 4. The estimator, tested

### 4.1 The shrinkage cannot change the marginal spread

The estimator forms the sample covariance and returns `(1 − α)·S + α·diag(S)`. Every diagonal
entry is therefore unchanged at every intensity, and the marginal standard deviation of each
parameter is the sample one regardless of α. Measured on the generated population, marginal
standard deviations in the transformed space are 0.85 to 1.00 of the published ones in adults,
0.88 to 1.07 in adolescents and 0.83 to 1.00 in children, with medians of 0.92 to 0.94. The
shortfall is the per-marginal truncation at 2.5 standard deviations applied when drawing, plus
the behavioural screen, and it is small.

So the first charge fails on inspection. Reducing α cannot widen the population, and setting α
to zero returns a rank-nine covariance in twenty-nine dimensions that collapses every draw onto
the affine span of the ten published subjects.

### 4.2 The attenuated correlation is not distinguishable from the estimate it is measured against

The production-sensitivity correlation is estimated from ten subjects per class. Its Fisher
interval is correspondingly wide:

| Class | Published r | 95% interval | After shrinkage at α = 0.5 | Inside |
|---|---|---|---|---|
| Adult | +0.773 | +0.279 to +0.943 | +0.386 | yes |
| Adolescent | +0.442 | −0.261 to +0.838 | +0.221 | yes |
| Child | −0.321 | −0.791 to +0.387 | −0.160 | yes |

In every class the shrunk value lies inside the interval of the published estimate. The
realised values in the generated population are +0.350, +0.102 and −0.036, the further movement
being truncation and screening.

The correlation is also not a constant of the physiology. It is strongly positive in adults,
weakly positive in adolescents and negative in children, and pooling all thirty subjects with
class means removed gives +0.287, which is close to what the shrinkage already produces. A
procedure that restored the adult figure would be restoring one estimate from ten people, in one
of three classes, that the other two classes do not support.

### 4.3 The intensity in use is close to the analytic optimum

The intensity minimising expected squared error towards a diagonal target, computed analytically
per class, is 0.422 in adults, 0.483 in adolescents and 0.893 in children, against the 0.50 in
use. The setting is slightly too strong for adults, close to optimal for adolescents and much
too weak for children. Any change made to restore correlations would move α downwards, away from
the optimum in all three classes.

The reason heavy shrinkage is appropriate is visible in the matrix itself. Of the 406 pairwise
correlations within each class, 46 exceed the n = 10 critical value in adults, 44 in adolescents
and 31 in children, or 8 to 11 per cent against the 5 per cent expected under the null. There is
real structure, and it is a small fraction of what a sample correlation matrix at this size
appears to contain.

## 5. Discussion

The three measurements in section 4 answer the charges against the estimator, and the answer is
that it is doing its job. It preserves every marginal exactly, its intensity is near the value
that minimises expected error in two classes of three and too low in the third, and the
correlation it is accused of destroying was never resolved by ten subjects in the first place.
Changing it would consume a full population regeneration and every measurement downstream of it,
for a change that the data cannot show to be an improvement.

A mechanism worth stating, because it points the opposite way from the intuition behind the
charge: separating production from disposal should widen the distribution of outcomes rather
than narrow it, since decorrelating them admits subjects who produce strongly and dispose
weakly, and subjects who do the reverse. Restoring the published adult correlation would
therefore be expected to narrow the mean glucose spread further, while helping the hypoglycaemia
spread that is already several times too wide against the trial. That prediction is recorded
here before any such
change is made, and it is a trade rather than a repair.

The deficit itself has two sources that the measurements distinguish. The first is the source
population. Thirty published subjects with fasting glucose between 133.4 and 152.8 mg/dL cannot
generate a population wider than themselves under any procedure that respects their marginals,
and widening those marginals is a modelling choice with no data behind it: reaching the real
14.2 mg/dL would need the parameter spread scaled by a factor near 2.2, which would widen the
already excessive hypoglycaemia spread in the same proportion. The second is everything the
model does not represent. Meal size variance, carbohydrate estimation error, missed and late
boluses, illness, stress and adherence do not live in a parameter covariance. Two mechanisms in
this package already demonstrate the coupling: per-subject settings divergence moves the raw
spread from 8.44 to 9.68 mg/dL and costs per-subject coverage 4.4 percentage points and
plausibility 4.5, and per-subject treating style moves it to 10.21 while raising coverage 3.0
points and costing plausibility 8.6. Both are implemented, both close part of the gap, and both
are switched off by default because they buy width at the price of the subjects looking less
like people.

That two other groups, working with different models and different construction methods, arrive
at 0.50 to 0.63 and about 0.35 suggests the deficiency is a property of virtual populations of
this kind rather than of any one procedure. The one method that reached agreement on spread did
so by fitting to the outcome.

What remains available is distribution matching at the level of the population rather than the
individual: generate from wide priors, screen for plausibility, and then select or reweight the
ensemble so that the simulated marginal distribution of an outcome matches the observed one.
That approach was developed in quantitative systems pharmacology for models that are not
identifiable [3, 4], and it does not require any parameter to be recovered from any individual.
Whether it can widen mean glucose without widening hypoglycaemia further is the question it
would have to answer, and it should be asked with the mechanism switched off as well as on.

## 6. Conclusions

A virtual population built by resampling thirty published subjects carries 0.41 to 0.75 of the
real between-subject variation in mean glucose, and 0.54 to 0.73 of it in time in range. On
hypoglycaemia it runs the other way and by a margin that depends on the reference: 4.75 to 5.11
times the trial's variation in time below 54 mg/dL, and 0.91 of the do-it-yourself population's.
Two populations built independently by other groups show the same under-dispersion on the
measures describing where glucose sits, at 0.50 to 0.63 and about 0.35.

The covariance shrinkage is not the cause. It preserves every marginal standard deviation
exactly, so it cannot affect the spread at all; the correlation it attenuates cannot be
distinguished from an estimate made on ten subjects, and differs in sign between age classes;
and its intensity is close to the analytic optimum for the target it shrinks towards. The
estimator does not need changing, and changing it would be expected to narrow the deficient
statistic further while improving the excessive one.

## Provenance

Both measurement files carry a stamp, and the two agree on every field that identifies the
experiment:

| Field | Value |
|---|---|
| Population fingerprint | 704cfac086df54ba |
| Titrated settings digest | 5b66a9f91b08d0af |
| Commit | c169447d481b42d69f271611c5ffa63f4508eb9b |
| Patient model | simglucose 0.2.11 |
| Measured | 20 August 2026 |

The stamp also records the working tree as carrying uncommitted changes when the files were
written, so these figures are reproducible from the population and the settings named here
rather than from the commit alone.

Section 2 is supplied by `docs/measurements/spread_ratio.json` from `examples/spread_ratio.py`,
and section 4 by `docs/measurements/covariance_estimator.json` from
`examples/covariance_estimator.py`. The figures in section 5 describing this package's own
mechanisms come from `docs/FIDELITY.md`, where the spread-ratio rows of the two mechanism tables
are on a superseded pooled basis and only the raw standard deviations and the coverage and
plausibility movements are quoted here. Section 3 is computed from the published tables of the
cited studies and depends on nothing in this package.

## References

1. Resalat N, El Youssef J, Tyler NS, Castle JR, Jacobs PG. A statistical virtual patient
   population for the glucoregulatory system in type 1 diabetes with integrated exercise model.
   PLoS One 2019;14(7):e0217301. doi:10.1371/journal.pone.0217301. PMID 31344037.
2. Ahmad S, Ramkissoon CM, Beneyto A, Conget I, Giménez M, Vehí J. Generation of Virtual Patient
   Populations That Represent Real Type 1 Diabetes Cohorts. Mathematics 2021;9(11):1200.
   doi:10.3390/math9111200.
3. Allen RJ, Rieger TR, Musante CJ. Efficient Generation and Selection of Virtual Populations in
   Quantitative Systems Pharmacology Models. CPT Pharmacometrics Syst Pharmacol
   2016;5(3):140-146. doi:10.1002/psp4.12063. PMID 27069777.
4. Rieger TR, Allen RJ, Bystricky L, et al. Improving the generation and selection of virtual
   populations in quantitative systems pharmacology models. Prog Biophys Mol Biol
   2018;139:15-22. doi:10.1016/j.pbiomolbio.2018.06.002. PMID 29902482.
5. Schäfer J, Strimmer K. A shrinkage approach to large-scale covariance matrix estimation and
   implications for functional genomics. Stat Appl Genet Mol Biol 2005;4:Article32.
   doi:10.2202/1544-6115.1175. PMID 16646851.
