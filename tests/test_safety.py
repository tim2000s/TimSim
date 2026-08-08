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


def test_the_registration_history_records_one_current_entry_and_dates_the_rest():
    """A retired fingerprint cannot recompute once the criteria move, which is the point.

    It was hashed against the criteria of its day. What the record has to do is make a
    change visible and dated, and say how many criteria were in force when.
    """
    from timsim.validation import gate
    current = [e for e in gate.REGISTERED if "registered" in e]
    retired = [e for e in gate.REGISTERED if "retired" in e]
    assert len(current) == 1 and retired
    assert current[0]["criteria"] == len(gate.DEFAULT_CRITERIA)
    assert all(e["fingerprint"] for e in retired), "a retired entry lost its hash"
    assert all("note" in e for e in gate.REGISTERED)


def test_severe_low_duration_is_still_a_criterion():
    """It was retired on a comparison that was not like-for-like, and restored."""
    from timsim.validation import gate
    assert any(c.key == "longest_below_54_min" for c in gate.DEFAULT_CRITERIA)


def test_the_safety_metrics_read_blood_glucose_not_the_sensor():
    """Which is right for a safety verdict, and is why thresholds cannot be imported
    from trial figures without converting: a sensor understates a severe low."""
    import numpy as np
    from timsim import simulate
    from timsim.population import names
    from timsim.analysis import safety
    r = simulate(names("adult")[0], days=3, seed=11)
    rec = safety.summarise(r)
    truth = float(np.mean(np.asarray(r.bg, float) < 70.0) * 24 * 60)
    assert rec["minutes_below_70_per_day"] == pytest.approx(truth, rel=0.05)


def test_site_failure_is_no_longer_listed_as_wholly_uncovered():
    from timsim.validation import gate
    joined = " ".join(gate.UNCOVERED_HAZARDS)
    assert "therapy/site.py" in joined
    assert not any(h.startswith("infusion site failure, which the model has no mechanism")
                   for h in gate.UNCOVERED_HAZARDS)


# ------------------------------------------------------------ the reference algorithm
def _fake_info(minute, cgm, meal_g=0.0, delivered=None, sample=5.0):
    info = {"clock_minutes": minute, "sample_time": sample, "meal": meal_g / sample}
    if delivered is not None:
        info["delivered_bolus_u"] = delivered
    return info


class _Obs:
    def __init__(self, cgm):
        self.CGM = cgm


def _aid(**kw):
    from timsim.controller.reference import ReferenceAID
    from timsim.population import names
    return ReferenceAID(names("adult")[0], **kw)


def test_a_meal_bolus_subtracts_insulin_already_working():
    """It used not to. An uncapped full correction rode along with every meal."""
    from timsim.controller.reference import CORRECT_ABOVE
    a, b = _aid(), _aid()
    # give one of them a large dose to carry, then feed both the same meal at a high
    a.doses.append((0.0, 5.0))
    high = CORRECT_ABOVE + 80.0
    ba = a.policy(_Obs(high), 0, False, **_fake_info(10.0, high, meal_g=60.0)).bolus
    bb = b.policy(_Obs(high), 0, False, **_fake_info(10.0, high, meal_g=60.0)).bolus
    assert ba < bb, "insulin on board did not reduce the meal-time correction"


def test_the_ceiling_bounds_where_insulin_on_board_ends_up():
    """Testing only whether a dose may start let 2 U land at 5.9 U and finish at 7.9."""
    from timsim.therapy.insulin import iob as iob_of
    a = _aid(max_iob_u=6.0)
    a.doses.append((0.0, 5.9))
    high = 300.0
    a.policy(_Obs(high), 0, False, **_fake_info(5.0, high))
    assert iob_of(5.0, a.doses) <= 6.0 + 1e-9


def test_covering_carbohydrate_is_not_withheld_for_insulin_on_board():
    """The carbohydrate is real and arriving; only the correction part is bounded."""
    a = _aid(max_iob_u=6.0)
    a.doses.append((0.0, 20.0))
    bolus = a.policy(_Obs(110.0), 0, False, **_fake_info(5.0, 110.0, meal_g=60.0)).bolus
    assert bolus > 0.0


def test_the_algorithm_records_what_the_pump_delivered_not_what_it_asked_for():
    """Tracking its own requests took the believed insulin on board to 41.7 U."""
    a = _aid()
    a.policy(_Obs(300.0), 0, False, **_fake_info(5.0, 300.0))
    asked = a.doses[-1][1]
    a.policy(_Obs(120.0), 0, False, **_fake_info(10.0, 120.0, delivered=0.25))
    assert a.doses[-1][1] == pytest.approx(0.25)
    assert asked != pytest.approx(0.25)


def test_a_step_with_no_bolus_does_not_rewrite_an_earlier_dose():
    a = _aid()
    a.policy(_Obs(300.0), 0, False, **_fake_info(5.0, 300.0))
    a.policy(_Obs(120.0), 0, False, **_fake_info(10.0, 120.0, delivered=1.0))
    before = list(a.doses)
    a.policy(_Obs(120.0), 0, False, **_fake_info(15.0, 120.0, delivered=0.0))
    assert a.doses == before


def test_the_runner_reports_delivered_insulin_to_the_algorithm():
    from timsim import simulate
    from timsim.population import names
    seen = []

    class Spy:
        name = "spy"

        def policy(self, observation, reward, done, **info):
            from simglucose.controller.base import Action
            seen.append(info.get("delivered_bolus_u"))
            return Action(basal=0.02, bolus=4.0 / info["sample_time"])

    simulate(names("adult")[0], days=1, seed=0, controller=Spy())
    reported = [v for v in seen if v is not None]
    assert reported, "the runner never told the algorithm what was delivered"
    # the ceilings sit between the request and the pump, so at least one differs
    assert any(abs(v - 4.0) > 1e-9 for v in reported)
