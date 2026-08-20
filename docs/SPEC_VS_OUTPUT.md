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
now write a stamped file, and issue 32 records the rest of that story.

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
| titration closes about half of the settings gap | validation paper, METHODS | about 1 to 4 per cent depending on the denominator. 254 of the 298 subjects that clear the floors do so on basal alone and never reach the correction factor |
| four subjects clear the floors at no combination tried | validation paper | 32 of 330 |
| on the layered bench most incomplete runs end high | validation paper, METHODS, PADOVA_LIMITS | 54 of 61 end low, and in the DCLP3 Control-IQ cell all thirteen do |
| capability, ten of ten signatures in range | CAPABILITY, FIDELITY, STUDIES_AUDIT | three of ten on the current panel, four of eleven on the full stack |
| production at a 55 mg/dL clamp plateau is 0.14 mg/kg/min, and 0.01 at 45 | PADOVA_LIMITS, STUDIES_AUDIT, OVERVIEW | 0.49 and 0.46, both inside the human 0.42 to 0.84. The premise for counterregulation is inverted |
| production during a low is 1.28 mg/kg/min and holds rather than rising | MODEL, METHODS, PADOVA_LIMITS | 1.11 against 2.10 at euglycaemia, so it falls, at a ratio of 0.53 |
| autosens is pinned at 1.0, so any oref hypoglycaemia figure is an upper bound | OSAID | autosens is implemented and runs by default. Both arms are measured at 4.85 and 5.48 per cent below 70 mg/dL, so the caveat qualifying every oref figure no longer applies |
| the classifier separates at 0.709, and the axis is hyperglycaemia | EVIDENCE, FIDELITY | 0.784, and the heaviest feature is the sixty-minute autocorrelation |
| the ladder carries nine of 47 movements | STUDIES_AUDIT, SIMULATOR | six of 47, and the site layer now carries none |
| the outcome spread after a stuck high is inside the real range at 27.0 | FIDELITY, GUIDE, OSAID, VALIDATION, EVIDENCE | 24.58, below the range. The verdict reverses |
| the population is not reproducible from its seed | METHODS | repaired on 15 August in `d388796`. The paragraph tells a reader the opposite of the truth about the property the provenance argument rests on |
| Commons reference 79.60 across 71 users | METHODS | 80.05 across 77 users |
| the site layer costs three signatures | GUIDE | it gains one, four of eleven without it against five with |
| six graded levels of check | README, GUIDE | seven |

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

| Measurement | Cost | Why |
|---|---|---|
| layer ablation | 89 min | six arms, unstamped, and the reader that combines them now refuses them |
| hyperglycaemia gap | 208 min | four arms, same |
| capability table | 22 min | now writes a file, so the headline count becomes checkable |
| clamp | 1 min | same, and it is the calibration basis for the defence gain |
| production during a low | 5 min | same |
| the validation suite, ranking and gate | not yet timed | levels 1, 2, 4, 5, 6 and 7 have no current result, and `docs/validation.json` is from 8 August |
| the ablation branches, `hypo`, `visentin`, `visentin1` | not yet timed | never rerun by any rebuild; the files on disk are from 7 and 8 August |

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
