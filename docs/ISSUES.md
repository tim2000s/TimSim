# Testing and issues log

Every defect found in this package and in the work built on it, in the order it was found, with
how it surfaced and what was done about it. Defects introduced during the investigation are
logged the same way as ones that were already here, and are marked as such, because a log that
records only other people's mistakes is not a record of anything.

The dominant pattern is worth stating at the top. Of the twenty-four entries below, five are
coding errors. Most of the rest are measurements that were correct arithmetic on the wrong
comparison, or figures that could no longer be traced to the code that produced them. The
project's own standing rule, that a comparison must be computed the same way on both sides,
caught more of these than any test did.

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
