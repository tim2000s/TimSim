"""The signatures decide every verdict this package produces, so they are pinned."""
import numpy as np
import pytest

from simperson.analysis import signatures as S


def _flat(level=120.0, days=7):
    n = int(days * 24 * 12)
    t = np.arange(n) * 300.0
    return dict(t=t, bg=np.full(n, level), hour=(t / 3600.0) % 24)


def _sine(amp=40.0, period_h=24.0, days=7, level=140.0):
    n = int(days * 24 * 12)
    t = np.arange(n) * 300.0
    bg = level + amp * np.sin(2 * np.pi * t / (period_h * 3600.0))
    return dict(t=t, bg=bg, hour=(t / 3600.0) % 24)


def test_a_flat_trace_has_no_variability_and_no_events():
    d = _flat()
    cv = next(fn for k, _, fn in S.SIGS if k == "cv")(d)
    assert cv == pytest.approx(0.0, abs=1e-9)
    compress = next(fn for k, _, fn in S.SIGS if k == "compress")(d)
    assert compress == 0.0


def test_diurnal_amplitude_recovers_a_known_daily_swing():
    amp = next(fn for k, _, fn in S.SIGS if k == "diurnal")(_sine(amp=40.0))
    assert 75.0 < amp < 82.0          # peak-to-trough is twice the amplitude


def test_autocorrelation_is_high_for_a_smooth_curve():
    d = _sine(amp=40.0, period_h=24.0)
    acf30 = next(fn for k, _, fn in S.SIGS if k == "acf30")(d)
    assert acf30 > 0.95


def test_every_signature_has_a_real_range_and_a_unit():
    keys = {k for k, _, _ in S.SIGS} | {"drift"}
    assert keys == set(S.REAL_RANGE)
    assert keys == set(S.UNITS)


def test_in_real_range_respects_the_stated_tolerance():
    lo, hi = S.REAL_RANGE["cv"]
    assert S.in_real_range("cv", (lo + hi) / 2)
    assert not S.in_real_range("cv", lo - 0.5 * (hi - lo))
    assert S.in_real_range("cv", lo - 0.05 * (hi - lo))     # inside the 10% pad


def test_bootstrap_interval_brackets_the_point_estimate():
    v, lo, hi = S.boot_ci([1.0, 2.0, 3.0, 4.0, 5.0], seed=0)
    assert lo <= v <= hi


def test_report_names_every_signature():
    stats = {k: (float(np.mean(S.REAL_RANGE[k])), 0.0, 0.0) for k in S.REAL_RANGE}
    text = S.report(stats)
    for k in S.REAL_RANGE:
        assert k in text
    assert "OUT" not in text
