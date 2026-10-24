"""`LoopInputs.deviation_slopes` against values worked by hand from IobCobOref1Worker's loop.

With no insulin activity the average deviation is the 15-minute average delta. A rise that is
speeding up has its smallest deviation in the past and gives a positive `slopeFromMinDeviation`
and a zero `slopeFromMaxDeviation`; one that is slowing gives the reverse. Before an hour of
buckets exists the worker's starting values come back.
"""
import pytest

from timsim.controller.inputs import LoopInputs


def feed(bgs, activity=0.0, sens=50.0, keep=None):
    x = LoopInputs()
    x.init_inputs()
    out = []
    for k, bg in enumerate(bgs):
        x.readings.append(bg)
        out.append(x.deviation_slopes(5.0 * k, activity, sens))
    if keep is not None:
        keep.append(x)
    return out


def test_defaults_until_an_hour_of_buckets():
    out = feed([100.0 + k for k in range(15)])
    assert all(o == (0.0, 999.0) for o in out[:15])


def test_steady_rise_gives_zero_slopes():
    out = feed([100.0 + 3.0 * k for k in range(20)])
    assert out[-1] == (0.0, 0.0)


def test_accelerating_rise():
    # deltas growing by 0.5 per bucket, so the average deviation grows by 0.5 per bucket
    bg, d, bgs = 100.0, 0.0, []
    for _ in range(20):
        bgs.append(bg)
        d += 0.5
        bg += d
    s_max, s_min = feed(bgs)[-1]
    assert s_max == 0.0
    # smallest deviation is the oldest of the eleven, 55 min back and 11 buckets lower by 0.5 each
    assert s_min == pytest.approx(0.5, abs=1e-6)


def test_slowing_rise():
    bg, d, bgs = 100.0, 10.0, []
    for _ in range(20):
        bgs.append(bg)
        d -= 0.5
        bg += d
    s_max, s_min = feed(bgs)[-1]
    assert s_max == pytest.approx(-0.5, abs=1e-6)
    assert s_min == 0.0


def test_insulin_effect_enters_as_bgi():
    # flat glucose, activity 0.01 U/min at ISF 50: bgi -2.5, so a constant deviation of +2.5
    keep = []
    out = feed([120.0] * 20, activity=0.01, sens=50.0, keep=keep)
    assert out[-1] == (0.0, 0.0)
    assert keep[0].deviation_history[-1][1] == pytest.approx(2.5)
