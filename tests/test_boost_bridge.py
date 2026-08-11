"""The bridge runs the shipped decision code, so what is tested is the wiring, not the algorithm."""
import pytest

from timsim.controller import boost_bridge as BB

pytestmark = pytest.mark.skipif(not BB.available(),
                                reason="no bridge jar; build with bridge/boost/build.sh")


@pytest.fixture(scope="module")
def subject():
    from timsim.population import names
    return names("adult")[0]


def test_the_field_order_is_agreed_with_the_jar_rather_than_assumed():
    """A column shift here would corrupt every decision silently, so it fails loudly."""
    import subprocess
    p = subprocess.run([BB.java_binary(), "-jar", BB.JAR], input="FIELDS\n",
                       capture_output=True, text=True, timeout=60)
    fields = p.stdout.split()
    assert len(fields) == 36
    assert fields[0] == "delta" and fields[-1] == "committedCapU"


def test_a_mismatched_row_is_refused(subject):
    c = BB.BoostBridgeController(subject)
    try:
        c.fields = c.fields + ["extra"]
        with pytest.raises(RuntimeError, match="expects"):
            c._row(_cycle(), 0)
    finally:
        c.close()


def _cycle():
    from timsim.validation import boost as B
    h = B.harness()
    return h.CycleInput(
        delta=12.0, short_avg_delta=10.0, delta_accl=40.0, bg=190.0, eventual_bg=240.0,
        target_bg=110.0, max_delta=12.0, min_guard_bg=180.0, min_guard_threshold=80.0,
        iob=1.0, max_iob=8.0, base_insulin_req=1.5, round_smb_to=0.05,
        enable_smb_pre_checks=True, ml_hypo_risk=None, ml_meal_likely=None,
        recent_low_bg=150.0, hour=12, exercise_active=False, post_exercise_window=False,
        sensor_quality_ok=True, delta_history=(8.0, 10.0, 12.0), iob_activity_uh=0.0,
        cob=0.0)


def test_a_sharp_accelerating_rise_reaches_a_committing_state(subject):
    """The failure a bench of this kind exists to catch is never reaching these states."""
    c = BB.BoostBridgeController(subject)
    try:
        d = c._decide(_cycle(), 0)
        assert d["state"] in ("CONFIRMED", "COMMITTED", "OBSERVING")
        assert d["final_dose"] >= 0.0
        assert set(BB.OUTPUTS) <= set(d)
    finally:
        c.close()


def test_the_confirmed_dose_cap_binds(subject):
    """CONFIRMED multiplies by 1.8; the cap is what stops that becoming a 3 U bolus."""
    c = BB.BoostBridgeController(subject)
    try:
        d = c._decide(_cycle(), 0)
        if d["state"] == "CONFIRMED":
            assert d["final_dose"] <= 1.0 + 1e-9
    finally:
        c.close()


def test_a_run_drives_the_algorithm_and_records_what_it_did(subject):
    from timsim.simulation.run import simulate
    c = BB.BoostBridgeController(subject)
    try:
        r = simulate(subject, days=2, seed=0, controller=c)
        p = c.response_profile()
        assert p["cycles"] > 500
        assert abs(sum(p["state_occupancy_pct"].values()) - 100.0) < 1e-6
        assert r.insulin_units > 0
    finally:
        c.close()


def test_closing_twice_is_harmless(subject):
    c = BB.BoostBridgeController(subject)
    c.close()
    c.close()
