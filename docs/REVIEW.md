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
