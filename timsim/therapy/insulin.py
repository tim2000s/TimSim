"""The insulin action curve, shared by everything that needs insulin on board.

A bilinear activity curve with a peak partway through the duration of action. It is the
same shape the correction loop has always used here, lifted out so that the pump limit
enforcer and any algorithm under test read insulin on board off one definition rather
than three slightly different ones.
"""
DIA_MIN = 300.0           # duration of insulin action
PEAK_MIN = 75.0           # activity peak


def iob_fraction(age_min, dia_min=DIA_MIN, peak_min=PEAK_MIN):
    """Fraction of a bolus still to act, `age_min` after it was given."""
    if age_min <= 0:
        return 1.0
    if age_min >= dia_min:
        return 0.0
    p, d = float(peak_min), float(dia_min)
    if age_min < p:
        return 1.0 - (age_min ** 2) / (p * d)
    return ((d - age_min) ** 2) / (d * (d - p))


def oref_iob_fraction(age_min, dia_min=DIA_MIN, peak_min=PEAK_MIN):
    """Fraction of a bolus still to act under oref0's exponential curve.

    This is the curve AndroidAPS applies in every insulin plugin it ships and that oref0 uses
    in `lib/iob/calculate.js` (Loop's exponential model, LoopKit/Loop issue 388), so it is the
    one the AndroidAPS adapters must compute insulin on board with. The bilinear-like
    `iob_fraction` above leaves 0.04 to 0.08 more of each unit on board between one and four
    hours at a 300-minute duration and 75-minute peak (0.840 against 0.764 at 60 minutes, 0.480
    against 0.411 at 120), so an adapter using it reports more insulin on board than the
    application it stands for. It is the loop's belief about insulin, and the simulated body's
    insulin kinetics are not affected by it.
    """
    import math

    if age_min <= 0:
        return 1.0
    end, peak = float(dia_min), float(peak_min)
    if age_min >= end:
        return 0.0
    tau = peak * (1 - peak / end) / (1 - 2 * peak / end)
    a = 2 * tau / end
    s = 1 / (1 - a + (1 + a) * math.exp(-end / tau))
    return 1 - s * (1 - a) * ((age_min ** 2 / (tau * end * (1 - a)) - age_min / tau - 1)
                              * math.exp(-age_min / tau) + 1)


def iob(minute, doses, dia_min=DIA_MIN, peak_min=PEAK_MIN):
    """Insulin on board at `minute`, from an iterable of (minute, units)."""
    return float(sum(u * iob_fraction(minute - m, dia_min, peak_min) for m, u in doses))


__all__ = ["iob_fraction", "oref_iob_fraction", "iob", "DIA_MIN", "PEAK_MIN"]
