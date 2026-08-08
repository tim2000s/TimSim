"""The infusion site layer carries the largest single fidelity correction, so it is tested.

What matters is not that sites fail at some rate but that the failures have the properties
the DCLP3 traces show: insulin goes missing rather than glucose being disturbed, the pump
log still says it was delivered, and nobody notices until morning.
"""
import numpy as np
import pytest

from timsim.therapy.site import InfusionSite, _asleep


def _site(seed=0, **kw):
    return InfusionSite(np.random.default_rng(seed), **kw)


def _failing_at(minute, residual=0.1, seed=0):
    """A site whose current set fails at a chosen instant, so timing can be tested."""
    s = _site(seed)
    s._fails_at, s._residual = float(minute), float(residual)
    s._expires_at = max(s._expires_at, minute + 4 * 1440.0)
    return s


def test_an_intact_site_passes_everything_through():
    s = _site(failures_per_30_days=0.0)
    basal, bolus, lost = s.apply(0.0, 0.02, 1.5, 5.0)
    assert (basal, bolus, lost) == (0.02, 1.5, 0.0)
    assert s.report()["site_failures"] == 0


def test_a_failed_site_attenuates_and_counts_what_it_swallowed():
    s = _failing_at(600.0, residual=0.2)
    basal, bolus, lost = s.apply(600.0, 0.02, 1.0, 5.0)
    assert basal == pytest.approx(0.004)
    assert bolus == pytest.approx(0.2)
    # The loss covers the basal over the step as well as the bolus, which is where most of
    # it goes: 0.02 * 5 + 1.0 = 1.1 commanded, 20% absorbed.
    assert lost == pytest.approx(1.1 * 0.8)
    assert s.report()["site_units_lost"] == pytest.approx(lost)


def test_the_failure_rate_lands_near_the_population_figure():
    """Calibrated against 3.82 long excursions per 30 days in the DCLP3 calibration split."""
    counts = []
    for seed in range(60):
        s = _site(seed)
        for k in range(int(90 * 1440 / 5)):
            s.absorbed_fraction(k * 5.0)
        counts.append(s.failures / 3.0)
    assert 3.5 < np.mean(counts) < 7.0
    # and it has to vary between people, not just average correctly
    assert np.std(counts) > 1.0


def test_a_high_reading_while_awake_gets_the_site_changed():
    start = 10 * 60.0                      # 10:00, awake
    s = _failing_at(start)
    assert s.absorbed_fraction(start) < 1.0
    minute = start
    while minute < start + 600 and s.absorbed_fraction(minute) < 1.0:
        s.observe(minute, 300.0)
        minute += 5.0
    assert s.absorbed_fraction(minute) == 1.0
    assert minute - start < 300.0


def test_a_high_reading_while_asleep_does_not():
    """The overnight gap against DCLP3 is the reason this behaviour exists."""
    start = 0.0                            # midnight
    s = _failing_at(start)
    assert s.absorbed_fraction(start) < 1.0
    minute = start
    while minute < 6 * 60.0:
        s.observe(minute, 320.0)
        assert s.absorbed_fraction(minute) < 1.0
        minute += 5.0


def test_being_high_briefly_is_not_taken_for_a_failed_site():
    s = _failing_at(10 * 60.0)
    assert s.absorbed_fraction(10 * 60.0) < 1.0
    for k in range(12):                    # an hour above the threshold, then back down
        s.observe(10 * 60.0 + k * 5.0, 280.0)
    s.observe(11 * 60.0, 140.0)
    for k in range(24):
        s.observe(11 * 60.0 + k * 5.0, 140.0)
    assert s.absorbed_fraction(13 * 60.0) < 1.0


def test_a_set_is_replaced_on_schedule_even_if_nothing_was_noticed():
    s = _failing_at(60.0)
    assert s.absorbed_fraction(60.0) < 1.0
    assert s.absorbed_fraction(s._expires_at + 5.0) == 1.0


def test_sleep_covers_the_hours_it_should():
    assert _asleep(0.0) and _asleep(3 * 60.0) and _asleep(23.5 * 60.0)
    assert not _asleep(8 * 60.0) and not _asleep(22 * 60.0)


def test_the_layer_can_be_switched_off_and_changes_nothing_when_it_is():
    """A layer that leaves a trace when off would make every ablation unreadable."""
    from timsim import simulate
    from timsim.population import names
    name = names("adult")[0]
    a = simulate(name, days=2, seed=3, layers=("physiology", "behaviour", "loop", "sensor"))
    b = simulate(name, days=2, seed=3,
                 layers=("physiology", "behaviour", "loop", "sensor", "site"))
    assert "site" not in a.layers and "site" in b.layers
    assert "site_failures" not in a.meta and "site_failures" in b.meta
