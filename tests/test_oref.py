"""The oref adapter, tested on what would fail without saying so.

An adapter that mangles its inputs does not crash. It produces a run that looks like the
simulator behaving oddly, and the mistake is attributed to the wrong side. Every test here
covers a failure of that kind rather than an exception.
"""
import numpy as np
import pytest

from timsim.controller import oref as O
from timsim.controller.inputs import LoopInputs
from timsim.population import names
from timsim.therapy import profile as profile_mod
from timsim.therapy.insulin import DIA_MIN

pytestmark = pytest.mark.skipif(not O.available(),
                                reason="oref not gathered; run bridge/oref/build.sh")


@pytest.fixture(scope="module")
def subject():
    return names("adult")[0]


@pytest.fixture
def controller(subject):
    c = O.OrefController(subject)
    yield c
    c.close()


# --------------------------------------------------------------------- the bridge
def test_the_bridge_runs_the_real_algorithm_and_answers(controller):
    """If this fails the JavaScript did not load, and nothing downstream means anything."""
    r = _cycle(controller, bg=180.0, delta=8.0)
    assert "reason" in r and r["reason"], "oref explains every decision; an empty one is wrong"
    assert r["eventualBG"] is not None


def test_stray_output_on_the_channel_is_an_error_rather_than_a_silent_skip():
    """oref writes its autosens line to stdout, which arrived interleaved with the replies.

    Silencing it is a correctness fix rather than a tidy-up, so a regression has to be loud.
    """
    class Corrupt(O.OrefController):
        def __init__(self):
            pass
    c = Corrupt()
    c.proc = type("P", (), {"stdin": type("I", (), {"write": lambda *a: None,
                                                    "flush": lambda *a: None})(),
                            "stdout": type("O", (), {"readline": lambda *a: "Autosens ratio: 1\n"})()})()
    with pytest.raises(RuntimeError, match="not a reply"):
        c._send({"x": 1})


def test_the_profile_travels_hourly_because_sensitivity_moves_through_the_day(controller):
    """oref reads sensitivity and the scheduled basal afresh every cycle."""
    prof = controller.profile
    hours = {prof.isf_at(h * 60.0) for h in range(24)}
    if len(hours) == 1:
        pytest.skip("this subject has a flat sensitivity schedule")
    _cycle(controller, bg=140.0, delta=0.0, minute=3 * 60.0)
    _cycle(controller, bg=140.0, delta=0.0, minute=15 * 60.0)
    assert "ISF" in controller.suggestions[-1]["reason"]


# ------------------------------------------------------------- the temporary basal
def test_a_temporary_basal_is_held_between_cycles_rather_than_forgotten(controller):
    """The failure this guards is not subtle: a loop that forgets its own temporary basal
    reverts to the scheduled rate every five minutes and cannot withhold insulin at all."""
    scheduled = controller.profile.basal_at(0.0) * 60.0
    controller._apply({"rate": 0.0, "duration": 30}, minute=0.0, sample=5.0,
                      scheduled_rate=scheduled)
    assert controller.temp_rate == 0.0
    assert controller.temp_left == 25.0
    # oref says nothing this cycle, and the temporary basal has to keep running
    action = controller._apply({}, minute=5.0, sample=5.0, scheduled_rate=scheduled)
    assert action.basal == 0.0, "the pump reverted to schedule while a zero temp was live"
    assert controller.temp_left == 20.0


def test_a_temporary_basal_expires_and_the_schedule_resumes(controller):
    scheduled = controller.profile.basal_at(0.0) * 60.0
    controller._apply({"rate": 0.0, "duration": 10}, 0.0, 5.0, scheduled)
    controller._apply({}, 5.0, 5.0, scheduled)
    action = controller._apply({}, 10.0, 5.0, scheduled)
    assert controller.temp_rate is None
    assert action.basal == pytest.approx(scheduled / 60.0)


def test_a_zero_duration_cancels_rather_than_setting_a_zero_rate(controller):
    """oref cancels with duration 0, which hands control back to the schedule. Reading that
    as a zero rate would switch basal off indefinitely."""
    scheduled = controller.profile.basal_at(0.0) * 60.0
    controller._apply({"rate": 1.5, "duration": 30}, 0.0, 5.0, scheduled)
    action = controller._apply({"rate": 0.0, "duration": 0}, 5.0, 5.0, scheduled)
    assert controller.temp_rate is None
    assert action.basal == pytest.approx(scheduled / 60.0)


def test_the_running_temporary_basal_is_reported_back_to_oref(controller):
    """oref decides whether a new temp is needed by comparing with the one it believes is
    running, so a currenttemp of zero every cycle makes it reissue constantly."""
    scheduled = controller.profile.basal_at(0.0) * 60.0
    controller._apply({"rate": 0.0, "duration": 30}, 0.0, 5.0, scheduled)
    r = _cycle(controller, bg=120.0, delta=0.0, minute=5.0)
    assert r is not None
    assert controller.temp_left > 0


def test_a_microbolus_enters_the_ledger_so_it_counts_against_insulin_on_board(controller):
    scheduled = controller.profile.basal_at(0.0) * 60.0
    controller._apply({"rate": 0.0, "duration": 30, "units": 0.4}, 100.0, 5.0, scheduled)
    assert controller.doses == [(100.0, 0.4)]
    assert controller.last_bolus_min == 100.0
    assert controller.bolus_iob(100.0) == pytest.approx(0.4)


# ---------------------------------------------------------------- the forward curve
def test_the_forward_curve_is_self_consistent(controller):
    """oref integrates `activity` to build every prediction it makes, so it has to be the
    derivative of the insulin on board beside it rather than an independent guess."""
    controller.doses = [(0.0, 3.0)]
    curve = controller.iob_curve(10.0, scheduled_u_per_hour=1.0, ticks=12, step=5.0)
    for a, b in zip(curve, curve[1:]):
        implied = a["iob"] - a["activity"] * 5.0
        assert implied == pytest.approx(b["iob"], abs=1e-9)


def test_zero_delivery_predicts_less_insulin_than_carrying_on(controller):
    """`iobWithZeroTemp` is the floor oref checks before dosing. A copy of the ordinary
    curve makes that check meaningless and oref doses into a fall."""
    controller.doses = [(0.0, 2.0)]
    curve = controller.iob_curve(10.0, scheduled_u_per_hour=1.2, ticks=24, step=5.0)
    assert curve[0]["iobWithZeroTemp"]["iob"] == pytest.approx(curve[0]["iob"], abs=1e-9)
    assert curve[-1]["iobWithZeroTemp"]["iob"] < curve[-1]["iob"] - 0.5


def test_a_running_temporary_basal_shows_up_in_the_forward_curve(controller):
    high = controller.iob_curve(0.0, 1.0, ticks=24, step=5.0, temp_rate=3.0, temp_minutes=60.0)
    none = controller.iob_curve(0.0, 1.0, ticks=24, step=5.0)
    assert high[-1]["iob"] > none[-1]["iob"]


def test_the_last_bolus_time_is_supplied_so_a_microbolus_can_ever_fire(controller):
    """oref computes the age of the last bolus by subtraction. Left undefined it is not
    zero but NaN, every comparison against the microbolus interval is false, and SMB
    silently never fires for the whole run while everything else looks ordinary."""
    controller.last_bolus_min = -600.0
    for k in range(6):
        r = _cycle(controller, bg=170.0 + 12.0 * k, delta=12.0, minute=5.0 * k)
    assert "NaN" not in r["reason"], "the bolus age reached oref as NaN"
    assert any(s.get("units") for s in controller.suggestions), \
        "oref never microbolused on a steep rise, so the interval check is failing shut"


# ------------------------------------------------------------------ shared with Boost
def test_both_algorithms_read_the_same_glucose_status():
    """A difference between the two arms has to belong to the algorithms. Two copies of the
    delta calculation would put a difference in the adapters instead."""
    from timsim.controller.boost import BoostController
    assert BoostController.glucose_status is LoopInputs.glucose_status
    assert BoostController._basal_iob is LoopInputs.basal_iob


def test_pruning_the_ledger_changes_no_arithmetic():
    """It is a speed fix. If it moved insulin on board it would be a silent dosing change."""
    class L(LoopInputs):
        pass
    a, b = L(), L()
    a.init_inputs(); b.init_inputs()
    doses = [(float(t), 0.1) for t in range(0, 2000, 5)]
    a.doses, b.doses = list(doses), list(doses)
    b.prune(2000.0)
    assert len(b.doses) < len(a.doses)
    assert b.bolus_iob(2000.0) == pytest.approx(a.bolus_iob(2000.0), abs=1e-12)
    assert b.doses[0][0] > 2000.0 - DIA_MIN


def test_a_dose_over_an_hour_old_still_counts_after_a_cycle(controller):
    """Issue 54. The adapter pruned with a 240-minute margin added to the cutoff, so a full
    cycle dropped every dose more than an hour old and oref saw about half the insulin on
    board. Pruning at the real call site must leave a 2-hour-old unit in the ledger."""
    scheduled = controller.profile.basal_at(0.0) * 60.0
    controller._apply({"units": 1.0}, 0.0, 5.0, scheduled)
    expected = controller.bolus_iob(120.0)
    assert expected > 0.3
    handed = _cycle(controller, bg=140.0, delta=0.0, minute=120.0)["IOB"]
    assert controller.doses[0] == (0.0, 1.0)
    # what oref was given this cycle, before any microbolus it then decided on
    assert handed == pytest.approx(expected, abs=1e-6)


def test_the_adapters_compute_insulin_on_board_with_oref0s_curve():
    """Issue 54. AndroidAPS and oref0 use the exponential curve of lib/iob/calculate.js. These
    are oref0 0.7.1's own figures for one unit at a 5-hour duration and 75-minute peak; the
    package's own curve gives 0.960, 0.840, 0.653, 0.480, 0.213 and 0.053 at the same ages."""
    class L(LoopInputs):
        pass
    loop = L()
    loop.init_inputs()
    loop.doses = [(0.0, 1.0)]
    oref0 = {30: 0.925, 60: 0.764, 90: 0.581, 120: 0.411, 180: 0.159, 240: 0.033}
    for age, value in oref0.items():
        assert loop.bolus_iob(float(age)) == pytest.approx(value, abs=5e-4), age


# ------------------------------------------------------------------------ end to end
@pytest.mark.slow
def test_a_short_run_closes_the_loop_rather_than_running_open(subject):
    """The check that matters: oref has to actually move insulin about. An adapter that
    drops every instruction still produces a plausible-looking run, because the scheduled
    basal alone keeps a virtual subject roughly in range."""
    from timsim import simulate
    c = O.OrefController(subject)
    try:
        r = simulate(subject, days=3, seed=0, controller=c)
        p = c.response_profile()
        assert p["cycles"] > 800
        assert p["temp_issued_pct"] > 20.0, "oref issued almost no temporary basals"
        assert p["smb_pct"] > 1.0, "oref never microbolused, so SMB is not reaching it"
        bg = np.asarray(r.bg)
        assert 70.0 < bg.mean() < 250.0
    finally:
        c.close()


# ---------------------------------------------------------------------------- helper
def _cycle(controller, bg, delta, minute=0.0):
    """One decision, without a simulator behind it."""
    obs = type("Obs", (), {"CGM": bg})()
    controller.readings.append(bg - delta)
    controller.policy(obs, 0.0, False, clock_minutes=minute, sample_time=5.0, meal=0.0)
    return controller.suggestions[-1]
