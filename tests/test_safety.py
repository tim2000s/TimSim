"""The safety record, the gate, and the fault injections that feed them."""
import numpy as np
import pytest

from timsim.analysis import safety
from timsim.validation import faults, gate


class _Run:
    """A stand-in Result carrying only what the safety record reads."""

    def __init__(self, bg, insulin=None, name="adult#001", completed=True, dt=5.0):
        self.name = name
        self.bg = np.asarray(bg, float)
        self.cgm = self.bg
        self.sample_time = dt
        self.completed = completed
        self.insulin_series = np.asarray(insulin if insulin is not None
                                         else np.full(len(bg), 0.05), float)
        self.rescue_grams = 0.0
        self.rescue_events = 0
        self.meta = {}

    @property
    def time_in_range(self):
        return 100.0 * np.mean((self.bg >= 70) & (self.bg < 180))


def test_lbgi_rises_with_lows_and_hbgi_with_highs():
    low = safety.lbgi_hbgi(np.full(288, 60.0))
    normal = safety.lbgi_hbgi(np.full(288, 110.0))
    high = safety.lbgi_hbgi(np.full(288, 300.0))
    assert low[0] > normal[0] and high[1] > normal[1]
    assert normal[0] < 1.0 and normal[1] < 1.0


def test_a_severe_low_is_counted_by_duration_not_just_by_depth():
    trace = np.full(576, 120.0)
    trace[100:130] = 50.0                       # 30 samples at 5 min = 150 minutes
    r = safety.summarise(_Run(trace))
    assert r["longest_below_54_min"] == pytest.approx(150.0)
    assert r["minutes_below_54_per_day"] > 0


def test_a_brief_dip_below_54_is_not_counted_as_an_episode():
    trace = np.full(576, 120.0)
    trace[100:102] = 50.0                       # ten minutes, under the episode floor
    r = safety.summarise(_Run(trace))
    assert r["longest_below_54_min"] == 0.0


def test_peak_hourly_insulin_finds_the_worst_hour():
    insulin = np.full(576, 0.1)
    insulin[200:212] = 2.0                      # twelve 5-min steps is one hour
    r = safety.summarise(_Run(np.full(576, 120.0), insulin=insulin))
    assert r["peak_insulin_per_hour_u"] == pytest.approx(24.0)


def test_the_rate_bound_is_the_rule_of_three_when_nothing_happened():
    per_year = safety.rate_upper_bound(0, 2800)
    assert per_year == pytest.approx(3.0 / 2800 * 365.25, rel=0.05)
    assert safety.rate_upper_bound(5, 2800) > per_year


def test_the_worst_subject_is_named_rather_than_averaged_away():
    good = [safety.summarise(_Run(np.full(576, 120.0), name=f"s{i}")) for i in range(9)]
    bad_trace = np.full(576, 120.0)
    bad_trace[100:200] = 45.0
    bad = safety.summarise(_Run(bad_trace, name="the_bad_one"))
    w = safety.worst_of(good + [bad])
    assert w["minutes_below_54_per_day"]["worst_subject"] == "the_bad_one"
    assert w["minutes_below_54_per_day"]["median"] == 0.0


def test_the_gate_fails_a_cohort_with_a_subject_that_did_not_complete():
    runs = [_Run(np.full(576, 120.0), name=f"s{i}") for i in range(9)]
    runs.append(_Run(np.full(200, 120.0), name="s9", completed=False))
    v = gate.evaluate(runs)
    assert not v["passed"]
    assert "runs that did not complete" in v["failed"]


def test_the_gate_reports_the_exposure_bound_alongside_a_pass():
    runs = [_Run(np.full(8064, 120.0), name=f"s{i}") for i in range(10)]   # 28 days each
    v = gate.evaluate(runs)
    assert v["exposure"]["severe_episodes_observed"] == 0
    assert v["exposure"]["upper_bound_per_subject_year"] > 0
    assert v["uncovered_hazards"]


def test_the_fingerprint_changes_when_a_threshold_moves():
    moved = list(gate.DEFAULT_CRITERIA)
    moved[1] = gate.Criterion(moved[1].key, moved[1].summary, 999.0, moved[1].direction,
                              moved[1].hazard, moved[1].rationale)
    assert gate.fingerprint() != gate.fingerprint(tuple(moved))


def test_a_dropout_fault_withholds_readings_for_its_window():
    f = faults.NoReadings(start_min=60, duration_min=30)
    assert f.cgm(55, 120.0) == 120.0
    assert f.cgm(75, 120.0) is None
    assert f.cgm(95, 120.0) == 120.0


def test_a_stuck_reading_repeats_the_value_it_froze_on():
    f = faults.StuckReading(start_min=60, duration_min=30)
    f.cgm(55, 100.0)
    assert f.cgm(60, 140.0) == 140.0
    assert f.cgm(75, 200.0) == 140.0
    assert f.cgm(95, 200.0) == 200.0


def test_a_delivery_fault_drops_insulin_and_counts_what_was_lost():
    f = faults.NoDelivery(start_min=60, duration_min=30)
    assert f.delivery(75, 0.02, 3.0) == (0.0, 0.0)
    assert f.units_lost == pytest.approx(3.0)
    assert f.delivery(95, 0.02, 1.0) == (0.02, 1.0)


def test_faults_compose_in_order():
    both = faults.Faults(faults.NoReadings(60, 30), faults.CompressionLow(200))
    assert both.cgm(75, 120.0) is None
    assert both.cgm(200, 120.0) == 120.0        # the dip starts from zero depth
    assert both.cgm(210, 120.0) < 90.0          # and reaches its nadir ten minutes in
    assert both.report()["faults"][0]["fault"] == "NoReadings"


# ------------------------------------------------------------------ what the design binds
def test_the_design_covers_the_configuration_and_not_just_the_size():
    """A verdict from a run with a failed-site hazard is not comparable with one without."""
    from timsim import simulate
    from timsim.population import names
    from timsim.validation import gate
    name = names("adult")[0]
    five = [simulate(name, days=1, seed=0)]
    four = [simulate(name, days=1, seed=0,
                     layers=("physiology", "behaviour", "sensor"))]
    assert gate.design_of(five)["layers"] != gate.design_of(four)["layers"]
    assert gate.fingerprint(design=gate.design_of(five)) \
        != gate.fingerprint(design=gate.design_of(four))


def test_the_design_notices_settings_that_change_the_world():
    from timsim import simulate
    from timsim.population import names
    from timsim.validation import gate
    name = names("adult")[0]
    a = [simulate(name, days=1, seed=0)]
    b = [simulate(name, days=1, seed=0, isf_scale=2.4)]
    assert gate.fingerprint(design=gate.design_of(a)) \
        != gate.fingerprint(design=gate.design_of(b))


def test_evaluate_binds_the_design_without_being_asked():
    from timsim import simulate
    from timsim.population import names
    from timsim.validation import gate
    r = [simulate(names("adult")[0], days=1, seed=0)]
    assert gate.evaluate(r)["fingerprint"] == gate.fingerprint(design=gate.design_of(r))


def test_the_registration_history_is_consistent_with_the_current_criteria():
    """Every recorded fingerprint has to be reproducible, or the record proves nothing."""
    from timsim.validation import gate
    for entry in gate.REGISTERED:
        assert gate.fingerprint(design=entry["design"]) == entry["fingerprint"], entry
    current = [e for e in gate.REGISTERED if "registered" in e]
    assert len(current) == 1
    assert "site" in current[0]["design"]["layers"]


def test_site_failure_is_no_longer_listed_as_wholly_uncovered():
    from timsim.validation import gate
    joined = " ".join(gate.UNCOVERED_HAZARDS)
    assert "therapy/site.py" in joined
    assert not any(h.startswith("infusion site failure, which the model has no mechanism")
                   for h in gate.UNCOVERED_HAZARDS)
