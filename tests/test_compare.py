"""The comparison harness exists to refuse four specific mistakes, so it is tested on them.

Each of these was made for real on this package and each produced a confident wrong finding.
A test that only checked the arithmetic would not have caught any of them.
"""
import numpy as np
import pytest

from timsim.validation import compare as C


def _cohort(name, signal, per_subject, n=4, step=5.0, seed=0):
    rng = np.random.default_rng(seed)
    segs = tuple((f"{name}#{i}", rng.normal(140, 40, per_subject))
                 for i in range(n))
    return C.Cohort(name, signal, step, segs)


# ------------------------------------------------------------------ the four mistakes
def test_a_reading_cannot_be_compared_with_a_glucose_by_accident():
    """The one that cost an investigation into missing counterregulation."""
    real = _cohort("trial", C.READING, 2000)
    sim = _cohort("sim", C.TRUTH, 2000)
    with pytest.raises(ValueError, match="different quantities"):
        C.compare(real, sim, C.episode_stats(54.0))


def test_the_signal_mismatch_can_be_measured_on_purpose_and_is_labelled():
    real = _cohort("trial", C.READING, 2000)
    sim = _cohort("sim", C.TRUTH, 2000)
    out = C.compare(real, sim, C.episode_stats(54.0), allow_signal_mismatch=True)
    assert "warning" in out and "against" in out["signal"]
    assert "warning" in C.report(out)


def test_exposure_is_matched_so_half_a_year_is_not_compared_with_a_month():
    """18,000 real windows against 1,870 simulated ones was the original version."""
    real = _cohort("trial", C.READING, 47000)      # about 163 days each
    sim = _cohort("sim", C.READING, 8064)          # 28 days each
    out = C.compare(real, sim, C.time_in_band())
    assert out["real"]["days"] == pytest.approx(out["simulated"]["days"], rel=0.02)
    loose = C.compare(real, sim, C.time_in_band(), match_exposure=False)
    assert loose["real"]["days"] > 4 * loose["simulated"]["days"]


def test_a_fixed_sample_is_taken_from_the_middle_not_the_start():
    """The opening month of a trial is the run-in and reads low."""
    ramp = np.arange(8064 * 3, dtype=float)
    c = C.Cohort("ramp", C.READING, 5.0, (("a", ramp),))
    middle = c.sample(28.0, take=C.MIDDLE).segments[0][1]
    start = c.sample(28.0, take=C.START).segments[0][1]
    assert start[0] == ramp[0]
    assert middle[0] > start[0]
    assert abs(middle.mean() - ramp.mean()) < abs(start.mean() - ramp.mean())


def test_one_function_computes_the_peak_on_both_sides():
    """A peak per excursion and every sample past the threshold pooled are not the same."""
    v = np.array([100, 200, 260, 200, 100, 100, 190, 100], float)
    found = C.episodes(v, 5.0, 180.0, below=False)
    assert [d for d, _ in found] == [15.0, 5.0]
    assert [p for _, p in found] == [260.0, 190.0]
    assert np.median([p for _, p in found]) == 225.0    # per episode
    assert np.median(v[v >= 180]) == 200.0              # pooled, a different number


# ------------------------------------------------------------------------ the basics
def test_mixed_sample_intervals_are_refused():
    a = _cohort("a", C.READING, 2000, step=5.0)
    b = _cohort("b", C.READING, 2000, step=1.0)
    with pytest.raises(ValueError, match="sample intervals differ"):
        C.compare(a, b, C.time_in_band())


def test_a_bare_sequence_is_refused_so_the_signal_travels_with_the_numbers():
    real = _cohort("trial", C.READING, 2000)
    with pytest.raises(TypeError, match="Cohort"):
        C.compare(real, [np.zeros(100)], C.time_in_band())


def test_an_unknown_signal_is_refused():
    with pytest.raises(ValueError, match="signal must be"):
        C.Cohort("x", "sensor-ish", 5.0, (("a", np.zeros(10)),))


def test_an_empty_cohort_is_refused_rather_than_returning_nothing():
    with pytest.raises(ValueError, match="no segments"):
        C.Cohort("x", C.READING, 5.0, ())


def test_segments_of_one_subject_count_as_one_subject():
    c = C.Cohort("x", C.READING, 5.0,
                 (("a", np.zeros(300)), ("a", np.zeros(300)), ("b", np.zeros(300))))
    assert c.subjects == 2
    assert c.days == pytest.approx(900 * 5 / 1440)


def test_episodes_are_bounded_at_the_end_of_a_segment():
    v = np.array([40.0, 40.0, 40.0])
    assert C.episodes(v, 5.0, 54.0)[0][0] == 15.0


# --------------------------------------------------------------------- against results
def test_a_cohort_from_results_carries_the_signal_it_was_built_from():
    from timsim import simulate
    from timsim.population import names
    r = [simulate(names("adult")[0], days=2, seed=0)]
    assert C.from_results(r).signal == C.READING
    assert C.from_results(r, signal=C.TRUTH).signal == C.TRUTH
    with pytest.raises(ValueError, match="signal must be"):
        C.from_results(r, signal="bg")


def test_reading_and_truth_give_different_episode_counts_on_the_same_run():
    """This is the finding the harness exists to stop being made by accident."""
    from timsim import simulate
    from timsim.population import names
    res = [simulate(n, days=10, seed=7) for n in names("adult")[:3]]
    stat = C.episode_stats(70.0)
    on_reading = stat(C.from_results(res, signal=C.READING))
    on_truth = stat(C.from_results(res, signal=C.TRUTH))
    assert on_reading["episodes"] != on_truth["episodes"]


# ------------------------------------------------------- per-subject coverage
def test_coverage_finds_a_counterpart_when_one_exists():
    """Visentin's criterion: for each real subject, does a virtual one behave like it."""
    rng = np.random.default_rng(0)
    real = C.Cohort("real", C.READING, 5.0,
                    tuple((f"r{i}", rng.normal(140 + i * 4, 40, 2000)) for i in range(10)))
    same = C.Cohort("same", C.READING, 5.0,
                    tuple((f"s{i}", rng.normal(140 + i * 4, 40, 2000)) for i in range(10)))
    assert C.coverage(real, same)["real_covered"] > 0.8


def test_coverage_notices_a_population_that_lives_somewhere_else():
    rng = np.random.default_rng(1)
    real = C.Cohort("real", C.READING, 5.0,
                    tuple((f"r{i}", rng.normal(140, 40, 2000)) for i in range(10)))
    elsewhere = C.Cohort("high", C.READING, 5.0,
                         tuple((f"s{i}", rng.normal(320, 40, 2000)) for i in range(10)))
    out = C.coverage(real, elsewhere)
    assert out["real_covered"] < 0.2
    assert len(out["uncovered"]) >= 8


def test_coverage_reports_both_directions():
    """A population covering every real subject can still contain implausible ones."""
    rng = np.random.default_rng(2)
    # the real population has to have a spread of its own, or standardising by it degenerates
    real = C.Cohort("real", C.READING, 5.0,
                    tuple((f"r{i}", rng.normal(130 + i * 8, 35, 3000)) for i in range(8)))
    wide = C.Cohort("wide", C.READING, 5.0,
                    tuple((f"s{i}", rng.normal(130 + i * 8, 35, 3000)) for i in range(8))
                    + tuple((f"x{i}", rng.normal(300 + i * 30, 35, 3000)) for i in range(8)))
    out = C.coverage(real, wide)
    assert out["real_covered"] > 0.8, "the real range is spanned"
    assert out["simulated_plausible"] < 0.7, "half the virtual subjects resemble nobody"


def test_coverage_measures_spread_in_both_directions():
    rng = np.random.default_rng(3)
    real = C.Cohort("real", C.READING, 5.0,
                    tuple((f"r{i}", rng.normal(140 + i * 10, 40, 2000)) for i in range(10)))
    narrow = C.Cohort("narrow", C.READING, 5.0,
                      tuple((f"s{i}", rng.normal(185, 40, 2000)) for i in range(10)))
    assert C.coverage(real, narrow)["spread_ratio"]["mean"] < 0.3


def test_coverage_refuses_a_signal_mismatch():
    rng = np.random.default_rng(4)
    real = C.Cohort("real", C.READING, 5.0,
                    tuple((f"r{i}", rng.normal(140, 40, 2000)) for i in range(5)))
    truth = C.Cohort("truth", C.TRUTH, 5.0,
                     tuple((f"s{i}", rng.normal(140, 40, 2000)) for i in range(5)))
    with pytest.raises(ValueError, match="not the same outcome"):
        C.coverage(real, truth)


def test_a_subject_profile_covers_every_clinical_zone():
    v = np.array([40, 60, 120, 200, 300], float)
    p = C.subject_profile(v)
    assert set(p) >= {n for _, _, n in C.ZONES} | {"mean", "cv"}
    assert sum(p[n] for _, _, n in C.ZONES) == pytest.approx(100.0)


def test_exposure_is_matched_on_the_total_not_the_mean():
    """Capping each subject at the mean leaves uneven cohorts unmatched, and said otherwise.

    Durations of one day and 199 have the same mean as 100 and 100, so the per-subject budget
    was 100 and the sampled totals were 101 against 200 while `exposure_matched` reported true.
    Simulated cohorts are exactly this shape, because a run that terminates early leaves a short
    record and the runs that terminate are the ones that went furthest wrong.
    """
    mk = lambda name, durs: C.Cohort(
        name, C.READING, 5.0,
        tuple((f"{name}{i}", np.full(int(d * 288), 100.0)) for i, d in enumerate(durs)))

    for a_durs, b_durs in ([1, 199], [100, 100]), ([50, 50], [100, 100]), \
                          ([28, 28, 3, 2], [180] * 4):
        out = C.compare(mk("a", a_durs), mk("b", b_durs), C.time_in_band())
        a_days, b_days = out["real"]["days"], out["simulated"]["days"]
        assert abs(a_days - b_days) <= 0.01 * max(a_days, b_days), (a_durs, b_durs, out)
        assert out["exposure_matched"] is True


def test_exposure_matched_reports_the_outcome_not_the_request():
    """The field said whether matching was asked for, which is not the same question."""
    mk = lambda name, durs: C.Cohort(
        name, C.READING, 5.0,
        tuple((f"{name}{i}", np.full(int(d * 288), 100.0)) for i, d in enumerate(durs)))
    out = C.compare(mk("a", [10, 10]), mk("b", [40, 40]), C.time_in_band(),
                    match_exposure=False)
    assert out["exposure_requested"] is False
    assert out["exposure_matched"] is False
