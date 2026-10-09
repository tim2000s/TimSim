# Testing and issues log

Every defect found in this package and in the work built on it, in the order it was found, with
how it surfaced and what was done about it. Defects introduced during the investigation are
logged the same way as ones that were already here, and are marked as such, because a log that
records only other people's mistakes is not a record of anything.

The dominant pattern is worth stating at the top. Of the thirty-eight entries below, a minority
are coding errors. Most of the rest are measurements that were correct arithmetic on the wrong
comparison, or figures that could no longer be traced to the code that produced them. The
project's own standing rule, that a comparison must be computed the same way on both sides,
caught more of these than any test did.

A second pattern runs through entries 28 to 38 and is worth naming separately, because it is the
one that keeps recurring. A measurement that cannot say which experiment produced it will
eventually be read against one it does not belong to, and the failure is silent every time: the
output is complete, the arithmetic is right, and nothing looks wrong. Four of those entries are
the same defect found in a new place after the previous instance was fixed without the cause
being. The signature to watch for is a stage finishing far faster than it should, or two arms
agreeing to every decimal.

| # | Found | Issue | Severity |
|---|---|---|---|
| 1 | 15 Aug | Measurements lived outside the repository and one source was lost | high |
| 2 | 15 Aug | The DCLP3 correction factor was never measured from the release | high |
| 3 | 15 Aug | The carbohydrate ratio was described as agreeing when it does not | medium |
| 4 | 15 Aug | The Commons user count matched no set of users | medium |
| 5 | 15 Aug | Fast entries parser dropped 3.5 per cent of readings (introduced here) | high |
| 6 | 15 Aug | The carbohydrate response claim was measured on a tenth of the sample | high |
| 7 | 15 Aug | The meal peak claim rested on the same tenth | high |
| 8 | 15 Aug | The population could not be regenerated from its seed | critical |
| 9 | 15 Aug | The population existed in one uncommitted copy with no backup | critical |
| 10 | 15 Aug | Titrated settings were not tied to the population they were fitted to | critical |
| 11 | 15 Aug | Commons windows were selected on glucose coverage alone | high |
| 12 | 15 Aug | Cohorts were matched on age alone | medium |
| 13 | 16 Aug | The layer ladder silently reused cached results from the old population | high |
| 14 | 16 Aug | The hepatic defence gain was calibrated on an unstable median | high |
| 15 | 16 Aug | Over-claim about that gain, from the same instability (introduced here) | medium |
| 16 | 16 Aug | Gaps were quoted in spread units, which cannot establish a gap | high |
| 17 | 16 Aug | Study 06 refused a mechanism on a refuted premise | high |
| 18 | 16 Aug | Study 08's conclusion inverts once the layers are present | medium |
| 19 | 16 Aug | Example scripts assume the package is pip-installed | low |
| 20 | 16 Aug | The titrator replaced the settings store rather than merging | medium |
| 21 | 16 Aug | Argument list silently collapsed by zsh, misdiagnosed once (introduced here) | low |
| 22 | 16 Aug | Disjoint cohort draws exhaust the adult pool | medium |
| 23 | 16 Aug | `simulate_cohort` ran every subject serially on a fourteen-core machine | medium |
| 24 | 16 Aug | An absorption test compared a reconstructed ratio against an exact bound | low |
| 25 | 18 Aug | The hepatic defence gain was fitted on a sample too small to fit it | high |
| 26 | 18 Aug | The titration store is guarded by the population, and settings depend on the physiology | high |
| 27 | 19 Aug | Every result stamped itself as not reproducible | high |
| 28 | 19 Aug | The ladder reported complete in under a minute from the previous day's rungs | high |
| 29 | 20 Aug | A suppression list excused five producers that had no stamping code to wait for | medium |
| 30 | 20 Aug | The bench arm reached the file header and never reached a run | high |
| 31 | 20 Aug | A cell that measured nothing reported OK in three seconds | high |
| 32 | 20 Aug | Two measurement families lived outside the archive and outside the guard | medium |
| 33 | 20 Aug | A ceiling check that tested only whether the clamp had fired | high |
| 34 | 20 Aug | A plan-only run overwrote the results it preceded, and the fix reached one caller of two | medium |
| 35 | 20 Aug | Three stages of the rebuild produced no measurement file at all | high |
| 36 | 20 Aug | The rebuild does not rebuild everything | high |
| 37 | 20 Aug | The matrix carries the placeholder its own guard exists to reject | medium |
| 38 | 20 Aug | A bench arm was measured three times because the option it varied does not reach it (introduced here) | low |

---

## 1. Measurements lived outside the repository and one source was lost

Numbers quoted in the validation write-up came from scripts in a session scratch directory. The
markdown source of the first paper draft was gone by the time it was asked for; only its PDF
survived. Nothing that produced a figure could be rerun.

**How it surfaced.** Asked to rewrite the paper, the source could not be found. The scripts
behind its tables did not exist anywhere in the checkout.

**Fix.** The five measurements were moved into `examples/`, writing into `docs/measurements/`,
taking their paths from the repository root so a checkout anywhere reproduces them. Committed in
`ebee20a`.

## 2. The DCLP3 correction factor was never measured from the release

`METHODS.md`, `PADOVA_LIMITS.md`, `titrate.py` and `profile.py` all stated that DCLP3
participants ran a correction factor of 35 mg/dL per unit. No code produced that figure.

**How it surfaced.** Asked to align the correction factor with the real data, it was measured
directly from `InsulinPumpSettings_a.txt`, per participant across all time segments, restricted
to the 112 closed-loop participants.

**Fix.** The median is 40.0 mg/dL per unit with an inter-quartile range of 30.0 to 50.0. The
1800-rule value implied by their recorded total daily insulin is 37.6, which is consistent.
Corrected in the two modules and the three documents, `ebee20a` and `0ba59d8`.

## 3. The carbohydrate ratio was described as agreeing when it does not

`profile.py` recorded "Real settings and measured ones agree, 8.0 in the trial against 8.9 here"
and concluded that carbohydrate ratio needed no correction.

**How it surfaced.** Measured alongside issue 2 from the same file.

**Fix.** The trial median is 8.0 g per unit, inter-quartile range 7.0 to 11.0, against 12.5
across the generated population, so the generated ratio is the weaker of the two and the two do
not agree. Corrected in `ebee20a`.

## 4. The Commons user count matched no set of users

`METHODS.md` and `OVERVIEW.md` reported 221 OpenAPS Data Commons users.

**How it surfaced.** Writing a reproducible Commons measurement required counting them. The
April 2026 export holds 240 user directories, 131 with a readable glucose series, 103 holding a
28-day window meeting the coverage threshold, and 71 of those with pump records as well. No
filter produces 221.

**Fix.** The nested counts are documented in `docs/measurements/README.md`, and the figure is
corrected wherever it appeared. `0ba59d8`.

## 5. Fast entries parser dropped 3.5 per cent of readings — introduced here

The streaming parser written for the 6 GB Commons export used a carry buffer to hold the last,
possibly incomplete, JSON object across chunk boundaries. A Python operator-precedence error
meant the conditional applied only to the second element of a tuple assignment, and the final
object of each chunk boundary was discarded.

**How it surfaced.** Validated against `json.load` on a complete file before trusting it: 43,669
readings against 45,264.

**Fix.** Carry handling rewritten and the trailing object flushed after the loop. The parser now
matches `json.load` exactly on the validation file. Had this not been checked, every Commons
figure would have been about 3.5 per cent short with no visible symptom.

## 6. The carbohydrate response claim was measured on a tenth of the sample

`PADOVA_LIMITS.md` reported that real people rise 30.7 mg/dL per logged 10 g against the model's
20.3, across 848 entries with no insulin within half an hour, and concluded the model was short
by 1.2 to 1.4 times. That conclusion was load-bearing for the paper's meal section.

**How it surfaced.** No code in the repository produced any of those numbers, so it was
remeasured. Under the same stated filter the full export gives 19.71 mg/dL per logged 10 g
across 7,996 entries from 128 users. 848 is a tenth of 7,996, which is the sample the
`entries_*.json` glob returns before it is widened to `*entries*.json` to catch users whose
filenames carry no prefix.

**Fix.** The filter is now recorded per meal rather than applied, so the definition of an
uncovered meal can be varied without reparsing the export. Across every defensible definition
the real rise sits between 15.7 and 19.7 per logged 10 g against a model 22.20, so the model's
response is larger than real, not smaller. Both sections of `PADOVA_LIMITS.md` rewritten, and
the interface calibration they proposed withdrawn. `258eed3` and `0ba59d8`.

## 7. The meal peak claim rested on the same tenth

The same document reported the model's uncovered meal peaking at 206 minutes against a real 145.

**How it surfaced.** Remeasured with issue 6.

**Fix.** Real peaks run 177 to 248 minutes across the filter variants and the model peaks at 225,
inside that range. Rewritten in `0ba59d8`.

## 8. The population could not be regenerated from its seed

`generate()` seeded each class with `seed + hash(klass) % 10_000`. Python salts string hashing
per process, so `hash('adult')` returned 5103, 3342 and 8570 on three consecutive interpreters
and `generate(seed=2026)` produced a different hundred subjects every run.

**How it surfaced.** `METHODS.md` recorded the defect and left it unrepaired. Verified by calling
`hash` in three separate processes.

**Fix.** `class_seed()` derives from SHA-256, the same construction already used by
`simulation/run.py::subject_seed`. Verified reproducible: identical subject names, identical
digest, maximum difference 5.7e-14 across 61 numeric columns between two independent
generations. `d388796`.

## 9. The population existed in one uncommitted copy with no backup

`vpop_params.csv`, `vpop_quest.csv`, `vpop_report.json` and `titrated_settings.json` are all
gitignored, deliberately, because they derive from the published parameter tables. Combined with
issue 8, the subjects every figure in `docs/` had been measured on existed in exactly one place
and could not be rebuilt.

**How it surfaced.** Investigating issue 8.

**Fix.** Backed up locally to `~/.timsim-population-backup/` with SHA-256 fingerprints and a note
recording why it could not be regenerated. Issue 8 removes the underlying risk for anything
generated afterwards.

## 10. Titrated settings were not tied to the population they were fitted to

Subject names are positional, so regenerating the population reuses every name for a different
body. `adolescent#004` went from a correction factor of 21.8 to 43.5 under the same name. The
titration store recorded nothing tying it to a population, so `profile_for` would have dosed
every subject on another body's settings and no arithmetic would have looked wrong.

**How it surfaced.** Checked what would break immediately after reseeding, before running
anything on the new population.

**Fix.** The store records a digest of `vpop_params.csv`; `profile_for` and `titrated_subjects`
raise when it does not match what is on disk. Verified against the stale store: both refuse it.
This is the failure mode `METHODS.md` describes as worse than a crash. `d388796`.

## 11. Commons windows were selected on glucose coverage alone

Twenty-seven of ninety-eight users appeared to take 90 per cent or more of their insulin as
basal and to log no carbohydrate at all, which reads as fully closed-loop living. They were
about to be used as a real reference population for the unannounced-meal comparison.

**How it surfaced.** Their outcomes were better than conventional users', which is the wrong
direction for a fully closed-loop group. Counting their records first showed 1,256 to 7,417
boluses each, with thousands of meal-bolus events. Their treatment data is missing from the
selected window, not their meals.

**Fix.** A window now also requires treatment records. Excluding those users moves the median
daily requirement from 34.7 to 38.4 U/day and removes a spurious bolus-free group. The outcome
reference is unaffected. `9547c04`.

## 12. Cohorts were matched on age alone

`cohort.matched` sampled by age bin, which was all the public DCLP3 release was thought to
support, leaving what age stands in for unmatched.

**How it surfaced.** Asked to address total daily dose for the Commons cohort, which publishes no
demographics at all.

**Fix.** `matched_on_traits` matches each real person to the nearest unused subject in
standardised age and log-insulin space and returns the distance achieved. Against DCLP3 it gives
an age median of 27.8 against 28.5 and a requirement of 46.8 against 47.9, where the age-only
draw gave 32.1 and left insulin unmatched. `9547c04`.

## 13. The layer ladder silently reused cached results from the old population

`layer_ladder_by_controller.py` reads per-subject JSON from `docs/ladder/` when present. In a
rerun intended to remeasure everything on the regenerated population, it printed a complete
result table having done no work.

**How it surfaced.** It reported completion in 0 minutes where the other steps took 2 to 209.

**Fix.** Stale files moved aside and the ladder rerun properly. The result changed: 9 of 47
rung-signature movements are carried by the person, against the 12 the study reports, and
hypoglycaemia recovery drops from carried by all four drivers to three of four, which by the
study's own criterion makes it an interaction rather than a property of the person.

## 14. The hepatic defence gain was calibrated on an unstable median

The gain was set against a population median of endogenous glucose production at a clamped
55 mg/dL plateau. That median is a weak statistic here: the distribution is zero-inflated, and it
reads 0.49 mg/kg/min across twenty adults and 0.18 across thirty-four for the same setting.

**How it surfaced.** Rerunning the clamp on the regenerated population, then across the whole
adult class rather than the script's default first twenty.

**Fix.** Gain moved from 0.25 to 0.20, which places the median at 0.65 at the 55 mg/dL plateau
and 0.57 at 45, both inside the human 0.42 to 0.84 and closest to the human mean among gains
inside at both. The instability is documented beside the constant, and the robust statement is
recorded as the zero count rather than the median: seven of thirty-four still produce nothing
where no real person does, and no gain fixes that. `b169578`.

## 15. Over-claim about that gain, from the same instability — introduced here

It was reported that the undefended model now produced 0.49 mg/kg/min, inside the human range,
and that the shipped gain overshot to 0.95, above it. Both figures came from the clamp script's
default of the first twenty adults.

**How it surfaced.** Running the calibration across all thirty-four adults immediately
afterwards.

**Fix.** Corrected in the same commit and to the reader: the undefended median is 0.18, well
below the human range, and the shipped 0.25 gave 0.76, inside it. The mechanism was not badly
miscalibrated. The instability that produced the error is now documented so the median is not
quoted as a point estimate again.

## 16. Gaps were quoted in spread units, which cannot establish a gap

Every comparison reported a simulated median beside a real one and expressed the difference in
units of the real between-person spread. That says how large a difference is, not whether it is
distinguishable from the cohort having been drawn differently.

**How it surfaced.** Asked to consider inter-group variation as a baseline for the simulator
itself. Bootstrapping the simulated cohort medians showed intervals wider than several of the
gaps being reported.

**Fix.** A gap is now reported as distinguishable only when the real median falls outside the
simulated cohort's 95 per cent interval. Two baselines support it: splitting each real population
at random in two moves its median by 0.15 to 0.29 of its own spread, and disjoint simulated
cohorts give the group effect directly. On the existing runs the test says the pairing where the
algorithm genuinely matches its reference is indistinguishable from real people on time in range,
time above 180 and mean glucose, while hypoglycaemia is distinguishable in every pairing.
`12ce054`.

## 17. Study 06 refused a mechanism on a refuted premise

The study declined to implement an arrest of a falling glucose because "the model already
produces four times the endogenous glucose of long-standing type 1 diabetes during a low". That
compares production during spontaneous lows under a closed loop with a figure from a
hyperinsulinaemic clamp; production here is linear in remote insulin, which differs by roughly a
factor of two between those states.

**How it surfaced.** The audit of all ten studies against current measurements.

**Fix.** Under the clamp protocol the model gives 0.14 mg/kg/min at the 55 mg/dL plateau against
a human 0.59, so it produces nothing where people who have lost the glucagon arm still produce
something. The mechanism was indicated and has since been implemented. Corrected in both places
the claim appears. `ef9ff19`.

## 18. Study 08's conclusion inverts once the layers are present

The study reports that fourteen of fifteen incomplete runs ended between 10 and 13 mg/dL, and
concludes that survival selects on the variable hypoglycaemia statistics measure.

**How it surfaced.** Termination directions counted across 380 runs of the bench matrix.

**Fix.** The finding holds on the bare model, where every failure is a low, and inverts on the
layered bench, where 48 of 62 terminations are high, because the person eats when they go low.
The consequence is restated rather than withdrawn: survival still biases every cohort figure, but
on the layered bench it biases time above range rather than hypoglycaemia. Addendum added.
`ef9ff19`.

## 19. Example scripts assume the package is pip-installed

Eight scripts import `timsim` with no path handling, so they only run from a context that
happens to put the repository on `sys.path`. A runner invoking them by path fails immediately.

**How it surfaced.** The first study rerun pass failed every step in under a second.

**Fix.** `PYTHONPATH` set explicitly in the runner, and the scripts written since take the
repository root from their own location. The underlying fix is `pip install -e .` in the working
environment, which has not been done.

## 20. The titrator replaced the settings store rather than merging

`titrate_cohort.py` wrote the store from the subjects it was given, so titrating nine new
subjects would have discarded the fifty-one already done.

**How it surfaced.** Read before running, while planning the replicate cohorts.

**Fix.** `--add` merges into the existing store, skips subjects already titrated against the
current population, and refuses to extend a store fitted to a different one.

## 21. Argument list silently collapsed by zsh, misdiagnosed once — introduced here

A subject list was built into a shell variable and passed unquoted. zsh, unlike bash, does not
word-split unquoted parameter expansions, so nine `--subject` arguments arrived as one string and
argparse rejected them.

**How it surfaced.** The titration run failed. It was first attributed to a transient and
relaunched unchanged, which failed identically. Only then was it traced.

**Fix.** `${=NEW}` forces splitting. The misdiagnosis is logged because assuming a transient
without evidence cost a second failed run.

## 22. Disjoint cohort draws exhaust the adult pool

Measuring the group effect requires cohorts that share no subjects. Four disjoint cohorts of
twenty-five matched to DCLP3 degrade sharply: the third is 80 per cent under 18 and the fourth
88 per cent, against a trial that is 28 per cent.

**How it surfaced.** Sizing the replicate design and reading the match distance reported by
`matched_on_traits`, which exists to make exactly this visible.

**Fix.** Three disjoint cohorts of fifteen, matched at 0.479 to 0.596, which is also close to the
number of subjects the main arms complete. Recorded as a limit of the population rather than
worked around: a hundred subjects support about three independent DCLP3-matched groups.

## 23. `simulate_cohort` ran every subject serially

`simulate_cohort` was a plain loop over subjects, so every study script built on it used one
core regardless of the machine. `hyperglycaemia_gap` took 218 minutes and `layer_ablation` 89,
and the six-configuration classifier arbiter would have taken about seven hours.

**How it surfaced.** The machine sat at a load average of 2 on fourteen cores while a job was
running. That was noticed and worked around by filling the idle capacity with other jobs, twice,
before anyone asked why the job itself was not using it. The prompt was a direct question about
whether the arbiter could run in parallel.

**Fix.** `simulate_cohort` takes a `workers` argument, defaulting to one so no existing caller
changes behaviour. Results are identical: on six subjects run both ways, every CGM reading
matches to the bit and the order of results is preserved, because a subject's random stream
comes from `subject_seed(name, seed)` rather than from where it sits in the list or when it
runs. Six subjects went from 134 seconds to 24.

Two things it refuses rather than getting wrong. A controller holding a live resource cannot be
pickled to a worker, so an `OrefController`, which owns a node subprocess, produces a warning
and a serial run instead of a corrupted one. And because Python spawns rather than forks on
macOS, a caller must put the call behind `if __name__ == "__main__":` or every worker re-runs
the calling script; that is documented on the function.

## 24. An absorption test compared a reconstructed ratio against an exact bound

`test_the_factor_is_bounded_so_a_tail_draw_cannot_stop_absorption` clamps the meal absorption
factor into `MEAL_ABSORPTION_BOUNDS` and then checks the bound by dividing the clamped rate by
the unclamped one. The clamp is exact; the division is not.

**How it surfaced.** The test suite was run after the parallelism change and this failed at
2.6000000000000005 against a bound of 2.6, an excess of 4.4e-16, or one unit in the last place.
It had passed for months and began failing because regenerating the population gave `adult#001`
a different `kabs`, one that happens to divide unluckily.

**Fix.** A tolerance of 1e-9 on both bounds, which is many orders of magnitude below any draw
the test exists to catch. Logged rather than fixed silently because the failure was informative:
a test that depends on the exact value of a subject's parameters is testing the population as
well as the behaviour, and this one gave no hint of that until the population changed.

## 25. The hepatic defence gain was fitted on a sample too small to fit it

`HYPO_EGP_DEFENCE` opposes insulin's suppression of endogenous glucose production as glucose
falls, and it is fitted by matching the median production at a clamp plateau to the human
reference of 0.42 to 0.84 mg/kg/min. It was fitted on the first twenty adults, then on
thirty-four, then on a hundred and fifty, and the answer moved each time: 0.95, then 0.20, then
0.05.

**How it surfaced.** The population was grown to 600 subjects for reasons unrelated to this, and
the calibration was rerun at n=150 because the subjects were available. The undefended model
produces a median of 0.50 mg/kg/min at the 55 mg/dL plateau, already inside the human interval,
where at n=20 it had produced 0.49 and at n=34 it had produced 0.18.

**Why it moved.** The distribution is zero-inflated. 49 of 150 subjects produce nothing at all
at that plateau, so the median sits wherever the proportion of pinned-at-zero subjects puts it,
and that proportion is estimated badly at small n. The quantity being fitted was therefore a
property of the sample size as much as of the model.

**Fix.** The gain is 0.05, fitted at n=150, and the sweep is recorded in `patient/varying.py`
beside it with the zero counts at every gain. The zero tail is named as a separate defect the
mechanism does not repair: raising the gain to 0.25 removes twelve of the forty-nine and carries
the median to 1.05, above the human interval at both plateaus.

Everything measured under the old gain was rebuilt rather than patched, since the gain enters
every simulated minute. `examples/rebuild_all.sh` runs that rebuild.

## 26. The titration store is guarded by the population, and settings depend on the physiology

`profile_for` refuses settings fitted to a different population, checked by a fingerprint of
`vpop_params.csv`. Changing a physiology constant leaves that fingerprint untouched, so the
store is accepted and every subject silently carries settings fitted under the old physiology.

**How it surfaced.** Preparing the rebuild for issue 25. The population had not changed, only
the defence gain, so the guard would have passed and the rebuild would have measured a new
physiology through settings titrated against the old one.

**Why it matters more than it looks.** Titration weakens a subject's settings until its own
record clears the consensus hypoglycaemia floors. The defence gain is one of the things
determining how much hypoglycaemia a subject has, so the titrated settings are an output of the
physiology as much as of the population, and reusing them would have partly cancelled the change
being measured.

**Fix.** `examples/rebuild_all.sh` deletes the store before retitrating, and says why in the
script. The guard itself is unchanged: extending the fingerprint to cover the physiology
constants would invalidate the store on any edit to `varying.py`, including edits to comments,
which would make it useless.

## 27. Every result stamped itself as not reproducible

`provenance.stamp` recorded the working tree as dirty whenever `git status` returned anything,
and results are written into the repository under `docs/measurements/`. A run therefore dirtied
the tree by completing, and `check_compatible` refuses to merge dirty results, so shards could
not be combined without `--allow-dirty`.

**How it surfaced.** Checking what the rebuild would stamp its outputs with before starting it.

**Fix.** The flag now asks whether anything outside `docs/` differs from the commit, which is
the question it was meant to ask: whether the code that ran is identified. Verified both ways,
with a results-only tree reading clean and a one-character edit to `patient/varying.py` reading
dirty.

The first attempt at the fix did not work and is worth recording. `git status --porcelain` puts
the path at a different offset for a staged change than an unstaged one, so slicing a fixed
three characters dropped the leading character of every staged path, no path matched the
exclusion, and the flag stayed set for exactly the reason it had just been changed to ignore. It
was caught by checking the flag against a tree that should have read clean rather than by
assuming the edit worked.

## 28. The ladder reported complete in under a minute from the previous day's rungs

**What happened.** The 19 August 2026 rebuild logged `OK layer_ladder (0 min)` and printed a
full signature table. Every rung had been measured the previous afternoon, between 16:17 and
18:03 on 18 August, under settings that this rebuild had retitrated at 09:53 and an absorption
scale that had changed since. The table described a configuration that no longer existed.

**Why it happened, twice.** `layer_ladder_by_controller.py` writes one file per rung into
`docs/ladder` and skips any rung whose file is already there. That skip is wanted: the ladder is
twenty rungs and about an hour and three quarters, so a rerun after an interruption should not
start again. It was conditioned on the file existing and nothing else. The rungs carried no
provenance stamp, so no check was possible even in principle.

The archive step in `rebuild_all.sh` should have removed them and did not, because it walks
`docs/measurements` and the ladder writes somewhere else. The same defect was found and
corrected once before by archiving the rungs by hand, which fixed the instance and left the
cause in place.

**How it surfaced.** A stage that had taken 106 minutes reporting 0. The completion time was the
only signal: the output was a complete, plausible table, and nothing in it indicated its age.

**Fix.** Two, because either alone would have failed. Each rung now carries a provenance stamp
and is reused only when that stamp binds against the current one on every field in `BINDING`; an
unstamped rung never binds, so the twenty already on disk could not have been reused. And the
archive step now moves `docs/ladder` as well, with the reason recorded beside it.

**What it cost.** Nothing downstream, because the ladder feeds a study rather than the matrix,
and it was caught before anything was written from it. Had the completion time been 5 minutes
rather than 0 it would probably not have been noticed.

## 29. A suppression list excused five producers that had no stamping code to wait for

**What happened.** `tests/test_provenance_coverage.py` asserts that every measurement on disk
records the experiment that produced it, with an allow-list, `PENDING_REBUILD`, for files written
before the guard existed. Fourteen names sat on that list under one justification: each
producer now stamps, each file merely predates the change, so each entry clears at the next
rebuild. It was true of nine. `fit_control_iq`, `capability_decomposition`, `calibrate_exercise`,
`calibrate_glucagon` and `calibrate_egp_floor` wrote no stamp at all, so those five entries
described a wait with no end.

**Why it happened.** The list was assembled by running the guard and adding whatever failed. A
file that fails because its producer stamps and a file that fails because its producer does not
are identical at the point of failure, and the producers were never read afterwards. The
justification was then written once, over the whole list, from the majority case.

**How it surfaced.** By reading the five producers the list named instead of the list itself,
during an unrelated check of which measurements bind to the current population.

**What it cost.** Less than it might have. `control_iq_fit.json` was the live entry, on disk and
read by the Control-IQ stand-in, and it does record a population fingerprint of its own, which
matches the population in use. What it does not record is the settings digest, the commit or the
patient model version, so the field that matters most happened to be present and the rest were
absent. The other four are archived and nothing reads them.

**Fix.** All five producers stamp. `cohort_replicates.json` was regenerated after the guard went
in and is removed from the list, so it is now checked rather than excused, and the thirteen that
remain carry the property the comment claims. The comment records that the list was audited
against the code it excuses, since a suppression that is never read against its subject is
indistinguishable from one that is no longer needed.

A sixth producer turned up on the same sweep by a different route. `calibrate_hypo_defence.py`
did not stamp either, and it was on no list, because its output is archived rather than on disk
and a guard that reads what is present cannot see a file that is absent. It supplies study 10 and
will be regenerated, at which point it would have written the first unstamped measurement of the
new set. It stamps now. Every producer of a measurement that depends on the population does; the
four that do not are the ones computed from real records alone, where a population stamp would
be a fiction.

## 30. The bench arm reached the file header and never reached a run

**What happened.** `cohort_replicates.py` gained `--controller` and `--arm` so that the group
floor could be measured in cells other than the single one it had been quoted from. Both values
were assigned to module globals inside `main` and read by the worker function, under a comment
saying the workers inherited them at fork. macOS starts subprocesses by spawn. Each worker
re-imported the module and read the defaults defined beside the function, so every run used the
layered arm under the Control-IQ stand-in no matter what was asked for. The metadata written
beside the results was produced in the parent and recorded the request faithfully, so the file
carried `"arm": "bare"` and `"layers": []` above 247 runs of the layered arm.

**Why it happened.** The comment asserted a start method rather than checking one, and it was
written on a machine where the assertion is false. Nothing compared the two halves of the
output: the header came from the parent and the rows from the children, and no code read either
against the other.

**How it surfaced.** The bare cell reported a summary table identical to the layered cell's in
all thirty-six figures. Two arms agreeing to two decimals on six statistics across three
replicates is not a result, and comparing the rows confirmed it, with all 247 matching to within
1e-9 on mean glucose.

**Fix.** The arm and the algorithm travel in each job tuple, which no start method can strip.
Each row returns the layers and the controller it was measured under, and the script refuses to
write a file whose rows disagree with the arm requested. Checked on a seven-subject run before
the full cells were restarted: the bare arm sits 5 to 21 mg/dL below the layered arm on the same
subjects, which is the direction the layers move a subject.

**What it cost.** Thirty-nine minutes of machine time and no conclusion, since it was caught on
the first cell the option produced and the file was removed before anything read it. The
dangerous case is the one that did not happen. Had the two arms come out close rather than
identical, the table would have read as a finding, and a floor that does not differ between arms
is precisely the result this measurement exists to test for.

## 31. A cell that measured nothing reported OK in three seconds

**What happened.** With the arm and the algorithm reaching the workers for the first time,
`--controller oref` reached `simulate` and was rejected, because `oref` is not among the four
names that function accepts. All 247 runs raised. The script then took medians over an empty
set, printed a table of NaN, wrote it to disk and exited zero, so the harness recorded
`OK oref_layered` three seconds after starting it and did the same for the second oref cell.

**Why it happened, in two parts.** oref0 SMB is the real algorithm behind a bridge rather than a
name the simulator knows, so `bench_matrix.py` builds an `OrefController` per subject and closes
it afterwards. `cohort_replicates.py` gained a `--controller` option that passed its argument
straight through, and nothing had exercised that path, because issue 30 meant the value never
left the parent process. One defect concealed the other for as long as it lasted.

The second part is that nothing refused to write. The summary is built with `nanmedian` and its
relatives, which turn an empty set into NaN rather than into an error, so the output was complete
in structure and empty of measurement.

**How it surfaced.** A forty-minute cell finishing in three seconds, which is the same signal as
issue 28 and was again the only one available.

**Fix.** The worker builds the controller the way the matrix does, per subject and closed in a
`finally`. The script refuses to write when fewer than 30 runs completed, naming the most common
failure and separating runs that raised from runs that started and stopped short. Real cells
complete between 78 and 84 of 90 per replicate, so the threshold only fires on a cell that has
gone wrong.

**What it cost.** Six seconds of machine time and two files of NaN, both deleted. Had anything
read them the NaN would have been visible immediately. What would not have been visible is the
log, which is committed and recorded two cells as measured.

## 32. Two measurement families lived outside the archive and outside the guard

**What happened.** Measurements are written to three places, not one. Most go to
`docs/measurements`, which the rebuild archives and the provenance test reads. The ladder writes
to `docs/ladder`, which was added to both after issue 28. The layer ablation and the
hyperglycaemia gap write one file per arm into `docs` itself, and were in neither. So the six
ablation arms and the four gap arms were never archived between rebuilds and were never checked
for a stamp, and each family is read back by a `table()` that combines its arms into a comparison.

**Why it happened.** The archive step walks `docs/measurements`, and the guard globs the same
directory. Both were written against where measurements are supposed to go rather than against
where they actually go. Issue 28 found the same thing for the ladder and fixed the instance:
`docs/ladder` was named explicitly and the cause, that no one had enumerated the output
locations, was left alone. Two more families were sitting behind it.

**How it surfaced.** Building a map of every measurement file for a documentation audit, which
required listing where each one lives. Nothing else would have shown it, because the failure is
an absence: no stage reported anything, no table looked wrong, and the arms on disk were in fact
consistent with each other by luck rather than by check.

**Fix.** Three parts, matching the three that were missing. Both `table()` functions refuse an
arm with no stamp and call `provenance.check_compatible` on the arms they combine, which is what
that module says anything combining results must do and what neither reader was doing. The
rebuild archives both families by name rather than by wildcard, since `docs` also holds older
artefacts that no stage regenerates and a glob would destroy them. And the provenance test now
covers all three families in `docs`, asserting both that each arm is stamped and that the arms of
one family bind to each other.

**What it cost.** Nothing measurable, and that is the uncomfortable part. The arms on disk were
written in one sitting each and are consistent, so no published figure is known to be wrong. The
new tests fail on them, correctly, because unstamped files cannot be shown to be consistent, only
assumed to be. Both families need rerunning at about 89 minutes and 208 minutes to clear it, and
the test message says to rerun rather than to add an exclusion.

## 33. A ceiling check that tested only whether the clamp had fired

**What happened.** `check_delivery_limits_bind` is a level 1 check, the level whose failure
invalidates every level above it. Its verdict was that each of the three counters had fired at
least once. Whether any ceiling actually held was never asserted, so a run whose insulin on board
finished above the ceiling passed as long as the clamp had fired somewhere along the way. Its
stored result, from 8 August 2026, reports a peak of 10.8 U against a declared 8.6 and records a
pass.

**Why it happened.** The check was written to catch a bench whose limits were absent altogether,
which is what "bind" means and what the counters measure. Binding is necessary and not
sufficient, and the note the check prints carried the peak and the ceiling side by side without
anything comparing them. A reader would have had to do the subtraction the check declined to do.

**How it surfaced.** A documentation audit read the note and the verdict against each other. The
two numbers in it, 10.8 against 8.6, are the same pair the comment in `therapy/limits.py` uses to
describe the defect that comment was written to repair, which is what made it worth chasing.

**Fix.** The check asserts that insulin on board stays under its own ceiling, with a tolerance of
one bolus increment because the peak is recorded before rounding. Run on current code it holds
exactly: 8.4, 8.7 and 10.1 U against ceilings of the same values across three subjects.

**What it cost.** Nothing, and only by luck of sequencing. The breach was real when that result
was written, was repaired on 17 August when the ceiling was extended to constrain basal above
schedule, and the check has not been run since. Had the repair not happened independently, this
check would have gone on passing.

## 34. A plan-only run overwrote the results it preceded, and the fix reached one caller of two

**What happened.** `cohort_replicates.py --plan-only` prints which subjects a replicate set would
need and stops. It wrote that plan to the results path. Inside a rebuild this is harmless, because
the plan stage runs before the results stage and is overwritten by it. Run on its own on 20 August
2026 it replaced 247 completed runs with a list of names.

**Why it happened.** The two outputs shared a path because in the only order anyone had run them,
the order made it safe. Nothing recorded that the safety came from the sequence rather than from
the code.

**Fix, and the half of it that was missed.** The plan writes to its own file and `rebuild_all.sh`
reads the new path. `examples/overnight.sh` ran the same two stages and was not updated, so it
called `--plan-only` and then read the old path, which after the fix holds a results file with no
`need_titration` key. That stage would have titrated nobody and reported it in a line
indistinguishable from having nothing to do, after which the replicates would have run against
subjects with no settings. Corrected on 20 August 2026, and the file has since been deleted as
superseded by `rebuild_all.sh`.

**What it cost.** A 39-minute rerun for the instance. The second caller was never exercised
between the fix and its correction, so nothing was measured through it.

## 35. Three stages of the rebuild produced no measurement file at all

**What happened.** The hypoglycaemic clamp, the capability table and production during a low
printed a table to standard output and stored nothing. Their figures lived only in a stage log
that the next rebuild overwrote. The clamp is the calibration basis for the hepatic defence gain
and the capability table is the source of the headline signature count, so two of the three carry
claims the package leads with.

**Why it happened.** Each was written to be read once by the person running it, and neither was
revisited when the rest of the package moved to stamped measurement files. Logs are not archived,
not stamped and not covered by the provenance guard, so nothing noticed.

**How it surfaced.** An audit of every quantitative claim against the measurements, which could
not verify them and had to record why.

**Fix.** All three write a stamped JSON file beside the table they print, and all three have been
rerun. `production_during_a_low.py` also printed the clamp comparison as a hardcoded sentence
carrying a superseded 0.14 mg/kg/min; it reads that figure from the clamp's own output now, or
omits it.

**What it cost.** The larger part of the 581 claims that the audit could not check. Nothing was
measured wrongly, and nothing could be shown to have been measured rightly.

## 36. The rebuild does not rebuild everything

**What happened.** `rebuild_all.sh` opens by saying it rebuilds every measurement in the package.
Nine measurement producers were absent from it. Six still are: `capability_decomposition`,
`calibrate_hypo_defence`, `calibrate_glucagon`, `calibrate_exercise`, `calibrate_egp_floor` and
`hypoglycaemia_arms`. Their outputs were archived by the rebuild that superseded them and no
pipeline was ever going to bring them back, so studies 09, 10 and 16 cannot be written from
anything on disk.

**Three more of the same shape.** The ladder runs at ten subjects because the rebuild passes no
subject count, while `LADDER.md` documents twenty and its power argument turns on the difference.
`layer_ablation.py` measures its six rungs when no arm is named and its three branches only when
one is, so `hypo`, `visentin` and `visentin1` have never been part of a rebuild and the files on
disk are from 7 and 8 August, recording a `loop` layer that no longer exists. And
`standalone_parallel.sh` duplicates ten of `rebuild_all.sh`'s stages rather than complementing
them, so running one after the other, which is how the restate is described, repeats about eleven
hours of work.

**How it surfaced.** Listing which script writes which measurement, in order to build a map for
the documentation audit.

**Fix, partial.** `group_floor`, `spread_ratio` and `covariance_estimator` were added, along with
the three remaining floor cells. The six calibration producers are a cost decision rather than an
oversight to correct silently, since adding them lengthens every future rebuild, and they are
recorded in `SPEC_VS_OUTPUT.md` as what studies 09, 10 and 16 need.

## 37. The matrix carries the placeholder its own guard exists to reject

**What happened.** `bench_matrix.json` records `simglucose: unknown`. It ran on 19 August 2026,
before the version fix landed, so it carries the exact placeholder that issue 27 was raised to
remove, and `simglucose` is a binding field because it identifies the patient model. This is the
package's largest measurement: 1,208 runs feeding the tables, the distance figures and every
paper.

**Why it went unnoticed.** The file is on the `PENDING_REBUILD` list in
`tests/test_provenance_coverage.py`, which excuses it from both the stamp check and the
placeholder check. The list is correct that the file predates the fix. What the list cannot say is
which excused file matters most.

**How it surfaced.** Reading the stamps of the matrix and the baseline side by side to check they
shared a population and settings, which they do.

**Fix.** Rerun on 20 August 2026 against a clean tree. The population, the settings and the
simulation code are unchanged since it last ran, so it is expected to reproduce, as the ablation
and the hyperglycaemia gap did.

**What it cost.** Nothing measurable. What it removes is the ability to say the matrix ran on the
same patient model as everything else, which the package's own rule requires before two results
may be combined.

## 38. A bench arm was measured three times because the option it varied does not reach it

**What happened.** A baseline was designed to separate the layer effect from the meal-announcement
effect by measuring the bare arm at all three announcement scenarios as well as the layered arm.
The three bare arms came back identical to every decimal of every measure. `run.py` sets
`announce="behaviour" in effective`, so meal announcement is a behaviour: with the behaviour layer
off there is nothing to withdraw and the bare arm announces every meal whatever is asked for.

**Why it happened.** Not for want of documentation. `examples/bench_matrix.py`, the file the new
arm set was added to, has opened since 15 August 2026 with this: "Announcement is a property of
the person, so it only varies on the layered bench: the bare patient has no behaviour layer and
announces everything by construction. That gives four arms per pairing rather than six." The new
set was written directly beneath that paragraph and contradicted it. The design was taken from
what the arms are called rather than from what the file said they do.

This is the reverse of issue 30, where identical numbers meant an option had failed to reach the
run. Here identical numbers were correct and the option was meaningless. The signature does not
distinguish the two, which is why the rule is to establish which before concluding either.

**How it surfaced.** The signature is the same either way, so the check that caught issue 30
caught this too.

**Fix.** `BASELINE_BENCHES` holds one bare arm, and the reader resolves either name so the file
already written still reads. The question the design was after is answered by the other cut: the
layer effect grows from 8.17 to 15.17 points of time in range as announcement is withdrawn, so the
two interact. Attributing that to a layer needs the rungs above behaviour measured at each
scenario, which is a ladder question.

**What it cost.** 436 of 1,308 runs, about 72 minutes of a 216-minute job. No result was wrong,
and a third of the machine time bought nothing.

## 39. A pinned baseline held four settings stores and claimed one

Found 26 August 2026, in the pin made on the 24th.

`docs/measurements/baseline_2026-08-24/` was created to fix a real problem: the titrated settings
store is generated locally, excluded from git and destroyed by the next titration, so a checkout
reproduces the code that made a figure and not the settings it was measured on. The directory
copies every measurement behind `docs/BASELINE.md` together with the store, and its README states
the population, settings and simglucose version the set was measured under.

The files were copied from disk without checking that their stamps agreed. Three settings stores
were represented, not one:

    8000d3ede7314482   validation, day_profile, controller_crosscheck
    9252e3400f4c6249   excursion_recovery, intake_clock, engagement_arm
    a37df6ce355212c7   settings_sweep

Of those, three are simulated measurements taken under doses different from the rest, and the
README asserted a single store over all of them. The pin was made to prevent exactly this and
introduced it.

It surfaced because study 17 was verified against the measurements the rebuild produced rather
than the ones it was written from. Four excursion figures disagreed, the disagreement was traced
to a different subject panel, and the panel differed because that measurement predated a
retitration the others were made after.

Two things follow. The correction-factor sweep, remeasured on the current meal template, moves
time above 180 mg/dL by 3.6 percentage points where the superseded version moved it by 1.5, so the
paper's claim that the loop absorbed the lever almost entirely was too strong and has been
rewritten. `docs/BASELINE.md` is unaffected, and its tables reproduce against the rebuilt arms row
for row, which is also the evidence that the pipeline is deterministic.

The check that would have caught it is comparing the binding stamps across a set before archiving
it, which is what `provenance.check_compatible` already does for results that are combined. An
archive is a set that will be combined by whoever reads it, and it was not being checked.

## 40. Recording that a store was verified changed the identity of the store

Found 25 August 2026.

The settings fingerprint hashed the whole `titrated_settings.json`. Re-stamping a store, to record
that a code change had been checked against it and found inert, rewrote the file's metadata and
moved the digest from 8000d3ede7314482 to 046e0da5bc380688 while every one of the 330 subjects and
all 306 adopted settings stayed identical.

Every measurement taken after the re-stamp therefore declared itself a different experiment from
the baseline it was meant to extend, and `check_compatible` would have refused to combine two sets
of figures computed on the same doses. A note saying "this was checked" invalidated what it
checked.

`provenance._settings_digest` now digests the settings themselves: each subject's adopted scales
and whether it cleared the floors, which is what binds a result, since a subject that cleared
nothing is excluded from every cohort. The current store and the archived copy agree at
0df43fd250fadd47.

Fingerprints recorded before the change hash the whole file and will not match one computed after
it. Measurements carrying 046e0da5bc380688 and 0df43fd250fadd47 were made on the same settings.

## 41. A mechanism was refused on a sweep whose parameter never reached the simulation

Found 27 August 2026, while rebuilding study 07.

`07 Meal peak timing` refused three explanations for an apparent 45-minute discrepancy in when a
simulated meal peaks. The first was absorption, recorded as "slowing gastric emptying and
intestinal absorption together by a factor of three moves the modelled peak by ten minutes and
then saturates". That measurement had no producer. It existed only as a comment in
`person/behaviour.py`, so nothing could reproduce it or rerun it on a later configuration.

Writing the producer reproduced the shape of the defect before reproducing the finding. The first
version swept `meal_absorption_scale` from 0.33 to 2.0 and returned an identical time to peak at
every scale, because that argument is applied inside the physiology block in `simulation/run.py`
and the meal-response measurement runs with no layers enabled. A run without that layer accepts the
argument and ignores it.

With the layer enabled and its other variation switched off, a threefold slowing moves the peak
from 252 to 362 minutes and a doubling moves it to 148, monotonically and without saturating. The
mechanism that was refused is the dominant control on the quantity it was refused for.

Whether the original measurement had this exact defect cannot be established, since it left no
artefact. What can be said is that a parameter applied only inside a layer is inert in a
measurement that enables no layers, that the meal-response measurement is one such, and that "moves
ten minutes and saturates" across a sixfold range is what an inert parameter looks like when the
residual is noise.

Two things follow beyond the one study. A refutation with no producer cannot be checked and should
not be relied on, which is the same finding as issue 36 reaching a different document. And an
argument that a run accepts and silently ignores is a defect in `simulate` rather than in the
caller: `meal_absorption_scale` passed without the physiology layer should raise rather than pass.

## 42. A design argument survived four months as a figure with no producer, and was wrong

Found 28 August 2026, while rebuilding study 12.

Titration runs under the built-in correction loop, and two reasons were recorded for not running
it under the open-loop arm. One is circularity and needs no measurement. The other was exposure,
recorded in `therapy/titrate.py`, `docs/METHODS.md` and `CLAUDE.md` as "that regimen spends 0.25
per cent of time below 70 mg/dL against a real 4.07 and so never exercises the settings at all",
with "13 of 15 completing subjects clear both floors at the physiological settings and the
procedure returns its own starting point".

No script produced any of those numbers. They came from a run on a population that has since been
reseeded and a ladder that has since acquired a second lever, and nothing in the repository could
regenerate them.

`examples/titration_reference.py` reruns the rejected design: the same ladder, the same floors,
the same 90 subjects, driven by the open-loop regimen. It spends 2.39 per cent of time below 70
mg/dL at the physiological rung, which is more than the 1.92 the correction loop produces on the
same rung, and it moves the settings of 19 of 90 subjects. The stated reason is refuted in both
of its parts. The arm exercises the settings, and the ladder does not return its own starting
point.

The design choice survives on a different measurement. The open-loop ladder clears no combination
for 15 of 90 subjects against the correction loop's 4, and 11 of those 15 are subjects the loop
dosed safely, 4 of them without touching their settings. Since an untitrated subject is dropped
from every cohort, titrating there would shrink each cohort by a sixth for a reason belonging to
the regimen rather than to the subject.

This is issue 36 and issue 41 in a third place, and the pattern is now specific enough to state
as a rule. A claim carried in a docstring rather than in a measurement file does not survive a
population change, because nothing recomputes it and nothing flags it as stale. Two of the three
instances found so far were also wrong, and in both the replacement argument reached the same
conclusion by a different route, which is why neither was caught by anything downstream
behaving oddly.

## 43. Two controllers were indexed under one key, and one of them was silently discarded

Found 28 August 2026, while rebuilding study 14 from `baseline_effects.json`.

`baseline_effects.py` indexed every run as `idx[cohort][bench][name]`. The baseline bench set runs
the DCLP3 cohort under both the Control-IQ stand-in and oref0 SMB, with the same 86 subject names
and the same four bench labels in both, so each Control-IQ run was overwritten by the oref0 SMB
run with the same key. Three hundred and forty-four of the 1,260 runs reached no comparison.

Nothing looked wrong in the output. The header prints the controllers from the file's `pairings`
block rather than from the runs it indexed, so it read "controller control-iq, oref" above a
report describing oref alone. The completion table showed 85/86 rather than 172, which is the
count a single controller produces and is what a reader would expect to see.

The discarded arm was not a duplicate of the one that survived. Under the Control-IQ stand-in the
DCLP3 cohort holds 95.59 per cent of readings in range on the bare model and 83.26 layered, a
layer effect of -12.33 points; under oref0 SMB the same cohort gives 93.49 and 85.90, an effect of
-7.59. The paper's headline was therefore wrong by nearly a factor of two, and in the direction
that understates what the layers do.

The announcement result inverted rather than shifted. On the surviving oref0 SMB arms, withdrawing
every meal announcement costs 0.08 to 0.84 percentage points of time in range with every interval
spanning zero, which reads as a bench that cannot detect meal announcement at all. With the
Control-IQ arm restored it costs that controller 4.84 points with an interval of -7.22 to -3.58,
which is the separation the two designs predict: the stand-in has no meal detection and oref0 SMB
microboluses on deviation from prediction.

A second defect in the same function was hidden behind the first. The age split called
`effect(arms, "bare_some", ...)`, an arm name this file does not carry, where the code four lines
above had already resolved the bare arm's name into a local. It reported "0 subjects complete both
arms" for every age band, which is the signature of a stage that skipped its work rather than one
that found nothing.

Both are the same failure as issue 38 in a different place: an arm distinguished by a field the
analysis does not key on. The rule that follows is that an index over experimental runs keys on
every field the bench varies, and a report prints the controllers it indexed rather than the ones
the file says it ran.

## 44. Two gates of one pre-registered argument were measured on different populations

Found 30 August 2026, while implementing the two-timescale liver `docs/PADOVA_AUDIT.md` entry 3
recommended.

The entry concludes that no value of `ki` reproduces both the human suppression curve and the meal
response the parameter was identified on, that "the two requirements do not overlap", and that the
divergence is therefore structural. Two gates carry that conclusion and each has its own producer.

`liver_delay_fit.py` selects `names()[:20]`, which is `adult#001` upward.
`meal_with_bolus.py` selects `sorted(titrate.titrated_subjects())[:40]`, which sorts
alphabetically and returns `adolescent#001` upward.

So gate 1 was measured on twenty adults and gate 2 on forty adolescents, and the sentence saying
they do not overlap compares them directly.

Rerun on one adult panel, the meal reads 92.5 minutes at eleven times the published rate against
the stored 67.5 on adolescents. The gate allows 20 minutes either side of the real 112, so the
same configuration fails on one panel by 44.5 minutes and passes on the other by 19.5. The stock
arm reads 102.5 on both, which is why the disagreement was not visible from the headline figures.

A second defect sits underneath it. The statistic is degenerate for a fifth of subjects: the
stored file carries a tenth percentile of 0 minutes in both arms, and a trough to peak of zero
means the peak sits at the meal moment and glucose only falls afterwards, so the bolus dominated
and no meal rise was measured. Those runs enter the median that a 20-minute criterion is read off.
They are now dropped and counted.

Neither defect says the two-timescale liver works. Both say the gates cannot currently decide it,
and that a negative result was recorded with more confidence than its measurement supported.

This is the fourth instance in one week of two numbers disagreeing because they were taken over
different people, after issue 43, the rescue treated-share window, and the panel that broke the
layer ladder. The provenance stamp binds population, settings and code, and does not bind
membership. Every one of these would have been caught by a stamp that recorded the subject list
and an analysis that refused to compare two measurements whose lists differ.

## 45. A gate deciding a mechanism was read off a median the mechanism does not move

Found 30 August 2026, rerunning the two-timescale liver sweep after issue 44 put both gates on
one panel.

Two defects, the second underneath the first.

The sweep dropped degenerate meals rung by rung, so each fast fraction was medianed over the
subjects that happened to give a meal rise at that fraction: 31 of 40 at a fraction of zero,
falling monotonically to 27 at one. Five rungs, five panels, differing by six people. The stored
meal read 125 min at one end and 105 in the middle and 115 at the other, and on one panel of the
25 subjects usable at every rung it reads 115 at every rung but one, which reads 120. The entire
apparent movement was the membership. This is issue 44 one level down and inside the commit that
fixed issue 44, which is the fifth instance in a week.

That flat 115 then looked like a second finding, that the liver leaves the meal alone. It is not.
Paired on the same 25 subjects, stock against the whole gain on the fast delay, the mechanism
moves 22 of them, ten by an hour or more, individual subjects running from -210 min to +100. The
paired median is 0.0 min with a 95 per cent interval of -5.0 to 20.0. The movements cancel.

So gate 2 passes at every rung including the one with the mechanism switched off, and the sweep
is decided by gate 1 alone. Gate 1 selects a fast fraction of 1.0, at which the published slow
pathway carries none of the gain, so what the sweep adopts is a single-timescale liver at 10.5
times the published rate. The two-timescale mechanism is not what satisfied the gates.

The audit's conclusion that the meal response is lost above twice the published rate was read off
this same median, on a different panel again.

The rule this adds is about what a gate is allowed to be. A statistic used to decide a mechanism
is checked against that mechanism first, by switching it off and requiring the number to move, and
paired per subject rather than compared between medians. `docs/CAPABILITY.md` already scores
against the distribution of real individuals for this reason. A gate does not, yet: trough to peak
runs 60 to 365 min across this panel against a criterion of 112 plus or minus 20, so a cohort
median can sit inside the band with almost no subject in it.

`examples/liver_meal_gate_paired.py` is the producer, and it belongs in front of any gate before
the gate is used.

## 46. A meal protocol measuring one meal was used to judge a mechanism, and read 35 minutes off real

Found 30 August 2026, building the per-person meal comparison the studies database made possible.

`examples/meal_with_bolus.py` gives a subject one 60 g meal at midday, on a fixed seed with no
layers, and searches for the peak over the following 720 minutes on `Result.bg`. Every gate about
the meal response in `docs/PADOVA_AUDIT.md` was read off it.

Four things were wrong with it as a comparison against real people, and the fourth is the one that
mattered.

It reads `bg`, where the real side can only be a sensor. Sensor error near 12 mg/dL moves where a
minimum and a maximum fall on a slowly turning trace.

It locates the peak by `argmax` of the difference against a counterfactual run of the same subject
eating nothing. No real trace has a counterfactual, and the docstring already said the absolute
trace was the right choice.

A 720 minute window does not select a meal. Isolation is what admits one on the real side, and
only the evening meal has nothing logged after it, so the share of admitted meals falling between
16:00 and 21:00 runs 0.32 at a 180 minute window and 0.77 at 720 on 964 real people. The simulated
meal is eaten at midday.

And it measures one meal per subject, where the quantity being compared is a property of a person.
Real participants contribute hundreds of meals each, and their within-person interquartile range
is 90 minutes at a 240 minute window against a between-person spread of 50 across the tenth to
ninetieth percentile of their medians. So the larger of the two components was absent from the
simulated side by construction, and the whole simulated spread sat in the smaller one.

The consequence is measurable in both directions. At a 240 minute window this producer reads 115
minutes where the real reference reads 80 and a matched protocol reads 80, so the gap the liver
work was trying to close belonged to the measurement. And pairing the liver arms on it gives six
to ten subjects of twenty moving by an hour or more at every window, where the same pairing on a
person's forty meals gives a difference of at most one 5 minute sampling step. One meal responds
to the liver. A person's typical meal does not.

The rule this adds sits beside issue 45. A statistic compared against real people is measured on
the same unit as the real one. If the real quantity is a property of a person, one observation per
simulated subject does not measure it, however carefully that observation is controlled.

## 47. The tool that proves a change inert passed without testing anything

Found 31 August 2026, adding `bolus_series` to `Result` so a meal that was bolused could be told
from one that was not.

The settings store carries a fingerprint over nine files and refuses a store produced by code that
no longer matches, which is right: the failure it prevents is a settings ladder run against
different physiology. `examples/restamp_settings.py` is the escape hatch. It runs a sample of
subjects with the change in place, stashes the working tree, runs them again, and re-stamps only
if every measure agrees.

The stash is the whole mechanism and nothing checked that the change was in it. With the change
committed and only a measurement file uncommitted, it stashed the measurement file, ran the same
code twice and reported three subjects identical. It would have re-stamped the store on that.

The signature is the one this log already names: two arms that agree to every decimal have usually
been handed the same configuration. Here they were the same configuration, by construction, and
the report read as the strongest possible pass.

Fixed two ways. It now refuses unless one of the fingerprinted files actually differs from HEAD,
and it takes `--worktree REF`, which checks the reference commit out separately and probes there
instead of stashing. The population and the settings store are not in git, so the second checkout
symlinks them from the first: both sides have to read the same subjects and the same settings or
the comparison measures the population.

The change itself was then verified properly, five subjects across three age classes at 28 days,
every measure identical including the summed glucose traces, and the store re-stamped from
578597f67d50c246 to d98cc5df0c709645.

The rule this adds is narrow and worth stating anyway. A check that compares two arms states what
made them differ, and refuses when nothing did. An escape hatch from a guard needs the same
scrutiny as the guard, and this one had less.

## 48. A published protocol was matched to the wrong meal and the wrong denominator

Found 1 September 2026, one day after the comparison it invalidates was committed.

`examples/hinshaw_meal.py` reproduces Hinshaw et al. (Diabetes 2013;62:2223-2229) so the model's
meal fluxes can be read against a human measurement. Two errors, and both were in the protocol
rather than in the code.

The meal was the wrong one. The paper's methods describe a 10 kcal/kg meal at 55 per cent
carbohydrate and, separately, breakfast, lunch and dinner with about 50 g of carbohydrate each.
The first is the standardisation meal eaten between 17:00 and 17:30 on the evening before the
first study day. The producer used it, giving subjects a median 112 g where the study meals carry
about 50.

The denominator was the wrong one. The tracer is dosed per kilogram of fat-free mass and the
companion paper states rates are expressed that way. This model reports per kilogram of body
weight. Hinshaw's cohort ran 53.6 kg of fat-free mass against 74.7 kg of weight, so every
reference number was 28 per cent too large as quoted.

Both errors pushed the same way and one hid the other. Production suppression read 43.3 per cent
against a reference of 43.5 to 52.3 and was reported as a match. Corrected, it reads 18.6 per cent
against 43.5 to 52.3, and the model suppresses less than half as much as measured. Fasting
production read 13.5 against 16.2 to 19.5 and was reported as three-quarters of the human rate;
corrected, the reference is 11.6 to 14.0 and 13.5 sits inside it.

A third thing surfaced that is not an error here. Hinshaw's measured appearance implies about 59 g
of glucose entering the circulation from a meal the methods describe as about 50 g of
carbohydrate, on the fat-free normalisation, and about 83 g on body weight. The lower reading is
the more plausible of the two and is still 18 per cent above what the meal is said to contain, so
the appearance comparison carries that uncertainty and cannot be resolved from the paper.

The rule is one this log already has in another form. A reproduction of a published protocol
states which meal, which window and which denominator, and checks the reference against something
it must satisfy: a meal cannot deliver more glucose than it contains, and a flux quoted per
kilogram has to say per kilogram of what.

## 49. Two like-for-like meal comparisons on one quantity reached opposite conclusions

Found 2 September 2026, resolving a contradiction between study 17 and this week's measurements.

Study 17 reports that the simulated rise per 10 g of carbohydrate "remained inside the real 15.9
to 19.7 mg/dL at every scale, so the meal failure is one of timing rather than of magnitude".
`sim_meal_shape.json` reports a simulated 13.0 against a real 23.6 on unbolused meals. Same
physical quantity, opposite verdicts, and each comparison is internally consistent.

The real references agree once the definition is matched. Measured on identical Loop meals from
the studies database, 150 subjects, uncovered by the same bolus rule, the rise is 21.1 mg/dL per
10 g from the trough and 18.9 from the reading at the meal at a 240 minute window, and 22.3 and
19.7 at 360. The 19.7 is the top of the Commons range study 17 quotes, so two real cohorts on two
continents agree to a decimal once they are asked the same question. The apparent disagreement was
the trough clock against the entry clock, worth 2.2 to 2.6 per 10 g, plus a median over people
rather than over meals.

The simulated sides differ for a reason that is not a definition. `meal_response.py` states in its
own first paragraph that the quantity is "a property of the metabolic model, so it is measured on
the bare patient with no layers", and it runs `layers=()` under a basal-only controller.
`sim_meal_shape.py` runs the full layers under the correction loop. So study 17 compared a
simulated subject with no controller against real people whose loops were running, and the
simulated figure is high partly because nothing was removing the rise.

The gap between the two simulated protocols is 21.5 with no loop against 13.0 with one, so the
simulated loop removes 8.5 mg/dL per 10 g from an unannounced meal. Real Loop participants, whose
loops were also running, reach 23.6. Whatever the real algorithm does to an unannounced meal, it
takes far less out of it than this one does.

Neither producer is wrong about what it measures. The error is in the sentence study 17 draws from
it, which compares a property of the metabolic model against a population running closed-loop
therapy and concludes the magnitude is right. The conclusion that survives is narrower: the
model's meal rise is right when nothing is dosing, and the gap opens once a controller is.

The rule is one this log keeps finding in new forms. A comparison is like-for-like in every
respect or in none, and a controller running on one side and not the other is as large a mismatch
as a different definition. `meal_response.py` says what it measures plainly; the paper quoted it
against something else.

## 50. The controller was blamed for a difference that was the panel

Found 2 September 2026, immediately after issue 49 attributed 8.5 mg/dL per 10 g of an unannounced
meal's rise to the built-in correction loop.

Tim's objection was that the built-in loop is a substrate rather than part of the person, so
nothing it does bears on the bench. Running the same meals under four controllers was meant to
test whether the algorithms actually benchmarked behave the same way.

Read off each run's own common panel, they looked very different: 18.4 mg/dL per 10 g with no
modulation, 15.8 under the Control-IQ stand-in, 13.0 under the built-in loop. That reads as the
built-in loop removing 5.4 and the stand-in 2.6.

Intersected on the ten subjects present in all four runs, they are not different at all:

    no modulation        10.3 / 17.1 / 20.8
    oref0 SMB            11.2 / 14.1 / 17.6
    Control-IQ stand-in   9.6 / 17.4 / 19.9
    built-in loop        12.6 / 15.3 / 19.8
    real, Loop           14.0 / 23.6 / 34.7

The built-in loop removes 1.8 rather than 5.4, the stand-in removes nothing, and the spread across
four controllers is 3.3 mg/dL per 10 g against a gap to real of 6.5 to 9.5. Each run's panel was
set by which subjects cleared 20 admitted meals in every liver arm of that run, and that differed
by controller, so the columns were different people.

So the controller is not the explanation and issue 49's attribution is withdrawn. The shortfall is
in the model rather than in what is driving it, which puts it back where the liver measurements
are.

Two things bound this. The common panel is ten subjects, limited by oref0, and the liver arms in
these runs terminated 22 and 17 subject-arms of 40 against stock's 3, so nothing about the arms
should be read from them at all. And oref0's own usable panel is 10 against 34 for the others,
because it microboluses on a rise and its own delivery reclassifies an unannounced meal as covered
under the one unit threshold this measurement uses.

The rule is the one this log already has twice this week, in a third place. A comparison across
conditions holds the panel fixed across those conditions, and a panel defined by what each
condition happened to admit is not fixed.

## 51. The simulated meal rise was divided by grams eaten and the real one by grams logged

Found 4 September 2026 in a review of the meal comparison, before the measurement that settles it.

`examples/sim_meal_shape.py` read its meals from `Result.meal_log`, which holds every scheduled
meal at the grams that reached the gut, and isolated each index meal from every other eaten meal.
`examples/real_meal_shape.py` can only read what a person entered: the index meals are the logged
entries, the denominator is the logged grams, and a meal nobody logged neither counts nor breaks
another meal's isolation. The two sides therefore measured rise per gram over different grams and
admitted meals under different rules, and the repository already assumes the two gram counts
differ, since `run.py` scales the schedule so that 192 g eaten a day logs as 162.

The fix on the simulated side is to keep the record a real person leaves. `BehaviourScenario` now
writes `(minute, eaten grams, announced grams)` per meal into `Result.announced_log`, and the
producer takes `--record announced`, which indexes the entered meals, divides by the entered
grams and isolates from entered meals and rescues only. The settings store was re-stamped rather
than retitrated, since nothing reads the new column during a run, and the five probed subjects
agreed to nine decimals.

Measured under oref0 SMB on 40 subjects over 42 days at seed `BENCH`, stock physiology, against
the eaten record of 2 September on the same subjects, paired per subject
(`sim_meal_shape_announced_oref.json` against the stock arm of `sim_meal_shape_asym_oref.json`,
paired by `examples/meal_record_pairing.py` into `meal_record_pairing.json`):

    window   n   rise per 10 g, eaten   announced   paired difference [95 per cent]
      180   37                  10.3        10.2      -0.1  [-0.7, 0.4]
      240   35                  11.1        11.8       0.4  [-0.1, 1.1]
      300   22                  10.7        12.2       1.0  [ 0.0, 1.9]

    window   n   time to peak, eaten   announced   paired difference
      180   37                  80.0        82.5       2.5  [-2.5, 5.0]
      240   35                  87.5        95.0       5.0  [ 0.0, 10.0]
      300   22                  96.2       105.0      10.0  [ 1.2, 22.5]

The three terminations are the same three subjects on the same days in both files, so the runs
are one realisation read two ways and the differences above are the protocol alone.

On rise per gram the defect is small. The person template's estimate is unbiased
(`CARB_ESTIMATE_BIAS` is 1.0 with a 25 per cent coefficient of variation), so changing the
denominator from the plate to the entry adds noise and no offset, and the 0.4 at 240 min is
inside its own interval. The review that found this defect projected a correction of 2.8 to 5.0
mg/dL per 10 g by applying the 0.84 logged-to-eaten ratio to the real covered rise. That
arithmetic was entirely the ratio. With the bias at 1.0 the protocol contributes nothing to it,
and the ratio itself is a literature assumption the record cannot test, since the real side has
no plate to compare its entries against. Whether a bias below 1.0 belongs in the person layer is
a separate question, to be pre-registered against the whole statistic table as `CONTRIBUTING.md`
requires, and this measurement neither supports nor refutes it.

That question was put on 4 September 2026 (`examples/carb_bias.py`, with the predictions and
the result in its docstring). A bias of 0.84 moved the covered rise on the announced record from
11.2 to 12.8 mg/dL per 10 entered grams, +1.8 [0.8, 2.8] paired on 32 subjects under oref0 SMB,
below the 13.3 the denominator gives on its own, and moved the eaten-record rise -0.2 [-0.7,
0.7]. It failed the registered rule and was not adopted.

On duration the matched protocol moves the simulated side away from the real one. A meal nobody
entered no longer breaks isolation, so a window that used to reject an index meal for a snack
inside it now admits it, and the snack's rise lands inside the window and moves the peak later:
four more meals a subject at 240 min and eight more at 300. The real side has always been
measured this way. Under the eaten record the simulated median at 240 min stood 7.5 min above
the real 80; under the record the real side is forced to use it stands 15 above.

The rule is the one issue 48 states for a published protocol, applied to a record: a comparison
against what people logged is made on what the simulated person logged, and the eaten record
is kept for questions about the model rather than for questions about the fit to data.

## 52. The real meal reference pooled children with adults, against an adult panel

Found 4 September 2026 while measuring insulin delivered by the peak (`examples/insulin_by_peak.py`),
when the daily insulin of the real reference came out at 38.7 U/day against a simulated 69.1 and
the first place to look was who the reference was.

`examples/real_meal_shape.py` admitted every participant of a study. Loop enrolled from infancy:
371 of its 919 participants are under 18, and 297 of the 767 with twenty admitted meals at a 240
minute window. The simulated panel is adults, `adult#001` onward, so the reference the rise gap
has been quoted against since 30 August 2026 was a third children and adolescents, whose meals
rise more per gram and whose daily insulin is a fraction of an adult's. ReplaceBG is unaffected,
its youngest participant being 19.

The fix is an age floor in the query, `--min-age`, at 18 by default, recorded in the file, with the
bind parameters moved into one function so the three callers of the query (the reference, the
insulin measurement and the keystone test) admit the same meals. Regenerated on the adults the
Loop reference at 240 min reads:

    quantity, Loop at 240 min          pooled (767)   adults (470)
    rise per 10 g, all meals               17.0          15.8
    rise per 10 g, covered                 16.5          15.1
    rise per 10 g, uncovered               23.6          21.4
    time to peak, min                      80            85
    people at 180 min, both studies        964           654

The simulated covered rise under oref0 SMB, 11.5 mg/dL per 10 entered grams, stands 3.6 short of
the adult reference where it stood 5.0 short of the pooled one, and the time to peak, 95 against
85, is 10 min late rather than 15. The gap did not close. The carbohydrate bias verdict of the
same day is unchanged by the move, since its 12.8 is below the half-way mark on either reference
(13.9 pooled, 13.2 adult) and below the 13.3 the denominator gives on its own. `liver_brake.py`
carried the pooled uncovered figure as a constant, corrected here without rerunning its arms,
whose simulated numbers do not depend on it; `liver_brake.json` from before this date prints the
pooled figure in its comparison column.

The pattern is issue 44 again, two sides measured on different populations, one level up: the
protocol and the definition were matched on 2 September and the people were not.

## 53. Three documents quoted a spread and a calibration that no file on disk produced

Found 6 September 2026 while bringing the studies up to the measurements, on checking each
quoted figure against the file named beside it.

The spread paper, `FIDELITY.md` and the new technical shortcomings article carried the
between-subject spread ratios of the 20 August run (mean glucose 0.64, 0.75 and 0.41 of the three
references; time below 54 mg/dL 4.75, 5.11 and 0.91), with the settings digest and commit of that
run in the spread paper's provenance table. `spread_ratio.json` had been regenerated on 24 August
by the full rebuild, on the settings every other figure now stands on, and reads 0.57, 0.67 and
0.46 on mean glucose and 4.38, 4.73 and 1.09 on time below 54. The direction of every finding is
unchanged and every new value sits inside the old interval. The as-observed hypoglycaemia ratios
moved further, from 7.29, 8.80 and 1.87 to 6.81, 6.08 and 1.11, so the sentence saying that
including the terminated runs widens the Commons ratio considerably was wrong on the current
population and has been rewritten.

The validation paper, `DESIGN_HYPOGLYCAEMIA.md` and the article also quoted the hepatic defence
calibration on "150 adults" (undefended median 0.48 mg/kg/min at 55 mg/dL, 41 of 110 at zero,
1.06 at a gain of 0.25). That `hypo_defence_gain.json` had been moved to `archive_pre_review/` on
17 August, carried no provenance stamp, and predated the population rebuild. The calibration was
rerun on all 300 adults with the pre-registered expectation of an undefended median near 0.5,
about a third at zero and a recommended gain of 0.05. It reads 0.46 with 86 of 230 at zero, and
recommends 0.05; the documents now quote it (0.57 at 0.05, 1.03 at 0.25, 79 of 232 at zero).

Neither correction changed a verdict. The defect is the one this log records most often: a
number that could not be traced to the file said to hold it, here because the file had been
replaced by a rebuild in one case and archived in the other, and the prose was not reread against
either.

## 54. The oref adapter handed oref about half the insulin on board, on a curve AndroidAPS does not use

Introduced 11 August 2026 in 11c7ffb, when the oref0 adapter was added, and found 9 October 2026
from outside the package: the oref digital twin rebuilds insulin on board from an exported run's
treatments with oref0's own `lib/iob`, and on one subject over three days its figure sat a median
1.09 U above the one this adapter had logged.

Two defects, one in the ledger and one in the curve.

The ledger. `OrefController.policy` pruned with `margin=CURVE_TICKS * sample`, 240 minutes, and
`LoopInputs.prune` added the margin to the cutoff, giving `minute - 300 + 240`. Every bolus and
basal deviation more than an hour old was dropped before oref saw the ledger. The docstring's
reasoning ran backwards: a forward tick reads the ledger at a later time, where an old entry is
older still, so the duration of action before now is the only cutoff that changes no arithmetic.
The existing test for pruning called `prune` without the margin and so could not see the call
site. On adult#001, untitrated, two days, seed 7, the insulin on board oref was handed averaged
1.31 U; with pruning off it averaged 2.60 U.

The curve. `LoopInputs` computed insulin on board with the package's `iob_fraction`, which
leaves more of each unit on board between one and four hours than the exponential curve of
oref0's `lib/iob/calculate.js`, the curve every AndroidAPS insulin plugin uses (0.840 against
0.764 at 60 minutes, 0.480 against 0.411 at 120, at a 300-minute duration and 75-minute peak).
An adapter standing for AndroidAPS therefore reported more insulin on board than AndroidAPS
would. The Boost adapter inherits the same methods.

Fix: `prune` takes no margin and cuts at the duration of action, and the AndroidAPS adapters'
ledger arithmetic uses `oref_iob_fraction`, added to `therapy/insulin.py`. The reference loop,
the pump-limit enforcer and the simulated body keep the package curve; they do not stand for an
application. With both fixes the twin's rebuild sat a median 0.27 U from the adapter's figure
(74% of cycles within 0.5 U, against 27% before), the residual being the twin's 0.05 U temp
pulses and its assumption that no temp is running at each decision.
`test_a_dose_over_an_hour_old_still_counts_after_a_cycle` and
`test_the_adapters_compute_insulin_on_board_with_oref0s_curve` both fail on the code before the
fix.

Measured on 9 October 2026 by `examples/issue54_effect.py` (`docs/measurements/issue54_effect.json`):
twelve adults with settings titrated the same day, 28 days on the benchmark seed under oref0 SMB,
run once with both defects restored and once as fixed. Before the fix oref was handed a mean
1.70 U of insulin on board (median 1.62, range 0.97 to 2.59); after it 2.73 U (2.70, 1.64 to
3.81), a paired rise of 1.03 U [0.90, 1.16]. On the sensor reading:

| | Before: median, mean (range) | After: median, mean (range) | After − before, mean [95% CI] |
|---|---|---|---|
| Time below 70, % | 4.12, 4.12 (1.8–6.5) | 2.21, 1.96 (0.3–3.4) | −2.16 [−2.69, −1.69] |
| Time below 54, % | 1.19, 1.29 (0.4–2.6) | 0.55, 0.59 (0.1–1.3) | −0.70 [−0.99, −0.44] |
| Time in range, % | 86.97, 84.03 (72.6–91.1) | 86.06, 84.35 (74.8–94.1) | +0.32 [−1.09, +1.71] |
| Time above 180, % | 9.40, 11.85 (3.4–21.5) | 12.05, 13.69 (3.2–22.8) | +1.84 [+0.86, +2.88] |
| Mean glucose, mg/dL | 131.7, 131.9 | 139.1, 137.7 | +5.85 [+4.78, +7.03] |

Time below 70 fell in all twelve subjects, rescue carbohydrate events from 691 to 362, and
delivered insulin from 64.4 to 59.7 U a day. True glucose moved the same way (time below 70
−2.04 [−2.56, −1.55]). The defect roughly doubled the oref0 arm's time below range while leaving
time in range where it was, which is the signature a comparison of algorithms on hypoglycaemia
cannot see past. Every oref0 figure produced between 11c7ffb and f0e5e45 is therefore suspect on
hypoglycaemia, including the oref0 cells of the group floor, `rank_drivers.py` and the night
studies run under oref0, and needs rerunning before it is quoted. The Boost arm changes by the
curve alone and has not been measured.
