"""Which random month a run lives, declared once so that scripts cannot disagree.

Two separate problems put these constants in one place.

Settings were fitted and scored on the same month. `titrate_cohort.py` ran at seed 11 and so did
`bench_matrix.py`, `capability_table.py`, `two_benches.py`, `cohort_replicates.py`,
`fit_control_iq.py` and `production_during_a_low.py`. A subject's meal schedule, sensor noise,
infusion set failures and day-to-day sensitivity are a deterministic function of its name and the
seed, so titration weakened each subject's settings until that subject cleared the consensus
hypoglycaemia floors on exactly the month the benchmark then measured it on. A quantity fitted on
a sample and reported on the same sample is not a measurement of anything, and here the quantity
fitted was hypoglycaemia, which is what most of these figures are about.

A real person titrates against their own record and then goes on living, so the settings are
carried into a month they were not chosen against. `BENCH` is that month.

The other problem was that scripts disagreed by accident. The ladder and the oref cohort ran at
seed 0 while the matrix ran at seed 11, so two figures about the same subjects under the same
settings were measured on different months, and nothing in either output said so. Every script
now takes its seed from here, and the seed is recorded beside the population fingerprint in the
result files.

The values themselves carry no meaning beyond being different from each other. What matters is
that titration and evaluation never share one, and that everything compared against everything
else uses the same one.
"""

# The month settings are titrated on. Not to be used for any reported measurement.
TITRATION = 11

# The month everything is measured on. Held out from titration.
BENCH = 101

__all__ = ["TITRATION", "BENCH"]
