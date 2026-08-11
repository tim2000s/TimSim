"""Boost as the known algorithm.

Every other test in this suite checks TimSim against itself or against statistics. These
check it against a real automated insulin delivery algorithm, replayed on 193,714 cycles
from 19 real users, where the expected response is known independently of anything in this
package.

The tests are in four layers, and they fail in a useful order. If the units layer fails,
the reference is wrong and nothing above it means anything. If the reference layer fails,
either the harness or the cohort moved. If the adapter layer fails, TimSim is feeding the
algorithm inputs it would not recognise, and the simulator is not on trial. Only when
those three hold does the last layer say anything about TimSim.

Skipped unless the Boost harness and its cohort cache are present. Point
`BOOST_HARNESS_DIR` at them if they live somewhere other than `~/oref-investigations`.
"""
import numpy as np
import pytest

from timsim import population
from timsim.validation import boost as B

pytestmark = pytest.mark.skipif(
    not (B.available() and population.available()),
    reason="needs the Boost harness, its cohort cache, and a generated population")

SUBSET_USERS = 4          # enough to be representative, small enough to stay quick


@pytest.fixture(scope="module")
def cohort():
    return B.cohort()[:SUBSET_USERS]


@pytest.fixture(scope="module")
def raw_cohort():
    return B.cohort(fix_units=False)[:SUBSET_USERS]


@pytest.fixture(scope="module")
def full_cohort():
    """Every user. The reference is a whole-cohort figure and a subset does not reproduce
    it: four users give an idle occupancy ten points away from the nineteen-user number,
    which is between-user variation rather than a defect."""
    return B.cohort()


# ------------------------------------------------------------------ layer 1: the units
def test_the_cached_cohort_is_now_stored_in_mgdl(raw_cohort):
    """The cache was rewritten in mg/dL on 2026-08-06, so nothing needs converting on load.

    It previously held target_bg in mmol/L for all nineteen users, and eventual_bg and
    min_guard_bg in mmol/L for fourteen, in fields the harness reads as mg/dL. A predicted
    minimum of 5.6 sits under the 80 mg/dL hard gate on every cycle, which disabled the
    algorithm on 74% of them. The loader keeps its detection so a stale copy is caught.
    """
    for user in raw_cohort:
        _, converted = B.normalise_units(user["cycles"])
        assert not any(converted.values()), \
            f"{user['user_id']} still holds mmol/L in {[k for k, v in converted.items() if v]}"


def test_the_units_detector_still_catches_a_stale_cache():
    """The correction is retired from the data and kept in the loader, so it has to work."""
    h = B.harness()
    mmol = [h.CycleInput(
        delta=0.0, short_avg_delta=0.0, delta_accl=0.0, bg=120.0, eventual_bg=6.7,
        target_bg=5.0, iob=0.0, cob=0.0, base_insulin_req=0.0, max_iob=6.0,
        ml_hypo_risk=None, ml_meal_likely=None, recent_low_bg=100.0, hour=12,
        exercise_active=False, post_exercise_window=False, enable_smb_pre_checks=True,
        min_guard_bg=5.6, min_guard_threshold=80.0, max_delta=0.0, round_smb_to=0.05,
        sensor_quality_ok=True)] * 50
    fixed, converted = B.normalise_units(mmol)
    assert converted["target_bg"] and converted["min_guard_bg"] and converted["eventual_bg"]
    assert not converted["bg"]
    assert fixed[0].min_guard_bg > 80.0


def test_units_are_detected_on_the_median_not_on_single_values():
    """One mg/dL reading below 40 is a real severe low and must not trigger a conversion."""
    h = B.harness()
    cycles = [h.CycleInput(
        delta=0.0, short_avg_delta=0.0, delta_accl=0.0, bg=bg, eventual_bg=120.0,
        target_bg=100.0, iob=0.0, cob=0.0, base_insulin_req=0.0, max_iob=6.0,
        ml_hypo_risk=None, ml_meal_likely=None, recent_low_bg=100.0, hour=12,
        exercise_active=False, post_exercise_window=False, enable_smb_pre_checks=True,
        min_guard_bg=100.0, min_guard_threshold=80.0, max_delta=0.0, round_smb_to=0.05,
        sensor_quality_ok=True) for bg in [120.0] * 50 + [35.0]]
    _, converted = B.normalise_units(cycles)
    assert not converted["bg"]


# -------------------------------------------------------------- layer 2: the reference
def test_replaying_the_cache_is_reproducible(full_cohort):
    """Whatever the replay gives, it has to give the same thing twice."""
    a = B.response_profile([o for u in full_cohort for o in B.respond(u["cycles"])])
    b = B.response_profile([o for u in full_cohort for o in B.respond(u["cycles"])])
    assert a == b
    assert a["cycles"] == B.REFERENCE_VIA_PORT["cycles"]


def test_the_restored_dose_chain_matches_the_plugin():
    """Phase 2.5 was missing from the port and is now back, verified against logged output.

    The plugin logs its own `boostv5_doseaftercaps`, so the restored stage was checked
    against it directly rather than inferred: mean absolute error 0.0000 U, every row within
    0.01 U. The end-to-end dose ratio moved from 2.24 to 0.86.
    """
    gate = B.FIDELITY_GATE
    assert gate["dose_chain_passes"]
    assert 0.75 < gate["dose_ratio"] < 1.25
    assert gate["dose_ratio_before_phase25"] > 2.0


def test_the_port_state_machine_still_diverges():
    """Locked as failing on purpose, because it is the remaining known gap.

    The dose magnitude is fixed and the timing is not. On real inputs the port reaches
    RECOVERING on 0.6% of decisions against a logged 5.8%, and CONFIRMED on 0.3% against
    2.5%. Until that closes, a TimSim result has to be read against the port's own behaviour
    rather than against the plugin's logs.
    """
    gate = B.FIDELITY_GATE
    assert not gate["state_machine_passes"]
    assert gate["state_agreement_pct"] < 90.0
    port = B.PORT_ON_REAL_INPUTS["state_occupancy_pct"]
    logged = B.REFERENCE["state_occupancy_pct"]
    assert port["RECOVERING"] < logged["RECOVERING"] / 3
    assert port["CONFIRMED"] < logged["CONFIRMED"] / 3


def test_the_phase25_stage_is_wired_into_the_port():
    """A run with the stage disabled must dose more, or the port has drifted back."""
    h = B.harness()
    assert hasattr(h, "velocity_scaled_dose_factor")
    assert h.velocity_scaled_dose_factor(60.0) == 1.0
    assert h.velocity_scaled_dose_factor(10.0) == pytest.approx(0.40)
    assert h.apply_state_dose_cap(h.MealHypothesis.CONFIRMED, 5.0) == pytest.approx(1.0)
    assert h.apply_state_dose_cap(h.MealHypothesis.COMMITTED, 5.0) == pytest.approx(0.25)
    assert h.apply_state_dose_cap(h.MealHypothesis.IDLE, 5.0) == pytest.approx(5.0)


def test_attribution_separates_the_port_from_the_simulator():
    """A TimSim gap has to be split, because the port contributes to both sides.

    Scoring the simulator straight against the plugin's logs blames it for the port's own
    shortfall. Running the same port on real inputs gives the control that cancels it.
    """
    sim = {"state_occupancy_pct": dict(B.PORT_ON_REAL_INPUTS["state_occupancy_pct"])}
    a = B.attribute(sim)
    for state, row in a.items():
        assert row["simulator_effect"] == pytest.approx(0.0, abs=0.01), state
        assert row["port_error"] == pytest.approx(
            B.PORT_ON_REAL_INPUTS["state_occupancy_pct"][state]
            - B.REFERENCE["state_occupancy_pct"][state], abs=0.01)





def test_the_logged_reference_reaches_the_states_that_matter():
    """If the shipped algorithm never commits, there is nothing for TimSim to be tested on."""
    occupancy = B.REFERENCE["state_occupancy_pct"]
    assert occupancy["COMMITTED"] > 1.0 and occupancy["CONFIRMED"] > 1.0
    assert B.REFERENCE["dose_mean_by_state_u"]["CONFIRMED"] > \
        10 * B.REFERENCE["dose_mean_by_state_u"]["IDLE"]


# ---------------------------------------------------------------- layer 3: the adapter
def test_the_adapter_reproduces_the_acceleration_convention():
    """Confirmed against a real record: delta 7.0 on a short average of 2.75 logs as 154.5."""
    delta, short_avg = 7.0, 2.75
    accl = 100.0 * (delta - short_avg) / abs(short_avg)
    assert accl == pytest.approx(154.5, abs=0.1)


def test_the_adapter_builds_structurally_valid_cycles():
    from timsim import simulate
    from timsim.controller.boost import BoostController

    name = population.names("adult")[0]
    c = BoostController(name, target_bg=90.0)
    simulate(name, days=2, seed=0, layers=("physiology", "behaviour", "sensor"),
             controller=c)

    assert len(c.cycles) > 300
    for field in ("bg", "eventual_bg", "target_bg", "min_guard_bg", "iob", "cob"):
        vals = np.array([getattr(x, field) for x in c.cycles], float)
        assert np.all(np.isfinite(vals)), f"{field} carries a non-finite value"
    # glucose fields have to be in mg/dL, which is the defect the cohort cache carries
    for field in ("bg", "eventual_bg", "target_bg", "min_guard_bg"):
        assert np.median([getattr(x, field) for x in c.cycles]) > 40.0, field
    assert all(0 <= x.hour <= 23 for x in c.cycles)
    # Insulin on board is measured against the scheduled basal, as AndroidAPS does, so it
    # goes negative when the loop has been withholding. Real users sit at -0.4 U at the
    # fifth percentile; an adapter counting boluses alone never does.
    iob = [x.iob for x in c.cycles]
    assert min(iob) < 0.0, "insulin on board never went negative"
    assert max(iob) > 0.0


def test_the_adapter_is_deterministic():
    from timsim import simulate
    from timsim.controller.boost import BoostController

    name = population.names("adult")[0]
    runs = []
    for _ in range(2):
        c = BoostController(name, target_bg=90.0)
        simulate(name, days=1, seed=3, layers=("physiology", "behaviour", "sensor"),
                 controller=c)
        runs.append([o.final_dose for o in c.outputs])
    assert runs[0] == runs[1]


def test_the_min_guard_reconstruction_is_not_pathologically_low():
    """The first version subtracted all of insulin on board rather than the part that acts.

    That put the predicted minimum about 38 mg/dL below current glucose against a real 20,
    and tripped the hard gate on 39% of cycles against a real 8.6%, which left Boost
    switched off for most of the run.
    """
    from timsim import simulate
    from timsim.controller.boost import BoostController

    name = population.names("adult")[0]
    c = BoostController(name, target_bg=90.0)
    simulate(name, days=3, seed=0, layers=("physiology", "behaviour", "sensor"),
             controller=c)
    gap = np.median([x.bg - x.min_guard_bg for x in c.cycles])
    assert gap < 30.0, f"predicted minimum sits {gap:.1f} mg/dL below glucose"


# ------------------------------------------------------- layer 4: the simulator on trial
def test_the_input_fidelity_report_covers_every_field_the_algorithm_reads():
    from timsim import simulate
    from timsim.controller.boost import BoostController

    name = population.names("adult")[0]
    c = BoostController(name, target_bg=90.0)
    simulate(name, days=2, seed=0, layers=("physiology", "behaviour", "sensor"),
             controller=c)
    real = [x for u in B.cohort()[:2] for x in u["cycles"]]
    report = B.input_fidelity(c.cycles, real_cycles=real)
    assert set(report) == set(B.INPUT_FIELDS)
    for field, row in report.items():
        assert len(row["real"]) == 3 and len(row["simulated"]) == 3


def test_the_exercise_check_fails_a_simulator_that_never_commits():
    """The check has to be able to fail, so it is given a run that never leaves idle."""
    idle = {"state_occupancy_pct": {"IDLE": 100.0, "OBSERVING": 0.0,
                                    "CONFIRMED": 0.0, "COMMITTED": 0.0}}
    result = B.check_the_simulator_exercises_the_algorithm(idle)
    assert not result["pass"]
    assert "CONFIRMED" in result["note"] and "COMMITTED" in result["note"]


def test_the_simulator_now_reaches_the_states_that_carry_the_dosing():
    """The stored result, so a regression in the adapter shows up as a test failure.

    Before the adapter was calibrated against oref's logged internals this sat at 0.87%
    against a logged 5.4%. The three calibrations that moved it were the projection, the
    insulin request and the basal decision, each fitted to the plugin's own logged values
    rather than to this number.
    """
    result = B.check_the_simulator_exercises_the_algorithm(B.TIMSIM_MEASURED)
    assert result["pass"], result["note"]
    assert B.TIMSIM_MEASURED["state_occupancy_pct"]["COMMITTED"] > 3.0
    assert B.TIMSIM_MEASURED["time_below_70_pct"] < 6.0


def test_the_rescue_calibration_moved_rescue_behaviour_and_not_the_residual():
    """Both halves of an honest negative result, kept so neither gets quietly dropped.

    Calibrating the rescue model against real carb entries halved the rescue rate and
    raised the size, which is what it was fitted to do. It did not move the excess
    observing-state occupancy, and the count of sustained rises stayed where it was: fewer
    but larger rescues produce about the same number of meal-shaped spikes.
    """
    r = B.SIMULATOR_RESIDUAL
    resc = r["rescues_per_day"]
    assert resc["timsim_after"] < resc["timsim_before"] / 1.5
    grams = r["grams_per_rescue"]
    assert abs(grams["timsim_after"] - grams["real_mean"]) < 5.0
    # and the thing it was hoped would follow, which did not
    sust = r["sustained_50_per_day"]
    assert abs(sust["timsim_after"] - sust["timsim_before"]) < 0.5
    # what the residual turned out to be, once measured like for like
    band = r["score_bands_pct"]
    assert abs(band["timsim"]["above_entry"] - band["real"]["above_entry"]) < 6.0
    assert abs(r["score_mean"]["timsim"] - r["score_mean"]["real"]) < 0.01
    acf = r["score_autocorrelation_lag1"]
    assert acf["timsim"] > 2.5 * acf["real"]


def test_the_exercise_check_passes_a_simulator_that_matches_the_field():
    result = B.check_the_simulator_exercises_the_algorithm(
        {"state_occupancy_pct": dict(B.REFERENCE["state_occupancy_pct"])})
    assert result["pass"]


def test_the_discriminability_result_against_dclp3_is_recorded():
    """The strongest claim available, and the direction of its failure.

    Kept as a test so neither the figure nor its interpretation drifts out of the
    documentation. Separable at 0.709, and the axis is hyperglycaemia.
    """
    from timsim.validation import replication as R
    d = R.AGAINST_DCLP3
    assert d["auc"] > d["null_p95"], "no longer separable; the claim has changed"
    assert d["auc"] < 0.9, "trivially separable; something has regressed badly"
    hyper = d["marginals"]["pct_above_180"]
    assert hyper[1] < hyper[0], "simulated time above 180 no longer the low side"
    # the autocorrelations matching is what retired the persistence worry
    for k in ("acf30", "acf60"):
        assert abs(d["marginals"][k][2]) < 0.1


# ------------------------------------------------- the inputs AndroidAPS actually computes
def test_the_glucose_status_follows_the_androidaps_windows():
    """delta, shortAvgDelta and longAvgDelta are averages of scaled contributions.

    Every earlier reading contributes (current - then) / minutesAgo * 5, averaged over 2.5
    to 7.5 minutes, 2.5 to 17.5 and 17.5 to 42.5. Not differences of consecutive readings.
    """
    from timsim.controller.boost import BoostController
    from timsim.population import names
    c = BoostController(names("adult")[0])
    c.readings = [100.0 + 2.0 * k for k in range(10)]      # a steady 2 mg/dL per 5 min
    delta, short, long = c.glucose_status()
    for v in (delta, short, long):
        assert abs(v - 2.0) < 1e-9, "a constant slope must give the same figure in every window"


def test_max_delta_is_the_signed_maximum_of_the_three():
    """It is a hard gate. It was being built as the largest absolute recent difference,
    which is a different quantity: a median of 6.3 against 2.0 in the field."""
    from timsim.controller.boost import BoostController
    from timsim.population import names
    c = BoostController(names("adult")[0])
    c.readings = [200.0 - 5.0 * k for k in range(10)]      # falling steadily
    delta, short, long = c.glucose_status()
    assert max(delta, short, long) < 0.0, "a steady fall cannot give a positive maxDelta"


def test_basal_below_schedule_produces_negative_insulin_on_board():
    from timsim.controller.boost import BoostController
    from timsim.population import names
    c = BoostController(names("adult")[0])
    for k in range(6):
        c.observe_basal(k * 5.0, 0.0, 0.1)                 # suspended against a schedule
    assert c._basal_iob(30.0) < 0.0


def test_basal_at_schedule_contributes_nothing():
    from timsim.controller.boost import BoostController
    from timsim.population import names
    c = BoostController(names("adult")[0])
    for k in range(6):
        c.observe_basal(k * 5.0, 0.1, 0.1)
    assert c._basal_iob(30.0) == 0.0


def test_the_delta_history_is_windowed_deltas_not_raw_differences():
    """`deltaDeclining` exits COMMITTED and needs three strictly decreasing values.

    A raw difference of consecutive readings on this sensor is mostly noise, so the
    condition almost never fired and the state held 25.2% of cycles against a logged 5.4%.
    """
    from timsim import simulate
    from timsim.controller.boost import BoostController
    from timsim.population import names
    name = names("adult")[0]
    c = BoostController(name)
    simulate(name, days=2, seed=0, controller=c)
    assert c.delta_history, "no delta history was kept"
    tails = [x.delta_history for x in c.cycles if len(x.delta_history) >= 3]
    assert tails
    declining = [all(t[i] > t[i + 1] for i in range(len(t) - 1)) for t in tails]
    assert 0.02 < sum(declining) / len(declining) < 0.45, "the exit condition never fires"
