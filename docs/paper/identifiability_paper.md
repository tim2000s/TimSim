# Can a Virtual Population Be Fitted to Real People? Parameter Identifiability in the UVA/Padova Type 1 Diabetes Model, Reviewed and Audited Against Two Free-Living Datasets

Candidate for publication. The audit figures below are traceable to the release files and to
the package source at the commit recorded under Provenance. The review figures are traceable to
the cited papers, with the verification procedure stated in the final section.

## Abstract

**Background.** Virtual populations used to benchmark automated insulin delivery are commonly
built by resampling the thirty subjects published with the UVA/Padova simulator. Those subjects
carry a narrow range of physiology, and populations derived from them under-represent the
variation between real people. An obvious remedy is to fit the population to real continuous
glucose and pump records instead, using the hierarchical Bayesian and simulation-based inference
machinery that the digital twin literature has developed. Whether the available data supports
that fit for a model of this size has not been established.

**Methods.** Three things were done. The free-parameter structure of the S2008 model as
implemented in `simglucose` was audited, separating parameters that are estimated from those
fixed by convention and those determined algebraically by the steady-state balance equations.
The published identifications of UVA/Padova and of comparable type 1 diabetes models were
reviewed, with each citation verified against PubMed, Crossref or the paper's own full text.
Two real datasets were audited for the quantities an identification would require: the DCLP3
trial release and a 240-user export from the OpenAPS Data Commons.

**Results.** Of 62 parameter columns, 29 are estimated, 11 are fixed and 20 are determined by
closure. Three of the 29 appear nowhere in the model's differential equations, leaving 26 with
any effect on simulated glucose. Eight of those 26 describe insulin kinetics and are observed,
after closure, by a single scalar per subject. The only published identification of UVA/Padova
in real people required venous plasma glucose and plasma insulin sampled through three 23-hour
inpatient admissions in 47 subjects, fitted the glucose subsystem alone with plasma insulin
supplied as a forcing function, took population values for glucagon, and reported an insulin
sensitivity posterior statistically indistinguishable from its prior. Four independent groups
working from free-living records replaced the model with a reduced one carrying about eight free
parameters. On that reduced model, posterior credible intervals from Markov chain Monte Carlo
covered the true parameter 23.25 per cent of the time at a nominal 95 per cent. In the DCLP3
release, body weight and height are absent (0 non-null of 170 screening records) and no
carbohydrate quantity is recorded anywhere (the single `Carbs` column is 0 non-null of 25,344
rows), while insulin delivered is fully recoverable from 221,293 bolus records and 2,610,773
basal rate changes over a median 164 days per participant. In the Commons export, 103 of 240
users have a 28-day window at 70 per cent sensor coverage and 77 of those have a reconstructable
daily requirement, with glucose, delivery and self-logged carbohydrate all present and no
demographics at all.

**Conclusions.** Fitting the 26 effective parameters of this model per subject from continuous
glucose and pump records is not supported by either dataset. Body weight is absent from both and
the model is parameterised per kilogram throughout, so body weight trades directly against
insulin sensitivity and production. Carbohydrate is absent from one and self-reported in the
other. Endogenous production cannot be separated from utilisation without tracers, and insulin
kinetics cannot be recovered without plasma insulin. Simulation-based inference changes the cost
and the honesty of the uncertainty estimate; it adds no information, so the calibrated posterior
over a 26-dimensional vector observed through sensor glucose is close to the prior in most
directions. Population-level distribution matching does not require individual identifiability
and remains available.

**Keywords.** identifiability, simulation-based inference, virtual population, type 1 diabetes,
UVA/Padova, digital twin

## 1. Introduction

The UVA/Padova simulator was accepted as a substitute for animal testing on the strength of a
population of virtual subjects whose parameters were estimated from tracer studies. Thirty of
those subjects are published with the S2008 release. Packages that need more than thirty, this
one included, generate them by resampling: parameters are transformed to an approximately
Gaussian space, a covariance is estimated within each of the three age classes, draws are taken
and each draw is closed by the steady-state balance equations so that the resulting subject sits
at a consistent fasting state.

The weakness of that procedure is measurable. A population generated this way reproduces the
marginal spread of the published thirty and nothing wider, and the published thirty have fasting
glucose confined between 133.4 and 152.8 mg/dL. Measured against the DCLP3 trial, the population
used here carries a between-subject standard deviation in mean glucose of 6.0 to 6.8 mg/dL
against an implied 14.2 in the trial, about 45 per cent of the real variation.

The digital twin literature suggests a remedy. If individual subjects can be fitted to their own
continuous glucose and pump records, then a population can be assembled from real people rather
than from resampled published ones, and it will carry whatever variation those people carry.
Recent work on simulation-based inference makes the computational objection to that programme
much weaker than it was, since a neural posterior estimator can be trained once and then applied
to each new subject in seconds.

This paper asks whether the data supports the programme, which is a separate question from
whether the inference machinery works. It is answered in three parts: what the model leaves
free, what has actually been identified in published work and with what measurements, and what
the two real datasets available here contain.

## 2. What the model leaves free

The `simglucose` implementation of S2008 stores 62 columns per subject. They divide into three
groups, and the division matters because only one of them is a target for estimation.

Eleven are fixed by convention across all subjects: four initial states that are zero at rest,
hepatic extraction at basal, the fraction of intestinal absorption reaching plasma, the two renal
excretion parameters, insulin-independent utilisation, and two housekeeping fields.

Twenty are determined algebraically once the others are set. Basal plasma and tissue glucose,
basal plasma and liver insulin, the two subcutaneous insulin states, the steady-state infusion
rate, the zero-order utilisation term, one insulin transfer rate, the basal disposal rate, and
nine initial state entries all follow from the requirement that the subject be at rest. A test
in this package asserts that closing each of the thirty published subjects from its 29 estimated
values reproduces all 62 columns to a relative residual below 1e-9. That test is what makes the
generated subjects members of the same family as the published ones, and it is unaffected by how
the 29 values are chosen, since it never inspects a generated subject.

Twenty-nine are estimated. Three of those, `m5`, `CL` and `PCRb`, appear in no equation of the
model as implemented and in no closure relation; they occupy columns and nothing more. The
effective dimension of the problem is therefore 26, and those 26 fall into blocks that differ
sharply in how well any glucose measurement can see them:

| Block | Parameters | What observes them |
|---|---|---|
| Meal transit | `kmax`, `kmin`, `b`, `d`, `kabs` | the shape of the post-meal rise, given known carbohydrate |
| Glucose kinetics and action | `Gb`, `Vg`, `k1`, `k2`, `Km0`, `Vmx`, `p2u`, `ki`, `ksc`, `EGPb`, `kp2`, `kp3`, `BW` | the whole trace |
| Insulin kinetics | `Ib`, `Vi`, `m1`, `m2`, `m4`, `kd`, `ka1`, `ka2` | plasma insulin, which free-living data never measures |

The insulin block is the clearest case. After closure, the steady-state infusion rate is a
function of `m1`, `m2`, `m4`, `Ib` and `Vi`, and the subject's basal requirement is that rate
scaled by body weight. So the entire block is observed through one number per subject. Eight
unknowns against one observation is not a hard estimation problem; it is an underdetermined
system, and any procedure applied to it returns whatever prior it was given.

## 3. What has been identified, and with what

### 3.1 The only identification of UVA/Padova in real people

Visentin, Dalla Man and Cobelli identified the model in 47 subjects drawn from the AP@home
project across six clinical centres [1]. Each subject completed three 23-hour inpatient
admissions, giving 141 daily traces. Venous plasma glucose was measured on a YSI 2300 every 15
minutes for two hours after each meal, every 30 minutes otherwise and hourly overnight. Plasma
insulin was assayed by chemiluminescence on the same schedule. Meals were scheduled and weighed
at 50 g for breakfast, 60 g for lunch and 80 g for dinner.

Three limitations of that work bear directly on the present question, and the authors state each
of them.

The model cannot be identified by least squares or maximum likelihood from glucose and insulin
data alone, because many different combinations of meal appearance, endogenous production and
utilisation give an equally good fit. The method used was Bayesian maximum a posteriori
estimation with the simulator's own lognormal joint prior, which is the same distribution that
resampling draws from.

Production could not be separated from utilisation or renal loss, because no tracers were used.
Only the net rate of disappearance was estimated.

The insulin subsystem was bypassed entirely, with measured plasma insulin used as a forcing
function. The authors note that this precludes applying the method from sensor glucose and pump
data, which is the setting the present question concerns.

The fit was good by the usual measures, at R² of 0.962 ± 0.027 and a normalised fit index of
0.812 ± 0.066, at roughly three hours of computation per subject. Reported parameter precision
was a coefficient of variation of 1.3 ± 0.2 per cent, which describes precision conditional on a
strong prior rather than information contributed by the data. The decisive result for a
population-generation programme is what happened to the posteriors: the insulin sensitivity
parameter `Vmx` came back statistically indistinguishable from its prior at both breakfast and
the combined lunch and dinner window (P > 0.05). Only the gastric emptying parameters moved, and
only where the meal composition differed from the liquid meal the prior was built on
(P < 0.0001). The authors observe that the power of the method rests on the quality of the
prior, and that a different prior would give different posteriors.

A population assembled from those posteriors would carry the prior's covariance with estimation
noise added to it. It would not widen the between-subject spread, because the data did not
determine the parameters independently of the prior.

### 3.2 What groups working from free-living data did instead

Four groups have approached the same problem from sensor glucose and pump records. All four
replaced the model.

| Work | Model used | Data required | Free parameters |
|---|---|---|---|
| Visentin 2016 [1] | UVA/Padova S2013 glucose subsystem | inpatient plasma glucose and insulin, 23 h, weighed meals | ~25, insulin and glucagon excluded |
| ReplayBG [2] | single-compartment Bergman type | CGM, insulin, carbohydrate records | 8 |
| Colmegna 2020 [3] | time-invariant structure plus a daily sensitivity channel | CGM, pump, meal records, free living | structure plus one time-varying channel |
| Siket 2026 [4] | custom Hovorka-flavoured model | CGM, self-reported meals, insulin, activity, heart rate | four hierarchical levels |
| Hoang 2025 [5] | ReplayBG's model, described by its authors as a simplified UVA/Padova | 264 CGM points over 22 h, meals and insulin known | 8 physiological plus 9 initial states |

The convergence is the finding. Four groups, working independently and with different aims,
reduced to a model of roughly eight free parameters when the observation was sensor glucose. The
reduction is the field's answer to the identifiability question, arrived at four times.

### 3.3 What the uncertainty looks like when it is measured honestly

The simulation-based inference work is the most informative, because it is the only study that
scored posterior calibration rather than fit quality [5]. Fifty glucose trajectories were
generated from parameter vectors drawn from the prior, so the true parameters were known.
Neural posterior estimates contained the true parameter within the 95 per cent credible interval
96.5 per cent of the time. Markov chain Monte Carlo posteriors from the same model and the same
data contained it 23.25 per cent of the time.

That result is usually read as an argument for the newer method. It is more useful read as a
measurement of the likelihood surface: over these eight parameters, given 22 hours of sensor
glucose with meals and insulin known, the surface is flat enough that a sampler's intervals are
roughly four times too narrow. Reconstruction quality moved in the direction that implies.
In-sample mean absolute relative difference was 12.60 ± 6.19 per cent for the calibrated method
against 6.73 ± 2.82 per cent for the sampler, and on the following day 14.84 ± 8.84 per cent
against 20.20 ± 16.69 per cent. Inference time fell from 2,767 s to 3.36 s.

The evaluation used no real patient data. It also used a one-compartment glucose equation with
no two-compartment structure, no `kp1` to `kp3` production term, no renal excretion and no
Michaelis-Menten utilisation, so it says nothing directly about the 26 parameters at issue here
beyond the direction the evidence points.

Three further results support the same reading. A hierarchical Bayesian fit of a reduced model
to ten free-living patients over 500 daily windows returned boundary solutions: the
hypoglycaemia coefficient converged to its lower bound of zero in every patient, glucose
effectiveness converged to its lower bound in seven of ten, and the carbohydrate absorption time
constant pinned to its upper bound of 10 minutes [4]. The same work imposed a linear association
between endogenous production and insulin sensitivity to stop the variance inflating, which is
the physiological coupling a fitted population would want to recover, handled by assumption
because it could not be. A review of control-oriented glucose models found that few are globally
identifiable and observable at once, and that routinely collected data often cannot guarantee a
unique solution even in quantity; the minimal identifiable structures needed about two days of
data and gave mean absolute errors of 21.5 to 21.6 mg/dL on 77 real adult records, rising to
36.6 to 39.2 mg/dL on a one-day validation window [6]. And in a non-diabetic oral tolerance
study of 237 participants with plasma insulin available, fitting three parameters of a reduced
model still left 6 of 404 fits unidentifiable on sensor glucose by profile likelihood, against
11 of 404 on plasma glucose [7]. Three parameters, with plasma insulin measured, and
identifiability was not automatic.

## 4. What the data contains

### 4.1 DCLP3

The trial release covers 168 participants, 112 of whom ran a closed loop and 56 a
sensor-augmented pump. Median follow-up is 164 days per participant, with sensor glucose at
roughly five-minute cadence.

Insulin delivered is fully recoverable. Boluses appear as 221,293 records carrying amount and
type, of which 217,035 are standard and 4,257 extended. Basal delivery is recoverable by
integrating 2,610,773 commanded rate changes. Pump settings carry half-hourly basal profiles
along with up to ten carbohydrate ratios and ten correction factors per participant.

Two quantities an identification needs are absent, and both were confirmed directly against the
release rather than inferred from the loader used elsewhere in this package. No carbohydrate
quantity is recorded anywhere: the only column of that name in the release holds 0 non-null
values across 25,344 rows and 168 participants. Body weight and height are likewise empty, at 0
non-null of 170 screening records for each. Age is present, at a median of 28.5 years, and total
daily insulin is present at a median of 47 U/day.

Carbohydrate could be back-inferred as each bolus divided by that participant's own carbohydrate
ratio. Doing so assumes the participant counted the meal correctly and dosed for it correctly,
which is the assumption a meal model exists to test.

### 4.2 The OpenAPS Data Commons

The export holds 241 user directories. Per user there are sensor entries, treatment records
carrying boluses, carbohydrate entries and temporary basal rates, and profile records carrying
basal schedules, carbohydrate ratios, sensitivity factors and targets.

Yield after quality filtering is 103 users with a 28-day window at 70 per cent sensor coverage,
of whom 77 have a daily insulin requirement that can be reconstructed. Across those, the median
requirement is 38.2 U/day at 45 per cent basal, with 19 boluses and 179.6 g of logged
carbohydrate per day. Reconstruction has to resolve temporary basal rates against the underlying
schedule, since 12.3 per cent of records carry only a percentage.

This is the only source with sensor glucose, delivered insulin and carbohydrate together. Its
limitations are that no demographic data exists at all, so body weight is again unavailable;
logged carbohydrate is under-reported by an unmeasured amount; and 17 users have treatment
records missing from their window while their glucose looks intact.

### 4.3 The closed-loop problem

Every Commons user runs a closed loop, and 112 of the 168 DCLP3 participants did. Insulin is
therefore a function of glucose through a controller that is not part of the model being
identified, and in the trial's case is proprietary. The 56-participant sensor-augmented arm of
DCLP3 is the only substantial open-loop data on either side, and it is the arm with no
carbohydrate records.

## 5. Discussion

The three audits agree, and they agree for a reason that is not about inference technique.

The closure is not an obstacle. It confines estimation to the 29 free values and leaves the test
against the published thirty untouched. Anyone proposing to fit this population can do so
without disturbing the property that makes its subjects members of the published family.

Body weight is an obstacle, and a simple one. The model is parameterised per kilogram
throughout. With weight unmeasured, a subject who is heavy and insulin-resistant is
indistinguishable from one who is light and sensitive, because the products that enter the
equations are the same. Neither dataset records it.

Carbohydrate is an obstacle of a different kind. Absent from DCLP3 entirely, it is present in
the Commons as a self-logged quantity with a known downward bias of unknown size, which biases
the meal transit block and insulin sensitivity in a known direction by an unknown amount.

Endogenous production and insulin kinetics are obstacles that no free-living dataset can remove,
because the measurements that separate them are tracer infusions and plasma insulin assays. This
is the constraint Visentin met with far richer data than either dataset here provides, and met
by excluding the affected subsystems from the fit.

What simulation-based inference contributes is real but narrow. It removes the computational
argument against fitting many subjects, and it produces intervals that are honest about how
little the data determines. Neither of those adds information. On a 26-dimensional vector
observed through sensor glucose, an honest posterior is close to the prior in most directions,
and a population assembled from such posteriors reproduces the prior. That is the same
conclusion Visentin reached from a much better-instrumented study, and the same conclusion the
coverage measurement implies from the other direction.

Two routes remain open and neither requires individual identifiability. Population-level
distribution matching, developed in quantitative systems pharmacology for exactly this
situation, generates candidates from wide priors, screens them for plausibility and then selects
or reweights the ensemble so that simulated marginal distributions match observed ones [8, 9].
And a substantial part of the missing variation between people is behavioural rather than
physiological. Meal size variance, carbohydrate estimation error, missed and late boluses and
adherence do not live in a parameter covariance, and no amount of physiological fitting recovers
them; a separate decision layer is the published response to that [10].

The limitations of this paper are those of a review joined to an audit. The review covers work
locatable in the indexed literature to August 2026 and may miss unpublished or
differently-indexed methods. The audit covers two datasets and its conclusions about missing
fields are conclusions about those releases, not about what the underlying trials collected. And
the argument establishes that the data does not support the fit, which is weaker than
establishing that no fit would help; a dataset carrying body weight, weighed meals and an
open-loop arm would reopen the question, and the DCLP3 sensor-augmented arm is closer to that
than anything else examined here.

## 6. Conclusions

Twenty-six of the sixty-two parameter columns in the S2008 model have any effect on simulated
glucose, eight of those are observed by a single scalar per subject after closure, and the
separation of endogenous production from utilisation requires tracers that no free-living
dataset contains. The only published identification of the model in real people needed inpatient
plasma glucose and plasma insulin, excluded two subsystems, and returned an insulin sensitivity
posterior indistinguishable from its prior. Four independent groups working from sensor and pump
data reduced the model to about eight parameters, and on that reduced model the honest posterior
is wide enough that a sampler's intervals cover the truth 23.25 per cent of the time at a
nominal 95 per cent. In the two datasets available here, body weight is absent from both and
carbohydrate is absent from one and self-reported in the other.

Fitting a virtual population subject by subject from these records would return the prior with
extra steps. The remaining question worth asking is whether a population can be made to match
the distribution of real outcomes without being fitted to real individuals, and that question
does not turn on identifiability at all.

## Sources and verification

Every citation was checked against PubMed E-utilities, Crossref or the paper's own full text,
and references [1] and [5] were read in full. This procedure was adopted because an earlier
review commissioned for this work returned several plausible references that could not be traced
to any record.

Two claims encountered during the review are recorded as unverified and are not relied on above.
The first is a report that the UVA/Padova model has been analysed with the nonlinear
observability rank condition and the Fisher information matrix; no source could be located. The
second is a preprint casting virtual sub-population selection as a linear program over 6,062
virtual subjects (arXiv:2409.00232); the preprint exists and no peer-reviewed version was found.

The audit figures for DCLP3 in section 4.1 were computed directly from the release files. The
Commons figures in section 4.2 come from `docs/measurements/commons_cohort.json` and
`docs/measurements/commons_requirement.json`. The parameter counts in section 2 come from
`timsim/population/derive.py` and from the parameter list read by `simglucose`'s patient class.

The package source read for those counts is commit c169447d481b42d69f271611c5ffa63f4508eb9b,
against simglucose 0.2.11. Nothing in this paper is measured by simulation, so no population or
settings fingerprint applies and none of its figures move with a rebuild.

## References

1. Visentin R, Dalla Man C, Cobelli C. One-Day Bayesian Cloning of Type 1 Diabetes Subjects:
   Toward a Single-Day UVA/Padova Type 1 Diabetes Simulator. IEEE Trans Biomed Eng
   2016;63(11):2416-2424. doi:10.1109/TBME.2016.2535241. PMID 26930671.
2. Cappon G, Vettoretti M, Sparacino G, Del Favero S, Facchinetti A. ReplayBG: A Digital Twin
   Based Methodology to Identify a Personalized Model From Type 1 Diabetes Data and Simulate
   Glucose Concentrations to Assess Alternative Therapies. IEEE Trans Biomed Eng
   2023;70(11):3227-3238. doi:10.1109/TBME.2023.3286856. PMID 37368794.
3. Colmegna P, Wang K, Garcia-Tirado J, Breton MD. Mapping data to virtual patients in type 1
   diabetes. Control Eng Pract 2020;103:104605. doi:10.1016/j.conengprac.2020.104605.
4. Siket M, Kovacs L, Eigner G. Hierarchical Bayesian modelling of glucose-insulin dynamics in
   type 1 diabetes. PLoS One 2026;21(2):e0341034. doi:10.1371/journal.pone.0341034.
   PMID 41650132.
5. Hoang T-D, Bissoto A, Naik VV, Flühmann T, Shlychkov A, Garcia-Tirado J, Koch LM.
   Simulation-based inference for personalised glucose models. Lecture Notes in Computer Science
   2025:35-46. doi:10.1007/978-3-032-07694-6_4. Preprint arXiv:2507.01740.
6. Hoyos JD, Villa-Tamayo MF, Builes-Montaño C, Ramírez-Rincón A, Godoy JL, García-Tirado J,
   Rivadeneira P. Identifiability of Control-Oriented Glucose-Insulin Linear Models: Review and
   Analysis. IEEE Access 2021;9:69173-69188. doi:10.1109/ACCESS.2021.3076405.
7. Erdős B, O'Donovan SD, Adriaens ME, et al. Leveraging continuous glucose monitoring for
   personalized modeling of insulin-regulated glucose metabolism. Sci Rep 2024;14:8037.
   doi:10.1038/s41598-024-58703-6. PMID 38580749.
8. Allen RJ, Rieger TR, Musante CJ. Efficient Generation and Selection of Virtual Populations in
   Quantitative Systems Pharmacology Models. CPT Pharmacometrics Syst Pharmacol
   2016;5(3):140-146. doi:10.1002/psp4.12063. PMID 27069777.
9. Rieger TR, Allen RJ, Bystricky L, et al. Improving the generation and selection of virtual
   populations in quantitative systems pharmacology models. Prog Biophys Mol Biol
   2018;139:15-22. doi:10.1016/j.pbiomolbio.2018.06.002. PMID 29902482.
10. Vettoretti M, Facchinetti A, Sparacino G, Cobelli C. Type-1 Diabetes Patient Decision
    Simulator for In Silico Testing Safety and Effectiveness of Insulin Treatment. IEEE Trans
    Biomed Eng 2018;65(6):1281-1290. doi:10.1109/TBME.2017.2746340.
