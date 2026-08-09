"""Choosing the right people to run, which is a choice and was being made by accident."""
import numpy as np
import pytest

from timsim.population import cohort


def test_a_matched_cohort_follows_the_reference_age_distribution():
    """34 adults at a median of 49 were being compared against a trial at a median of 29."""
    ref = np.concatenate([np.full(19, 15.0), np.full(48, 35.0)])   # 28% under 18
    picked, _ = cohort.matched(ref, n=30, seed=0)
    got = cohort.describe(picked)
    assert abs(got["fraction_under_18"] - 0.28) < 0.12
    assert abs(got["age_median"] - np.median(ref)) < 12


def test_a_bin_the_reference_does_not_have_is_not_filled():
    """A cohort quietly topped up from the wrong age group is worse than a smaller one."""
    ref = np.full(40, 9.0)                       # children only
    picked, _ = cohort.matched(ref, n=20, seed=0)
    assert picked
    assert max(cohort.ages(picked).values()) < 18


def test_a_shortfall_is_reported_rather_than_absorbed():
    ref = np.full(60, 30.0)                      # more adults of one age than exist
    picked, shortfall = cohort.matched(ref, n=90, seed=0)
    assert shortfall, "ran out of subjects and said nothing"
    assert len(picked) < 90


def test_the_same_seed_picks_the_same_cohort():
    ref = np.concatenate([np.full(10, 15.0), np.full(30, 40.0)])
    a, _ = cohort.matched(ref, n=20, seed=3)
    b, _ = cohort.matched(ref, n=20, seed=3)
    c, _ = cohort.matched(ref, n=20, seed=4)
    assert a == b and a != c


def test_an_empty_reference_is_refused():
    with pytest.raises(ValueError, match="no reference ages"):
        cohort.matched([])


def test_describe_reports_what_a_result_has_to_be_quoted_with():
    from timsim.population import names
    got = cohort.describe(names("adult")[:5])
    assert set(got) == {"n", "age_median", "age_min", "age_max", "fraction_under_18"}
    assert got["n"] == 5
