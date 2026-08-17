# Critical review, August 2026

A read-only review of the package conducted while the rebuild ran, so that a finding could not
change the code underneath a job in flight. Findings are numbered and carry the evidence that
established them. Severity is judged by what a finding does to a published figure, not by how
awkward it is to fix.

Nothing here is a style note. Where the code and its documentation disagree, the disagreement is
recorded against the documentation as well, since a claim that outruns the code is the failure
this package is most exposed to.

## R1. Settings are fitted and evaluated on the same 28 days (severe)

`examples/titrate_cohort.py` defaults to seed 11 and `titrate_subject` runs 28 days.
`bench_matrix.py`, `capability_table.py`, `two_benches.py`, `cohort_replicates.py`,
`fit_control_iq.py` and `production_during_a_low.py` all carry `DAYS, SEED = 28, 11`.

One generator supplies everything stochastic in a run, and `subject_seed(name, seed)` makes it a
deterministic function of the subject and the integer. A subject's meal schedule, sensor noise
realisation, infusion set failure times and day-to-day sensitivity sequence at seed 11 are
therefore identical between the titration run and the benchmark run.

Titration weakens a subject's settings until that subject's record clears the consensus
hypoglycaemia floors. What it clears them on is the seed 11 realisation. The benchmark then
scores the subject on the same realisation, so the settings were selected against the specific
lows the evaluation goes on to measure. That is in-sample evaluation of a fitted quantity.

The bias runs towards less hypoglycaemia than the settings would produce on a month they were
not fitted to, so the reported excess time below 54 mg/dL is if anything understated rather than
manufactured. The direction is favourable to the conclusions drawn so far and the magnitude is
unmeasured, which is the part that has to change.

A real person titrates on their own record and then goes on living, so the honest analogue is to
fit on one month and score on another. The correction is to titrate at one seed and benchmark at
a different one, which leaves the titration currently in progress valid and changes only the
evaluation.

## R2. Scripts disagree about which realisation they run

`layer_ladder_by_controller.py` and `oref_cohort.py` default to seed 0; the six scripts above use
seed 11. Figures from the ladder and from the autosens arms are therefore measured on a different
month from every figure in the bench matrix, for the same subjects under the same settings.

They are individually valid and they are not comparable with each other, which is not visible in
any output because the seed is not carried into the result files alongside the population
fingerprint and the settings digest.

Note that seed 0 is out of sample with respect to a titration run at seed 11, so the ladder and
the autosens arms do not carry R1.

## R3. Simulated and real variability are computed with different estimators (minor)

`therapy/titrate.py::consensus_report` computes CV with `np.std`, which is the population
estimator. `examples/bench_tables.py` computes the DCLP3 reference CV with `g.std(ddof=1)`.

Over 8,064 readings the two differ by a factor of 1.00006, so no published figure moves. It is
recorded because the comparison is between a simulated number and a real one, and the two sides
should not be reaching for different estimators of the same quantity.

## R4. The titration ladder does not return the weakest settings it claims to (moderate)

`titrate_subject` tries basal at 1.00, 0.95, 0.90, 0.85 and 0.80 with the correction factor
untouched. If none clears the floors it moves to the correction factor, and does so at
`floor = min(basal_scales)`, which is 0.80.

So a subject needing a small weakening of the correction factor receives it on top of the largest
basal reduction available, rather than on top of the smallest reduction that works with it. The
combination at basal 1.00 with a correction factor scale of 1.25 is never tried, and neither is
any intermediate basal.

The module docstring says settings are weakened "until its own record clears the consensus
hypoglycaemia floors, and no further, because settings looser than necessary cost time in range".
For the subjects reaching the second lever that is not what the procedure does. The behaviour is
a defensible modelling choice, since basal is the first thing a clinician moves, but it is not
the behaviour described, and the subjects it affects are the ones with the most hypoglycaemia.

## R5. The population fingerprint covers the parameters and not the questionnaire (moderate)

`population_fingerprint` digests `vpop_params.csv` alone. The generator also writes
`vpop_quest.csv`, carrying each subject's age and its starting therapy settings, which
`therapy/profile.py::for_subject` reads.

A regeneration that changed the questionnaire and not the parameters would leave the fingerprint
unchanged, and every guard built on it would pass while subject names resolved to different
settings and ages. Cohort matching is on age, so the cohorts would change composition without
any guard noticing.

This is the same class as issue 26 in ISSUES.md, where the fingerprint did not cover the
physiology either.

## R6. Switching a layer off changes the random month, not just the layer (severe)

`simulate` builds one generator, `rng = default_rng(subject_seed(name, seed))`, and every
stochastic component draws from it in sequence:

    set_meal_variability(rng, ...)      physiology only
    set_sensitivity(rng, days, ...)     physiology only
    draw_sessions(rng, ...)             activity only
    draw_meals(days, rng, ...)          always
    rng.integers(1, 1_000_000)          always, seeds the CGM noise model
    OnlineArtefacts(rng, ...)           sensor only
    InfusionSite(rng, ...)              site only
    Person(rng, ...)                    always

A component that draws only when its layer is on leaves the generator in a different state for
everything after it. Switching the physiology layer off therefore changes the meal schedule, the
sensor noise realisation, the infusion set failure times and the person's own draws. Switching
the sensor off changes the site failures and the person.

Measured directly on adult#001 at seed 11 over one day, meals as (minute, grams):

    all four layers    (459.0, 44)  (730.6, 60)  (961.2, 3)   (1149.6, 92)
    no physiology      (476.5, 66)  (743.9, 101) (976.3, 20)  (1246.6, 111)

The two arms eat different food at different times. This is the comparison `run.py` opens by
describing as one where "a difference between two runs is attributable to a named mechanism
rather than to the bundle", and for any arm involving the physiology or activity layers it is
not.

It affects the bare-against-layered comparison that `distance_to_real.py` reports, the ablation
table in `docs/FIDELITY.md`, and the layer ladder, which adds layers cumulatively so that each
rung perturbs every draw made after it.

The effect is on variance rather than on the expected value, since the realisation drawn is
independent of the layer being tested. Paired intervals computed from the observed differences
are therefore honest about the variance they contain, and the consequence is that layer effects
are harder to detect than they should be: a movement declared indistinguishable from zero may be
a real effect buried under a different month. The ladder's count of carried movements is a lower
bound rather than a measurement.

The correction is one generator per purpose, each keyed on the subject, the seed and the name of
the component, so that a component's stream does not depend on which other components ran.

## R7. The maximum basal ceiling can be exceeded by half an increment (minor)

`Enforcer.apply` clamps the requested rate to `max_basal_u_per_hour` and then quantises with
`_to_nearest`, which rounds up as readily as down. A ceiling of 2.03 U/h quantised to the nearest
0.05 returns 2.05.

`_round_down` carries a docstring explaining that boluses round down precisely so that a ceiling
holds exactly. The same reasoning applies to the basal ceiling and is not applied to it. The
overshoot is bounded by half an increment, 0.025 U/h.

## R8. Basal can be cut below the scheduled rate when the insulin-on-board ceiling binds (moderate)

When above-schedule basal would breach maximum insulin on board, `apply` recomputes

    basal = _round_down((scheduled + remaining / sample_minutes) * 60.0, increment) / 60.0

and rounds the result down. Where the scheduled rate does not itself sit on an increment
boundary, the rounding takes the delivered rate below the schedule. A scheduled 0.62 U/h with no
remaining headroom returns 0.60.

The class docstring states the principle the code departs from here: basal at or below schedule
"is the person's background requirement rather than something the algorithm added". Withholding
part of it is not what the ceiling is for, and the subjects affected are those under algorithms
that ride the insulin-on-board limit, which is oref0 SMB in particular.

## R9. The time axis is reconstructed rather than recorded (minor)

Readings are filtered with `keep = [i for i, c in enumerate(cgm) if c is not None and c > 0]` and
the clock is then rebuilt as `np.arange(len(cgm)) * step_minutes`. If any reading were ever
dropped, every later sample would be labelled with an earlier time than it occurred, and nothing
would indicate it.

No reading is dropped today: a `None` from the fault injector is replaced by the last seen value
before it reaches the list, and glucose is bounded well above zero. The filter is therefore inert
and the reconstruction is safe, which is why this is minor rather than severe. It is recorded
because the guard and the reconstruction contradict each other, and whichever is right the other
is wrong.

## What was changed

R6 is corrected in `simulation/run.py`. `stream(name, seed, purpose)` returns an independent
generator per component, keyed on the subject, the seed and the component's name, so a
component's draws no longer depend on which other components ran. Verified: dropping any of the
four layers leaves the meal schedule identical, three subjects at one seed still live three
different months, and the infusion site's drawn failure rate is unchanged when the sensor layer
toggles. Two regression tests in `tests/test_run.py` hold it.

R1 and R2 are corrected by `timsim/seeds.py`, which declares `TITRATION = 11` and `BENCH = 101`.
Every script that measures anything now takes `seeds.BENCH`, and titration takes
`seeds.TITRATION`, so settings are carried into a month they were not fitted against and no two
scripts disagree about which month that is by accident.

R7 and R8 are corrected in `therapy/limits.py`, each with a regression test: the basal ceiling
now holds when it does not sit on an increment boundary, and the insulin-on-board ceiling no
longer rounds delivery below the scheduled rate.

R4 is answered in the documentation rather than the code. Searching the full grid would triple
the cost of titration, and walking basal down before touching the correction factor is what a
clinician does. The module docstring now says the search is along a path rather than over the
grid, names the combination that is never tried, and states that the affected subjects end more
conservative than necessary, which understates their hypoglycaemia.

R3, R5 and R9 are recorded and not yet acted on. None of them moves a published figure.

## Still outstanding

The seed is recorded in `Result.meta`, in the bench matrix and now in the ablation payload, but
not in every result file, so two outputs can still be compared without their realisation being
visible. The provenance stamp is the natural place for it.

## R10. The defence gain was fitted partly on clamp failures (moderate, corrected)

`examples/calibrate_hypo_defence.py` read each subject's production at a nominal plateau and
discarded the glucose the clamp actually achieved, which `clamp` returns alongside it. The
clamp's controller can only add glucose, so the descent is set by the insulin infusion and a
sufficiently insulin-resistant subject never arrives: 31 of 150 do not come within 3 mg/dL of
the 55 mg/dL target, and one of the first eight adults settles at 62.8.

Production is `kp1 - kp2*Gp - kp3*Id`, so a subject held above the plateau reports a lower
figure than it would at the plateau and is likelier to floor at zero. Pooling them drags the
median down and inflates the zero count, and the median is what the gain is fitted on.

Corrected by excluding subject-plateau pairs the clamp missed and reporting how many were
excluded. The undefended median moves from 0.50 to 0.48 mg/kg/min and the chosen gain is
unchanged at 0.05, so the constant is robust to it. The zero-inflated tail is unchanged in
proportion, 41 of 110 against 53 of 150.

Two tests in `tests/test_hypo_defence.py` asserted that every subject on an eight-subject panel
held between 50 and 60 mg/dL, which the clamp cannot promise. They now exclude the subjects that
did not arrive, require most of the panel to arrive, and assert only the direction of the
result, since a median over eight subjects of a zero-inflated quantity is not stable enough to
carry a two-sided bound. That instability is the same one that produced the original 0.20.

# Second pass

A second review at the same depth, before any rerun, on the modules the first pass reached only
in part and on those it did not reach at all.

## R11. Two meals rounding to the same minute lost one of them (moderate, corrected)

`BehaviourScenario` built its schedule as `{int(round(h * 60)): (grams, is_snack)}`. Meals are
drawn on a continuous clock, so two can round to the same integer minute, and the dict
comprehension then kept only the later one. `Result.meal_log` was built from the drawn schedule
rather than from the scenario, so it went on reporting a meal that was never announced, never
bolused and never reached the gut.

Measured over 200 subjects at 28 days: 20,268 meals drawn, 3 subjects losing one meal each. Rare,
and silent, and it puts a phantom meal into any analysis that reads the log, which the meal
response measurement does.

Corrected by merging rather than dropping, since eating twice in one minute is eating once, and
by deriving the log from the same delivery schedule every arm uses. Grams are now conserved:
adult#027 draws 102 meals totalling 6,043 g and delivers them on 101 minutes totalling 6,043 g.

## R12. The glucose series ran one sample behind the event logs (moderate, corrected)

The run is primed with one step before the loop opens, so the model has already advanced by one
interval when the first sample is read. `Result.minutes` was built as `arange(n) * step`, which
places that first sample at minute zero, while `meal_log` and `rescue_log` carry the model's own
clock. Every sample was therefore labelled one interval earlier than the events that caused it.

Established rather than argued. `rescue_log` records the reading that triggered each decision, so
the reading can be located in the series: across ten rescues the decision was stamped exactly 5.0
minutes after the sample whose value triggered it, on every one.

The delivery path is unaffected, and that is worth stating because it looked like a second
defect. `person.observe` is called with the post-increment minute, which is the model clock, and
the scenario collects on the model clock too, so a rescue reaches the gut exactly the intended 4
to 16 minutes after the reading. The two offsets cancel. What did not cancel was the label on the
glucose series.

Consequence: any measurement locating an event in the series was one sample early, including the
meal response and the meal peak timing. One sample on a peak time near 200 minutes is small and
it is systematic and it is in the direction of reporting meals as peaking sooner than they do.

Corrected by numbering the series from `step_minutes` rather than zero, which is where the first
sample actually sits. Verified by the same rescue probe, now aligned to 0.0 minutes on every
rescue, and held by a regression test.

## R13. Total daily insulin is an assumption, and two things treat it as a measurement (moderate)

`population/generate.py` records `TDI` as the subject's basal requirement doubled, on the
conventional half-basal half-bolus split. It was undocumented at the point of definition.

Two things read it. `therapy/profile.py` sizes the maximum bolus and the maximum insulin on
board from it, so the delivery ceilings are a fixed multiple of basal. And
`population/cohort.py::matched_on_traits` matches cohorts to real people on age and log(TDI),
which is described in the paper as matching on age and daily insulin.

Because the simulated figure is a constant multiple of basal, that second matching dimension
carries no information the basal rate does not, while the real side of the match is a recorded
pump total that includes how much its owner actually bolused. The match is looser than the
description implies. Documented at the definition; the description is for the spec review to
correct.

## R14. The refusal to compare partial overlap is not on the path that produces the tables (moderate)

`analysis/cohort.py::paired_subjects` raises when no subject completes every arm, because a
comparison from partial overlap invents a population. `examples/bench_tables.py::paired`
reimplements the same rule and returns whatever it finds, including nothing, and that is the
function the published tables and the distance measurement are built on.

Guarded in `distance_to_real.py`, which refuses below ten paired subjects. `bench_tables.py`
still reports without a floor, which is defensible for a table that prints its own paired count
beside every row, and is recorded so the difference is a choice rather than an oversight.

## R15. The sensor layer exists twice, and the tests mostly exercise the copy that never runs (moderate)

`sensor/realism.py` carries two implementations. `OnlineArtefacts` is what `simulate` uses.
`add_sensor_noise`, `inject_compression_lows` and `apply` are a batch version, and nothing
outside `tests/test_sensor.py` imports any of them.

They are not the same mechanism. The batch version enforces a minimum gap between events and
hardcodes a depth threshold of 26.0 mg/dL where the online one takes `min_depth` as a
parameter, so the two place compression lows differently.

Most of the sensor suite therefore tests code no simulation runs, and a change to the live path
could pass it. Recorded rather than repaired, since deleting the batch path removes test
coverage and that is a decision about what the suite is for.

## Checked and clear

Two things that looked like defects and are not, recorded so they are not re-investigated.

The DCLP3 cache is ordered. 100 of 112 participants have timestamps that are not strictly
increasing, which matters because `signatures._lag_corr` and `_within_band_outcome_sd` use
`searchsorted`. Measured across 5,660,584 steps: 3,541 duplicate timestamps and no inversions
at all. `searchsorted` needs non-decreasing input, which holds, and the duplicates are 0.06 per
cent of readings.

The insulin ledgers are not a bottleneck. Neither `Enforcer.doses` nor `CorrectionLoop.boluses`
is ever pruned, and both are summed on every step, so an 8,064-step run sums a list that grows
to thousands of entries whose contribution is exactly zero beyond the duration of action.
Pruning them was implemented and measured: a 28-day run took 86.9 seconds before and 86.9
seconds after, because the ODE integration dominates. The change was reverted rather than kept,
since an optimisation that moves nothing is complexity without a result.

## Coverage of this pass

Reviewed at depth: `patient/varying.py`, `person/behaviour.py`, `controller/loop.py`,
`therapy/limits.py`, `therapy/profile.py`, `analysis/cohort.py`, `population/generate.py`,
`population/cohort.py`, `validation/dclp3.py`, `sensor/realism.py`, `simulation/run.py`.

Not yet reviewed at depth, and therefore not cleared: `validation/checks.py`, `boost.py`,
`replication.py`, `gate.py`, `oref.py`, `ranking.py`, `faults.py`; `controller/oref.py`,
`boost.py`, `boost_bridge.py`, `boost_autoconfig.py`, `autosens.py`, `inputs.py`,
`reference.py`; `person/activity.py`; the internals of `analysis/signatures.py`; and most of
`examples/`. The oref controller is the largest gap, since it drives three of the four cohort
pairings.

## R16. oref was told its carbohydrate was entered in 1970 (moderate, corrected)

`controller/oref.py` sent `meal_data.lastCarbTime` as `0`, the epoch, while `currentTime`
advances with the simulation. Traced through the shipped `determine-basal.js` rather than
inferred:

    lastCarbAge   = (systemTime - meal_data.lastCarbTime) / 60000        ~28,000,000 min
    remainingCATime = remainingCATimeMin + 1.5 * lastCarbAge / 60        ~700,000 h
    totalCI       = ci / 5 * 60 * remainingCATime / 2                    unbounded
    totalCA       = totalCI / csf                                        unbounded
    remainingCarbs = max(0, mealCOB - totalCA - ...)                     collapses to 0
    remainingCIpeak = remainingCarbs * csf * 5 / 60 / (remainingCATime/2) 0

So on every cycle where carbohydrate impact was being observed, the algorithm predicted no
further carbohydrate absorption at all, throughout every announced meal. That biases it towards
under-delivering, and oref0 SMB is one of the two algorithms the validation work compares.

Corrected by carrying the clock of the last carbohydrate the loop was told about.

The consequence was measured rather than asserted, three subjects over five days, paired, with
the old behaviour reproduced exactly by pinning the carb clock so the bridge sends zero again:

    subject        arm      U/5d   TIR%   >180%   <70%    mean
    adult#001      epoch   311.1   79.6    12.8   7.64   124.8
    adult#001      fixed   311.7   80.2    12.7   7.08   125.0
    adult#002      epoch   298.5   88.0     9.4   2.57   121.9
    adult#002      fixed   297.9   88.3     9.2   2.57   122.2
    adult#003      epoch   378.0   75.5    19.8   4.72   141.1
    adult#003      fixed   379.7   75.3    19.7   5.00   140.6

Insulin moves about 0.2 per cent and time in range under six tenths of a point, which is inside
what a single subject varies by between months. The input was wrong and the outcome barely
moved, because the suppressed prediction is one of several oref takes a minimum over and is
usually not the binding one. Both halves are worth stating: the bridge was misreporting its
inputs, and no published figure turns on it.

## R17. Two of oref's meal inputs are constants, and one of them is load-bearing (moderate)

`meal_data.slopeFromMaxDeviation` and `slopeFromMinDeviation` are sent as zero. oref computes
them from how its observed deviations moved over the previous hour and combines them as
`min(slopeFromMaxDeviation, -slopeFromMinDeviation / 3)`, then uses the result to decay
predicted carbohydrate impact along the unannounced-meal curve.

Zero means that curve never decays, so the unannounced-meal prediction is more persistent here
than in a real deployment. That is the exact path the meal announcement work exercises, so it
bears on the withdrawal result directly.

Not repaired: reconstructing them needs a record of predicted against observed deviation that
this bridge does not keep. Recorded in the module docstring beside the inputs that are absent
by choice, so it is not mistaken for one of them.

# Third pass

Over the modules the second pass listed as uncleared, plus the scripts that produce the paper's
central numbers.

## R3 is narrower than recorded

The first pass reported that simulated and real variability were computed with different
estimators. Checked properly: `bench_matrix.py` computes the simulated CV with `ddof=1` and
`bench_tables.py` computes the real one with `ddof=1`, so the published comparison is
consistent. `titrate.consensus_report` and the fidelity signatures use `ddof=0`, and each of
those is internally consistent across both sides of its own comparison. No single comparison
mixes the two, and the difference would be 0.006 per cent at 8,064 readings in any case. The
finding as first written was wider than the facts.

## R18. The signatures rebuilt their own clock (minor, corrected)

`analysis/signatures.py::from_result` built its time axis as `arange(n) * sample_time` rather
than reading `Result.minutes`, so it kept the numbering R12 corrected one level up. Only
`diurnal` reads the hour and five minutes is a twelfth of its bin, so nothing moves, but the two
clocks disagreeing is what R12 was about. It now takes the clock from the result.

## R19. oref's sensitivity detection was fed bolus activity alone (moderate, corrected)

`LoopInputs.activity_u_per_hour` differenced the bolus ledger only. oref derives its deviation
as `delta - (-activity * sens * step)`, so understating the insulin at work understates the fall
that insulin should have produced and charges the difference to the person's sensitivity
instead. Basal delivered away from the schedule is real insulin and was not counted, and under
oref0 SMB a temporary basal is running most of the time.

The call now asks for the full ledger, and Boost keeps the bolus-only reading, which is what it
logs. Measured over five days, two subjects: autosens median moves from 0.95 to 0.96 on one
subject, insulin by under a unit, time below 70 mg/dL by 0.14 points. Small, and the input was
wrong.

## R20. A published baseline was computed over the sealed half (moderate, corrected)

`examples/cohort_variation.py::real_reference` built the real spread and the split-half baseline
from all 112 DCLP3 closed-loop participants. Two things follow.

The held-out half is sealed behind the fingerprint in `dclp3.split` so a fitted Control-IQ
stand-in can be scored on data it never saw, and `hyperglycaemia_gap.py` says so explicitly
where it restricts. Computing a published baseline over all of them spends that.

And the units stop matching. `bench_tables.py` reports gaps in the calibration half's spread.
Measured across both populations the p10 to p90 spreads differ by up to 7 per cent and the
median time below 54 mg/dL differs by a quarter, 0.20 against 0.16, which is the measure the
hypoglycaemia finding rests on. A group effect of 0.72 spreads and a gap of 0.72 spreads were
not the same quantity.

Restricted to the calibration half, which is what every other consumer already does.

## R21. A CLOSE-IT cohort would have been scored against DCLP3 people (moderate, corrected)

The same function matched `cohort in ("dclp3", "close_it")` and returned DCLP3 participants for
both. CLOSE-IT publishes summaries rather than participants, so it supports no per-person spread
at all. Nothing called it with `close_it` today, so no figure is affected. It now returns
nothing, which is what `bench_tables.py` already assumed.

## R22. Cohorts are matched on all 112 and fitted against 67 (documented)

`build_cohorts.dclp3_traits` matches cohorts to the traits of every closed-loop participant,
while `fit_control_iq.py` matches to the calibration half. Left as it is and documented, because
the seal protects outcomes rather than demographics: nothing in `build_cohorts` is fitted, and
estimating the trait distribution from twice as many people is the better estimate. The two
halves are a stratified random split, so the choice moves the cohorts by nothing measurable.

## What remains unreviewed

Three passes have not covered everything, and the honest list is short enough to state.
`validation/checks.py`, `boost.py`, `replication.py`, `gate.py`, `ranking.py` and `faults.py`
are the validation harness rather than sources of published figures.
`controller/boost.py`, `boost_bridge.py` and `boost_autoconfig.py` drive an algorithm that is no
longer in the papers. `person/activity.py` is a layer that is off by default and has never been
in the default stack. Those are the grounds for stopping, and they are grounds about relevance
rather than evidence that the code is right.

# Fourth pass

Over everything the third pass left, on the principle that grounds about relevance are not
evidence of correctness. 17,520 lines across 100 files.

## R23. A fifth of real temporary basals were being discarded (severe, corrected)

`examples/real_meals.py::temp_basals` kept only records carrying an `absolute` rate and dropped
the rest, so those periods were scored as if the pump had run its schedule. Measured across 31
Commons users and 2,047,711 temporary basal records: 82.1 per cent carry an absolute rate, 12.3
per cent carry only a percentage, and 5.6 per cent carry neither.

The commonest dropped value is a full suspend, so withheld insulin was being counted as
delivered. The percentage is a change relative to the schedule rather than a fraction of it,
which the data settles rather than the specification: values run from -100 to +400 in steps of
ten, symmetric about zero, with -100 the single commonest, and a fraction cannot be negative.

Two published things read this. The meal filters in `docs/PADOVA_LIMITS.md` include one defined
as "the loop within 0.5 U of schedule over 4 h", which cannot mean what it says while a fifth of
the loop's actions are invisible. And `examples/commons_requirement.py` reconstructs the daily
insulin requirement that `matched_on_traits` matches the Commons cohort on.

Rerun after the fix, the requirement moves materially:

    measure                       before     after    change
    basal_per_day                  17.63     16.10     -1.53
    scheduled_basal_per_day        17.77     17.77     +0.00
    bolus_per_day                  21.23     21.71     +0.48
    tdd                            38.39     38.20     -0.19
    basal_share                     0.50      0.45     -0.05
    users qualifying                  71        77         6

Six more users qualify, because the filter admits users with temporary basals in the window and
theirs had all been invisible. The Commons cohort was therefore matched to a basal requirement
8.7 per cent too high, drawn from a slightly different set of users.

Worth setting beside R13: the generated population assumes total daily insulin is basal doubled,
a basal share of 0.50, where these real users measure 0.45.

## R24. The built-in loop's meal correction ignored insulin on board (moderate, corrected)

`_BasalBolus.act` computed a meal bolus as `grams / cr + (cgm > 150) * (cgm - target) / cf`,
with no subtraction of insulin already acting and no cap. `controller/reference.py` documents
the same defect and its repair; this one survived.

It matters because this is the driver titration runs under. A baseline that stacks insulin
provokes hypoglycaemia, and the procedure answers hypoglycaemia by weakening the settings that
are then handed to the algorithms being benchmarked.

The pump ceiling was catching it rather than the arithmetic: over ten days the insulin-on-board
limit bound 13, 15 and 15 times on three subjects, about half a per cent of steps, with peak
insulin on board sitting exactly at the ceiling for every one. After subtracting insulin on
board from the correction, bindings fall to 12, 14 and 5.

## R25. Two more Boost inputs were constants nothing supplied (moderate, corrected)

`METHODS.md` records three inputs read off the cycle with `getattr(cycle, name, default)` where
none of the names was a field, so every run sent the default. Two more survived that repair:
`asleep` defaulted to False and `fast_carb_confirm_enabled` to True, and neither is a field on
any cycle. The jar reads both, at positions 24 and 25 of its own `FIELDS`.

So the algorithm was told the person is never asleep, on a bench whose infusion-site model turns
on exactly that distinction, and fast-carb confirmation was pinned on whatever
`boost_autoconfig.py` had decided for the subject.

Sleep now comes from `therapy/site.py::_asleep`, the same window the person uses, which puts the
night at 23:00 to 07:00. The confirmation flag arrives through the constructor, as the three
knobs already did after the same defect was found in them. `V5Config` does not carry it, so
reading it from there would have raised on the first cycle.

## R26. My own clock correction broke two consumers (moderate, corrected)

R12 renumbered the glucose series so sample `i` sits at minute `(i + 1) * step`. Two places
located events by array position on the old convention and were left a sample out.

`examples/meal_response.py` indexed the meal as `int(MEAL_HOUR * 60 / step)` and now searches
the run's own clock, so the window start and the reported time to peak no longer depend on where
the series is numbered from. `examples/hyperglycaemia_gap.py` binned readings by hour from
`arange(len(g)) * sample_time`, which put every reading one step early, in a comparison against
the trial's hour-by-hour profile whose deepest gap sits between midnight and 04:00.

Audited the rest: no other script derives a time or an hour from a sample index.

## Checked and clear

`population/derive.py`, the steady-state closure every generated subject rests on, matches all
thirty published subjects and is guarded by a test. `validation/compare.py` refuses mismatched
signals and sample intervals and records the exposure. `validation/ranking.py` carries its own
account of a statistical error it has already corrected, with the arithmetic. `controller/
reference.py` reconciles what the pump delivered against what it asked for. `person/activity.py`
is off by default and self-consistent. `therapy/insulin.py` returns exactly zero beyond the
duration of action, which is what makes the unpruned ledgers harmless.

`validation/oref.py` is reachable from nothing: no module imports it and no document cites it.

# Fifth and sixth passes: units, and statistics

Different lenses rather than a re-read: every unit conversion on the delivery path, then every
statistic that reaches a paper.

## R27. Withheld basal never gave its headroom back (severe, corrected)

`Enforcer` claimed to count insulin on board "the way the open-source systems count it" and did
not: its ledger held only bolus insulin and basal above schedule, so it could never go negative,
where AndroidAPS reports negative insulin on board through a suspension. An algorithm that had
been withholding, correctly saw its own figure go negative and asked for a catch-up temporary
basal was cut back by a ceiling computed from a figure that never fell.

Measured under oref0 SMB over five days: the ceiling bound on 15.6 per cent of steps on one
subject and 12.8 on another. With deviations counted in both directions the binds fall towards
the algorithm legitimately riding a ceiling it shares with the pump, and the outcomes move:
adult#001 takes 3 per cent more insulin and its time below 54 mg/dL rises from 0.20 to 2.92 per
cent on untitrated settings. The difference was the bench's, not the algorithm's. Held by a
regression test in which an hour's suspension buys back a catch-up basal untouched.

Related and recorded: oref and Boost keep requested boluses in their ledgers where the reference
controller reconciles against delivery. Measured under oref, the enforcer clamped zero boluses
in ten subject-days, so the ledgers agree in practice; basal, the side that was wrong, is
reconciled by both bridges.

## R28. The shard stamp recorded neither the shard index nor the count (moderate, corrected)

In `bench_matrix.py` the progress loop rebound `i` to the completed-row count and the pairing
print rebound `n` to the last cohort's size, and the shard stamp was written from both after the
fact. `merge_shards.py` reads that stamp to check it holds every shard exactly once, so a
two-machine run would have been unmergeable or, worse, merged on garbage bookkeeping. The
single-machine default never exercised it.

## R29. The reproducibility comparison set a range against a split-half (moderate, corrected)

The bench's group variation was summarised as the range of the replicate medians over three or
four disjoint cohorts, and the trial's as the 95th percentile of a split-half gap. Those are
different statistics with different expectations, near 1.7 sigma for a range of three against
2.8 for a split-half 95th percentile, and the group sizes differed as well, 90 against halves
of 67. Both mismatches run the same way and flatter the bench, and the draft claim that the
bench was more reproducible than the trial rested partly on them. `cohort_replicates.py` now
computes the same split-half statistic on each replicate's own runs and prints the group sizes
beside it.

## R30. The fixed panels ran on settings no person carries (moderate, corrected)

The capability table, the layer ablation, the ladder, the hyperglycaemia gap and the production
measurement all ran their subjects on physiological settings, because `simulate` falls back to
`for_subject` when no profile is passed and nothing passed one. The package's own doctrine is
that an untitrated benchmark measures the settings as much as anything, and three of the ten
capability signatures read hypoglycaemia behaviour directly.

`simulate_cohort` now takes a `profile_factory`, the panels pass `titrate.profile_for`, the
bridge controllers receive the same profile so the matching guard holds, and the rebuild
titrates the panel subjects explicitly. The gap script's settings arms, which weakened the
correction factor through an `isf_scale` argument an explicit profile silences, now scale the
titrated profile instead; without that they would silently have become copies of their partner
arms. `configuration_arbiter.py` keeps its own untitrated design, which is internally
consistent and predates titration, and is recorded here rather than changed.

## Checked and clear, fifth and sixth passes

The delivery unit conversions are consistent end to end: U/min at the pump boundary, U per step
inside the enforcer and the site, U/h at the oref boundary, with the conversions at the edges
and nowhere else. `fit_control_iq` fits on the calibration half and reports against the held
out half with no leak; its held-out rerun is the same deterministic simulation scored against
the other reference, which is wasteful and harmless. The bootstrap machinery seeds every
signature's interval separately and identically on both sides of each comparison.

# Seventh and eighth passes: state, and the tests themselves

## R31. A reused controller began with the previous run's insulin (severe, corrected)

`simulate` never cleared controller state. Two runs of one subject at one seed came out
different, with 169 doses carried across, and `simulate_cohort` given a plain `controller=`
object shares one instance across every subject at the default worker count, so each subject
inherited the last one's ledger. The parallel path was accidentally safe, because each job
pickles its own copy.

`simulate` now calls `reset` before every run. Two things had to be got right. simglucose's base
`Controller` declares `reset` and raises `NotImplementedError` from it, so `hasattr` is true for
every subclass and testing that way brought down every custom-controller test. And the built-in
`_BasalBolus` had no `reset` at all while holding a bolus ledger and a week of adaptive ratio
history, so it was given one and its constructor now calls it.

## R32. Resetting the reference controller left an index into the list it had just emptied

`ReferenceAID.reset` cleared `doses` and left `_pending` pointing into it. A run ending on a step
that gave a bolus leaves one set, so reuse raised `IndexError` on the next run's first cycle
rather than on the last one's. Found by calling `reset` for the first time; it had never run in
anger.

## The tests were mutation-tested rather than trusted

Every regression test written during this review was checked by reverting the fix it guards and
confirming it fails. All five kill their mutant: the per-component streams, the clock, the
controller reset, the negative insulin-on-board ledger, and the basal ceiling at a
non-increment boundary.

The first attempt at the seeding mutation passed, which was the useful part. Reverting only the
meal stream does not reproduce a defect that required every component to share one generator, so
the mutation was unfaithful rather than the test weak. A mutation that reverts all seven streams
kills it. A mutation test is only worth what the mutation is.

An audit for tests that cannot fail found one: `test_closing_twice_is_harmless` asserts nothing
and passes if `close` is a no-op, though its subject is idempotence and "does not raise" is the
claim. Three `pytest.raises` blocks carry no `match`, and all three pin a custom exception type,
which is the assertion. The remaining seventeen pin the message.

# Ninth pass: adversarial

Running the guards against inputs built to slip past them, rather than reading them.

## R33. The titration store was trusted for values that reach a body (severe, corrected)

`profile_for` read `scale` and `basal_scale` and multiplied a correction factor and a basal
rate by them without checking either. Probed against a store with each field corrupted:

    scale is negative        ACCEPTED, correction factor -28.5 mg/dL per unit
    scale is zero            ACCEPTED, correction factor 0, so an infinite correction
    scale is nan             ACCEPTED
    basal_scale is negative  ACCEPTED, negative basal

A negative correction factor is the dangerous one, because an algorithm dosing against it
corrects in the wrong direction on every cycle while every number in the output stays finite and
plausible. The procedure itself only writes values from `SCALES` and `BASAL_SCALES`, so a bad
one means the store was edited, merged or partly written; the check is here because of what the
values do, not because they are expected.

A second defect surfaced under the same probe. `rec.get("basal_scale", 1.0) or 1.0` treats a
stored zero as missing, so a subject recorded as receiving no basal ran at its full rate. Only
a missing or null entry means unscaled now.

`save` also wrote in place. A titration takes hours and a process dying partway left a truncated
file, which `load` refuses, correctly, losing all of it. It writes to a temporary file and
renames, which is atomic on one filesystem.

## R34. Two shards with different titrated settings would have merged (moderate, corrected)

`BINDING` was `("population", "commit", "dirty")`, so `check_compatible` accepted stamps
differing in the titrated settings digest and in the simglucose version. Both are inputs.

Settings are generated locally and never committed, so two machines can sit at the same commit
with the same population and different settings: titration takes a subject list, and a run over
a different subset writes a different store. Every subject's correction factor and basal rate
come from it. `docs/REMOTE_WORKER.md` tells the second machine to copy the store across, and
nothing enforced that it had. simglucose is the patient model, pinned in the lock file, and two
results from different versions are two models.

Both are binding now, with `python`, `host` and `when` left as context, which is what sharding
across machines requires.

## What the probes found nothing wrong with

The population fingerprint guard refuses a missing fingerprint, a wrong one, and a subject
marked as not titrated, and refuses a subject absent from the store rather than falling back.
The distance measurement refuses a comparison built from too few paired survivors, checked by
thinning a real matrix until three subjects completed both arms. The bridged controllers close
their node processes on `close`, on garbage collection without it, and on a run that raises
midway. Parameters passed into `simulate` are copied, so a caller's object is not mutated and
two runs from one object agree to the bit.
