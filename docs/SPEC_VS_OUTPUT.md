# What the documents claim against what the measurements contain

An audit of every quantitative claim in the documentation against the rebuilt measurement set,
made before the papers are rewritten so the rewrite has a list rather than a memory.

The first pass was made on 18 August 2026 and covered nine documents by inspection. This is the
second, made on 20 August 2026 across sixteen documents, with every claim traced to the file and
key that backs it or recorded as having no backing file at all. Where the two passes disagree,
this one supersedes.

The short version is that every document predates the rebuild and none can be quoted as it
stands. That is expected: the defence gain moved, the seeding changed, the panels moved onto
titrated settings, the cohorts were rebuilt from a corrected requirement, and the population grew
from 100 subjects to 600. What was not expected is how much cannot be checked at all.

## The scale

Each claim is one number with a meaning. Superseded means a current measurement covers it and
disagrees. Unverifiable means the measurement it needs is archived, absent, or exists only as a
log that the next rebuild overwrites.

| Document | Superseded | Unverifiable | Current | Real data | Structural |
|---|---|---|---|---|---|
| docs/paper/validation_paper.md | 213 | 9 | 67 | 56 | 35 |
| docs/FIDELITY.md, lines 1-650 | 154 | 133 | 95 | 89 | 95 |
| docs/FIDELITY.md, lines 651-end | 72 | 256 | 16 | 124 | 37 |
| docs/LADDER.md | 64 | 6 | 7 | 7 | 17 |
| docs/EVIDENCE.md | 15 | 63 | 5 | 21 | 20 |
| docs/README.md | 17 | 10 | 9 | 5 | 4 |
| docs/GUIDE.md | 14 | 7 | 6 | 1 | 7 |
| docs/CAPABILITY.md | 13 | 13 | 4 | 10 | 35 |
| docs/STUDIES_AUDIT.md | 12 | 5 | 3 | 2 | 6 |
| docs/METHODS.md | 11 | 13 | 5 | 34 | 27 |
| docs/VALIDATION.md | 11 | 27 | 0 | 8 | 24 |
| docs/PADOVA_LIMITS.md | 11 | 6 | 8 | 7 | 15 |
| docs/OVERVIEW.md | 10 | 5 | 6 | 3 | 3 |
| docs/OSAID.md | 4 | 17 | 1 | 4 | 21 |
| docs/SIMULATOR.md | 3 | 6 | 2 | 0 | 3 |
| docs/MODEL.md | 2 | 5 | 1 | 14 | 28 |

That is 626 superseded and 581 unverifiable. `docs/VALIDATION.md` has no current claims at all,
because the only level with a post-rebuild measurement is level 3 and every level-3 count in it
has moved.

## Why so much cannot be checked

Four structural causes, in order of how much they account for.

Three stages of the rebuild wrote no measurement file. The clamp, the capability table and
production during a low printed a table to standard output and stored nothing, so their figures
lived in a log that the next run overwrote. The clamp is the calibration basis for the hepatic
defence gain and the capability table is the source of the headline signature count. All three
now write a stamped file and all three have been rerun, so this cause is closed. Issue 32 records
the rest of that story.

Six producers are in no pipeline. `capability_decomposition.py`, `calibrate_hypo_defence.py`,
`calibrate_glucagon.py`, `calibrate_exercise.py`, `calibrate_egp_floor.py` and
`hypoglycaemia_arms.py` are invoked by neither `rebuild_all.sh` nor `standalone_parallel.sh`.
Their outputs were archived by the rebuild and nothing was going to bring them back, so studies
09, 10 and 16 cannot be written from anything on disk.

Eight files in `docs/` predate the rebuild and were never rerun by it: `power.json`,
`validation.json`, `replication.json`, `ranking.json`, `gate_reference.json`, `hypo.json`,
`visentin.json` and `visentin1.json`, dated between 1 and 8 August. The last two record a `loop`
layer that no longer exists. Everything in `EVIDENCE.md` about ranking, gating, negative controls
and faults rests on them, as does the whole Visentin comparison in `FIDELITY.md`.

The Boost evidence is not a measurement. `docs/OSAID.md` and `docs/EVIDENCE.md` take about forty
figures from constants hardcoded in `timsim/validation/boost.py` and stamped 11 August, six days
before the refit, against a population that no longer exists.

## Claims that are now wrong, with their replacements

The full per-document tables are long. These are the ones that change a conclusion rather than a
decimal.

| Claim | Where | Now |
|---|---|---|
| the population is 100 subjects | README, OVERVIEW, GUIDE, SIMULATOR, FIDELITY, METHODS, EVIDENCE | 600, of which 330 are titrated. The exposure arithmetic in README and EVIDENCE is computed from 2,800 subject-days against a real 16,800 |
| hypoglycaemia group effect 1.63 spreads | FIDELITY, LADDER, validation paper | superseded three times, and it is no longer one number. Measured in four cells it is 1.06, 1.29, 1.72 and 3.65, so the cell has to be named with it |
| indistinguishable from real people on four of six measures, everything except how low it goes | validation paper | three of six, and the identity has inverted: time below 70 agrees while time in range and time above 180 do not |
| titration closes about half of the settings gap | validation paper, METHODS | about 1 to 4 per cent depending on the denominator. 272 of the 306 subjects that clear the floors do so on basal alone and never reach the correction factor, and the population median correction factor moves from 18.6 to 18.9 mg/dL per unit |
| four subjects clear the floors at no combination tried | validation paper | 24 of 330, unevenly across the age classes at 7 of 21 children against 8 of 199 adults |
| titration cannot run under the open-loop arm because it spends 0.25 per cent of time below 70 mg/dL and never exercises the settings | METHODS, CLAUDE.md, `therapy/titrate.py` | it spends 2.39 per cent, more than the reference loop's 1.92 on the same rung, and moves 19 of 90 subjects. The design choice stands on exclusion instead: 15 of 90 subjects clear at no combination there against 4 under the reference loop. Recorded as issue 42 |
| on the layered bench most incomplete runs end high | validation paper, METHODS, PADOVA_LIMITS | 54 of 61 end low, and in the DCLP3 Control-IQ cell all thirteen do |
| capability, ten of ten signatures in range | CAPABILITY, FIDELITY, STUDIES_AUDIT | five of ten with the padding the scorer applies, three of ten without it, on 73 of 80 completed runs against a documented 66. See the note below, since the convention decides the number |
| production at a 55 mg/dL clamp plateau is 0.14 mg/kg/min, and 0.01 at 45 | PADOVA_LIMITS, STUDIES_AUDIT, OVERVIEW | 0.49 and 0.46, both inside the human 0.42 to 0.84. The premise for counterregulation is inverted |
| production during a low is 1.28 mg/kg/min and holds rather than rising | MODEL, METHODS, PADOVA_LIMITS | 1.11 against 2.10 at euglycaemia, so it falls, at a ratio of 0.53 |
| autosens is pinned at 1.0, so any oref hypoglycaemia figure is an upper bound | OSAID | autosens is implemented and runs by default. Both arms are measured at 4.85 and 5.48 per cent below 70 mg/dL, so the caveat qualifying every oref figure no longer applies |
| the classifier separates at 0.709, and the axis is hyperglycaemia | EVIDENCE, FIDELITY | 0.784, and the heaviest feature is the sixty-minute autocorrelation |
| the ladder carries nine of 47 movements | STUDIES_AUDIT, SIMULATOR | six of 47, and the site layer now carries none |
| the insulin week-to-week CV responds to the sensitivity mechanism under every closed loop | `analysis/signatures.py`, study 03 | under one driver of four. Boost gives -1.78 [-2.91, -0.38]; the built-in loop and oref0 SMB span zero. Removing the day-to-day term alone moves nothing anywhere, since a weekly average divides it by roughly the square root of seven |
| the outcome spread after a stuck high is inside the real range at 27.0 | FIDELITY, GUIDE, OSAID, VALIDATION, EVIDENCE | 24.58, below the range. The verdict reverses |
| the population is not reproducible from its seed | METHODS | repaired on 15 August in `d388796`. The paragraph tells a reader the opposite of the truth about the property the provenance argument rests on |
| Commons reference 79.60 across 71 users | METHODS | 80.05 across 77 users |
| the site layer costs three signatures | GUIDE | it gains one, four of eleven without it against five with |
| six graded levels of check | README, GUIDE | seven |
| level 7 resolves a defect at twelve subjects, an A/A paired standard deviation of 0.218 and a detectable shift of 0.176 | VALIDATION, EVIDENCE | measured post-rebuild in `ranking_power.json`: the standard deviation is 0.492 at twelve subjects and the detectable shift 0.398, so three of the four named defects fail at that size. At forty the floor is 0.231 and every shift clears it on the point estimate, but a standard deviation from forty pairs has a relative standard error near 11 per cent, so the floor is 0.231 give or take 0.026 and the shifts of 0.24 (stale readings) and 0.26 (sensitivity error) sit inside that; two defects separate clearly and two are marginal. The sizing projections of 0.105 at thirty-four and 0.061 at a hundred were extrapolated from the stale spread and are superseded by measurement at three sizes |
| real meals rise for 112 minutes, quartiles 70 to 165, over 5,189 meals | PADOVA_AUDIT, PADOVA_LIMITS, STUDIES_AUDIT, `meal_with_bolus.py`, `patient/varying.py` | not reproducible as stated, because the analysis window was never recorded and the window sets the value. Measured on 654 adults and 172,028 meals in `real_meal_shape.json` (adults since 4 September 2026, issue 52), the pooled median runs 70 min at a 180 minute window to 135 at 720, so 112 corresponds to something near 360 to 480. The simulated side used 720 |
| no value of `ki` meets both the clamp and the meal, so the divergence is structural | PADOVA_AUDIT entry 3 and its summary table | withdrawn rather than replaced. The two gates were measured on different populations (issue 44), the meal gate returns the same verdict with the mechanism switched off (issue 45), and the protocol it was read off measures one meal where the real quantity is a property of a person (issue 46). Nothing has been shown either way |
| the two-timescale liver satisfies both gates at a fast fraction of 1.0 | `liver_two_timescale.json` | at that fraction the published slow pathway carries none of the gain, so the configuration is a single-timescale liver at 10.5 times the published rate. The mechanism in `varying.py` contributed nothing at the point of adoption |
| the simulated meal response is comparable to the real one | PADOVA_LIMITS, FIDELITY | at a matched 240 minute window the old protocol reads 115 min against a real 80. Measuring every meal a subject eats over 42 days with the person's layers on reads 80. The gap belonged to the protocol |
| the simulated rise per 10 g under oref0 SMB is 11.5 against a real 17.0, and the gap is partly the denominator | ISSUES 49 and 50, the review of 4 September | the denominator differed (issue 51) and correcting it moves the rise 0.4 mg/dL per 10 g [-0.1, 1.1] at 240 min, paired on 35 subjects, so the gap to real stands. Under the matched record the simulated time to peak at 240 min reads 95 against the real 80, where the eaten record read 87.5. The real 17.0 pooled children with adults (issue 52); the adult reference is 15.8, covered 15.1, time to peak 85 |

## The capability count depends on a convention no document states

`signatures.in_real_range` widens each published interval by ten per cent of its span before
asking whether a median falls inside. Rerun on 20 August 2026 the shipped configuration puts five
of ten medians inside with that padding and three of ten without it. The two that only the
padding admits are glucose variability, at 34.76 against 29.5 to 34.3, and the rise tail, at 3.45
against 3.7 to 6.6.

`FIDELITY.md` does say so, at line 81, for the ablation table it quotes, and
`layer_ablation.py` prints the same sentence beneath its own table. `CAPABILITY.md` does not, and
neither did `capability_table.py` until it was given an output file. So the convention is stated
where the count is eleven and unstated where the count is ten, which is the reverse of where it
matters, since the ten-signature panel is the one the headline is drawn from. The figure the
documents carry, four of ten, matches neither convention.

The rewrite has to state the convention wherever it states the count, because the choice moves
the headline by two signatures out of ten. The padding is defensible, since the intervals are four
cohort medians rather than a sampled distribution, but it cannot be invisible while it is doing
that much work.

Completion also moved, from a documented 66 of 80 runs to 73 of 80, and the ordering by driver
inverted. The document records oref0 SMB as the worst at 15 of 20 and the built-in loop as the
best at 18. The current run gives oref0 19 of 20 and the built-in trend loop 20 of 20, with the
worst being the open-loop and Boost arms at 17 each. Since a subject that stops early is excluded
from every percentile above, the columns are conditioned on a different set of survivors than the
ones the document describes.

## Documents that need rewriting rather than renumbering

`docs/paper/validation_paper.md`. Roughly 56 per cent of its quantitative content is superseded
and four load-bearing arguments have changed sign or identity. The sections needing rebuilding
rather than correcting are what survives the comparison, the group effect, settings, and
counterregulation, along with the completion-direction argument used twice as a methodological
point. One row of its distinguishability table cannot be reconstructed at all without running
`cohort_variation.py` on the fitted controller.

`docs/LADDER.md`. Sixty-four of about a hundred claims move, nine of the twelve landing rows point
the model in a different direction, and the ladder on disk holds ten subjects where the document
describes twenty. Its power argument turns on that difference.

`docs/VALIDATION.md`. No current claims. Levels 1, 2, 4, 5, 6 and 7 have no post-rebuild
measurement.

## What has to be rerun before the rewrite

| Measurement | State | Why |
|---|---|---|
| layer ablation | done, 11 min at twelve workers | six arms, now stamped and binding |
| hyperglycaemia gap | done, 23 min at twelve workers | four arms, same |
| capability table | done, 22 min | writes a file for the first time, so the headline count is checkable |
| clamp | done, 2 min | same, and it is the calibration basis for the defence gain |
| production during a low | done, 5 min | same |
| the validation suite, ranking and gate | outstanding, not yet timed | levels 1, 2, 4, 5, 6 and 7 have no current result, and `docs/validation.json` is from 8 August |
| the ablation branches, `hypo`, `visentin`, `visentin1` | outstanding, not yet timed | never rerun by any rebuild; the files on disk are from 7 and 8 August and record a layer that no longer exists |

The five that are done reproduced exactly. Across the ablation and the gap, 188 figures came back
identical to the ninth decimal against copies taken before the rerun, and the clamp and production
figures matched their logs. That was worth establishing on its own: it means every superseded
value in this document that was read off an unstamped file is correct, and all of them now bind to
a commit rather than to a log the next run would overwrite. The two long stages take 11 and 23
minutes rather than the 89 and 208 recorded in the rebuild log, because both were run on a single
core there and both now take `--workers`.

The six producers with no pipeline stage are a separate decision, since adding them lengthens
every future rebuild and studies 09, 10 and 16 are what they unblock.

## Inconsistencies that predate the rebuild

These were wrong before the rebuild and will still be wrong after it, so a rerun does not clear
them.

`FIDELITY.md` gives the four-layer signature count as six, eight and seven in three places, and
the classifier floor as 0.926 and 0.937. It gives the DCLP3 severe-low episode count as 2,322 and
2,242, the exposure as 10,754 and 10,676 days, and the rate as 0.22 and 0.21 a day. It reports the
physiology arm as losing one subject, five subjects and half the cohort.

`LADDER.md` states a bare and a layered rebound of 45.2 per cent each and a paired difference of
6.0 points between them. It says a movement of 38.6 minutes takes recovery from 99.4 minutes into
a range of 50 to 59.

`CAPABILITY.md` gives the compression-lows overlap as 29 per cent in its table and 43 per cent in
its prose.

`EVIDENCE.md` reports the ranking separation as three of four defects and as four of four,
depending on which key of `ranking.json` is read, and no code in the repository writes the second
one.

`VALIDATION.md` presents the previous minimum detectable differences as 2.34, 1.79 and 1.04
against a current 2.43, 1.86 and 1.09. The figures it calls superseded are the ones in the file.

`docs/arbiter_default.json` is labelled "the four default layers" and holds three.

## What was corrected in code during this pass

The delivery-limits check at level 1 asserted only that each ceiling had bound at least once,
never that any ceiling held, so a run whose insulin on board finished above the ceiling passed as
long as the clamp had fired. Its stored result reports a peak of 10.8 U against a declared 8.6 and
records a pass. Run on current code the ceiling holds exactly, at 8.4, 8.7 and 10.1 U against
ceilings of the same values, so the breach was real, was repaired on 17 August, and the check that
should have confirmed it could not have. It now asserts the ceiling as well as the binding.

`production_during_a_low.py` printed the clamp comparison as a hardcoded sentence carrying the old
0.14 mg/kg/min. It reads the figure from the clamp's output now, or omits it.

The arbiter's `default` arm carries three layers and was labelled "the four default layers", where
`DEFAULT_LAYERS` holds four including the site layer. Any table keyed on those labels therefore
read the three-layer arm as the shipped configuration, which reverses the comparison the arm
exists to make, since `default` is the comparator for `site` rather than the shipped stack. It is
now labelled for what it is. The comment beside it also gave stale settings figures: `isf_scale`
2.4 puts the median correction factor at 41.2 mg/dL per unit across the 34 adults the arbiter
runs, against 17.2 from their own physiology, where the comment said 35.3 and 14.7 on the
hundred-subject population. DCLP3 participants ran 40.0 across all 112 and 35.0 across the
calibration half, so that arm sits at the top of what real people ran rather than in the middle.

The rest is recorded as issues 29 to 33.
