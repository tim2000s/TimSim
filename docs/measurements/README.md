# Measurements

Each file here is the output of one script in `examples/`, and every number quoted in a
paper should be traceable to one of them. The scripts write only into this directory and
take their paths from the repository root, so a checkout anywhere reproduces them.

| Output | Produced by | What it measures |
|---|---|---|
| `commons_cohort.json` | `examples/commons_cohort.py` | Outcomes for OpenAPS Data Commons users on one 28-day window each |
| `commons_middle.json` | `examples/commons_cohort.py middle` | The same with the window taken from the middle of the record, kept as the sensitivity check against `densest` |
| `real_meals.json` | `examples/real_meals.py` | Uncovered real meals, bolus-free for 30 min before and 120 min after |
| `real_meals_dia.json` | `examples/real_meals.py` | The same with a full insulin action duration cleared before the meal, which is the version to quote |
| `meal_response.json` | `examples/meal_response.py` | The simulated response to one uncovered meal at 30, 50 and 70 g |
| `paper_tables.json` | `examples/paper_tables.py` | Per-subject outcomes for every bench arm, read into tables by `examples/analyse_tables.py` |

The Commons and real-meal scripts read the April 2026 OpenAPS Data Commons export, which is
not redistributed with this package. Filenames in that export carry a user-id prefix for
some users and not others, so the glob is `*entries*.json` rather than `entries_*.json`.
Matching the narrower pattern silently drops most of the sample.
