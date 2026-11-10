# Excursions above 180 mg/dL: the OpenAPS Data Commons as a second real reference

Status: complete, 10 November 2026. Real-record measurement; no simulation was run.

## Question

`excursion_recovery.json` (25 August 2026) puts the median peak of simulated closed-loop excursions
above 180 mg/dL at 194.6 mg/dL against 209.0 on the DCLP3 closed-loop arm, the calibration half,
and that gap is the current lead in `timsim-next-steps.md`: simulated excursions do not climb high
enough. DCLP3 was the only real reference, one commercial system in a trial. This measures the
same statistics on the OpenAPS Data Commons (n=240 release, April 2026), people running
open-source loops in daily life, split by system.

## Method

`commons_excursions.py` imports `excursions()` and `summarise()` from `examples/excursion_recovery.py`
and applies them unchanged. Traces are cut as `dclp3.traces` cuts them: a gap over 8 minutes ends a
segment, segments under 288 readings are dropped, and a participant's record must span 7 days. Two
steps were added because the Commons mixes sensors and uploaders. Readings were thinned to one at
least 270 seconds after the last kept, since some uploaders record every minute and `excursions()`
assumes five-minute steps, and values outside 39 to 401 mg/dL were dropped. Glucose is in mg/dL in
both the AAPS uploader's tables and the Nightscout entries; no participant's median fell below 30,
which a stored mmol/L series would give (`looping-behaviours/scripts/verify_commons.py`).

The system of each UTC day is the commonest in that day's Nightscout devicestatus (Loop, AAPS, an
OpenAPS rig, or an OpenAPS-format record that is neither), and AAPS for the AAPS uploader's own
glucose. A change of system ends a segment. Days with no algorithm record are reported apart, since
they include people who were not looping. Excursions are pooled across people, as in the original;
the 95 per cent intervals resample people (1,000 draws). DCLP3 was recomputed per person with the
same code so it carries an interval too. It reproduced the stored figures exactly (37,502
excursions, median peak 209.0), which confirms that the definition is the one used on 25 August.

Expected before running: Commons peaks within about 10 mg/dL of DCLP3's; OpenAPS and AAPS no lower
than Loop.

## Results

| Set | People | Excursions | A day | Median peak, mg/dL | Per-person median | Median duration, min | Median fall, mg/dL/h | Time above 180, % |
|---|---|---|---|---|---|---|---|---|
| Commons, days with a loop record | 150 | 56,778 | 2.27 | 203.0 [201.0, 206.0] | 203.2 | 55 [50, 60] | 60.0 [56.0, 65.5] | 13.6 |
| AAPS | 82 | 40,702 | 2.32 | 203.0 [201.0, 206.0] | 202.0 | 50 [45, 60] | 63.0 [57.6, 69.2] | 12.5 |
| OpenAPS rig | 62 | 11,351 | 2.15 | 205.0 [200.0, 210.0] | 205.8 | 65 [55, 75] | 55.2 [49.1, 60.7] | 17.2 |
| Loop | 25 | 4,273 | 2.06 | 199.0 [194.0, 204.0] | 203.5 | 55 [50, 60] | 52.0 [45.6, 61.5] | 11.9 |
| OpenAPS-format, unresolved | 13 | 452 | 2.98 | 224.0 [208.0, 239.0] | 215.0 | 80 [65, 145] | 65.6 [47.7, 72.0] | 19.0 |
| Commons, no loop record | 94 | 28,175 | 2.47 | 206.0 [204.0, 209.0] | 206.0 | 65 [60, 75] | 54.9 [50.1, 60.0] | 17.7 |
| DCLP3 closed loop, recomputed | 67 | 37,502 | 3.49 | 209.0 [207.0, 212.0] | 208.0 | 60 [55, 65] | 59.5 [56.0, 60.4] | |
| TimSim closed (25 Aug) | 36 | 2,810 | 2.79 | 194.6 | | 40 | 60.8 | 13.9 |

Time above 180 is the median across people for the simulated arm and the pooled share of readings
for the Commons. Real peaks are integer mg/dL, so their intervals move in whole steps.

Commons excursions on loop days peaked at a median 203.0 mg/dL [201.0, 206.0], 6 mg/dL below
DCLP3's 209.0 [207.0, 212.0]; the intervals do not overlap. The simulated 194.6 lies below both, by
8.4 mg/dL against the Commons and 14.4 against DCLP3. The real systems did not differ from one
another in peak height: AAPS 203.0, OpenAPS rigs 205.0 and Loop 199.0, with overlapping intervals.
Duration was 55 minutes [50, 60] on the Commons against 60 on DCLP3 and 40 simulated, and the fall
rate was the same in all three, near 60 mg/dL per hour. The Commons had fewer excursions a day
than DCLP3 (2.27 against 3.49) at a time above 180 near the simulated arm's.

## Verdict

The shortfall in simulated peak height holds against a second real cohort, at about half the size:
194.6 against 203.0 [201.0, 206.0] mg/dL on the Commons, against 209.0 on DCLP3. Simulated
excursions also remain shorter (40 minutes against 55 and 60) while falling at the real rate, so the
reading of 25 August stands: they end sooner because they climb less far. DCLP3 sits at the high end
of the two real references, so a calibration aimed at DCLP3 alone would overshoot open-source loop
users by about 6 mg/dL. Whether 194.6 is distinguishable from 203.0 by the rule in REVIEW.md item 23
needs the simulated cohort's own interval, which excursion_recovery.json does not keep (it stores no
per-run excursions); rerunning that producer with them stored would settle it.

## Limits

The Commons spans 2016 to 2026 and several sensor generations, and no era split was made beyond the
system. Pooling weights people by their excursion count, and one long record contributes many; the
per-person medians (202.0 to 206.0 across the main systems) agree with the pooled figures. The
system is read per UTC day from devicestatus, so a day on which someone switched contributes to the
commoner one. "OpenAPS-format, unresolved" (13 people) are records with an oref block that carry
neither AAPS's nor oref0's device fields, and could be Trio, iAPS or a rig.

## Files

| File | What it holds |
|---|---|
| `commons_excursions.py` | The measurement |
| `commons_excursions_output.txt` | Its printed table |
| `commons_excursions.json` | The same, with provenance; aggregate figures only, no participant identifiers |

    ~/.venvs/boost-insilico/bin/python -I examples/2026-11-commons-excursions/commons_excursions.py \
        > examples/2026-11-commons-excursions/commons_excursions_output.txt

It reads the `commons` schema of the local database, loaded by `looping-behaviours/scripts/load_commons.py`
and `load_commons_ns.py`, and the local DCLP3 cache. Neither dataset is redistributed.
