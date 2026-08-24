# Baseline of 24 August 2026

Every measurement behind `docs/BASELINE.md` as published on this date, pinned so the document can
be read without resolving a commit or regenerating a population. The copy of `BASELINE.md` here is
the document those figures appeared in.

The titrated settings store is the reason this directory exists. It is generated locally and not
committed, because it derives from the published UVA/Padova parameter tables, so a checkout of any
commit reproduces the code that made these figures and not the settings they were measured on. A
store is also destroyed by the next titration. The copy here is the only record of `8000d3ede7`.

    population    704cfac086df54ba
    settings      8000d3ede7314482
    simglucose    0.2.11
    commit        4f0b971

Two fields are removed from the store copied here. The per-rung `isf` and `basal_u_per_day` are
physiological quantities derived from the licensed parameter tables, which this repository does not
redistribute, so the committed copy carries what the ladder decided and the outcomes it decided on
and not the parameters underneath. The unredacted store is on the private Drive mount under
`TimSim stores/`. Two earlier archives, `archive_pre_review` and `archive_gain020`, were committed
before this was noticed and still carry those fields.

## What is here

| File | What it holds |
|---|---|
| `BASELINE.md`, `BASELINE.pdf` | the document as published |
| `titrated_settings.json` | the settings store: adopted scales and the ladder trace for all 330 subjects, with the per-rung correction factor and basal requirement removed |
| `cohorts.json` | which subjects are in which cohort, and the match distances |
| `validation.json` | the four arms across three pairings, 916 runs |
| `validation_table.json` | the arms tabulated with intervals and verdicts |
| `controller_crosscheck.json` | both cohorts under both controllers, paired per subject |
| `day_profile.json` | mean glucose and time above 180 by hour, simulated and DCLP3 |
| `intake_clock.json` | 292,140 Commons carbohydrate entries by local hour |
| `excursion_recovery.json` | excursion duration, peak and descent rate, closed and open loop |
| `settings_sweep.json` | the correction-factor sweep, refuting mechanism A |
| `engagement_arm.json` | per-subject engagement on and off, refuting mechanism D |

## What this baseline established

The distance from real people depends on which real people: 4.8 percentage points of time in range
against the OpenAPS Data Commons, 12.0 against DCLP3, 16.3 against CLOSE-IT. Of the range between
them, 2.6 points is the choice of controller and 1.2 the choice of cohort, measured by running both
cohorts under both algorithms. The rest is the reference population, and two randomised trial
populations running different algorithms agree with each other to within 2.3 points while a
self-selected population on the same algorithm as one of them sits 11 points above both.

Six candidate explanations of the residual were tested against criteria fixed in advance and none
survived. The ledger is `docs/DESIGN_ALIGNMENT.md`.

The residual as it stands: the descent from a peak runs at 62.7 mg/dL per hour against a real 59.5,
so recoveries are right; excursions are too few and peak too low; and 36 per cent of the day's
deficit in mean glucose sits in the six hours from 21:00 to 03:00, where the participants' evening
glucose persists and the simulated cohort's returns to its fasting level.

## Reproducing it

The code is at commit 4f0b971. The population and the settings store are not, so a rerun needs
`examples/generate_population.py`, then `examples/titrate_cohort.py`, then
`examples/bench_matrix.py --benches combined`. The population fingerprint should come out
704cfac086df54ba; the settings fingerprint will not necessarily reproduce, since the ladder is
deterministic in its inputs but its inputs include every file in `titrate.code_fingerprint`.
Comparing `titrated_settings.json` here against a fresh store is the check that matters.
