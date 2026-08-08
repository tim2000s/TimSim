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
   target and broke something else, and that is only visible when the whole table is
   shown.
4. Do not fit the parameter to the statistic it is being judged on. Where you do, say so
   explicitly, because the row then stops being a test.

A change that improves one statistic and silently degrades three is not an improvement,
and the table in `docs/FIDELITY.md` is there to make that visible.

## The bar for a new subject population

Anything generated has to survive `timsim.population.generate.screen`. Where you loosen a
gate, say which subjects it lets in and why they are people.

## The bar for harness work

Every harness fix comes with a check that would have caught the defect, added to the right
level in `timsim/validation/checks.py`. This is not a formality. Of the eight defects
listed in `docs/OSAID.md` section 2, most survived a passing test suite because the tests
exercised each function in isolation while the defect was in how it was wired up. The
compression-low rate function was correct and was being handed a grid it did not expect;
the sensor layer did exactly what its tests asked and was applied after the run had ended.
A unit test on its own does not clear this bar.

## The bar for a new safety criterion

Anything added to `validation/gate.py` names the hazard it covers and where its threshold
comes from. A threshold with no source is a threshold someone chose, and it will be read
as though it came from somewhere. Where a criterion is this package's own judgement rather
than a published target, the rationale field says so.

Moving an existing threshold changes the fingerprint, which is what makes the move
visible. A verdict quoted
against a fingerprint that no longer resolves is a verdict whose criteria were edited after
the fact.

## Style

`CLAUDE.md` has the full set of rules and they apply to prose anywhere in the repository,
including docstrings and commit messages. The short version: plain British English, no
em-dashes, no bold for emphasis, nothing written in threes, and no dramatic closing lines.
Explain why a thing is the way it is rather than what a line does. Report uncertainty with
an interval and a verdict, since a bare point estimate is not a finding.

## Tests

`pytest -q`, which takes about three minutes. The load-bearing test is
`test_closure_reproduces_every_published_subject`: it checks that the steady-state
relations in `population/derive.py` reproduce all thirty published subjects. A failure
there means nothing else in the population is trustworthy.
