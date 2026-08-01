"""The sensor layer injects artefacts, and must inject only what it claims to."""
import numpy as np

from simperson.sensor.realism import add_sensor_noise, apply, inject_compression_lows


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
