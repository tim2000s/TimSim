# The studies

They live in the Research-Papers repository, under `TimSim/`, alongside the Boost series. The
two programmes are kept together because their limitations are opposite: Boost works from the
records of real people and cannot produce a counterfactual, and this one can produce a
counterfactual and cannot guarantee its people resemble real ones.

The series was withdrawn in August 2026 and has been rebuilt. Sixteen of the seventeen studies
are written and built to PDF, and an eighteenth was added on 6 September 2026. Study 10 is
withdrawn permanently, since the rebuilt clamp inverted its premise, and study 01 is blocked on
field records that live in the Boost repositories. `Research-Papers/TimSim/REBUILD_STATUS.md` is
the authority on where each one stands, checked by opening each measurement file rather than by
reading what a study says it used, and this table should be read against it rather than instead
of it. The hepatic defence gain was refitted from 0.20 to 0.05 on the clamp reproduced across the
generated adults, and it enters every simulated minute, so no figure measured under the old value
can be quoted beside one measured under the new. `examples/rebuild_all.sh` produces the
replacement set, retitrating the population first because titrated settings are an output of the
physiology as well as of the population. Issue 25 in [ISSUES.md](../ISSUES.md) records what moved
and why, and issues 44 to 52 record the week to 4 September that reversed three claims in studies
07, 15 and 17, each brought up to the measurements on 6 September.

## What each study answers, and what supplies its figures

| # | Study | Question | Measurement |
|---|---|---|---|
| 00 | The simulator | What is this and what can it answer? | framing only |
| 01 | Driving shipped algorithms | Can the real code run instead of a port? | `bench_matrix.json`; blocked on Boost field records |
| 02 | The layer ladder under four drivers | Which layers change the person rather than the run? | `layer_ladder.json` |
| 03 | A statistic that could not see | Does the drift signature measure the person? | `layer_ablation.json`, `drift_ablation.json` |
| 04 | Sensitivity detection | Does missing autosens explain oref0's hypoglycaemia? | `oref_autosens_{on,off}.json`, `target_ablation.json` |
| 05 | Where a low comes from | Why rebound more often than real people? | `real_rescues.json`, `hypoglycaemia_arms.json` |
| 06 | Four mechanisms for realism | Can absorption, activity or slow sensitivity close the gaps? | `mechanism_regression.json` |
| 07 | Meal peak timing | Is the meal peak late, and where does the covered rise gap sit? | `sim_meal_shape_*.json`, `real_meal_shape.json`, `insulin_by_peak.json`, `insulin_profile_rise.json`, `meal_yield_ranking.json` |
| 08 | No floor under a falling glucose | Why do runs fail to complete? | `extreme_tail.json`, terminations |
| 09 | Capability | What can this be used for? | `capability` log |
| 10 | Counterregulation | Withdrawn: the rebuilt clamp inverted its premise | `hypo_defence_gain.json`, `clamp.json` |
| 11 | Two benches | How much does the bench itself decide? | `two_benches.json` |
| 12 | Titration | What do settings measured from physiology cost? | `titration_reference.json` |
| 13 | Configuration | How far does configuration move a benchmark? | `bench_matrix.json` |
| 14 | The validation paper | Do the layers move the bare model towards a real cohort? | see below |
| 15 | What S2008 misses | Where does the model depart from people? | [PADOVA_AUDIT.md](../PADOVA_AUDIT.md), `low_recovery.json`, `spread_ratio.json` |
| 16 | The simulator does not eat | The popular piece on the bench and its reference | the studies above |
| 17 | What the gap is not | Which explanations for the gap survive pre-registration? | `spread_ratio.json`, `sim_meal_shape_*.json`, `carb_bias.json`, `insulin_requirement.json` |
| 18 | Technical shortcomings of the model | What is every measured departure of S2008 from people, and what does each cost? | [PADOVA_AUDIT.md](../PADOVA_AUDIT.md), `hypo_defence_gain.json`, `low_recovery.json`, `spread_ratio.json` |

Study 16 in the original plan was the counterregulation and exercise design, which now lives in
[DESIGN_COUNTERREGULATION_AND_EXERCISE.md](../DESIGN_COUNTERREGULATION_AND_EXERCISE.md) and is
supplied by `glucagon_calibration.json`, `exercise_calibration.json` and `exercise_arm.json`.

Four results are papers rather than studies, because each carries a claim against real
populations or against the published literature rather than a property of the package.

[The validation paper](../paper/validation_paper.md) asks whether the layers move the bare model
towards a real closed-loop cohort, measured against DCLP3 and the OpenAPS Data Commons in units
of the spread between real people. `distance_to_real.json` and `cohort_variation.json` supply it,
with `hypo_defence_gain.json`, `low_recovery.json` and `insulin_requirement.json` for the
counterregulation, untreated recovery and insulin requirement sections added in September 2026.

The meal behaviour paper asks what the model does with carbohydrate, and what withdrawing meal
announcement is worth under two algorithms, against real uncovered meals from the Commons and
against the CLOSE-IT trial. `meal_response.json`, `real_meals.json` and the announcement arms of
`bench_matrix.json` supply it. Study 07, on meal peak timing, is folded into it: the finding that
the peak arrives inside the real range once the two clocks are started at the same event belongs
with the rest of the meal work rather than on its own.

[The identifiability paper](../paper/identifiability_paper.md) asks whether the population could
be fitted to real people instead of resampled from thirty published ones, and answers that
neither dataset supports it. It joins a review of every published identification of UVA/Padova
and of comparable models to an audit of what the S2008 implementation leaves free and of what
DCLP3 and the Commons contain. Nothing in it is measured by simulation, so none of its figures
move with a rebuild.

[The spread paper](../paper/spread_paper.md) asks why virtual populations carry less variation
between subjects than real cohorts do, and tests the covariance shrinkage that has been blamed
for it. The charge is refuted:
[covariance_estimator.json](../measurements/covariance_estimator.json) supplies that half, and
`examples/covariance_estimator.py` is parameter arithmetic that runs beside a rebuild. Its
figures describing this package's own population come from [FIDELITY.md](../FIDELITY.md) and move
with one.

[DESIGN_COUNTERREGULATION_AND_EXERCISE.md](../DESIGN_COUNTERREGULATION_AND_EXERCISE.md) holds
the counterregulation and exercise design in full: what each mechanism had to do to survive, fixed before either was built, and
what happened. The glucagon gate is refuted on magnitude and is imported by nothing. The exercise
layer is calibrated, reverses the finding that kept it switched off, and is adopted as a
switchable arm rather than a default because it worsens the measure the package is already worst
on and cannot represent exercise type.

The reference documents stay here, because they describe the code rather than the work:
[MODEL.md](../MODEL.md) for UVA/Padova itself, [SIMULATOR.md](../SIMULATOR.md) for what this
package puts on top, and [FIDELITY.md](../FIDELITY.md) and [LADDER.md](../LADDER.md) for the
measurements the studies produced.
