# Measurements

Each file here is the output of one script in `examples/`, and every number quoted in a
paper should be traceable to one of them. The scripts write only into this directory and
take their paths from the repository root, so a checkout anywhere reproduces them.

| Output | Produced by | What it measures |
|---|---|---|
| `commons_cohort.json` | `examples/commons_cohort.py` | Outcomes for OpenAPS Data Commons users on the middle 28-day window of each record |
| `commons_cohort_densest.json` | `examples/commons_cohort.py densest` | The same with the best-covered window instead of the middle one, kept as the sensitivity check |
| `commons_requirement.json` | `examples/commons_requirement.py` | Each Commons user's daily insulin, reconstructed from boluses and integrated temporary basals, which is the only physiological trait that export allows a cohort to be matched on |
| `real_meals.json` | `examples/real_meals.py` | Uncovered real meals, bolus-free for 30 min before and 120 min after |
| `real_meals_dia.json` | `examples/real_meals.py` | The same with a full insulin action duration cleared before the meal, which is the version to quote |
| `meal_response.json` | `examples/meal_response.py` | The simulated response to one uncovered meal at 30, 50 and 70 g |
| `paper_tables.json` | `examples/paper_tables.py` | Per-subject outcomes for every bench arm, read into tables by `examples/analyse_tables.py` |
| `driver_ranking.json` | `examples/rank_drivers.py` | The four closed-loop drivers on the forty-adult panel over 28 days, paired per subject, with an A/A arm on a second month giving the floor each difference is read against |
| `liver_delay_cohort.json` | `examples/liver_delay_cohort.py` | The clamp-fitted liver delay (12.0 times the published rate) against the published one on the two per-person cohorts, 28 days, paired per subject and read against the rescaled A/A floor; the log holds the printed tables |

The Commons and real-meal scripts read the April 2026 OpenAPS Data Commons export, which is
not redistributed with this package. Filenames in that export carry a user-id prefix for
some users and not others, so the glob is `*entries*.json` rather than `entries_*.json`.
Matching the narrower pattern silently drops most of the sample.

## Which Commons users a figure is computed over

Three nested sets, and a table should say which it used. 240 user directories are exported.
131 carry a readable glucose series. 103 of those hold a 28-day window at the middle of the
record with at least 70 per cent of the readings a five-minute sensor would produce. 71 of
those also hold pump records across that window, which is what a reconstructed daily
requirement needs.

The last filter is not cosmetic. Selecting the window on glucose coverage says nothing about
whether the pump was uploading, and 27 users looked as though they took most of their insulin
as basal and logged no carbohydrate at all. Counted across their whole records they carry
between 1,256 and 7,417 boluses each, so what is missing from those windows is the treatment
data rather than the meals. Left in, they drag the median daily requirement from 38.4 U/day
down to 34.7 and put a spurious group of apparently bolus-free users into the sample.

Restricting the outcome reference to those 71 does not move it: time in range 79.60 against
79.90 across all 103, mean glucose 134.72 against 134.16, CV 33.45 against 33.76.
