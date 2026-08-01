# Contributing to TimSim

## The bar for a new mechanism

This package exists because measuring where a simulator diverges from real data is more
useful than assuming it does not. A new layer or mechanism should come with the same
evidence:

1. Name the statistic it is meant to move, and show where that statistic currently sits
   relative to `signatures.REAL_RANGE`.
2. Implement the mechanism so it can be switched off, and show the statistic with and
   without it.
3. Report every other statistic too. Several mechanisms in this package moved their
   target and broke something else, and that is only visible if the whole table is shown.
4. Do not fit the parameter to the statistic it is being judged on. If you do, say so
   explicitly, because the row stops being a test.

A change that improves one statistic and silently degrades three is not an improvement,
and the table in `docs/FIDELITY.md` is there to make that visible.

## The bar for a new subject population

Anything generated has to survive `timsim.population.generate.screen`. If you loosen a
gate, say which subjects it lets in and why they are people.

## Style

Plain British English in comments and documentation. Explain why a thing is the way it is,
not what the line does. Report uncertainty with an interval and an explicit verdict; a
bare point estimate is not a finding.

## Tests

`pytest -q`. The load-bearing test is
`test_closure_reproduces_every_published_subject`: it checks that the steady-state
relations in `population/derive.py` reproduce all thirty published subjects. If that
fails, nothing else in the population is trustworthy.
