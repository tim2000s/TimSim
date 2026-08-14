"""What the Boost bridge sends the compiled algorithm, and what it records afterwards.

Three inputs were being defaulted rather than sent. `_row` read them off the cycle with
`getattr(..., default)`, and none of the three names is a field on `CycleInput`, so the default
went every time and nothing said so. That is the failure mode these tests exist to catch:
a marshalling gap that produces a plausible constant instead of an error.
"""
import dataclasses

import pytest

from timsim.controller import boost_bridge


def test_the_defaulted_fields_are_not_cycle_attributes():
    """The reason the gap was silent, pinned so a future reader does not re-add the getattr."""
    from timsim.validation import boost as boost_ref
    if not boost_ref.available():
        pytest.skip("the Boost cohort cache is not present")
    cycle_type = type(boost_ref.cohort()[0]["cycles"][0])
    fields = {f.name for f in dataclasses.fields(cycle_type)}
    for absent in ("cumulative_rise_30min", "confirmed_cap_u", "committed_cap_u"):
        assert absent not in fields


def test_the_cumulative_rise_follows_the_plugin_derivation():
    """`max(0, shortAvgDelta * 6)`, the same expression the plugin and the port both use.

    Sending nothing pins `velocityScaledDoseFactor` to its floor of 0.40 for every dose in
    every state, which removed 60.0 per cent of the raw request over 28 days.
    """
    class _C:
        short_avg_delta = 0.0

    c = _C()
    assert boost_bridge.BoostBridgeController._cumulative_rise(c) == 0.0
    c.short_avg_delta = 3.0
    assert boost_bridge.BoostBridgeController._cumulative_rise(c) == 18.0
    c.short_avg_delta = -4.0
    assert boost_bridge.BoostBridgeController._cumulative_rise(c) == 0.0, "a fall is not a rise"


def test_the_caps_are_read_from_the_configuration():
    """Otherwise an arm that varies them varies nothing the algorithm sees.

    One did: both arms of a cap comparison sent 1.0 and 0.25 to the algorithm, and the only
    thing the wider setting changed was the discarded port's dose.
    """
    import inspect
    src = inspect.getsource(boost_bridge.BoostBridgeController._row)
    assert "self.config.confirmed_cap_u" in src and "self.config.committed_cap_u" in src
    assert "getattr(cycle, \"confirmed_cap_u\"" not in src


def test_the_ledger_records_the_delivered_dose():
    """The parent records its own decision and the bridge discards that decision.

    Left uncorrected the algorithm reads insulin on board that nothing delivered, which feeds
    its eventual glucose, its minimum guard and the headroom clamping its request.
    """
    import inspect
    src = inspect.getsource(boost_bridge.BoostBridgeController.policy)
    assert "self.doses.pop()" in src and 'decision["final_dose"]' in src


def test_the_acceleration_denominator_is_floored():
    """The plugin floors it at 2.0 mg/dL, so a flat trace cannot show a large acceleration."""
    import inspect
    from timsim.controller import boost
    assert "max(abs(short_avg), 2.0)" in inspect.getsource(boost.BoostController.policy)
