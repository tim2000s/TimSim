"""The sensor layer injects artefacts, and must inject only what it claims to."""
import numpy as np

from timsim.sensor.realism import add_sensor_noise, apply, inject_compression_lows


def _trace(n=8640, level=120.0):
    """Three days of flat glucose on a five-minute grid."""
    return np.full(n, level, float)


def test_noise_raises_high_frequency_jitter_and_leaves_the_mean_alone():
    rng = np.random.default_rng(0)
    clean = _trace()
    noisy = add_sensor_noise(clean, rng, sigma=2.0)
    assert abs(noisy.mean() - clean.mean()) < 0.5
    second_diff = np.diff(np.diff(noisy))
    assert 4.0 < second_diff.std() < 7.0


def test_compression_lows_are_placed_at_about_the_requested_rate():
    rng = np.random.default_rng(1)
    clean = _trace(n=8640, level=110.0)          # 30 days at 5 min
    dipped, n = inject_compression_lows(clean, rng, rate_per_30d=4.0)
    assert 2 <= n <= 5
    assert dipped.min() < 70.0


def test_the_rate_is_the_same_on_a_three_minute_grid_as_on_a_five_minute_one():
    """The defect this catches: a span computed in samples rather than in minutes.

    An earlier version read `len(cgm) * 300 / 86400` regardless of the real interval, so
    a three-minute trace was read as 1.67 times its true length and got 1.67 times the
    dips. Thirty days is thirty days on either grid.
    """
    thirty_days_at_5 = _trace(n=30 * 24 * 12, level=110.0)
    thirty_days_at_3 = _trace(n=30 * 24 * 20, level=110.0)
    _, five = inject_compression_lows(thirty_days_at_5, np.random.default_rng(1),
                                      rate_per_30d=6.0, sample_minutes=5.0)
    _, three = inject_compression_lows(thirty_days_at_3, np.random.default_rng(1),
                                       rate_per_30d=6.0, sample_minutes=3.0)
    assert five == three == 6


def test_the_online_layer_places_the_same_number_of_dips_as_the_batch_one():
    from timsim.sensor.realism import OnlineArtefacts

    n = 30 * 24 * 12                                   # 30 days at 5 min
    art = OnlineArtefacts(np.random.default_rng(2), n, 5.0, noise_sigma=0.0,
                          compression_per_30d=6.0)
    out = np.array([art(i, 110.0) for i in range(n)], float)
    assert art.events == 6
    assert out.min() < 70.0


def test_the_online_layer_defers_a_dip_it_cannot_place_rather_than_dropping_it():
    """A dip scheduled while glucose is already low would never cross the detector."""
    from timsim.sensor.realism import OnlineArtefacts

    n = 30 * 24 * 12
    art = OnlineArtefacts(np.random.default_rng(3), n, 5.0, noise_sigma=0.0,
                          compression_per_30d=6.0)
    # the first third of the run sits far too high for a plausible dip to reach 70
    levels = np.where(np.arange(n) < n // 3, 300.0, 110.0)
    for i, level in enumerate(levels):
        art(i, float(level))
    assert art.events == 6


def test_the_online_layer_adds_jitter_without_moving_the_mean():
    from timsim.sensor.realism import OnlineArtefacts

    n = 2016
    art = OnlineArtefacts(np.random.default_rng(4), n, 5.0, noise_sigma=2.0,
                          compression_per_30d=0.0)
    out = np.array([art(i, 120.0) for i in range(n)], float)
    assert abs(out.mean() - 120.0) < 0.5
    assert 4.0 < np.diff(np.diff(out)).std() < 7.0


def test_a_compression_low_reverses_rather_than_persisting():
    rng = np.random.default_rng(2)
    clean = _trace(n=2016, level=110.0)
    dipped, n = inject_compression_lows(clean, rng, rate_per_30d=30.0)
    if n:
        i = int(np.argmin(dipped))
        assert dipped[min(i + 5, len(dipped) - 1)] > dipped[i] + 15.0


def test_no_compression_requested_means_none_injected():
    rng = np.random.default_rng(3)
    clean = _trace()
    dipped, n = inject_compression_lows(clean, rng, rate_per_30d=0.0)
    assert n == 0
    assert np.array_equal(dipped, clean)


def test_apply_is_the_two_layers_together():
    rng = np.random.default_rng(4)
    clean = _trace()
    out, n = apply(np.arange(len(clean)) * 300.0, clean, rng)
    assert out.shape == clean.shape
    assert out.std() > clean.std()
