"""The fall phase of a meal excursion.

The five tests of `area_above_trough`, `peak_to_return_min` and `effective_duration_min` were
drafted by the local model against a written specification and checked here, including the
arithmetic in their comments. The two covering `mean_elevation` and `fullness` are added because
those fields did not exist when the specification was written.

Every one was run against deliberately broken implementations before being kept: taking the last
crossing rather than the first, dropping the clamp on samples below the trough, omitting the step
multiplier, and measuring the return from the trough rather than the peak.
"""
import numpy as np
import pytest

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from timsim.analysis import meal_shape as ms


def test_simple_triangular_excursion():
    minutes = np.array([0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
    glucose = np.array([100.0, 120.0, 140.0, 120.0, 100.0, 100.0, 100.0])
    trough_i = 0
    peak_i = 2
    result = ms.fall(minutes, glucose, trough_i, peak_i, step_min=5.0)

    # peak_to_return_min: from peak (10.0) to first time glucose <= 100.0
    # glucose[4] = 100.0 at minute 20.0, so 20.0 - 10.0 = 10.0
    assert result["peak_to_return_min"] == pytest.approx(10.0)
    assert result["returned"] is True

    # area_above_trough: sum over i from trough_i=0 to end of max(0, glucose[i] - 100.0) * 5.0
    # i=0: max(0, 0) = 0
    # i=1: max(0, 20) = 20
    # i=2: max(0, 40) = 40
    # i=3: max(0, 20) = 20
    # i=4: max(0, 0) = 0
    # i=5: max(0, 0) = 0
    # i=6: max(0, 0) = 0
    # sum = 80, * 5.0 = 400.0
    assert result["area_above_trough"] == pytest.approx(400.0)

    # effective_duration_min = 400.0 / (140.0 - 100.0) = 400.0 / 40.0 = 10.0
    assert result["effective_duration_min"] == pytest.approx(10.0)


def test_never_returns_to_baseline():
    minutes = np.array([0.0, 5.0, 10.0, 15.0, 20.0])
    glucose = np.array([100.0, 120.0, 140.0, 130.0, 125.0])
    trough_i = 0
    peak_i = 2
    result = ms.fall(minutes, glucose, trough_i, peak_i, step_min=5.0)

    assert np.isnan(result["peak_to_return_min"])
    assert result["returned"] is False

    # area_above_trough: sum over i from 0 to 4 of max(0, glucose[i] - 100.0) * 5.0
    # i=0: 0
    # i=1: 20
    # i=2: 40
    # i=3: 30
    # i=4: 25
    # sum = 115, * 5.0 = 575.0
    assert result["area_above_trough"] == pytest.approx(575.0)
    assert result["area_above_trough"] > 0
    assert np.isfinite(result["area_above_trough"])


def test_first_crossing_not_last():
    minutes = np.array([0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0])
    glucose = np.array([100.0, 120.0, 140.0, 100.0, 90.0, 110.0, 100.0, 95.0])
    trough_i = 0
    peak_i = 2
    result = ms.fall(minutes, glucose, trough_i, peak_i, step_min=5.0)

    # First crossing: glucose[3] = 100.0 at minute 15.0, so 15.0 - 10.0 = 5.0
    assert result["peak_to_return_min"] == pytest.approx(5.0)
    assert result["returned"] is True


def test_flat_trace_peak_equals_trough():
    minutes = np.array([0.0, 5.0, 10.0, 15.0])
    glucose = np.array([100.0, 100.0, 100.0, 100.0])
    trough_i = 0
    peak_i = 2
    result = ms.fall(minutes, glucose, trough_i, peak_i, step_min=5.0)

    assert np.isnan(result["effective_duration_min"])


def test_glucose_below_trough_clamped():
    minutes = np.array([0.0, 5.0, 10.0, 15.0, 20.0])
    glucose = np.array([100.0, 120.0, 140.0, 90.0, 80.0])
    trough_i = 0
    peak_i = 2
    result = ms.fall(minutes, glucose, trough_i, peak_i, step_min=5.0)

    # area_above_trough: sum over i from 0 to 4 of max(0, glucose[i] - 100.0) * 5.0
    # i=0: 0
    # i=1: 20
    # i=2: 40
    # i=3: max(0, -10) = 0
    # i=4: max(0, -20) = 0
    # sum = 60, * 5.0 = 300.0
    assert result["area_above_trough"] == pytest.approx(300.0)
    assert result["area_above_trough"] >= 0


def test_mean_elevation_is_the_area_without_the_step_or_the_gaps():
    """The gap-robust form. Same trace as the triangular case, so the two can be checked against
    each other: the area is the mean times the number of samples times the step."""
    minutes = np.array([0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
    glucose = np.array([100.0, 120.0, 140.0, 120.0, 100.0, 100.0, 100.0])
    r = ms.fall(minutes, glucose, 0, 2, step_min=5.0)
    assert r["mean_elevation"] == pytest.approx(80.0 / 7)
    assert r["area_above_trough"] == pytest.approx(r["mean_elevation"] * 7 * 5.0)


def test_fullness_separates_a_square_excursion_from_a_spike():
    """The statistic the comparison turns on, with the height divided out.

    A square excursion sits near its peak for the whole window and a spike returns at once. Both
    have the same rise, so anything that did not divide by it would not separate them.
    """
    minutes = np.arange(0.0, 105.0, 5.0)
    square = np.concatenate([[100.0], np.full(19, 200.0)])
    spike = np.concatenate([[100.0, 200.0], np.full(18, 100.0)])
    fs = ms.fall(minutes, square, 0, 1, step_min=5.0)["fullness"]
    fp = ms.fall(minutes, spike, 0, 1, step_min=5.0)["fullness"]
    assert fs == pytest.approx(19 / 20)
    assert fp == pytest.approx(1 / 20)
    assert fs > 10 * fp


def test_fullness_is_nan_when_there_is_no_rise():
    minutes = np.arange(0.0, 50.0, 5.0)
    flat = np.full(10, 100.0)
    r = ms.fall(minutes, flat, 0, 3, step_min=5.0)
    assert np.isnan(r["fullness"]) and np.isnan(r["effective_duration_min"])
