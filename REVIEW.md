# REVIEW.md

The checks a change to this repository is reviewed against before it is committed. Each item is
written so that a reviewer can test a diff against it and name the item a finding breaks. Findings
are labelled important (fix before commit), nit (optional) or pre-existing (present before this
change; record it, do not block on it).

The tiers, and the checks each tier requires, are set in the global instructions and adapted here
to a simulator. Two records sit behind this file. `docs/ISSUES.md` is the incident log, numbered 1
to 54 at the time of writing, and `docs/REVIEW.md` holds the findings of the August 2026 critical
review, numbered R1 to R34. The table at the end maps each entry to what now catches it.

## Tiers in this repository

Nothing here doses a person, so the tiers are set by what a change can do to a result. The
measurements feed papers, and the Boost initial-settings trial drives
`timsim/controller/boost_engine.py` to choose settings that real users will start on, so a defect
that moves a simulated dose or a simulated body is treated as the dose path is treated elsewhere.
The log supports that ordering: the defects that moved published figures furthest (issues 25, 43
and 54, R6, R27 and R31) were all in the code below.

High: the simulated body and the doses reaching it. `timsim/patient/**`, `timsim/person/**`,
`timsim/sensor/**`, `timsim/simulation/run.py`, `timsim/therapy/**` (delivery limits, the
insulin curves, profiles, titration, the infusion site), `timsim/controller/**` and `bridge/**`
(the oref0 and Boost adapters and the code vendored or run behind them), `timsim/population/**`,
`timsim/seeds.py` and `timsim/provenance.py`. Cohort and panel selection
(`population/cohort.py`, `examples/panel.py`) and parallel orchestration (`simulate_cohort`,
`examples/rebuild_all.sh`, `examples/standalone_parallel.sh`, `merge_shards.py`, any producer that
runs a pool) are high as well, since issues 28, 30, 31 and 34 show them producing complete,
plausible output from the wrong runs. Before commit: `pytest -q` in full (about eighteen minutes),
including the guard tests named below; the checklist; for a change in behaviour, a paired
before-and-after measurement on a fixed panel by a committed producer, as `examples/issue54_effect.py`
does; and a fresh-context review of the diff. Before results from it are used: every result
carries a provenance stamp that binds, and the way back is the previous commit together with the
archived measurements under `docs/measurements/archive_*` or a pinned baseline.

The nine files listed in `therapy/titrate.py::_CODE` form a subset that needs one more step: any
edit to them invalidates every titrated settings store on disk, so it is followed by retitration
or by the inertness proof in item 2.

Medium: `timsim/analysis/**`, `timsim/validation/**` (the graded checks and the safety gate), and
the producers in `examples/` that read real records (`real_meal_shape.py`, `real_meals.py`, the
Commons and DCLP3 readers). These build the comparisons rather than the runs, and issues 5, 6, 11,
43, 52 and R23 were here. Unit tests, the checklist and the analysis items below.

Low: `docs/`, the papers, figures, the README and tooling. The analysis checklist in the global
instructions and items 19 to 28 below.

## Simulated body and dosing

1. A change to a physiology constant, the meal template or the delivery limits is followed by
   retitration, never by reuse of the store, because titrated settings are an output of the
   physiology (issue 26). `examples/rebuild_all.sh` deletes the store for this reason, and every
   measurement taken under the old value is rebuilt rather than patched (issue 25).
2. An edit to any file in `titrate._CODE` that is claimed to change nothing is proved inert with
   `examples/restamp_settings.py --against REF` (syntax tree, docstrings stripped) or
   `--worktree REF`, never by stashing. The tool must refuse when no fingerprinted file differs
   (issue 47). The settings digest is over the settings, not the file, so recording a check does
   not change the store's identity (issue 40). Guards: `test_a_store_from_different_code_is_refused`,
   `test_a_store_without_a_code_fingerprint_is_refused`.
3. A new stochastic component draws from its own `stream(name, seed, purpose)` and never from a
   generator shared with another component, so switching a layer off changes the layer and not
   the month (R6). Guards: `test_ablating_a_layer_changes_the_layer_and_not_the_month`,
   `test_the_meal_stream_does_not_move_when_a_component_is_added`.
4. Seeds come from `timsim/seeds.py`: settings are titrated at `TITRATION`, everything reported is
   measured at `BENCH`, and `AA` is never reported on its own. A literal seed in a producer is a
   finding (R1, R2). Population seeds derive from SHA-256, never from `hash()`, which Python salts
   per process (issue 8).
5. An argument to `simulate` that applies only inside a layer is either refused when that layer is
   off or exercised by a producer that shows the output moving with it (issue 41). This is
   pre-existing for `meal_absorption_scale`, which is still accepted silently without the
   physiology layer.
6. A controller holding a ledger or history implements `reset`, and `reset` leaves no index into
   anything it cleared (R31, R32). Guards: `test_a_reused_controller_does_not_carry_state_between_runs`,
   `test_resetting_a_controller_clears_the_index_into_its_own_dose_list`.
7. Delivery passes through `therapy/limits.py`; basal and bolus are quantised to the nearest
   increment, ceilings hold at non-increment boundaries, scheduled basal is never withheld, and
   withheld basal counts negatively (R7, R8, R27). A check on a ceiling asserts that the ceiling
   held, not that the clamp fired (issue 33). Guards: the ceiling and insulin-on-board tests in
   `tests/test_therapy.py`.
8. Every input an adapter sends to an algorithm is traced to simulation state. A constant, an
   epoch, or a `getattr` default standing in for a field the algorithm reads is a finding, and the
   trace is done through the vendored or bridged code rather than inferred (R16, R17, R19, R25).
   Field order is agreed with the jar (`test_the_field_order_is_agreed_with_the_jar_rather_than_assumed`).
9. Insulin on board handed to an AndroidAPS-standing adapter uses `oref_iob_fraction` and a ledger
   cut at the duration of action, with no margin; the reference loop, enforcer and body keep the
   package curve (issue 54). The controller's duration of action and limits match the rig's,
   which `simulate` enforces. Guards: `test_a_dose_over_an_hour_old_still_counts_after_a_cycle`,
   `test_the_adapters_compute_insulin_on_board_with_oref0s_curve`.
10. A non-finite dose, rate or duration from a bridged engine raises rather than reading as no
    dose (`boost_engine.py`, e7ad82c).
11. The harness steps every five minutes on `GuardianRT`. A change to the interval or the sensor
    reruns `examples/layer_ablation.py`. Event times are read from `Result.minutes` and the event
    logs, never rebuilt from an array index (R12, R18, R26).
12. `tests/test_population.py::test_closure_reproduces_every_published_subject` passes; a failure
    there invalidates every generated subject.

## Parallel runs and orchestration

13. Everything a worker needs travels in its job tuple. A module global set in `main` and read by
    a worker is a finding, because macOS spawns and the worker re-imports the module with its
    defaults (issue 30). Each row returns the configuration it ran under, and the producer refuses
    to write when rows disagree with the request.
14. A script that starts a pool does so under `if __name__ == "__main__":`, and its worker
    function is defined at module level so it can be pickled. A controller holding a live
    resource (`OrefController`'s node subprocess, `BoostController`'s JVM) crosses only as an
    importable factory; `_parallelisable` falls back to serial with a warning, which is read rather
    than ignored. Pools are sized at seven workers on this machine unless a run states otherwise
    (`rebuild_all.sh` defaults to twelve; pre-existing).
15. A producer refuses to write when too few runs completed, and separates runs that raised from
    runs that stopped short. A summary built with `nanmedian` over an empty set is a finding
    (issue 31).
16. Reuse of a file already on disk binds its provenance stamp; existence alone never qualifies a
    result for reuse (issue 28). A new output location is added by name to the archive step in
    `rebuild_all.sh` and to `tests/test_provenance_coverage.py` (issue 32).
17. A plan-only or dry-run mode writes to its own path. A change to a producer's interface or
    output path is followed by a search for every caller, shell scripts included (issue 34).
18. Shell argument lists are arrays or `${=VAR}` under zsh, which does not word-split (issue 21).
    Scripts set `PYTHONPATH` or take the repository root from their own location (issue 19).
    Nothing outside `docs/` is edited or committed while a producer is running, because
    `provenance.stamp` reads the commit and the dirty flag when the result is written, not when
    the run started.

## Measurements and comparisons

19. Every measurement file carries `provenance.stamp()`, and anything combining results calls
    `provenance.check_compatible`. A name added to `PENDING_REBUILD` has had its producer read
    (issues 27, 29, 37). An archive or pinned baseline is checked for agreeing stamps before it is
    written (issue 39). Guard: `tests/test_provenance_coverage.py`.
20. An index over runs keys on every field the bench varies (controller, arm, cohort, scenario),
    and a report prints what it indexed rather than what the file header says it ran (issue 43).
21. A comparison across conditions holds the panel fixed: the same subject list on both sides,
    intersected rather than taken per condition, and degenerate cases dropped and counted on that
    common panel. Panels are drawn with `examples/panel.py` from titrated subjects, not by name
    (issues 44, 45, 50; f5b56f2).
22. A comparison against real people is like for like in every respect: `cgm` against a sensor
    (`validation/compare.py` refuses `bg`), the same unit (a person's typical meal, not one meal),
    the same record (`announced_log` against entries), the same clock and definition, the same age
    floor, a controller running on both sides, and the DCLP3 calibration half only
    (issues 46, 49, 51, 52; R20, R21).
23. A statistic used to decide a mechanism is first shown to move when the mechanism is switched
    off, and is paired per subject (issue 45). A gap is reported as distinguishable only when the
    real median falls outside the simulated cohort's 95 per cent interval (issue 16). A median of a
    zero-inflated quantity is quoted with its n and its zero count (issues 14, 15, 25).
24. Every figure in prose, a docstring or a comment has a committed producer whose output exists on
    disk, and the prose is reread against that file after any rebuild. `docs/SPEC_VS_OUTPUT.md` is
    read before quoting from `docs/` (issues 1, 35, 36, 41, 42, 53).
25. A reproduction of a published protocol states the meal, the window and the denominator, and
    checks the reference against something it must satisfy (issue 48).
26. A reader of real records is validated against a reference parser on a complete file, widens
    its globs to every naming form, keeps percentage-only temporary basals, and requires treatment
    records in a selected window (issues 5, 6, 11; R23).
27. A check that compares two arms states what made them differ and refuses when nothing did. Two
    arms agreeing to every decimal, or a stage finishing far faster than its history, is a fault
    until it is shown whether the option failed to reach the run or reached it and does not apply
    (issues 28, 30, 31, 38, 47).
28. A new regression test is run against the broken implementation and shown to fail, as the
    review did for its own (`docs/REVIEW.md`, seventh and eighth passes). Tests drafted by the
    local model get the same treatment, and the commit says where the code came from.

## Repository

29. Files are staged by explicit path. The population, the settings store and anything derived
    from the published parameter tables are not committed (issue 9 for the backup rule).
30. No cohort or participant identifiers, tokens or site hosts appear in code, results or commit
    messages; the developer's own name may.

## Incident record and what catches each

| Incident (`docs/ISSUES.md`, `docs/REVIEW.md`) | Caught by |
|---|---|
| 1. Measurements outside the repository, one source lost | Item 24; global rule on where work lives |
| 2. DCLP3 correction factor never measured | Item 24 |
| 3. Carbohydrate ratio described as agreeing | Item 24 |
| 4. Commons user count matched no set of users | Item 24 |
| 5. Fast parser dropped 3.5 per cent of readings | Item 26 |
| 6. Carbohydrate response on a tenth of the sample | Item 26 |
| 7. Meal peak on the same tenth | Item 26 |
| 8. Population not regenerable from its seed | Item 4 |
| 9. Population in one uncommitted copy | Item 29; local backup with fingerprints |
| 10. Settings not tied to their population | `profile_for` population guard; item 2 |
| 11. Commons windows selected on glucose alone | Item 26 |
| 12. Cohorts matched on age alone | `matched_on_traits`; nothing in this list |
| 13. Ladder reused cached results | Item 16 |
| 14. Defence gain on an unstable median | Item 23 |
| 15. Over-claim from the same instability | Item 23 |
| 16. Gaps quoted in spread units | Item 23 |
| 17. Study refused a mechanism on a refuted premise | Item 22 |
| 18. Study conclusion inverts with layers present | Item 22 |
| 19. Examples assume a pip install | Item 18 |
| 20. Titrator replaced the store | `--add` merge; nothing in this list |
| 21. zsh collapsed an argument list | Item 18 |
| 22. Disjoint cohorts exhaust the adult pool | Match distance reported by `matched_on_traits`; nothing in this list |
| 23. `simulate_cohort` ran serially | Items 13 and 14 |
| 24. Exact bound on a reconstructed ratio | Nothing yet |
| 25. Defence gain on too small a sample | Items 1 and 23 |
| 26. Settings guard blind to physiology | Item 1; `rebuild_all.sh` deletes the store |
| 27. Every result stamped not reproducible | Item 19 |
| 28. Ladder complete in under a minute from stale rungs | Items 16 and 27 |
| 29. Suppression list excused unstamped producers | Item 19 |
| 30. Bench arm never reached the workers | Items 13 and 27 |
| 31. Empty cell reported OK in three seconds | Items 15 and 27 |
| 32. Two families outside archive and guard | Item 16; `test_docs_measurement_families_*` |
| 33. Ceiling check tested only that the clamp fired | Item 7 |
| 34. Plan-only run overwrote results; fix reached one caller | Item 17 |
| 35. Three stages wrote no measurement file | Item 24 |
| 36. Rebuild does not rebuild everything | Item 24; pre-existing for the six calibration producers |
| 37. Matrix carried the placeholder | Item 19 |
| 38. Bench arm measured three times on an inert option | Items 5 and 27 |
| 39. Pinned baseline held four settings stores | Item 19 |
| 40. Verification record changed the store's identity | Item 2 |
| 41. Mechanism refused on an inert sweep parameter | Item 5 (pre-existing in `simulate`); item 24 |
| 42. Design argument with no producer, and wrong | Item 24 |
| 43. Two controllers indexed under one key | Item 20 |
| 44. Two gates on different populations | Item 21 |
| 45. Gate read off a median the mechanism does not move | Items 21 and 23 |
| 46. One meal per subject against a per-person quantity | Item 22 |
| 47. Restamp tool passed on nothing | Items 2 and 27 |
| 48. Published protocol matched to the wrong meal and denominator | Item 25 |
| 49. Opposite conclusions from two meal comparisons | Item 22 |
| 50. Controller blamed for a panel difference | Item 21 |
| 51. Eaten grams against logged grams | Item 22 |
| 52. Real reference pooled children with adults | Item 22 |
| 53. Documents quoted figures no file produced | Item 24 |
| 54. oref adapter pruned insulin early, on the wrong curve | Items 8 and 9; the two named tests |
| R1, R2. Titration and benchmark on one seed; scripts on different seeds | Item 4 |
| R4, R13, R22. Documented modelling choices | Nothing in this list; recorded at the definition |
| R5. Population fingerprint misses the questionnaire | Nothing yet (pre-existing) |
| R6. Ablation changed the random month | Item 3 |
| R7, R8, R27. Ceiling rounding and withheld basal | Item 7 |
| R9. Time axis reconstructed | Item 11 |
| R10. Defence gain fitted partly on clamp failures | Item 23 |
| R11. Two meals in one minute lost one | Nothing yet; corrected in code without a regression test |
| R12, R18, R26. Clock one sample out, and its consumers | Item 11; `test_the_event_logs_and_the_glucose_series_share_one_clock` |
| R14. Partial-overlap refusal off the table path | Item 21 |
| R15. Sensor tests exercise a copy that never runs | Nothing yet (pre-existing) |
| R16, R17, R19, R25. Adapter inputs that were constants | Item 8 |
| R20, R21. Baseline over the sealed half; wrong cohort | Item 22 |
| R23. A fifth of temporary basals discarded | Item 26 |
| R24. Built-in loop ignored insulin on board | Item 7; `test_a_correction_cannot_exceed_the_insulin_on_board_ceiling` |
| R28, R34. Shard stamp bookkeeping and binding fields | Item 19 |
| R29. Range compared against a split-half | Item 23 |
| R30. Panels on physiological settings | Item 21 (`profile_factory=titrate.profile_for`) |
| R31, R32. Controller state across runs | Item 6 |
| R33. Store values trusted into a body | `test_a_settings_multiplier_at_or_below_zero_is_refused`, `test_the_store_is_written_atomically` |
| Boost engine returned NaN in a dose field (initial-settings ablation) | Item 10 |

A new entry in `docs/ISSUES.md` or `docs/REVIEW.md` adds a row here naming its check, or "nothing
yet".
