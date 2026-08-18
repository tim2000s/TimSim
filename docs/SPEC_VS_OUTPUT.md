# What the documents claim against what the measurements contain

An audit of every quantitative claim in the documentation against the rebuilt measurement set,
made before the papers are rewritten so the rewrite has a list rather than a memory.

The short version is that every document predates the rebuild and none of them can be quoted as
they stand. That is expected: the defence gain moved, the seeding changed, the panels moved onto
titrated settings and the cohorts were rebuilt from a corrected requirement, and each of those
touches every simulated figure. What follows is what has to change and what the new value is.

## The scale of it

    document                          numeric claims
    docs/FIDELITY.md                        632
    docs/paper/validation_paper.md          185
    docs/LADDER.md                          171
    docs/CAPABILITY.md                       94
    docs/METHODS.md                          68
    docs/VALIDATION.md                       61
    docs/PADOVA_LIMITS.md                    40
    README.md                                34
    docs/OVERVIEW.md                         10

Not every one is superseded; the real-data anchors mostly stand, and so does anything about the
published parameter tables. The simulated figures do not.

## Claims that are now wrong, with their replacements

| Claim | Where | Now |
|---|---|---|
| hypoglycaemia group effect 1.63 spreads | FIDELITY, LADDER, validation paper | superseded twice: 0.72 at n=90, and the baseline it is measured against was itself recomputed over the sealed half |
| capability, ten of ten signatures in range | CAPABILITY, FIDELITY, STUDIES_AUDIT | four of ten, and the attribution is in `capability_decomposition.json` |
| ladder, nine of 47 movements carried | STUDIES_AUDIT, ISSUES | remeasured on clean rungs after the stale-cache reuse; the count is in `docs/ladder/` |
| hepatic defence gain 0.25, then 0.20 | EVIDENCE, FIDELITY, METHODS, ISSUES | 0.05, fitted across 150 adults on plateau arrivals only |
| ablation, eight of eleven with four layers | FIDELITY, CAPABILITY, PLAN_ACTIVITY_SLEEP | one of eleven for stock, seven with four layers, five with all five |
| Commons reference 79.60 across 71 users | METHODS | 80.05 across 77 users, after the percentage-form temporary basals were recovered |
| titrated correction factor median 19.6 | METHODS | 20.3 for the union, 19.0 across the replicate set |

## Claims that stand

The real-data anchors are unaffected by anything in the rebuild, because nothing simulated feeds
them: the DCLP3 correction factor median of 40.0 mg/dL per unit, the consensus targets, the
Rickels clamp figures, the published parameter ranges, and the meal filters' real side apart
from the strictest one, which moved from 320 meals at 16.00 mg/dL per 10 g to 317 at 15.89.

The closure test's claim that the relations reproduce all thirty published subjects stands and
is guarded by a test.

## Three claims that were wrong for reasons other than the rebuild

Recorded separately because they are errors rather than staleness, and they would have needed
correcting whenever they were noticed.

`patient/varying.py` cited Hinshaw et al. 2015 in *Diabetes*. It is in the *American Journal of
Physiology: Endocrinology and Metabolism*, 309(5):E474–E486. Corrected in the source.

`person/activity.py` claimed a subject "falls 23 mg/dL over a sixty-minute session at intensity
0.7". Measured, the gains it described gave 10.8 mg/dL over forty-five minutes. The claim was
never measured and the gains were too weak by a factor of 2.5.

`docs/METHODS.md` says the population fingerprint makes a stale titration store raise. It does,
against a different population, and it does not against a different physiology: the store is
keyed on the parameter file alone, so a changed defence gain leaves it accepted. Issue 26.

## What this audit does not cover

Whether the documents' prose still describes what the code does, as opposed to whether their
numbers match. Four review passes covered the code and found the docstrings mostly accurate,
with the exceptions above. The prose in `docs/` has not been read line by line against the
current source and should be, as part of the rewrite rather than before it.
